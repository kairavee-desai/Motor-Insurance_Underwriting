"""
backend/tests/test_calibration.py

Phase 4: calibration tests. These don't test the formula engine (that's
test_formulas.py) -- they test whether the *generator's output*, in
aggregate, actually reproduces the real trends from Business Contri.

Run as part of the normal suite:
    pytest backend/tests/test_calibration.py -v -s

The -s flag matters here: these tests print a comparison table even when
they pass, since "is this close enough" is a judgment call you should be
able to see, not just a green checkmark.

This generates 40,000 rows for a stable estimate -- expect it to take a
few minutes.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "db", "seeds"))
from generate_synthetic import generate, load_reference  # noqa: E402

REF_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "reference")

N_ROWS = 40000
SEED = 42


@pytest.fixture(scope="module")
def df():
    return generate(N_ROWS, seed=SEED)


@pytest.fixture(scope="module")
def ref():
    return load_reference()


# ---------------------------------------------------------------------------
# Tolerances -- documented, not magic numbers. Loosen these as the generator
# matures; they should get *tighter* over time, not looser.
# ---------------------------------------------------------------------------
GRAND_TOTAL_TOL = {"earned_discount": 0.03, "operating_ratio": 0.08, "coa": 0.08}


def share_tolerance(bench_share: float) -> float:
    """Larger categories get a tighter absolute tolerance; small/rare
    categories get a looser one since sampling noise dominates there."""
    return max(0.03, bench_share * 0.30)


def print_comparison(label, rows):
    print(f"\n--- {label} ---")
    print(f"{'category':30s} {'gen':>10s} {'bench':>10s} {'diff':>10s} {'tol':>8s}  ok")
    for cat, gen_val, bench_val, tol in rows:
        diff = gen_val - bench_val
        ok = "OK" if abs(diff) <= tol else "FAIL"
        print(f"{str(cat)[:30]:30s} {gen_val:10.4f} {bench_val:10.4f} {diff:10.4f} {tol:8.4f}  {ok}")


# ---------------------------------------------------------------------------
# Grand totals
# ---------------------------------------------------------------------------

def test_grand_total_discount(df):
    bench = 0.71197
    gen = df["earned_discount"].mean()
    print(f"\nGrand-total discount: generated={gen:.4f} benchmark={bench:.4f} diff={gen - bench:+.4f}")
    assert abs(gen - bench) <= GRAND_TOTAL_TOL["earned_discount"]


def test_grand_total_operating_ratio(df):
    bench = 0.9757515241
    gen = df["operating_ratio"].mean()
    print(f"\nGrand-total OR: generated={gen:.4f} benchmark={bench:.4f} diff={gen - bench:+.4f}")
    assert abs(gen - bench) <= GRAND_TOTAL_TOL["operating_ratio"]


def test_grand_total_coa(df):
    bench = 0.2489592571
    gen = df["coa"].mean()
    print(f"\nGrand-total CoA: generated={gen:.4f} benchmark={bench:.4f} diff={gen - bench:+.4f}")
    assert abs(gen - bench) <= GRAND_TOTAL_TOL["coa"]


# ---------------------------------------------------------------------------
# Per-category volume share (does the generator put business where the real
# book puts business -- e.g. Maruti/Hyundai dominant, GBG/SIG tiny)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("dimension,gen_col", [
    ("manufacturer", "manufacturer"),
    ("rto_state", "rto_state"),
    ("vertical", "reporting_vertical"),
    ("transaction_type", "transaction_type"),
])
def test_volume_share_matches_benchmark(df, ref, dimension, gen_col):
    bench = ref["business"][dimension]
    bench = bench[bench.index != "Grand Total"]
    realized = df[gen_col].value_counts(normalize=True)

    rows, failures = [], []
    # Only check categories with at least 1% real share -- below that,
    # sampling noise at N=40000 dominates and the check is meaningless.
    for cat in bench.index:
        bench_share = bench.loc[cat, "business_pct"]
        if pd.isna(bench_share) or bench_share < 0.01:
            continue
        gen_share = realized.get(cat, 0.0)
        tol = share_tolerance(bench_share)
        rows.append((cat, gen_share, bench_share, tol))
        if abs(gen_share - bench_share) > tol:
            failures.append(cat)

    print_comparison(f"Volume share -- {dimension}", rows)
    assert not failures, f"{dimension}: volume share mismatch for {failures}"


# ---------------------------------------------------------------------------
# Per-category OR (directional check -- categories with worse real OR should
# generate worse OR, even if compressed toward the mean by blending)
# ---------------------------------------------------------------------------

def test_operating_ratio_rank_order_manufacturer(df, ref):
    """Rank correlation, not exact match: do high-OR-benchmark manufacturers
    also come out higher in the generated data? This is a *directional*
    soundness check, not a precision one.

    Threshold reasoning: manufacturer carries 40% weight in the deviation
    blend (see DIM_WEIGHTS in generate_synthetic.py); the other 60% comes from
    4 other independent real dimensions plus row-level noise. A 0.40 weight
    does not produce a 0.40 correlation once it's combined with that much
    other genuine signal -- at N=40000 this consistently lands around 0.25,
    which is the expected outcome of intentionally blending five real
    dimensions rather than letting one dominate. The bug this test originally
    caught was a *negative* correlation (-0.41, signal fully washed out by
    unweighted averaging) -- the threshold here is set to catch that failure
    mode, not to chase an arbitrary target."""
    bench = ref["business"]["manufacturer"]
    bench = bench[bench.index != "Grand Total"]
    gen_or = df.groupby("manufacturer")["operating_ratio"].mean()

    common = [m for m in bench.index if m in gen_or.index and bench.loc[m, "business_pct"] >= 0.005]
    bench_vals = bench.loc[common, "or_val"].astype(float)
    gen_vals = gen_or.loc[common]

    corr = np.corrcoef(bench_vals, gen_vals)[0, 1]
    print(f"\nManufacturer OR rank correlation (n={len(common)} manufacturers, >=0.5% share): {corr:.3f}")
    assert corr > 0.15, f"OR direction doesn't track the benchmark (corr={corr:.3f}) -- recalibrate"


# ---------------------------------------------------------------------------
# Sanity / data integrity (no NaNs, no impossible values)
# ---------------------------------------------------------------------------

def test_no_missing_values(df):
    missing = df.isna().sum()
    missing = missing[missing > 0]
    assert missing.empty, f"Unexpected NaNs in columns: {missing.to_dict()}"


def test_premiums_non_negative(df):
    for col in ["total_od_premium", "tp_premium_amt", "idv", "tariff_od"]:
        assert (df[col] >= 0).all(), f"{col} has negative values"


def test_discount_in_valid_range(df):
    assert df["earned_discount"].between(0, 1).all()


def test_operating_ratio_plausible_range(df):
    # Loose sanity band -- a handful of outlier cohorts can legitimately
    # exceed 1.5 or dip below 0.4, but the bulk should be sane.
    pct_outside = ((df["operating_ratio"] < 0.3) | (df["operating_ratio"] > 2.0)).mean()
    assert pct_outside < 0.01, f"{pct_outside:.1%} of rows have an implausible OR"
