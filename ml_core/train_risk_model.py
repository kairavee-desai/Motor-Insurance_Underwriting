import os
import pandas as pd
import numpy as np
import lightgbm as lgb
import shap
import joblib

DATA_PATH = "data/synthetic_policies.csv"
MODEL_DIR = "ml_core/artifacts"

def train_model():
    print("Loading synthetic policy data...")
    df = pd.read_csv(DATA_PATH)

    features = ['vehicle_age_years', 'segment_tier', 'rto_zone', 'fuel_type']
    target = 'od_loss_cost'

    X = df[features].copy()
    y = df[target]

    cat_features = ['segment_tier', 'rto_zone', 'fuel_type']
    for col in cat_features:
        X[col] = X[col].astype('category')

    monotone_constraints = [1 if col == 'vehicle_age_years' else 0 for col in features]

    print("Training LightGBM Pure Risk Model...")
    train_data = lgb.Dataset(X, label=y, categorical_feature=cat_features, free_raw_data=False)
    
    params = {
        'objective': 'regression',
        'metric': 'rmse',
        'learning_rate': 0.05,
        'num_leaves': 31,
        'monotone_constraints': monotone_constraints,
        'monotone_constraints_method': 'advanced',
        'seed': 42,
        'verbose': -1
    }

    model = lgb.train(params, train_data, num_boost_round=150)

    print("Generating SHAP Tree Explainer...")
    explainer = shap.TreeExplainer(model)
    
    os.makedirs(MODEL_DIR, exist_ok=True)
    model.save_model(os.path.join(MODEL_DIR, "lgb_risk_model.txt"))
    joblib.dump(explainer, os.path.join(MODEL_DIR, "shap_explainer.pkl"))
    
    base_value = explainer.expected_value
    if isinstance(base_value, np.ndarray):
        base_value = base_value[0]
    
    with open(os.path.join(MODEL_DIR, "baseline.txt"), "w") as f:
        f.write(str(base_value))

    print(f"\n✅ Training Complete!")
    print(f"Base Portfolio Risk (Expected Value): ₹{base_value:.2f}")
    print(f"Artifacts saved to {MODEL_DIR}/")

if __name__ == "__main__":
    train_model()
