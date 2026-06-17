"""
backend/db/seeds/reference_data.py

Hand-curated reference/lookup tables that don't come from a parseable source
file -- the discount benchmark tables and tariff rate tables were supplied as
photographs of printed sheets. Where the user supplied corrected figures
(RTO Zone, NEW_TRANSACTION_TYPE) those override the photographed values.
TP premium figures are IRDAI-fixed (regulator-set, identical across insurers)
and have been verified against current public sources rather than transcribed
from the partially-overlapping photo.

Run `python backend/db/seeds/reference_data.py` to materialize all of this as
CSVs under data/reference/.
"""

import csv
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "reference")


# ---------------------------------------------------------------------------
# Discount benchmark tables (source: company discount-trend photographs).
# Each value is the average *earned discount* observed for that category.
# None == '#NUM!' in the source (no/insufficient volume in that category).
# ---------------------------------------------------------------------------

DISCOUNT_BENCHMARKS = {
    "reporting_vertical": {
        "AFFINITY ALLIANCES": 0.71998, "AFFINITY SALES": 0.77136, "BANC HEALTH": 0.77368,
        "BANC HOME": 0.73806, "BANCA BLANK": 0.84445, "BBG": 0.75805, "COB": 0.70752,
        "CSC": 0.75023, "CSG": 0.79599, "E CHANNEL": 0.77499, "EMG BRANCH": 0.69321,
        "EMG VO": 0.74135, "EMG-Ibank": 0.68836, "EMG-Ibank-VO": 0.66653, "GBG": 0.48155,
        "HEALTH AGENCY": 0.73966, "HEALTH BROKING": 0.76561, "KRG": 0.71312,
        "KRG - AXIS": 0.69943, "KRG - BANDHAN": 0.71970, "KRG - HDFC": 0.75336,
        "KRG-YES": 0.75045, "M1": 0.68170, "M3": 0.74209, "M6": 0.75825,
        "MOTOR AGENCY": 0.78121, "MOTOR BROKING": 0.77677, "OTHERS": 0.84998,
        "PMG": 0.72306, "RETAIL TELESALES": 0.74278, "SIG": 0.67002, "SME": 0.80113,
        "SME AGENCY": 0.75475, "SME DIGITAL": 0.66287, "TRAVEL AGENCY": 0.89999,
    },
    "rto_state": {
        "ANDAMAN&NICOBAR": 0.63057, "ANDHRAPRADESH": 0.69103, "ARUNACHALPRADESH": 0.70593,
        "ASSAM": 0.72789, "BIHAR": 0.68128, "CHANDIGARH": 0.77317, "CHHATTISGARH": 0.61367,
        "DELHI": 0.77005, "GOA": 0.74084, "GUJARAT": 0.63887, "HARYANA": 0.76573,
        "HIMACHALPRADESH": 0.78906, "JAMMUANDKASHMIR": 0.73252, "JHARKHAND": 0.69971,
        "KARNATAKA": 0.73951, "KERALA": 0.65041, "LAKSHADWEEP": 0.70169,
        "MADHYAPRADESH": 0.71301, "MAHARASHTRA": 0.70471, "MANIPUR": 0.37639,
        "MEGHALAYA": 0.63146, "MIZORAM": 0.45266, "NAGALAND": 0.67060, "ODISHA": 0.72180,
        "PUNJAB": 0.74922, "RAJASTHAN": 0.70636, "SIKKIM": 0.67691, "TAMILNADU": 0.68595,
        "TELANGANA": 0.73305, "TRIPURA": 0.68770, "UTTARAKHAND": 0.76073,
        "UTTARPRADESH": 0.67339, "WESTBENGAL": 0.70388,
    },
    "emg_pmg": {
        "CORP": 0.79196, "EMG": 0.67275, "GBG": 0.48155, "IBANK": 0.75886, "MM": 0.74232,
        "OTHERS": 0.84446, "PMG": 0.71600, "SBGS": 0.76410,
    },
    # OVERRIDE: user-supplied corrected figures, not the photographed ones.
    "new_transaction_type": {
        "NEW": 0.54150, "RETENTION": 0.79017, "ROLLOVER": 0.79118, "USEDCAR": 0.54695,
    },
    "fuel_type": {
        "CNG": 0.689, "Diesel": 0.701, "Electric": 0.675, "Petrol": 0.725,
    },
    # Coarse manufacturer-tier grouping (distinct from the granular manufacturer table below).
    "segment_tier": {
        "HONDA": 0.74536, "HYUNDAI": 0.63475, "M&M": 0.75423, "MARUTI": 0.75032,
        "OTHERS": 0.63871, "PREMIUM 1": 0.77336, "PREMIUM 2": 0.64197, "TATA": 0.80805,
        "TOYOTA": 0.59556,
    },
    "vehicle_age_group": {
        ">=10": 0.77682, "0": 0.56903, "1": 0.81606, "2": 0.80975, "3": 0.78510,
        "4": 0.75817, "5": 0.73416, "6": 0.72246, "7": 0.70845, "8": 0.72018, "9": 0.73589,
    },
    "prev_year_ncb_flag": {
        "N": 0.70092, "Y": 0.80301,
    },
    "previous_year_ncb": {
        "0": 0.65785, "2": 0.60001, "10": 0.64036, "20": 0.80685, "25": 0.79938,
        "35": 0.78584, "40": 0.76195, "45": 0.76780, "50": 0.79202, "55": 0.74728,
        "65": 0.81459,
    },
    # Policy/business-type tier (distinct from Vehicle_Age_Group: mixes age bands
    # with status categories as found in the source -- kept as-is).
    "mod_biz_type1": {
        ">10y": 0.77846, "3-5y": 0.77009, "6-10y": 0.72343, "Accrued": 0.42275,
        "New": 0.55402, "Old": 1.00000, "SAOD": 0.81609, "SATP": None, "(blank)": 0.75113,
    },
    "zone": {
        "EAST": 0.678131, "NORTH": 0.73923, "SOUTH": 0.709027, "WEST": 0.689415,
    },
    # OVERRIDE: user-supplied corrected figures, not the photographed ones.
    "rto_zone": {
        "EAST": 0.69424, "NCR": 0.77005, "RON": 0.72235, "SOUTH": 0.71057, "WEST": 0.67983,
    },
    "manufacturer": {
        "ASHOK LEYLAND": 0.15031, "ASTON MARTIN": 0.86207, "ASTON MARTINE": 0.77906,
        "AUDI": 0.67376, "AUSTIN": 1.00000, "AVANTI": 0.85076, "BAJAJ": -0.10954,
        "BENTLEY": 0.82849, "BMW": 0.76514, "BUICK CAR": 1.00000, "BYD": 0.61457,
        "CADILLAC": 0.84665, "CHEVROLET": 0.30235, "CITROEN": 0.46368, "DAEWOO": 0.01305,
        "DATSUN": 0.30766, "FERRARI": 0.83029, "FIAT": 0.59267, "FORCE MOTOR": 0.72191,
        "FORCE MOTOR LTD": 0.52854, "FORCE MOTORS": 0.85420, "FORD": 0.55195, "GM": 0.41197,
        "HILLMAN CAR": 1.00000, "HM": 0.22141, "HONDA": 0.74536, "HUMMER": 0.68321,
        "HYUNDAI": 0.63488, "HYUNDAI MOTORS INDIA": 0.57245, "ISUZU MOTORS": 0.92001,
        "ISUZU MOTORS LTD": 0.61779, "JAGUAR": 0.76607, "JEEP": 0.72903,
        "JEETO MINIVAN": 0.81926, "KIA": 0.64474, "KIA MOTORS": 0.67233,
        "LAMBORGHINI": 0.81881, "LAMBORGINI": 0.81581, "LAND ROVER": 0.81163,
        "LOTUS": 0.78000, "M & M": 0.75381, "M&M": 0.75106, "MAHINDRA & MAHINDRA": 0.85902,
        "MARUTI": 0.75045, "MARUTI SUZUKI INDIA LIMITED": 0.69805, "MASERATI": 0.81594,
        "MAZDA": 0.54448, "MAZDA MOTOR": None, "MCLAREN": 0.71984, "MERCEDES": 0.78586,
        "MG CAR": 1.00000, "MINI": 0.72612, "MITSUBISHI": 0.64584, "MORRIS CAR": 1.00000,
        "MORRIS GARAGES": 0.66974, "NISSAN": 0.42389, "OBSOLETE": 0.67472, "OPEL": 1.00000,
        "OTHERS": 0.83458, "PORSCHE": 0.80972, "PREMIER": 0.90005, "RANGE ROVER": 0.83104,
        "RENAULT": 0.40381, "RENAULT INDIA PRIVATE LIMITED": 0.46654, "RHINO": None,
        "ROLLS ROYCE": 0.84099, "ROLLS-ROYCE": 0.87055, "SAN STORM": 0.84308,
        "SKODA": 0.50054, "SMART": 0.33233, "SSANGYONG": 0.65392,
        "STANDARD HERALD": 1.00000, "TATA": 0.78212, "TATA MOTORS": 0.82212,
        "TATA MOTORS LIMITED": 0.68662, "TESLA": 0.68067, "THE LONDON TAXI COMPANY": 0.30000,
        "TOYOTA": 0.60668, "TOYOTA MOTORS": 0.52768, "TRIUMPH": 1.00000, "TVS": -0.12675,
        "VAUXHALL": 1.00000, "VINFAST": 0.63121, "VINTAGE CARS": 1.00000,
        "VOLKSWAGEN": 0.57057, "VOLVO": 0.64498, "WILLS": 1.00000,
    },
}

GRAND_TOTAL_DISCOUNT = 0.71197  # fallback for any unmatched category


# ---------------------------------------------------------------------------
# Tariff OD rate table (source: printed tariff rate sheet, Private Car section).
# Rate is % of IDV. Anchored at vehicle age 0/5/10; ages in between are
# linearly interpolated by the loader, ages above 10 are held flat at the
# age-10 rate. Zone C (Rest of India) was cropped out of the source photo --
# approximated here as Zone B less a small uniform spread; revisit if a real
# Zone C table becomes available.
# ---------------------------------------------------------------------------

TARIFF_OD_RATES = {
    # zone -> age_anchor -> cc_bucket -> rate (% of IDV)
    "A": {
        0: {"<1000": 3.127, "1000-1500": 3.283, ">1500": 3.440},
        5: {"<1000": 3.283, "1000-1500": 3.447, ">1500": 3.612},
        10: {"<1000": 3.362, "1000-1500": 3.529, ">1500": 3.698},
    },
    "B": {
        0: {"<1000": 3.039, "1000-1500": 3.191, ">1500": 3.343},
        5: {"<1000": 3.191, "1000-1500": 3.351, ">1500": 3.510},
        10: {"<1000": 3.267, "1000-1500": 3.430, ">1500": 3.594},
    },
}
TARIFF_OD_RATES["C"] = {
    age: {bucket: round(rate * 0.97, 3) for bucket, rate in buckets.items()}
    for age, buckets in TARIFF_OD_RATES["B"].items()
}

ZONE_STATE_MAP = {
    "A": ["DELHI", "MAHARASHTRA", "TAMILNADU", "WESTBENGAL"],  # Mumbai/Chennai/Kolkata/Delhi states
    # All other state capitals fall in Zone B; anything not explicitly a
    # state-capital RTO falls in Zone C. The cohort generator decides this
    # per-row based on RTO_Location, not just RTO_state.
}


def interpolated_tariff_rate(zone: str, vehicle_age_years: int, cc_bucket: str) -> float:
    """Linearly interpolate the tariff table between its 0/5/10-year anchors."""
    anchors = TARIFF_OD_RATES[zone]
    age = max(0, min(vehicle_age_years, 10))
    if age <= 5:
        lo, hi, frac = 0, 5, age / 5
    else:
        lo, hi, frac = 5, 10, (age - 5) / 5
    lo_rate = anchors[lo][cc_bucket]
    hi_rate = anchors[hi][cc_bucket]
    return lo_rate + (hi_rate - lo_rate) * frac


# ---------------------------------------------------------------------------
# Fixed TP premium table -- IRDAI-notified rates (regulator-fixed, identical
# across all insurers). Verified against current public sources; the printed
# photo had two rows visually overlapping during the scroll/scan, this is the
# corrected mapping.
# ---------------------------------------------------------------------------

TP_PREMIUM_FIXED = {
    "ICE": {
        "<1000": {"1yr": 2094, "3yr_single": 6521},
        "1000-1500": {"1yr": 3416, "3yr_single": 10640},
        ">1500": {"1yr": 7897, "3yr_single": 24596},
    },
    "EV": {
        # kW bands; 1yr derived from the 3yr figure (no separately-published
        # 1yr EV rate found) -- flagged as an estimate, not a notified rate.
        "<30KW": {"1yr": round(5543 / 3 * 1.05, 0), "3yr_single": 5543},
        "30-65KW": {"1yr": round(9044 / 3 * 1.05, 0), "3yr_single": 9044},
        ">65KW": {"1yr": round(20907 / 3 * 1.05, 0), "3yr_single": 20907},
    },
}


def write_kv_csv(path, mapping, key_col, val_col):
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([key_col, val_col])
        for k, v in mapping.items():
            writer.writerow([k, "" if v is None else v])


def build():
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(os.path.join(OUT_DIR, "discount_benchmarks"), exist_ok=True)

    for dimension, mapping in DISCOUNT_BENCHMARKS.items():
        write_kv_csv(
            os.path.join(OUT_DIR, "discount_benchmarks", f"{dimension}.csv"),
            mapping, "category", "avg_discount",
        )

    with open(os.path.join(OUT_DIR, "tariff_od_rates.csv"), "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["zone", "age_anchor_years", "cc_bucket", "tariff_pct"])
        for zone, ages in TARIFF_OD_RATES.items():
            for age, buckets in ages.items():
                for bucket, rate in buckets.items():
                    writer.writerow([zone, age, bucket, rate])

    with open(os.path.join(OUT_DIR, "tp_premium_fixed.csv"), "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["fuel_class", "bucket", "term", "premium_inr"])
        for fuel_class, buckets in TP_PREMIUM_FIXED.items():
            for bucket, terms in buckets.items():
                for term, premium in terms.items():
                    writer.writerow([fuel_class, bucket, term, premium])

    print(f"Wrote {len(DISCOUNT_BENCHMARKS)} discount benchmark CSVs to {OUT_DIR}/discount_benchmarks/")
    print(f"Wrote tariff_od_rates.csv ({sum(len(b) for b in TARIFF_OD_RATES.values())} zone-age groups)")
    print(f"Wrote tp_premium_fixed.csv ({sum(len(b) for b in TP_PREMIUM_FIXED.values())} fuel-class buckets)")


if __name__ == "__main__":
    build()
