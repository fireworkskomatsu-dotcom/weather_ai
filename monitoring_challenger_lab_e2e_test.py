#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import pandas as pd

import monitoring_challenger_lab_ai as target
import monitoring_walk_forward_ai as walk


BASE = Path(__file__).resolve().parent


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


production_before = {
    name: digest(BASE / name)
    for name in ("prices.csv", "history.csv", "official_performance.json", "virtual_account.json")
}

data = pd.read_csv(BASE / "prices.csv", dtype={"Code": str})
with tempfile.TemporaryDirectory(prefix="weather_ai_challenger_test_") as temporary:
    empty_history = Path(temporary) / "history.csv"
    empty_history.write_text("", encoding="utf-8")
    report = target.build_report(data, history_path=empty_history)

    base = walk.evaluate(data)
    split = int(len(base) * 0.6)
    modified = data.copy()
    holdout_outcome_start = base[split]["outcome_date"]
    mask = (modified["Code"] == walk.TARGET_CODE) & (modified["Date"] > holdout_outcome_start)
    modified.loc[mask, "C"] = modified.loc[mask, "C"].astype(float) * 1.5
    modified_report = target.build_report(modified, history_path=empty_history)

checks = {
    "five_fixed_candidates": len(report["candidates"]) == 5,
    "selection_uses_development_only": report["selected_candidate"] == modified_report["selected_candidate"],
    "holdout_not_used_for_selection": report["holdout_policy"] == "last_40_percent_never_used_for_selection",
    "promotion_blocked_without_forward_30": report["status"] == "BLOCKED" and not report["promotion_checks"]["forward_directional_samples_at_least_30"],
    "official_eligible_false": report["official_eligible"] is False,
    "production_files_unchanged": production_before == {
        name: digest(BASE / name) for name in production_before
    },
}

print("===== MONITORING CHALLENGER LAB E2E =====")
for key, passed in checks.items():
    print(f"  {key}: {passed}")
print("RESULT:", "PASS" if all(checks.values()) else "FAIL")

if not all(checks.values()):
    raise SystemExit(1)
