"""
backend/db/seeds/generate_synthetic.py

Phase 3/4: Row-by-row synthetic policy generator with schema widening.

Follows the exact sequence described for the manual process: exshowroom/IDV ->
tariff rate -> Tariff_OD -> Earned Discount -> Basic OD -> NCB -> Total OD Premium ->
Zero Dep add-on -> fixed TP premium -> earned/written exposure -> commission ->
BSE -> CoA -> loss costs -> SLR -> OR.

Schema Widening (Phase 4.5): Added Commission Breakdown and Add-on flags based
on the raw data sample, while keeping the scope PC-only. Central_Reward is locked
to 1.570% of Reward_GWP based on observed ground truth.

Usage:
python backend/db/seeds/generate_synthetic.py --rows 20000 --seed 42
"""

import argparse
import csv
import os
import sys
from datetime import date, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from actuarial import formulas as f  # noqa: E402

REF_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "reference")
TODAY = date(2026, 6, 21)
GRAND_TOTAL_DISCOUNT = 0.71197

# ===========================================================================
# ASSUMPTIONS (documented, revisit when real data is available):
#   - RTO cluster: sampled uniformly across the 117 clusters.
#   - CC bucket mix and ex-showroom price bands: approximate India PV market splits.
#   - Vehicle age distribution: approximated as a renewal-heavy book.
#   - Tariff zone (A/B/C) and Zone/RTO_Zone derivation from RTO cluster/state.
#   - Manufacturer -> Segment tier mapping: rule-based (brand name match).
#   - Commission Add-ons: Kept at 0.0 base matching the raw sample sparsity.
# ===========================================================================

def load_reference():
    ref = {}

    def load_kv(path, key_col):
        df = pd.read_csv(path)
        return dict(zip(df[key_col].astype(str), pd.to_numeric(df.iloc[:, 1], errors="coerce")))

    disc_dir = os.path.join(REF_DIR, "discount_benchmarks")
    ref["discount"] = {
        name[:-4]: load_kv(os.path.join(disc_dir, name), "category")
        for name in os.listdir(disc_dir)
    }

    biz_dir = os.path.join(REF_DIR, "business_contribution")
    ref["business"] = {
        name[:-4]: pd.read_csv(os.path.join(biz_dir, name)).set_index("category")
        for name in os.listdir(biz_dir)
    }

    tariff_df = pd.read_csv(os.path.join(REF_DIR, "tariff_od_rates.csv"))
    ref["tariff_lookup"] = {
        (row.zone, int(row.age_anchor_years), row.cc_bucket): row.tariff_pct
        for row in tariff_df.itertuples()
    }
    tp_df = pd.read_csv(os.path.join(REF_DIR, "tp_premium_fixed.csv"))
    ref["tp_premium_lookup"] = {
        (row.fuel_class, row.bucket, row.term): row.premium_inr
        for row in tp_df.itertuples()
    }
    ref["product_codes"] = pd.read_csv(os.path.join(REF_DIR, "product_codes.csv"))

    masters_dir = os.path.join(REF_DIR, "categorical_masters")
    ref["masters"] = {
        name[:-4]: pd.read_csv(os.path.join(masters_dir, name)).iloc[:, 0].tolist()
        for name in os.listdir(masters_dir)
    }
    return ref


# ---------------------------------------------------------------------------
# Geography derivation (approximate)
# ---------------------------------------------------------------------------

STATE_TO_ZONE = {
    **{s: "NORTH" for s in ["DELHI", "HARYANA", "PUNJAB", "HIMACHALPRADESH", "JAMMUANDKASHMIR",
                            "UTTARAKHAND", "CHANDIGARH", "UTTARPRADESH", "RAJASTHAN"]},
    **{s: "SOUTH" for s in ["KARNATAKA", "KERALA", "TAMILNADU", "TELANGANA", "ANDHRAPRADESH",
                            "LAKSHADWEEP", "ANDAMAN&NICOBAR"]},
    **{s: "EAST" for s in ["WESTBENGAL", "ODISHA", "BIHAR", "JHARKHAND", "SIKKIM",
                           "ARUNACHALPRADESH", "ASSAM", "MANIPUR", "MEGHALAYA", "MIZORAM",
                           "NAGALAND", "TRIPURA"]},
    **{s: "WEST" for s in ["MAHARASHTRA", "GUJARAT", "GOA", "MADHYAPRADESH", "CHHATTISGARH"]},
}

STATE_TO_RTO_ZONE = {
    "DELHI": "NCR",
    **{s: "RON" for s in ["HARYANA", "PUNJAB", "HIMACHALPRADESH", "JAMMUANDKASHMIR",
                          "UTTARAKHAND", "CHANDIGARH", "UTTARPRADESH", "RAJASTHAN",
                          "MADHYAPRADESH", "CHHATTISGARH"]},
    **{s: "SOUTH" for s in ["KARNATAKA", "KERALA", "TAMILNADU", "TELANGANA", "ANDHRAPRADESH",
                            "LAKSHADWEEP", "ANDAMAN&NICOBAR"]},
    **{s: "EAST" for s in ["WESTBENGAL", "ODISHA", "BIHAR", "JHARKHAND", "SIKKIM",
                           "ARUNACHALPRADESH", "ASSAM", "MANIPUR", "MEGHALAYA", "MIZORAM",
                           "NAGALAND", "TRIPURA"]},
    **{s: "WEST" for s in ["MAHARASHTRA", "GUJARAT", "GOA"]},
}

TARIFF_ZONE_A_CLUSTERS = {"MUMBAI", "MUMBAI SURROUNDING", "Mumbai Surroundings", "NEW DELHI",
                          "DELHI SURROUNDING", "CHENNAI", "CHENNAI SURROUNDING", "KOLKATA",
                          "KOLKATA SURROUNDING"}
TARIFF_ZONE_B_CLUSTERS = {"BANGALORE", "BANGALORE SURROUNDING", "HYDERABAD", "HYDERABAD SURROUNDING",
                          "PUNE", "PUNE SURROUNDING", "AHMEDABAD", "AHMEDABAD SURROUNDING", "JAIPUR",
                          "JAIPUR SURROUNDING", "LUCKNOW", "LUCKNOW SURROUNDING", "CHANDIGARH",
                          "BHOPAL", "BHOPAL SURROUNDING", "PATNA", "PATNA SURROUNDING", "GUWAHATI",
                          "BHUBANESHWAR", "BHUBANESHWAR SURROUNDING", "RAIPUR", "RAIPUR SURROUNDING",
                          "RANCHI", "RANCHI SURROUNDING", "SHIMLA", "GANGTOK", "SHILLONG", "KOHIMA",
                          "ITANAGAR", "IMPHAL", "AIZAWL", "PANAJI", "DEHRADUN", "SRINAGAR", "JAMMU"}

def tariff_zone_for_cluster(cluster: str) -> str:
    if cluster in TARIFF_ZONE_A_CLUSTERS:
        return "A"
    if cluster in TARIFF_ZONE_B_CLUSTERS:
        return "B"
    return "C"

# ---------------------------------------------------------------------------
# Manufacturer -> segment tier + ex-showroom price band
# ---------------------------------------------------------------------------

ULTRA_LUXURY = {"FERRARI", "LAMBORGHINI", "LAMBORGINI", "ROLLS ROYCE", "ROLLS-ROYCE", "BENTLEY",
                "ASTON MARTIN", "ASTON MARTINE", "MASERATI", "MCLAREN", "PORSCHE"}
ENTRY_LUXURY = {"BMW", "AUDI", "MERCEDES", "JAGUAR", "LAND ROVER", "VOLVO", "MINI", "CADILLAC"}

PRICE_BANDS_LAKH = {
    "MARUTI": (4, 12), "HYUNDAI": (5, 14), "TATA": (5, 13), "HONDA": (7, 16),
    "M&M": (8, 18), "TOYOTA": (8, 20), "PREMIUM1": (35, 90), "PREMIUM2": (100, 600),
    "OTHERS": (5, 18),
}

def segment_tier_for_manufacturer(mfr: str) -> str:
    u = mfr.upper()
    if "HONDA" in u: return "HONDA"
    if "HYUNDAI" in u: return "HYUNDAI"
    if "MARUTI" in u: return "MARUTI"
    if "TATA" in u: return "TATA"
    if "TOYOTA" in u: return "TOYOTA"
    if "MAHINDRA" in u or u in {"M&M", "M & M"}: return "M&M"
    if u in ULTRA_LUXURY: return "PREMIUM2"
    if u in ENTRY_LUXURY: return "PREMIUM1"
    return "OTHERS"

def sample_exshowroom_price(rng, segment_tier: str) -> float:
    lo, hi = PRICE_BANDS_LAKH.get(segment_tier, PRICE_BANDS_LAKH["OTHERS"])
    mid = (lo + hi) / 2
    sigma = 0.3
    price = rng.lognormal(mean=np.log(mid), sigma=sigma)
    return float(np.clip(price, lo, hi)) * 100_000

# ---------------------------------------------------------------------------
# IRDA-standard IDV depreciation schedule
# ---------------------------------------------------------------------------

def idv_depreciation_factor(vehicle_age_years: int) -> float:
    age = vehicle_age_years
    if age == 0: return 0.95
    if age <= 1: return 0.85
    if age <= 2: return 0.80
    if age <= 3: return 0.70
    if age <= 4: return 0.60
    if age <= 5: return 0.50
    return 0.40

# ---------------------------------------------------------------------------
# Weighted sampling helpers
# ---------------------------------------------------------------------------

def weighted_choice(rng, df, weight_col="business_pct"):
    cats = df.index.tolist()
    if "Grand Total" in cats:
        cats = [c for c in cats if c != "Grand Total"]
    weights = df.loc[cats, weight_col].fillna(0).values.astype(float)
    if weights.sum() <= 0:
        weights = np.ones(len(cats))
    weights = weights / weights.sum()
    return rng.choice(cats, p=weights)

def lookup_discount(ref, dimension, key, default=GRAND_TOTAL_DISCOUNT):
    v = ref["discount"].get(dimension, {}).get(str(key))
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return default
    return float(v)

def lookup_loss_ratio(ref, dimension, key, col):
    biz = ref["business"].get(dimension)
    if biz is None or key not in biz.index:
        return None
    v = biz.loc[key, col]
    return None if pd.isna(v) else float(v)

CC_BUCKET_WEIGHTS = {"<1000": 0.22, "1000-1500": 0.55, ">1500": 0.23}
VEHICLE_AGE_WEIGHTS = {0: 0.18, 1: 0.14, 2: 0.12, 3: 0.11, 4: 0.10, 5: 0.09,
                       6: 0.08, 7: 0.07, 8: 0.05, 9: 0.03, 10: 0.03}

def sample_cc_bucket(rng, segment_tier):
    if segment_tier in ("PREMIUM1", "PREMIUM2"):
        return ">1500"
    cats = list(CC_BUCKET_WEIGHTS.keys())
    weights = np.array(list(CC_BUCKET_WEIGHTS.values()))
    return rng.choice(cats, p=weights / weights.sum())

def sample_vehicle_age(rng):
    cats = list(VEHICLE_AGE_WEIGHTS.keys())
    weights = np.array(list(VEHICLE_AGE_WEIGHTS.values()))
    return int(rng.choice(cats, p=weights / weights.sum()))

def random_date_in_range(rng, start: date, end: date) -> date:
    delta_days = (end - start).days
    return start + timedelta(days=int(rng.integers(0, delta_days + 1)))

# ---------------------------------------------------------------------------
# Per-row generation
# ---------------------------------------------------------------------------

def generate_row(rng, ref, row_id):
    manufacturer = weighted_choice(rng, ref["business"]["manufacturer"])
    rto_state = weighted_choice(rng, ref["business"]["rto_state"])
    vertical = weighted_choice(rng, ref["business"]["vertical"])
    emg_pmg = weighted_choice(rng, ref["business"]["emg_pmg"])
    transaction_type = weighted_choice(rng, ref["business"]["transaction_type"])
    fuel_type = rng.choice(ref["business"]["fuel_type"].index[:-1])
    ncb_flag = weighted_choice(rng, ref["business"]["ncb_flag"])

    if ncb_flag == "Y":
        ncb_df = ref["business"]["previous_year_ncb"]
        ncb_keys = [k for k in ncb_df.index if k not in ("0", "Grand Total")]
        ncb_pct_key = weighted_choice(rng, ncb_df.loc[ncb_keys])
        ncb_pct = float(ncb_pct_key) / 100.0
    else:
        ncb_pct = 0.0

    rto_cluster = rng.choice(ref["masters"]["rto_cluster"])
    segment_tier = segment_tier_for_manufacturer(manufacturer)
    vehicle_age = sample_vehicle_age(rng)
    cc_bucket = sample_cc_bucket(rng, segment_tier)
    zone = STATE_TO_ZONE.get(rto_state, "WEST")
    rto_zone = STATE_TO_RTO_ZONE.get(rto_state, "RON")
    tariff_zone = tariff_zone_for_cluster(rto_cluster)
    zero_dep_flag = bool(rng.random() < 0.35 and vehicle_age <= 5)
    term_years = 1 if rng.random() < 0.85 else 3

    # --- IDV / Tariff OD ---
    exshowroom = sample_exshowroom_price(rng, segment_tier)
    idv = exshowroom * idv_depreciation_factor(vehicle_age)
    tariff_pct = np.interp(
        min(vehicle_age, 10),
        [0, 5, 10],
        [
            ref["tariff_lookup"][(tariff_zone, 0, cc_bucket)],
            ref["tariff_lookup"][(tariff_zone, 5, cc_bucket)],
            ref["tariff_lookup"][(tariff_zone, 10, cc_bucket)],
        ],
    )
    tariff_od = f.actual_amt(idv, tariff_pct)

    # --- Earned discount ---
    discount_components = [
        lookup_discount(ref, "manufacturer", manufacturer),
        lookup_discount(ref, "segment_tier", segment_tier),
        lookup_discount(ref, "rto_state", rto_state),
        lookup_discount(ref, "rto_zone", rto_zone),
        lookup_discount(ref, "zone", zone),
        lookup_discount(ref, "reporting_vertical", vertical),
        lookup_discount(ref, "emg_pmg", emg_pmg),
        lookup_discount(ref, "fuel_type", fuel_type),
        lookup_discount(ref, "vehicle_age_group", vehicle_age if vehicle_age < 10 else ">=10"),
        lookup_discount(ref, "prev_year_ncb_flag", ncb_flag),
        lookup_discount(ref, "new_transaction_type", transaction_type),
    ]
    base_discount = float(np.mean(discount_components))
    noise = rng.normal(0, 0.08) * base_discount
    earned_discount = float(np.clip(base_discount + noise, 0.0, 0.97))

    basic_od_premium = tariff_od * (1 - earned_discount)
    ncb_amt = basic_od_premium * ncb_pct
    zero_dep_premium = (
        basic_od_premium * float(rng.uniform(0.08, 0.18)) * max(0.4, (1 - vehicle_age / 6))
        if zero_dep_flag else 0.0
    )
    total_od_premium = max(basic_od_premium - ncb_amt + zero_dep_premium, 0.0)

    # --- Fixed TP premium ---
    fuel_class = "EV" if fuel_type == "Electric" else "ICE"
    term_key = "1yr" if term_years == 1 else "3yr_single"
    if fuel_class == "EV":
        tp_bucket = {"<1000": "<30KW", "1000-1500": "30-65KW", ">1500": ">65KW"}[cc_bucket]
    else:
        tp_bucket = cc_bucket
    tp_premium_amt = float(ref["tp_premium_lookup"][(fuel_class, tp_bucket, term_key)])

    # --- Policy dates / earned vs written ---
    policy_start = random_date_in_range(rng, date(2025, 4, 1), date(2026, 6, 21))
    term_days = 365 * term_years
    days_elapsed = (TODAY - policy_start).days
    earned_fraction = float(np.clip(days_elapsed / term_days, 0.0, 1.0))
    written_od_premium = total_od_premium
    written_tp_premium = tp_premium_amt
    earned_od_premium = written_od_premium * earned_fraction
    earned_tp_premium = written_tp_premium * earned_fraction

    # --- Commission / BSE / CoA ---
    agent_addon = max(0.0, 0.205 * (1 - vehicle_age / 7)) if vehicle_age < 7 else 0.0
    total_commission_rate = min(0.195 + agent_addon, 0.40)
    bse_pct = float(rng.uniform(0, 0.03))
    irda_like = total_commission_rate * f._safe_div(total_od_premium, total_od_premium + tp_premium_amt)
    coa = irda_like + bse_pct

    # --- Loss costs (Weighted Deviation Model) ---
    GRAND_OR, GRAND_COA = 0.9757515241, 0.2489592571
    DIM_WEIGHTS = {"manufacturer": 0.40, "rto_state": 0.20, "vertical": 0.15,
                   "transaction_type": 0.15, "ncb_flag": 0.10}
    bench_dims = [
        ("manufacturer", manufacturer), ("rto_state", rto_state), ("vertical", vertical),
        ("transaction_type", transaction_type), ("ncb_flag", ncb_flag),
    ]

    or_dev, coa_dev, odlr_components, tplr_components = 0.0, 0.0, [], []
    for dim, key in bench_dims:
        w = DIM_WEIGHTS[dim]
        v_or = lookup_loss_ratio(ref, dim, key, "or_val")
        v_coa = lookup_loss_ratio(ref, dim, key, "coa")
        if v_or is not None:
            or_dev += w * (v_or - GRAND_OR)
        if v_coa is not None:
            coa_dev += w * (v_coa - GRAND_COA)
        odlr_components.append(lookup_loss_ratio(ref, dim, key, "odlr_pct"))
        tplr_components.append(lookup_loss_ratio(ref, dim, key, "tplr_pct"))

    bench_or = GRAND_OR + or_dev
    bench_coa = GRAND_COA + coa_dev
    target_slr = float(np.clip(bench_or - bench_coa, 0.25, 1.4))

    mean_odlr = float(np.nanmean([v for v in odlr_components if v is not None])) if any(v is not None for v in odlr_components) else 0.25
    mean_tplr = float(np.nanmean([v for v in tplr_components if v is not None])) if any(v is not None for v in tplr_components) else 0.25
    shape_avg = (mean_odlr + mean_tplr) / 2 if (mean_odlr + mean_tplr) > 0 else 1.0
    scale = target_slr / shape_avg if shape_avg > 0 else 1.0
    od_lr = mean_odlr * scale
    tp_lr = mean_tplr * scale

    od_lr = float(np.clip(od_lr * (1 + rng.normal(0, 0.06)), 0.05, 2.0))
    tp_lr = float(np.clip(tp_lr * (1 + rng.normal(0, 0.06)), 0.05, 2.0))

    od_loss_cost = total_od_premium * od_lr
    tp_loss_cost = tp_premium_amt * tp_lr

    od_slr = f.od_slr(od_loss_cost, total_od_premium)
    tp_slr = f.tp_slr(tp_loss_cost, tp_premium_amt)
    slr = f.slr(od_loss_cost, tp_loss_cost, total_od_premium, tp_premium_amt)
    operating_ratio = f.operating_ratio(slr, coa)
    
    # --- Schema Widening: Commissions & Add-ons ---
    reward_gwp = written_od_premium + written_tp_premium
    central_reward = reward_gwp * 0.01570
    actual_commission = reward_gwp * total_commission_rate

    return {
        "policy_id": row_id,
        "reporting_month": policy_start.strftime("%Y-%m-01"),
        "policy_start_date": policy_start.isoformat(),
        "term_years": term_years,
        "manufacturer": manufacturer,
        "segment_tier": segment_tier,
        "rto_state": rto_state,
        "rto_cluster": rto_cluster,
        "zone": zone,
        "rto_zone": rto_zone,
        "tariff_zone": tariff_zone,
        "reporting_vertical": vertical,
        "emg_pmg": emg_pmg,
        "transaction_type": transaction_type,
        "fuel_type": fuel_type,
        "cc_bucket": cc_bucket,
        "vehicle_age_years": vehicle_age,
        "prev_year_ncb_flag": ncb_flag,
        "ncb_pct": round(ncb_pct, 4),
        "ncb_amt": round(ncb_amt, 2),
        "exshowroom_price": round(exshowroom, 2),
        "idv": round(idv, 2),
        "tariff_pct": round(tariff_pct, 4),
        "tariff_od": round(tariff_od, 2),
        "earned_discount": round(earned_discount, 4),
        "basic_od_premium": round(basic_od_premium, 2),
        
        # Add-on Flags & Premiums
        "zero_dep_flag": zero_dep_flag,
        "zero_dep_premium": round(zero_dep_premium, 2),
        "rsa_flag": False, "rsa_prem": 0.0,
        "key_protect_flag": False, "key_protect_prem": 0.0,
        "tyre_protect_flag": False, "tyre_protect_prem": 0.0,
        "consumables_flag": False, "consumables_prem": 0.0,
        "engine_protect_plus_flag": False, "engine_protect_plus_prem": 0.0,
        "loss_of_personal_belongings_flag": False, "loss_of_personal_belongings_prem": 0.0,
        "rti_flag": False, "rti_prem": 0.0,
        "garage_cash_flag": False, "garage_cash_prem": 0.0,
        
        "total_od_premium": round(total_od_premium, 2),
        "tp_premium_amt": round(tp_premium_amt, 2),
        "written_od_premium": round(written_od_premium, 2),
        "written_tp_premium": round(written_tp_premium, 2),
        "earned_od_premium": round(earned_od_premium, 2),
        "earned_tp_premium": round(earned_tp_premium, 2),
        "earned_fraction": round(earned_fraction, 4),
        
        # Commission Breakdown
        "reward_gwp": round(reward_gwp, 2),
        "central_reward": round(central_reward, 2),
        "actual_commission": round(actual_commission, 2),
        "final_reward": 0.0,
        "bsc_adv": 0.0,
        "commission_adv": 0.0,

        "agent_commission_pct": round(agent_addon, 4),
        "total_commission_rate": round(total_commission_rate, 4),
        "bse_pct": round(bse_pct, 4),
        "coa": round(coa, 4),
        "od_loss_cost": round(od_loss_cost, 2),
        "tp_loss_cost": round(tp_loss_cost, 2),
        "od_slr": round(od_slr, 4),
        "tp_slr": round(tp_slr, 4),
        "slr": round(slr, 4),
        "operating_ratio": round(operating_ratio, 4),
    }

def generate(n_rows, seed=42):
    rng = np.random.default_rng(seed)
    ref = load_reference()
    rows = [generate_row(rng, ref, i + 1) for i in range(n_rows)]
    return pd.DataFrame(rows)

def print_calibration_summary(df, ref):
    print(f"\n=== Calibration summary ({len(df)} rows) ===")
    print(f"Grand-total avg discount  -> generated {df['earned_discount'].mean():.4f}  | benchmark 0.7120")
    print(f"Grand-total avg OR        -> generated {df['operating_ratio'].mean():.4f}  | benchmark 0.9758")
    print(f"Grand-total avg CoA       -> generated {df['coa'].mean():.4f}  | benchmark 0.2490")
    print("\nBy manufacturer (top 5 by row count):")
    top = df["manufacturer"].value_counts().head(5).index
    for m in top:
        sub = df[df["manufacturer"] == m]
        bench = ref["business"]["manufacturer"].loc[m] if m in ref["business"]["manufacturer"].index else None
        bench_or = bench["or_val"] if bench is not None else float("nan")
        print(f"  {m:20s} n={len(sub):5d}  gen_OR={sub['operating_ratio'].mean():.4f}  bench_OR={bench_or:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=20000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=str, default=os.path.join(REF_DIR, "..", "synthetic_policies.parquet"))
    args = parser.parse_args()

    ref = load_reference()
    df = generate(args.rows, seed=args.seed)
    df.to_parquet(args.out, index=False)
    csv_out = args.out.replace(".parquet", ".csv")
    df.to_csv(csv_out, index=False)
    print(f"Wrote {len(df)} rows to {args.out} and {csv_out}")
    print_calibration_summary(df, ref)
