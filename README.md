# Motor Insurance Underwriting Pricing Platform

A 7-layer deterministic + ML hybrid platform for motor insurance UW pricing simulation, built as a demo
for an eventual company-level deployment. Replicates the manual Excel pricing/discount-revision workflow,
generates trend-calibrated synthetic policy data, and layers a risk-based ML pricing model on top.

## Status
Phase 0 (scaffold) — in progress.

## Stack
FastAPI · DuckDB · Pandas · React (later) · LightGBM/XGBoost + SHAP (later)

## Structure
- `backend/` — FastAPI app, actuarial formula engine, data layers, simulation/impact/rules engines
- `data/` — reference lookup tables and generated synthetic datasets
- `ml/` — model training scripts and serialized models
- `docs/` — architecture notes and specs
