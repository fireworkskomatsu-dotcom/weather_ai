#!/usr/bin/env python3
from __future__ import annotations

import csv, hashlib, json, math, statistics
from datetime import datetime
from pathlib import Path
from typing import Any
import pandas as pd
import monitoring_walk_forward_ai as walk
import research_factory_v2_ai as research

BASE = Path(__file__).resolve().parent
PRICES, HISTORY = BASE / "prices.csv", BASE / "history.csv"
REPORT = BASE / "prospective_strategy_league_report.json"
REGISTRATION_DATE, EVALUATION_START = "2026-08-18", "2026-08-19"
MIN_FORWARD_DIRECTIONAL, MIN_FORWARD_DAYS, MIN_POSITIVE_BLOCKS = 60, 90, 4

def registry_hash() -> str:
    payload = {"registered_at": REGISTRATION_DATE, "evaluation_start": EVALUATION_START,
               "candidates": list(research.CANDIDATES), "direction_source": "research_factory_v2_ai.direction",
               "cost_pct": walk.ROUND_TRIP_COST_PCT}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

def forward_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    directional = [row for row in rows if row["direction"] != "SKIP"]
    values = [row["net_pct"] for row in directional]
    count, mean = len(values), statistics.fmean(values) if values else None
    # Ten frozen candidates share one promotion gate. 2.576 is the Bonferroni
    # one-sided 5% family-wise critical value for ten simultaneous tests.
    lower = mean - 2.576 * statistics.stdev(values) / math.sqrt(count) if count >= 2 else None
    compounded = 1.0
    for value in values: compounded *= 1 + value / 100
    return {"calendar_samples": len(rows), "directional_samples": count,
            "accuracy_pct": round(sum(row["correct"] for row in directional) / count * 100, 4) if count else None,
            "average_net_pct": round(mean, 6) if mean is not None else None,
            "familywise_lower_bound": round(lower, 6) if lower is not None else None,
            "compounded_net_pct": round((compounded - 1) * 100, 4)}

def block_stability(rows: list[dict[str, Any]]) -> dict[str, Any]:
    blocks = []
    if rows:
        size = max(1, math.ceil(len(rows) / 5))
        blocks = [forward_summary(rows[i:i + size]) for i in range(0, len(rows), size)][:5]
    return {"positive_blocks": sum((b["average_net_pct"] or 0) > 0 for b in blocks),
            "required": MIN_POSITIVE_BLOCKS, "blocks": blocks}

def build_report(data: pd.DataFrame) -> dict[str, Any]:
    records = walk.evaluate(data)
    forward_records = [row for row in records if row["decision_date"] >= EVALUATION_START]
    candidates = []
    for candidate in research.CANDIDATES:
        rows = [row for row in research.candidate_rows(records, candidate) if row["decision_date"] >= EVALUATION_START]
        candidates.append({"id": candidate, "forward": forward_summary(rows), "stability": block_stability(rows)})
    eligible = [c for c in candidates if c["forward"]["directional_samples"] >= MIN_FORWARD_DIRECTIONAL]
    champion = max(eligible, key=lambda c: (c["forward"]["familywise_lower_bound"] or -999,
                                             c["forward"]["compounded_net_pct"]), default=None)
    score, stable = (champion["forward"], champion["stability"]) if champion else ({}, {})
    buy_hold = ((forward_records[-1]["exit_price"] / forward_records[0]["entry_price"] - 1) * 100
                if forward_records else None)
    checks = {"registry_frozen_before_evaluation": REGISTRATION_DATE < EVALUATION_START,
              "at_least_90_forward_days": len(forward_records) >= MIN_FORWARD_DAYS,
              "champion_has_60_directional_outcomes": (score.get("directional_samples") or 0) >= MIN_FORWARD_DIRECTIONAL,
              "champion_familywise_lower_bound_positive": (score.get("familywise_lower_bound") or 0) > 0,
              "champion_compounded_positive": (score.get("compounded_net_pct") or 0) > 0,
              "champion_beats_buy_and_hold": buy_hold is not None and (score.get("compounded_net_pct") or 0) > buy_hold,
              "stable_in_four_of_five_blocks": (stable.get("positive_blocks") or 0) >= MIN_POSITIVE_BLOCKS}
    return {"schema_version": 1, "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "scope": "PROSPECTIVE_STRATEGY_LEAGUE_ONLY", "official_eligible": False, "real_money": False,
            "status": "FORWARD_PASS" if all(checks.values()) else "ACCUMULATING",
            "registered_at": REGISTRATION_DATE, "evaluation_start": EVALUATION_START,
            "registry_sha256": registry_hash(), "registry_locked": True, "retrospective_scoring_forbidden": True,
            "multiple_testing_control": "BONFERRONI_FAMILYWISE_5PCT_FOR_10_FROZEN_CANDIDATES",
            "candidate_count": len(candidates), "forward_calendar_samples": len(forward_records),
            "minimum_forward_days": MIN_FORWARD_DAYS, "minimum_directional_outcomes": MIN_FORWARD_DIRECTIONAL,
            "champion": champion, "buy_and_hold_pct": round(buy_hold, 4) if buy_hold is not None else None,
            "promotion_checks": checks, "candidates": candidates}

def append_public(report: dict[str, Any], history_path: Path) -> bool:
    rows = list(csv.reader(history_path.open(encoding="utf-8", newline=""))) if history_path.exists() else []
    target_date = max((r[16] for r in rows if len(r) >= 19 and r[0] == "FORWARD_V1"), default="")
    if not target_date or any(len(r) >= 2 and r[0] == "PROSPECTIVE_V3" and r[1] == target_date for r in rows): return False
    with history_path.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow(["PROSPECTIVE_V3", target_date, report["generated_at"], research.encode(report)])
    return True

def run(prices_path: Path = PRICES, history_path: Path = HISTORY, report_path: Path | None = REPORT) -> dict[str, Any]:
    report = build_report(pd.read_csv(prices_path, dtype={"Code": str}))
    if report_path is not None: report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_public(report, history_path)
    return report

if __name__ == "__main__":
    result = run()
    print(json.dumps({k: result[k] for k in ("status", "registered_at", "evaluation_start", "forward_calendar_samples", "promotion_checks")}, ensure_ascii=False, indent=2))
