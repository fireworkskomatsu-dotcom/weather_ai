#!/usr/bin/env python3
import hashlib
from pathlib import Path
import pandas as pd
import prospective_strategy_league_ai as target
import monitoring_walk_forward_ai as walk

BASE = Path(__file__).resolve().parent
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
protected = ["prices.csv", "history.csv", "official_performance.json", "official_decision_log.jsonl"]
before = {name: digest(BASE / name) for name in protected}
report = target.build_report(pd.read_csv(BASE / "prices.csv", dtype={"Code": str}))
checks = {
    "registry_is_locked": report["registry_locked"] is True and len(report["registry_sha256"]) == 64,
    "registry_precedes_evaluation": report["registered_at"] < report["evaluation_start"],
    "ten_candidates_registered": report["candidate_count"] == 10,
    "past_results_not_scored": report["forward_calendar_samples"] == sum(
        row["decision_date"] >= target.EVALUATION_START for row in walk.evaluate(pd.read_csv(BASE / "prices.csv", dtype={"Code": str}))
    ),
    "retrospective_scoring_forbidden": report["retrospective_scoring_forbidden"] is True,
    "real_money_disabled": report["real_money"] is False and report["official_eligible"] is False,
    "strong_forward_gate": report["minimum_forward_days"] == 90 and report["minimum_directional_outcomes"] == 60,
    "familywise_confidence_and_stability_required": report["multiple_testing_control"].startswith("BONFERRONI") and "champion_familywise_lower_bound_positive" in report["promotion_checks"] and "stable_in_four_of_five_blocks" in report["promotion_checks"],
    "benchmark_outperformance_required": "champion_beats_buy_and_hold" in report["promotion_checks"],
    "fail_closed_while_accumulating": report["status"] == "ACCUMULATING" and report["champion"] is None,
    "production_files_unchanged": before == {name: digest(BASE / name) for name in protected},
}
for name, passed in checks.items(): print(f"{name}: {passed}")
print("RESULT:", "PASS" if all(checks.values()) else "FAIL")
if not all(checks.values()): raise SystemExit(1)
