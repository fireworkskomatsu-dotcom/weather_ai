#!/usr/bin/env python3

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

import monitoring_walk_forward_ai as walk


BASE = Path(__file__).resolve().parent
PRICES = BASE / "prices.csv"
HISTORY = BASE / "history.csv"
REPORT = BASE / "monitoring_challenger_report.json"

CANDIDATES = (
    {"id": "CHAMPION_55", "long_at": 55, "short_at": 45, "allow_short": True, "skip_high_risk": False},
    {"id": "CONSERVATIVE_60", "long_at": 60, "short_at": 40, "allow_short": True, "skip_high_risk": False},
    {"id": "HIGH_CONVICTION_65", "long_at": 65, "short_at": 35, "allow_short": True, "skip_high_risk": False},
    {"id": "LONG_ONLY_60", "long_at": 60, "short_at": 40, "allow_short": False, "skip_high_risk": False},
    {"id": "RISK_VETO_60", "long_at": 60, "short_at": 40, "allow_short": True, "skip_high_risk": True},
)


def candidate_direction(row: dict[str, Any], candidate: dict[str, Any]) -> str:
    probability = row["probability_up"]
    if candidate["skip_high_risk"] and row["risk"] == "HIGH":
        return "SKIP"
    if probability >= candidate["long_at"]:
        return "LONG"
    if candidate["allow_short"] and probability <= candidate["short_at"]:
        return "SHORT"
    return "SKIP"


def candidate_rows(
    base_rows: list[dict[str, Any]],
    candidate: dict[str, Any],
) -> list[dict[str, Any]]:
    output = []
    for row in base_rows:
        direction = candidate_direction(row, candidate)
        market_return = row["market_return_pct"]
        gross = market_return if direction == "LONG" else -market_return if direction == "SHORT" else 0.0
        net = gross - walk.ROUND_TRIP_COST_PCT if direction != "SKIP" else 0.0
        output.append({
            **row,
            "direction": direction,
            "gross_directional_return_pct": round(gross, 6),
            "net_after_cost_pct": round(net, 6),
            "result": "CORRECT" if gross > 0 else "INCORRECT" if gross < 0 else "SKIP_OR_FLAT",
        })
    return output


def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    directional = [row for row in rows if row["direction"] != "SKIP"]
    correct = sum(row["result"] == "CORRECT" for row in directional)
    incorrect = sum(row["result"] == "INCORRECT" for row in directional)
    return {
        "samples": len(rows),
        "directional_samples": len(directional),
        "correct": correct,
        "incorrect": incorrect,
        "accuracy_pct": round(correct / len(directional) * 100, 4) if directional else None,
        "average_net_after_cost_pct": round(
            sum(row["net_after_cost_pct"] for row in directional) / len(directional),
            6,
        ) if directional else None,
    }


def forward_summary(history_path: Path) -> dict[str, Any]:
    outcomes = []
    if history_path.exists():
        with history_path.open("r", encoding="utf-8", newline="") as handle:
            outcomes = [row for row in csv.reader(handle) if row and row[0] == "OUTCOME_V1" and len(row) >= 13]
    directional = [row for row in outcomes if row[9] in {"LONG", "SHORT"}]
    correct = sum(row[10] == "CORRECT" for row in directional)
    incorrect = sum(row[10] == "INCORRECT" for row in directional)
    net_values = []
    for row in directional:
        market_return = float(row[8])
        gross = market_return if row[9] == "LONG" else -market_return
        net_values.append(gross - walk.ROUND_TRIP_COST_PCT)
    return {
        "outcomes": len(outcomes),
        "directional_samples": len(directional),
        "correct": correct,
        "incorrect": incorrect,
        "accuracy_pct": round(correct / len(directional) * 100, 4) if directional else None,
        "average_net_after_cost_pct": round(sum(net_values) / len(net_values), 6) if net_values else None,
    }


def build_report(data: pd.DataFrame, history_path: Path = HISTORY) -> dict[str, Any]:
    base_rows = walk.evaluate(data)
    split_index = int(len(base_rows) * 0.6)
    candidates = []
    for definition in CANDIDATES:
        rows = candidate_rows(base_rows, definition)
        candidates.append({
            "definition": definition,
            "development": summary(rows[:split_index]),
            "holdout": summary(rows[split_index:]),
        })

    eligible_for_selection = [
        item for item in candidates
        if item["development"]["directional_samples"] >= 30
        and item["development"]["average_net_after_cost_pct"] is not None
    ]
    selected = max(
        eligible_for_selection,
        key=lambda item: item["development"]["average_net_after_cost_pct"],
    ) if eligible_for_selection else None

    forward = forward_summary(history_path)
    holdout = selected["holdout"] if selected else {}
    checks = {
        "candidate_selected_on_development_only": selected is not None,
        "holdout_directional_samples_at_least_30": (holdout.get("directional_samples") or 0) >= 30,
        "holdout_accuracy_at_least_52": (holdout.get("accuracy_pct") or 0) >= 52,
        "holdout_average_net_positive": (holdout.get("average_net_after_cost_pct") or 0) > 0,
        "forward_directional_samples_at_least_30": forward["directional_samples"] >= 30,
        "forward_accuracy_at_least_52": (forward["accuracy_pct"] or 0) >= 52,
        "forward_average_net_positive": (forward["average_net_after_cost_pct"] or 0) > 0,
    }
    promoted = all(checks.values())
    compact_candidates = [
        {
            "id": item["definition"]["id"],
            "development": item["development"],
            "holdout": item["holdout"],
        }
        for item in candidates
    ]
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "PROMOTED" if promoted else "BLOCKED",
        "scope": "RESEARCH_CHALLENGER_ONLY",
        "official_eligible": False,
        "selection_policy": "development_first_60_percent_only",
        "holdout_policy": "last_40_percent_never_used_for_selection",
        "selected_candidate": selected["definition"]["id"] if selected else None,
        "promotion_checks": checks,
        "forward_summary": forward,
        "candidates": compact_candidates,
        "candidate_definitions_sha256": hashlib.sha256(
            json.dumps(CANDIDATES, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }


def main() -> None:
    data = pd.read_csv(PRICES, dtype={"Code": str})
    report = build_report(data)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "selected_candidate": report["selected_candidate"],
        "promotion_checks": report["promotion_checks"],
        "forward_summary": report["forward_summary"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
