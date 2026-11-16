"""
q3c_alpha_hs10.py

Phase 4 fix 3, step 3: compute alpha (price absorption) from the
10-digit quantity data downloaded in step 2.

For each HS10 line, for each quantity field (QY1 first, falling back
to QY2 if QY1 isn't usable), checks:
  - same non-"-"/non-blank unit in BOTH baseline and shock periods
  - India baseline value >= $1M
If usable:
    unit_value = value / quantity, for India and for "others" (world
    minus India), in each period.
    alpha = -(india_uv_pct_change - others_uv_pct_change) / india_tariff_change_pp
    (india_tariff_change_pp = India's own actual-duty-paid change,
    shock minus baseline, in points - NOT the India-vs-others gap used
    for epsilon; alpha is about price pass-through of India's OWN
    tariff change.)

If >= 8 usable lines: report median/p25/p75 as base/low/high.
Otherwise: keep the 0.3/0.45/0.6 fallback and say how many were usable.

READ-ONLY against raw/hts/top10_hs10_lines.json,
raw/census_hs10_qty/*. Writes data/phase4_alpha_hs10_v2.csv (new file).
"""

import csv
import json
import statistics
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
QTY_DIR = HERE / "raw" / "census_hs10_qty"
INDIA = "5330"

BASELINE_MONTHS = ["2024-10", "2024-11", "2024-12", "2025-01", "2025-02", "2025-03"]
SHOCK_MONTHS = ["2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03"]
FALLBACK_ALPHA = {"low": 0.3, "base": 0.45, "high": 0.6}


def load_lines():
    data = json.loads((HERE / "raw" / "hts" / "top10_hs10_lines.json").read_text(encoding="utf-8"))
    out = []
    for hs6, info in data.items():
        for line in info["hs10_lines"]:
            out.append((line, hs6, info["description"]))
    return out


def monthly_sums(code, months):
    """Returns dict with india_val, india_duty, india_qty1, qty1_unit,
    india_qty2, qty2_unit, world_val, world_duty, world_qty1, world_qty2
    summed/collected across months. Units must be consistent across
    months within the SAME call - if they vary, unit is set to 'MIXED'."""
    india_val = india_duty = world_val = world_duty = 0
    india_qty1 = india_qty2 = world_qty1 = world_qty2 = 0
    qty1_units, qty2_units = set(), set()
    for m in months:
        raw_file = QTY_DIR / f"{code}_{m}.json"
        if not raw_file.exists():
            continue
        saved = json.loads(raw_file.read_text(encoding="utf-8"))
        if saved["status"] != "ok" or not saved["rows"]:
            continue
        header, *records = saved["rows"]
        for rec in records:
            r = dict(zip(header, rec))
            val = int(r.get("CON_VAL_MO") or 0)
            is_world = "TOTAL FOR ALL" in (r.get("CTY_NAME") or "").upper()
            is_india = r.get("CTY_CODE") == INDIA and r.get("SUMMARY_LVL") == "DET"
            if not (is_world or is_india):
                continue
            qy1 = int(r.get("CON_QY1_MO") or 0)
            qy2 = int(r.get("CON_QY2_MO") or 0)
            u1 = r.get("UNIT_QY1") or "-"
            u2 = r.get("UNIT_QY2") or "-"
            if u1 != "-":
                qty1_units.add(u1)
            if u2 != "-":
                qty2_units.add(u2)
            if is_world:
                world_val += val
                world_qty1 += qy1
                world_qty2 += qy2
            if is_india:
                india_val += val
                india_qty1 += qy1
                india_qty2 += qy2
    return {
        "india_val": india_val, "world_val": world_val,
        "india_qty1": india_qty1, "world_qty1": world_qty1,
        "qty1_unit": qty1_units.pop() if len(qty1_units) == 1 else ("MIXED" if len(qty1_units) > 1 else "-"),
        "india_qty2": india_qty2, "world_qty2": world_qty2,
        "qty2_unit": qty2_units.pop() if len(qty2_units) == 1 else ("MIXED" if len(qty2_units) > 1 else "-"),
    }


DUTY_DIR = HERE / "raw" / "census_hs10_duty"


def duty_pct_for(line, months_list):
    """India's actual duty-paid rate (CAL_DUT_MO / CON_VAL_MO x 100),
    summed across months, for one HS10 line. Returns None if any month's
    file is missing (keeps the line out of the usable set rather than
    guessing)."""
    val = duty = 0
    for m in months_list:
        f = DUTY_DIR / f"{line}_{m}.json"
        if not f.exists():
            return None
        saved = json.loads(f.read_text(encoding="utf-8"))
        if saved["status"] != "ok" or not saved["rows"]:
            continue
        header, *records = saved["rows"]
        for rec in records:
            r = dict(zip(header, rec))
            if r.get("CTY_CODE") == INDIA and r.get("SUMMARY_LVL") == "DET":
                val += int(r.get("CON_VAL_MO") or 0)
                duty += int(r.get("CAL_DUT_MO") or 0)
    return (duty / val * 100) if val else None


def pct_change(old, new):
    return (new - old) / old * 100 if old else None


def main():
    lines = load_lines()

    usable = []
    skipped_reason = {"unit_mismatch_or_missing": 0, "below_1m": 0, "india_tariff_change_unavailable": 0}

    for line, hs6, desc in lines:
        b = monthly_sums(line, BASELINE_MONTHS)
        s = monthly_sums(line, SHOCK_MONTHS)

        if b["india_val"] < 1_000_000:
            skipped_reason["below_1m"] += 1
            continue

        # pick whichever quantity field is usable (same non-"-"/non-MIXED unit, nonzero qty, in BOTH periods)
        chosen = None
        for q in ("qty1", "qty2"):
            unit_b, unit_s = b[f"{q}_unit"], s[f"{q}_unit"]
            if unit_b not in ("-", "MIXED") and unit_b == unit_s and b[f"india_{q}"] > 0 and s[f"india_{q}"] > 0:
                chosen = q
                break
        if chosen is None:
            skipped_reason["unit_mismatch_or_missing"] += 1
            continue

        india_uv_b = b["india_val"] / b[f"india_{chosen}"]
        india_uv_s = s["india_val"] / s[f"india_{chosen}"]
        others_val_b, others_val_s = b["world_val"] - b["india_val"], s["world_val"] - s["india_val"]
        others_qty_b, others_qty_s = b[f"world_{chosen}"] - b[f"india_{chosen}"], s[f"world_{chosen}"] - s[f"india_{chosen}"]
        if others_qty_b <= 0 or others_qty_s <= 0:
            skipped_reason["unit_mismatch_or_missing"] += 1
            continue
        others_uv_b = others_val_b / others_qty_b
        others_uv_s = others_val_s / others_qty_s

        india_uv_pct = pct_change(india_uv_b, india_uv_s)
        others_uv_pct = pct_change(others_uv_b, others_uv_s)
        if india_uv_pct is None or others_uv_pct is None:
            skipped_reason["unit_mismatch_or_missing"] += 1
            continue

        # India's own tariff change, from the dedicated q3d duty download.
        duty_b = duty_pct_for(line, BASELINE_MONTHS)
        duty_s = duty_pct_for(line, SHOCK_MONTHS)
        if duty_b is None or duty_s is None:
            skipped_reason["india_tariff_change_unavailable"] += 1
            continue
        india_tariff_change_pp = duty_s - duty_b
        if india_tariff_change_pp == 0:
            skipped_reason["india_tariff_change_unavailable"] += 1
            continue

        alpha = -(india_uv_pct - others_uv_pct) / india_tariff_change_pp
        usable.append({
            "line": line, "hs6_parent": hs6, "description": desc,
            "quantity_field_used": chosen, "unit": b[f"{chosen}_unit"],
            "india_baseline_value_usd": b["india_val"],
            "india_unit_value_pct_change": round(india_uv_pct, 2),
            "others_unit_value_pct_change": round(others_uv_pct, 2),
            "india_tariff_change_pp": round(india_tariff_change_pp, 2),
            "alpha": round(alpha, 3),
        })

    with open(DATA_DIR / "phase4_alpha_hs10_v2.csv", "w", newline="", encoding="utf-8-sig") as f:
        if usable:
            w = csv.DictWriter(f, fieldnames=list(usable[0].keys()))
            w.writeheader()
            w.writerows(usable)
    print(f"Usable lines: {len(usable)} of {len(lines)} total")
    print(f"Skip reasons: {skipped_reason}")

    with open(DATA_DIR / "phase4_alpha_hs10_summary_v2.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if len(usable) >= 8:
            alphas = sorted(r["alpha"] for r in usable)
            n = len(alphas)
            median_a = statistics.median(alphas)
            p25 = alphas[max(0, int(0.25 * (n - 1)))]
            p75 = alphas[min(n - 1, int(0.75 * (n - 1)))]
            w.writerow(["tier", "alpha", "basis", "n_usable_lines"])
            w.writerow(["low", round(p25, 3), "25th percentile of measured alpha (10-digit lines)", n])
            w.writerow(["base", round(median_a, 3), "median of measured alpha", n])
            w.writerow(["high", round(p75, 3), "75th percentile of measured alpha", n])
            print(f"\n>= 8 usable lines ({n}) - using measured alpha: low={p25:.3f}, base={median_a:.3f}, high={p75:.3f}")
        else:
            w.writerow(["tier", "alpha", "basis", "n_usable_lines"])
            for tier, val in FALLBACK_ALPHA.items():
                w.writerow([tier, val, f"fallback - only {len(usable)} usable lines (<8 required)", len(usable)])
            print(f"\n< 8 usable lines ({len(usable)}) - keeping fallback alpha 0.3/0.45/0.6")


if __name__ == "__main__":
    main()
