import os
import pandas as pd
import numpy as np
import pytest

DATA_PATH = "data/synthetic_policies.csv"
REF_DIR = "data/reference/business_contribution"

@pytest.fixture(scope="module")
def generated_data():
    assert os.path.exists(DATA_PATH), f"Synthetic data file missing at {DATA_PATH}. Run generator first."
    return pd.read_csv(DATA_PATH)

def test_portfolio_wide_averages(generated_data):
    """Verify that portfolio-wide target metrics fall within tight actuarial tolerances."""
    df = generated_data
    
    # Portfolio targets from real benchmarks
    target_discount = 0.71197
    target_or = 0.97575
    target_coa = 0.24896

    # Allow a minor statistical drift (+/- 0.05) due to randomized noise generation
    assert df['earned_discount'].mean() == pytest.approx(target_discount, abs=0.03)
    assert df['operating_ratio'].mean() == pytest.approx(target_or, abs=0.05)
    assert df['coa'].mean() == pytest.approx(target_coa, abs=0.05)

def test_manufacturer_metric_direction(generated_data):
    """Verify that the generated manufacturer risk tracks the directional signal of benchmarks."""
    df = generated_data
    bench_path = os.path.join(REF_DIR, "manufacturer.csv")
    
    if os.path.exists(bench_path):
        bench_df = pd.read_csv(bench_path).set_index("category")
        # Filter out Grand Total row
        if "Grand Total" in bench_df.index:
            bench_df = bench_df.drop("Grand Total")
            
        gen_mfr = df.groupby("manufacturer")["operating_ratio"].mean()
        
        # Align indexes to compare overlapping brands
        common_idx = gen_mfr.index.intersection(bench_df.index)
        assert len(common_idx) >= 5
        
        # Calculate Rank Correlation to verify direction matches benchmark (positive trend)
        gen_series = gen_mfr.loc[common_idx]
        bench_series = bench_df.loc[common_idx, "or_val"]
        correlation = gen_series.corr(bench_series, method="spearman")
        
        assert correlation > 0.1, f"Manufacturer risk direction decoupled from benchmark! Corr: {correlation}"
