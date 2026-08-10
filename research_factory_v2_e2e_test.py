#!/usr/bin/env python3

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

import monitoring_walk_forward_ai as walk
import research_factory_v2_ai as target


BASE = Path(__file__).resolve().parent


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


protected = ["prices.csv", "history.csv", "official_performance.json", "official_decision_log.jsonl"]
before = {name: digest(BASE / name) for name in protected}
data = pd.read_csv(BASE / "prices.csv", dtype={"Code": str})
report = target.build_report(data)
records = walk.evaluate(data)
split = int(len(records) * 0.6)

future = data.iloc[-1].copy()
future["Code"] = "88880"
future["Date"] = "2099-12-31"
future["C"] = 1.0
future_report = target.build_report(pd.concat([data, pd.DataFrame([future])], ignore_index=True))

holdout_mutated = [dict(row) for row in records]
for row in holdout_mutated[split:]:
    row["market_return_pct"] *= -100
original_dev_scores = {
    candidate: target.summary(target.candidate_rows(records, candidate)[:split])
    for candidate in target.CANDIDATES
}
mutated_dev_scores = {
    candidate: target.summary(target.candidate_rows(holdout_mutated, candidate)[:split])
    for candidate in target.CANDIDATES
}

checks = {
    "ten_fixed_candidates": report["candidate_count"] == 10 and len(target.CANDIDATES) == 10,
    "research_only": report["scope"] == "RESEARCH_FACTORY_ONLY" and report["official_eligible"] is False,
    "selection_uses_development_only": report["selection_policy"] == "FIRST_60_PERCENT_ONLY",
    "holdout_never_used_for_selection": original_dev_scores == mutated_dev_scores,
    "future_row_does_not_change_historical_digest": report["records_sha256"] == future_report["records_sha256"],
    "costs_on_turnover": any(item["net_pct"] < item["gross_pct"] for item in target.candidate_rows(records, "BASE")),
    "confidence_bound_required": "holdout_95pct_lower_bound_positive" in report["promotion_checks"],
    "four_block_stability_required": report["selected"]["holdout_stability"]["required"] == 3,
    "fail_closed_on_weak_holdout": report["status"] == "RESEARCH_BLOCKED",
    "production_files_unchanged": before == {name: digest(BASE / name) for name in protected},
}

print("===== RESEARCH FACTORY V2 E2E =====")
for name, passed in checks.items():
    print(f"  {name}: {passed}")
print("RESULT:", "PASS" if all(checks.values()) else "FAIL")
if not all(checks.values()):
    raise SystemExit(1)
