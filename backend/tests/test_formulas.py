import pytest

from backend.actuarial import formulas as f

# ---------------------------------------------------------------------------
# Golden fixtures lifted directly from dummydatamaterial.xlsx -> 'Sample
# Pricing Sheet' (cached formula results from the live workbook: row 2/row 8
# and row 3/row 9). If this module is ever refactored, these two tests are
# the contract that must keep passing.
# ---------------------------------------------------------------------------

ROW_A = dict(
    wp=6.0,
    earned_discount=0.87255651272032,
    tp_gwp=14164.0,
    od_gwp=6920.0,
    od_slr=1.0017743718135836,
    tp_slr=0.30158952719994353,
    coa=0.1575879807925472,
    od_part_pct=0.3192557803468208,
    tariff_od=33952.30382,
    avg_idv=177333.66666666666,
    target_or=0.92,
    od_lc_change=0.0,
    tp_lc_change=0.0,
)

ROW_B = dict(
    wp=11.0,
    earned_discount=0.8940875570440281,
    tp_gwp=27034.0,
    od_gwp=19396.0,
    od_slr=0.9150661030181482,
    tp_slr=0.36080152587149505,
    coa=0.19492759275015867,
    od_part_pct=0.15826974633945146,
    tariff_od=54752.7735,
    avg_idv=155986.36363636365,
    target_or=0.92,
    od_lc_change=-0.11386526727079849,
    tp_lc_change=0.1113873143500019,
)


def run_chain(row, requested_discount=None):
    coa_on_od = f.coa_on_od(row["coa"], row["tp_gwp"], row["od_gwp"])
    n_od_lc = f.new_od_lc(row["od_slr"], row["od_gwp"], row["od_lc_change"])
    n_tp_lc = f.new_tp_lc(row["tp_slr"], row["tp_gwp"], row["tp_lc_change"])
    proposed_premium = f.proposed_premium_at_target_or(n_od_lc, n_tp_lc, row["tp_gwp"], coa_on_od, row["target_or"])
    new_disc = f.new_discount(proposed_premium, row["od_gwp"], row["od_part_pct"], row["earned_discount"])
    uw_disc = f.uw_discount(new_disc)
    req_disc = requested_discount if requested_discount is not None else uw_disc
    rev_od_prem = f.revised_od_premium(row["od_gwp"], req_disc, row["earned_discount"], row["od_part_pct"])
    rev_coa = f.revised_coa(coa_on_od, rev_od_prem, row["tp_gwp"])
    rev_coa_irda = f.revised_coa_irda(rev_od_prem, row["tp_gwp"])
    rev_slr = f.revised_slr(n_od_lc, n_tp_lc, row["tp_gwp"], rev_od_prem)
    rev_or = f.revised_or(rev_coa, rev_slr)
    rev_yield = f.revised_od_yield(rev_od_prem, row["avg_idv"], row["wp"])
    remark = f.uw_remark(rev_or)
    c1 = f.comm1(row["coa"], row["tp_gwp"], row["od_gwp"])
    c2 = f.comm2(rev_coa, rev_od_prem, row["tp_gwp"])
    c_irda = f.comm_irda(rev_coa_irda, rev_od_prem, row["tp_gwp"])
    disc_amt = f.disc_amount(row["earned_discount"], row["tariff_od"])
    rev_disc_amt = f.disc_amount(req_disc, row["tariff_od"])
    return dict(
        coa_on_od=coa_on_od, new_od_lc=n_od_lc, new_tp_lc=n_tp_lc,
        proposed_premium=proposed_premium, new_discount=new_disc, uw_discount=uw_disc,
        revised_od_premium=rev_od_prem, revised_coa=rev_coa, revised_coa_irda=rev_coa_irda,
        revised_slr=rev_slr, revised_or=rev_or, revised_od_yield=rev_yield, uw_remark=remark,
        comm1=c1, comm2=c2, comm_irda=c_irda, disc_amount=disc_amt, rev_disc_amount=rev_disc_amt,
    )


def test_row8_uw_discount_equals_requested():
    r = run_chain(ROW_A)
    assert r["coa_on_od"] == pytest.approx(0.4801423392, rel=1e-6)
    assert r["new_od_lc"] == pytest.approx(6932.278653, rel=1e-6)
    assert r["new_tp_lc"] == pytest.approx(4271.714063, rel=1e-6)
    assert r["proposed_premium"] == pytest.approx(-4153.360158, rel=1e-6)
    assert r["new_discount"] == pytest.approx(1.511337834, rel=1e-6)
    assert r["uw_discount"] == pytest.approx(0.9, rel=1e-6)
    assert r["revised_od_premium"] == pytest.approx(6444.263455, rel=1e-6)
    assert r["revised_coa"] == pytest.approx(0.1501418951, rel=1e-6)
    assert r["revised_coa_irda"] == pytest.approx(0.06097706275, rel=1e-6)
    assert r["revised_slr"] == pytest.approx(0.5436650565, rel=1e-6)
    assert r["revised_or"] == pytest.approx(0.6938069516, rel=1e-6)
    assert r["revised_od_yield"] == pytest.approx(0.006056627201, rel=1e-6)
    assert r["uw_remark"] == "Okay"
    assert r["comm1"] == pytest.approx(3322.584987, rel=1e-6)
    assert r["comm2"] == pytest.approx(3094.16373, rel=1e-6)
    assert r["comm_irda"] == pytest.approx(1256.631374, rel=1e-6)
    assert r["disc_amount"] == pytest.approx(29625.30382, rel=1e-6)
    assert r["rev_disc_amount"] == pytest.approx(30557.07344, rel=1e-6)


def test_row9_manual_requested_discount_override():
    r = run_chain(ROW_B, requested_discount=0.85)
    assert r["coa_on_od"] == pytest.approx(0.4666162163, rel=1e-6)
    assert r["new_od_lc"] == pytest.approx(15727.67053, rel=1e-6)
    assert r["new_tp_lc"] == pytest.approx(10840.37012, rel=1e-6)
    assert r["proposed_premium"] == pytest.approx(3742.437884, rel=1e-6)
    assert r["new_discount"] == pytest.approx(1.434157596, rel=1e-6)
    assert r["uw_discount"] == pytest.approx(0.9, rel=1e-6)
    assert r["revised_od_premium"] == pytest.approx(20673.8478, rel=1e-6)
    assert r["revised_coa"] == pytest.approx(0.2022047332, rel=1e-6)
    assert r["revised_coa_irda"] == pytest.approx(0.08450182742, rel=1e-6)
    assert r["revised_slr"] == pytest.approx(0.5568903623, rel=1e-6)
    assert r["revised_or"] == pytest.approx(0.7590950955, rel=1e-6)
    assert r["uw_remark"] == "Okay"
    assert r["comm1"] == pytest.approx(9050.488131, rel=1e-6)
    assert r["comm2"] == pytest.approx(9646.752639, rel=1e-6)
    assert r["comm_irda"] == pytest.approx(4031.400322, rel=1e-6)
    assert r["disc_amount"] == pytest.approx(48953.7735, rel=1e-6)
    assert r["rev_disc_amount"] == pytest.approx(46539.85748, rel=1e-6)


def test_edge_cases_no_divide_by_zero():
    assert f.od_slr(100, 0) == 0.0
    assert f.coa_on_od(0.3, 100, 0) == 0.0
    assert f.proposed_premium_at_target_or(100, 100, 100, 0.92, target_or=0.92) is None
    assert f.uw_discount(-0.5) == 0.10
    assert f.uw_discount(1.5) == 0.90
