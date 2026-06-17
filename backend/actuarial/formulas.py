"""
backend/actuarial/formulas.py

Pure-Python port of the actuarial formula library used in the manual Excel
pricing process.

Sources:
  - Basics_formulations.xlsx -> 'Formulas', 'Formulas TP', 'Formula YTD'
  - dummydatamaterial.xlsx   -> 'Sample Pricing Sheet' (row-level validated chain)

Every function below is a 1:1 translation of one named Excel measure/cell
formula. No business logic should be duplicated outside this module --
Layers 4/5/6 of the platform call into these functions only, so there is a
single source of truth for every actuarial calculation.
"""

from typing import Optional


def _safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Excel IFERROR(numerator/denominator, default)."""
    if denominator == 0:
        return default
    return numerator / denominator


def mround(value: float, multiple: float) -> float:
    """Excel MROUND -- round to the nearest multiple."""
    if multiple == 0:
        return 0.0
    return round(value / multiple) * multiple


# ---------------------------------------------------------------------------
# Baseline cohort metrics  (source: 'Formulas TP' / 'Formulas')
# ---------------------------------------------------------------------------

def od_slr(od_loss_cost: float, od_premium: float) -> float:
    """OD SLR = Total OD Loss Cost / Total OD Premium."""
    return _safe_div(od_loss_cost, od_premium)


def tp_slr(tp_loss_cost: float, tp_premium: float) -> float:
    """TP SLR = Total TP Loss Cost / Total TP Premium."""
    return _safe_div(tp_loss_cost, tp_premium)


def slr(od_loss_cost: float, tp_loss_cost: float, od_premium: float, tp_premium: float) -> float:
    """SLR = (OD Loss Cost + TP Loss Cost) / (OD Premium + TP Premium)."""
    return _safe_div(od_loss_cost + tp_loss_cost, od_premium + tp_premium)


def irda_component(od_premium: float, tp_premium: float, irda_rate: float = 0.195) -> float:
    """IRDA Component = 19.5% x OD_Premium / (OD_Premium + TP_Premium)."""
    return irda_rate * _safe_div(od_premium, od_premium + tp_premium)


def coa(irda: float, bse: float) -> float:
    """CoA = IRDA component + BSE%."""
    return irda + bse


def coa_on_od(coa_val: float, tp_gwp: float, od_gwp: float) -> float:
    """COA on OD = (CoA * (TP_GWP + OD_GWP)) / OD_GWP.  [Sample Pricing Sheet col A]"""
    return _safe_div(coa_val * (tp_gwp + od_gwp), od_gwp)


def operating_ratio(slr_val: float, coa_val: float) -> float:
    """OR = SLR + CoA."""
    return slr_val + coa_val


def od_yield(od_premium: float, avg_idv: float, wp: float) -> float:
    """OD Yield = OD_Premium / (Avg_IDV * WP).  [Sample Pricing Sheet col K]"""
    return _safe_div(od_premium, avg_idv * wp)


def basic_od_rate(basic_od_premium: float, idv: float) -> float:
    """BASIC OD RATE = Basic_OD_Premium / IDV."""
    return _safe_div(basic_od_premium, idv)


def actual_amt(idv: float, tariff_pct: float) -> float:
    """Actual Amt = IDV * Tariff% / 100."""
    return idv * tariff_pct / 100


def disc_pct(basic_od_premium: float, actual_amt_val: float) -> float:
    """Disc% = 1 - IFERROR(Basic_OD_Premium / Actual_Amt, 0)."""
    return 1 - _safe_div(basic_od_premium, actual_amt_val, default=0.0)


def earned_discount(tariff_od: float, basic_od_premium: float) -> float:
    """Earned Discount = (Tariff_OD - Basic_OD_Premium) / Tariff_OD."""
    return _safe_div(tariff_od - basic_od_premium, tariff_od)


def od_part_pct(basic_od_premium: float, ncb_amt: float, od_premium: float) -> float:
    """OD_Part% = (Basic_OD_Premium - NCB_AMT) / Total_OD_Premium."""
    return _safe_div(basic_od_premium - ncb_amt, od_premium)


def ncb_pct(ncb_amt: float, basic_od_premium: float) -> float:
    """NCB% = NCB_AMT / Basic_OD_Premium."""
    return _safe_div(ncb_amt, basic_od_premium)


# ---------------------------------------------------------------------------
# Discount revision chain  (source: 'Sample Pricing Sheet' rows 7-9 --
# validated 1:1 against the workbook's cached formula results)
# ---------------------------------------------------------------------------

def new_od_lc(od_slr_val: float, od_gwp: float, od_lc_change_pct: float = 0.0) -> float:
    """New OD LC = OD_SLR * OD_GWP * (1 + OD_LC_Change%).  [col O]"""
    return od_slr_val * od_gwp * (1 + od_lc_change_pct)


def new_tp_lc(tp_slr_val: float, tp_gwp: float, tp_lc_change_pct: float = 0.0) -> float:
    """New TP LC = TP_SLR * TP_GWP * (1 + TP_LC_Change%).  [col P]"""
    return tp_slr_val * tp_gwp * (1 + tp_lc_change_pct)


def proposed_premium_at_target_or(
    new_od_lc_val: float,
    new_tp_lc_val: float,
    tp_gwp: float,
    coa_on_od_val: float,
    target_or: float = 0.92,
) -> Optional[float]:
    """Proposed Premium = (New_OD_LC + New_TP_LC - Target_OR*TP_GWP) / (Target_OR - COA_on_OD).
    [col B]. Returns None if the denominator is zero (target_or == coa_on_od)."""
    denominator = target_or - coa_on_od_val
    if denominator == 0:
        return None
    return (new_od_lc_val + new_tp_lc_val - target_or * tp_gwp) / denominator


def new_discount(
    proposed_premium: Optional[float],
    od_gwp: float,
    od_part_pct_val: float,
    earned_discount_val: float,
) -> float:
    """New Discount = 1 - ((Proposed_Premium - OD_GWP*(1-OD_Part%)) / (OD_GWP*OD_Part%)) * (1 - Earned_Discount).
    [col C]. Falls back to Earned_Discount on any division error (Excel IFERROR)."""
    if proposed_premium is None or od_gwp == 0 or od_part_pct_val == 0:
        return earned_discount_val
    return 1 - ((proposed_premium - od_gwp * (1 - od_part_pct_val)) / (od_gwp * od_part_pct_val)) * (1 - earned_discount_val)


def uw_discount(new_discount_val: float, floor: float = 0.10, cap: float = 0.90, round_to: float = 0.05) -> float:
    """UW Discount = IF(New_Discount<=floor, floor, MIN(MROUND(New_Discount, round_to), cap)).  [col D]"""
    if new_discount_val <= floor:
        return floor
    return min(mround(new_discount_val, round_to), cap)


def revised_od_premium(
    od_gwp: float,
    requested_discount: float,
    earned_discount_val: float,
    od_part_pct_val: float,
) -> float:
    """Revised OD Premium = OD_GWP*(1-Req_Disc)/(1-Earned_Disc)*OD_Part% + OD_GWP*(1-OD_Part%).  [col F]"""
    return (
        _safe_div(od_gwp * (1 - requested_discount), 1 - earned_discount_val) * od_part_pct_val
        + od_gwp * (1 - od_part_pct_val)
    )


def revised_coa(coa_on_od_val: float, revised_od_premium_val: float, tp_gwp: float) -> float:
    """Revised CoA = (COA_on_OD * Revised_OD_Premium) / (Revised_OD_Premium + TP_GWP).  [col G]"""
    return _safe_div(coa_on_od_val * revised_od_premium_val, revised_od_premium_val + tp_gwp)


def revised_coa_irda(revised_od_premium_val: float, tp_gwp: float, irda_rate: float = 0.195) -> float:
    """Revised CoA (IRDA) = (IRDA_rate * Revised_OD_Premium) / (Revised_OD_Premium + TP_GWP).  [col H]"""
    return _safe_div(irda_rate * revised_od_premium_val, revised_od_premium_val + tp_gwp)


def revised_slr(new_od_lc_val: float, new_tp_lc_val: float, tp_gwp: float, revised_od_premium_val: float) -> float:
    """Revised SLR = (New_OD_LC + New_TP_LC) / (TP_GWP + Revised_OD_Premium).  [col I]"""
    return _safe_div(new_od_lc_val + new_tp_lc_val, tp_gwp + revised_od_premium_val)


def revised_or(revised_coa_val: float, revised_slr_val: float) -> float:
    """Revised OR = Revised_CoA + Revised_SLR.  [col J]"""
    return revised_coa_val + revised_slr_val


def revised_od_yield(revised_od_premium_val: float, avg_idv: float, wp: float) -> float:
    """Revised OD Yield = Revised_OD_Premium / (Avg_IDV * WP).  [col K]"""
    return _safe_div(revised_od_premium_val, avg_idv * wp)


def uw_remark(revised_or_val: float, threshold: float = 0.941) -> str:
    """UW Remark = IF(Revised_OR < threshold, "Okay", "High OR").  [col L]"""
    return "Okay" if revised_or_val < threshold else "High OR"


def comm1(coa_val: float, tp_gwp: float, od_gwp: float) -> float:
    """Comm1 = CoA * (TP_GWP + OD_GWP).  [col Q] -- baseline total acquisition cost amount."""
    return coa_val * (tp_gwp + od_gwp)


def comm2(revised_coa_val: float, revised_od_premium_val: float, tp_gwp: float) -> float:
    """Comm2 = Revised_CoA * (Revised_OD_Premium + TP_GWP).  [col R] -- revised total acquisition cost amount."""
    return revised_coa_val * (revised_od_premium_val + tp_gwp)


def comm_irda(revised_coa_irda_val: float, revised_od_premium_val: float, tp_gwp: float) -> float:
    """Comm(IRDA) = Revised_CoA_IRDA * (Revised_OD_Premium + TP_GWP).  [col S]"""
    return revised_coa_irda_val * (revised_od_premium_val + tp_gwp)


def disc_amount(discount_pct_val: float, tariff_od: float) -> float:
    """Disc (currency) = Discount% * Tariff_OD.  [col T / U]"""
    return discount_pct_val * tariff_od


# ---------------------------------------------------------------------------
# Frequency / severity building blocks (source: 'Formulas' -- used by Layer 5
# impact engine and as the Layer 7 ML target variable construction)
# ---------------------------------------------------------------------------

def od_ulr(od_loss_cost: float, od_premium_amt: float) -> float:
    """OD ULR = OD_Loss_Cost / OD_Premium_Amt."""
    return _safe_div(od_loss_cost, od_premium_amt)


def tp_ulr(tp_loss_cost: float, tp_premium_amt: float) -> float:
    """TP ULR = TP_Loss_Cost / TP_Premium_Amt."""
    return _safe_div(tp_loss_cost, tp_premium_amt)


def total_ulr(od_loss_cost: float, tp_loss_cost: float, od_premium_amt: float, tp_premium_amt: float) -> float:
    """ULR = (OD_Loss_Cost + TP_Loss_Cost) / (OD_Premium_Amt + TP_Premium_Amt)."""
    return _safe_div(od_loss_cost + tp_loss_cost, od_premium_amt + tp_premium_amt)


def frequency(claim_count: float, earned_policies: float) -> float:
    """Frequency = No_of_Claims / Earned_Policies."""
    return _safe_div(claim_count, earned_policies)


def average_claim_size(gross_claim_amt: float, claim_count: float) -> float:
    """ACS = Gross_Claim_Amt / No_of_Claims."""
    return _safe_div(gross_claim_amt, claim_count)


def burning_cost(frequency_val: float, acs_val: float) -> float:
    """Burning Cost (pure risk premium) = Frequency * Average_Claim_Size."""
    return frequency_val * acs_val
