import os
import duckdb
import joblib
import lightgbm as lgb
import pandas as pd
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="Motor Pricing UW API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_CONN = duckdb.connect(database=':memory:')
DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic_policies.parquet")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "ml_core", "artifacts")

# Global ML artifacts
risk_model = None
shap_explainer = None
base_risk_value = 0.0

@app.on_event("startup")
def startup():
    global risk_model, shap_explainer, base_risk_value
    
    # 1. Load Data
    if os.path.exists(DATA_PATH):
        DB_CONN.execute(f"CREATE VIEW policies AS SELECT * FROM read_parquet('{DATA_PATH}')")
        print("✅ DuckDB Loaded")
        
    # 2. Load ML Models
    try:
        risk_model = lgb.Booster(model_file=os.path.join(MODEL_DIR, "lgb_risk_model.txt"))
        shap_explainer = joblib.load(os.path.join(MODEL_DIR, "shap_explainer.pkl"))
        with open(os.path.join(MODEL_DIR, "baseline.txt"), "r") as f:
            base_risk_value = float(f.read())
        print("✅ LightGBM & SHAP Loaded")
    except Exception as e:
        print(f"⚠️ ML Load Error: {e}")

class SimulationRequest(BaseModel):
    fuel_type: Optional[List[str]] = None
    segment_tier: Optional[List[str]] = None
    requested_discount: float = 0.70
    commission_rate: float = 0.20

def build_where_clause(filters):
    conditions = []
    if filters.segment_tier:
        segments = "', '".join(filters.segment_tier)
        conditions.append(f"segment_tier IN ('{segments}')")
    if filters.fuel_type:
        fuels = "', '".join(filters.fuel_type)
        conditions.append(f"fuel_type IN ('{fuels}')")
    return " AND ".join(conditions) if conditions else "1=1"

@app.post("/cohort/summary")
def get_cohort_summary(filters: SimulationRequest):
    where = build_where_clause(filters)
    query = f"SELECT COUNT(*) as cnt, AVG(operating_ratio) as orat, SUM(earned_od_premium + earned_tp_premium) as gwp, AVG(earned_discount) as disc FROM policies WHERE {where}"
    res = DB_CONN.execute(query).df()
    
    return {
        "policy_count": int(res['cnt'][0]),
        "avg_or": float(res['orat'][0]) if pd.notna(res['orat'][0]) else 0,
        "total_gwp": float(res['gwp'][0]) if pd.notna(res['gwp'][0]) else 0,
        "avg_discount": float(res['disc'][0]) if pd.notna(res['disc'][0]) else 0
    }

@app.post("/simulate")
def simulate_pricing(req: SimulationRequest):
    where = build_where_clause(req)
    
    query = f"SELECT AVG(tariff_od) as avg_tariff, MODE(segment_tier) as seg, MODE(rto_zone) as rto, MODE(fuel_type) as fuel, ROUND(AVG(vehicle_age_years)) as age FROM policies WHERE {where}"
    cohort_data = DB_CONN.execute(query).df()
    
    if cohort_data.empty or pd.isna(cohort_data['avg_tariff'][0]):
        raise HTTPException(status_code=400, detail="Cohort too small to simulate.")
        
    avg_tariff = float(cohort_data['avg_tariff'][0])
    
    rep_features = pd.DataFrame({
        'vehicle_age_years': [int(cohort_data['age'][0])],
        'segment_tier': [cohort_data['seg'][0]],
        'rto_zone': [cohort_data['rto'][0]],
        'fuel_type': [cohort_data['fuel'][0]]
    })
    
    for col in ['segment_tier', 'rto_zone', 'fuel_type']:
        rep_features[col] = rep_features[col].astype('category')

    expected_loss = risk_model.predict(rep_features)[0]
    shap_vals = shap_explainer.shap_values(rep_features)[0]
    
    # --- NEW: Build the exact SHAP Breakdown Array for the UI ---
    shap_breakdown = []
    for i, col in enumerate(rep_features.columns):
        val = rep_features.iloc[0, i]
        impact = shap_vals[i]
        shap_breakdown.append({
            "name": f"{col} ({val})",
            "impact": round(impact, 0),
            # Red for Risk Penalty, Green for Risk Benefit
            "fill": "#ef4444" if impact > 0 else "#10b981" 
        })
    # Sort by absolute impact to show the biggest drivers at the top
    shap_breakdown.sort(key=lambda x: abs(x["impact"]), reverse=True)

    revised_premium = avg_tariff * (1.0 - req.requested_discount)
    commission_amt = revised_premium * req.commission_rate
    margin = revised_premium - commission_amt - expected_loss
    final_or = (expected_loss + commission_amt) / revised_premium if revised_premium > 0 else 1.5

    return {
        "waterfall": [
            {"name": "Base Tariff", "Amount": round(avg_tariff, 0), "fill": "#94a3b8"},
            {"name": "Discount", "Amount": -round(avg_tariff * req.requested_discount, 0), "fill": "#f87171"},
            {"name": "Commission", "Amount": -round(commission_amt, 0), "fill": "#fb923c"},
            {"name": "Expected Loss", "Amount": -round(expected_loss, 0), "fill": "#60a5fa"},
            {"name": "Net Margin", "Amount": round(margin, 0), "fill": "#34d399" if margin > 0 else "#ef4444"}
        ],
        "shap_breakdown": shap_breakdown, # Send the array to the frontend
        "final_or": round(final_or, 4)
    }
