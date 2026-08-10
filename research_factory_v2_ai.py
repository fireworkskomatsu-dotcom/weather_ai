#!/usr/bin/env python3

from __future__ import annotations

import base64
import csv
import hashlib
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import monitoring_walk_forward_ai as walk


BASE = Path(__file__).resolve().parent
PRICES = BASE / "prices.csv"
HISTORY = BASE / "history.csv"
REPORT = BASE / "research_factory_v2_report.json"
MIN_DIRECTIONAL = 30
MIN_ACCURACY = 52.0
MIN_POSITIVE_BLOCKS = 3


def encode(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def direction(rows: list[dict[str, Any]], index: int, candidate: str) -> str:
    row = rows[index]
    base = row["direction"]
    past = [item["market_return_pct"] for item in rows[:index]]
    trailing3 = sum(past[-3:]) if len(past) >= 3 else 0.0
    trailing5 = sum(past[-5:]) if len(past) >= 5 else 0.0
    trailing10 = sum(past[-10:]) if len(past) >= 10 else 0.0
    trailing20 = sum(past[-20:]) if len(past) >= 20 else 0.0
    if candidate == "BASE":
        return base
    if candidate == "INVERSE_BASE":
        return "SHORT" if base == "LONG" else "LONG" if base == "SHORT" else "SKIP"
    if candidate == "LONG_ONLY_BASE":
        return "LONG" if base == "LONG" else "SKIP"
    if candidate == "RISK_VETO_BASE":
        return "SKIP" if row["risk"] == "HIGH" else base
    if candidate == "TARGET_MOM_3":
        return "LONG" if trailing3 > 0 else "SHORT" if trailing3 < 0 else "SKIP"
    if candidate == "TARGET_MOM_5":
        return "LONG" if trailing5 > 0.5 else "SHORT" if trailing5 < -0.5 else "SKIP"
    if candidate == "TARGET_MR_3":
        return "SHORT" if trailing3 > 0 else "LONG" if trailing3 < 0 else "SKIP"
    if candidate == "TARGET_MR_5":
        return "SHORT" if trailing5 > 0.5 else "LONG" if trailing5 < -0.5 else "SKIP"
    if candidate == "REGIME_MOM_20":
        return "LONG" if trailing20 > 2 else "SHORT" if trailing20 < -2 else "SKIP"
    if candidate == "BASE_TREND_AGREE":
        return base if (base == "LONG" and trailing10 > 0) or (base == "SHORT" and trailing10 < 0) else "SKIP"
    return "SKIP"


CANDIDATES = (
    "BASE", "INVERSE_BASE", "LONG_ONLY_BASE", "RISK_VETO_BASE",
    "TARGET_MOM_3", "TARGET_MOM_5", "TARGET_MR_3", "TARGET_MR_5",
    "REGIME_MOM_20", "BASE_TREND_AGREE",
)


def candidate_rows(rows: list[dict[str, Any]], candidate: str) -> list[dict[str, Any]]:
    output = []
    previous = "SKIP"
    for index, row in enumerate(rows):
        selected = direction(rows, index, candidate)
        market = row["market_return_pct"]
        gross = market if selected == "LONG" else -market if selected == "SHORT" else 0.0
        turnover_cost = walk.ROUND_TRIP_COST_PCT if selected != previous and (selected != "SKIP" or previous != "SKIP") else 0.0
        output.append({
            "decision_date": row["decision_date"],
            "direction": selected,
            "gross_pct": gross,
            "net_pct": gross - turnover_cost,
            "correct": gross > 0,
        })
        previous = selected
    return output


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    directional = [row for row in rows if row["direction"] != "SKIP"]
    values = [row["net_pct"] for row in directional]
    count = len(values)
    average = statistics.fmean(values) if values else None
    standard_error = statistics.stdev(values) / math.sqrt(count) if count >= 2 else None
    lower = average - 1.96 * standard_error if average is not None and standard_error is not None else None
    compounded = 1.0
    for value in values:
        compounded *= 1 + value / 100
    return {
        "samples": len(rows),
        "directional_samples": count,
        "accuracy_pct": round(sum(row["correct"] for row in directional) / count * 100, 4) if count else None,
        "average_net_pct": round(average, 6) if average is not None else None,
        "mean_95pct_lower_bound": round(lower, 6) if lower is not None else None,
        "compounded_net_pct": round((compounded - 1) * 100, 4),
    }


def stability(rows: list[dict[str, Any]]) -> dict[str, Any]:
    blocks = []
    size = max(1, len(rows) // 4)
    for index in range(4):
        start = index * size
        end = len(rows) if index == 3 else min(len(rows), (index + 1) * size)
        blocks.append(summary(rows[start:end]))
    positive = sum((block["average_net_pct"] or 0) > 0 for block in blocks)
    return {"positive_blocks": positive, "required": MIN_POSITIVE_BLOCKS, "blocks": blocks}


def build_report(data: pd.DataFrame) -> dict[str, Any]:
    records = walk.evaluate(data)
    split = int(len(records) * 0.6)
    development_base = records[:split]
    holdout_base = records[split:]
    candidates = []
    for candidate in CANDIDATES:
        all_rows = candidate_rows(records, candidate)
        development = all_rows[:split]
        holdout = all_rows[split:]
        candidates.append({
            "id": candidate,
            "development": summary(development),
            "holdout": summary(holdout),
            "holdout_stability": stability(holdout),
        })
    selected = max(
        candidates,
        key=lambda item: (item["development"]["mean_95pct_lower_bound"] or -999, item["development"]["average_net_pct"] or -999),
    ) if candidates else None
    holdout = selected["holdout"] if selected else {}
    stable = selected["holdout_stability"] if selected else {}
    checks = {
        "development_selection_only": selected is not None,
        "holdout_directional_at_least_30": (holdout.get("directional_samples") or 0) >= MIN_DIRECTIONAL,
        "holdout_accuracy_at_least_52": (holdout.get("accuracy_pct") or 0) >= MIN_ACCURACY,
        "holdout_average_positive": (holdout.get("average_net_pct") or 0) > 0,
        "holdout_95pct_lower_bound_positive": (holdout.get("mean_95pct_lower_bound") or 0) > 0,
        "stable_in_three_of_four_blocks": (stable.get("positive_blocks") or 0) >= MIN_POSITIVE_BLOCKS,
    }
    promoted = all(checks.values())
    buy_hold = (holdout_base[-1]["exit_price"] / holdout_base[0]["entry_price"] - 1) * 100 if holdout_base else None
    report = {
        "schema_version": 2,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "scope": "RESEARCH_FACTORY_ONLY",
        "official_eligible": False,
        "status": "RESEARCH_PASS" if promoted else "RESEARCH_BLOCKED",
        "selection_policy": "FIRST_60_PERCENT_ONLY",
        "holdout_policy": "LAST_40_PERCENT_NEVER_USED_FOR_SELECTION",
        "multiple_testing_control": "FIXED_CANDIDATE_REGISTRY_AND_95PCT_LOWER_BOUND",
        "candidate_count": len(CANDIDATES),
        "selected_candidate": selected["id"] if selected else None,
        "promotion_checks": checks,
        "holdout_buy_and_hold_pct": round(buy_hold, 4) if buy_hold is not None else None,
        "selected": selected,
        "candidates": candidates,
        "records_sha256": hashlib.sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
    }
    return report


def append_public(report: dict[str, Any], history_path: Path) -> bool:
    rows = []
    if history_path.exists():
        with history_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
    target_date = max((row[16] for row in rows if len(row) >= 19 and row[0] == "FORWARD_V1"), default="")
    if not target_date or any(len(row) >= 2 and row[0] == "RESEARCH_V2" and row[1] == target_date for row in rows):
        return False
    with history_path.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow([
            "RESEARCH_V2", target_date, report["generated_at"], encode(report)
        ])
    return True


def run(prices_path: Path = PRICES, history_path: Path = HISTORY, report_path: Path | None = REPORT) -> dict[str, Any]:
    data = pd.read_csv(prices_path, dtype={"Code": str})
    report = build_report(data)
    if report_path is not None:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_public(report, history_path)
    return report


if __name__ == "__main__":
    result = run()
    print(json.dumps({key: result[key] for key in ("status", "candidate_count", "selected_candidate", "promotion_checks")}, ensure_ascii=False, indent=2))
