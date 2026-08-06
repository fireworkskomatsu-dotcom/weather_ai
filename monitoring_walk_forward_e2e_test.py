#!/usr/bin/env python3

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

import monitoring_walk_forward_ai as target


BASE = Path(__file__).resolve().parent


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


production_before = {
    name: digest(BASE / name)
    for name in (
        "prices.csv", "history.csv", "official_performance.json",
        "official_decision_log.jsonl", "virtual_account.json",
    )
}

data = pd.read_csv(BASE / "prices.csv", dtype={"Code": str})
end_date = data.loc[data["Code"] == target.TARGET_CODE, "Date"].max()
original = target.evaluate(data, end_date=end_date)

future = data.iloc[-1].copy()
future["Code"] = "88880"
future["Date"] = "2099-12-31"
future["C"] = 999999999.0
future_data = pd.concat([data, pd.DataFrame([future])], ignore_index=True)
after_future_injection = target.evaluate(future_data, end_date=end_date)

report = target.build_report(data)
records = target.evaluate(data)

checks = {
    "has_walk_forward_samples": len(records) >= 50,
    "research_only": report["scope"] == "RESEARCH_WALK_FORWARD_ONLY",
    "official_eligible_false": report["official_eligible"] is False,
    "future_row_does_not_change_past": original == after_future_injection,
    "outcomes_are_next_session_only": all(
        row["outcome_date"] > row["decision_date"] for row in records
    ),
    "overseas_same_day_forbidden": report["anti_leakage_policy"]["overseas_fx_crypto_data"] == "strictly_before_decision_date",
    "cost_included": report["assumed_round_trip_cost_pct"] > 0,
    "record_digest_present": len(report["records_sha256"]) == 64,
    "holdout_has_samples": report["holdout_segment"]["samples"] >= 30,
    "chronological_holdout_after_development": (
        report["development_segment"]["last_outcome_date"]
        <= report["holdout_segment"]["first_decision_date"]
    ),
    "production_files_unchanged": production_before == {
        name: digest(BASE / name) for name in production_before
    },
}

print("===== MONITORING WALK FORWARD E2E =====")
for key, passed in checks.items():
    print(f"  {key}: {passed}")
print("RESULT:", "PASS" if all(checks.values()) else "FAIL")

if not all(checks.values()):
    raise SystemExit(1)
