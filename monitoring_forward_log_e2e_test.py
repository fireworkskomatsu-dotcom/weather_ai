#!/usr/bin/env python3

from __future__ import annotations

import csv
import hashlib
import shutil
import subprocess
import sys
import tempfile
import os
from pathlib import Path

import pandas as pd


BASE = Path(__file__).resolve().parent


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


production_before = {
    name: digest(BASE / name)
    for name in (
        "history.csv",
        "prices.csv",
        "latest_weather.txt",
        "cards.json",
        "official_decision_log.jsonl",
        "virtual_account.json",
    )
}


with tempfile.TemporaryDirectory(prefix="weather_ai_monitoring_log_") as temporary:
    work = Path(temporary) / "weather_ai"
    work.mkdir()

    for name in ("weather_signal.py", "prices.csv"):
        shutil.copy2(BASE / name, work / name)

    prices = pd.read_csv(work / "prices.csv", dtype={"Code": str})
    latest = pd.to_datetime(prices["Date"]).max()
    shift = pd.Timestamp.now().normalize() - latest.normalize()
    prices["Date"] = (
        pd.to_datetime(prices["Date"]) + shift
    ).dt.strftime("%Y-%m-%d")
    prices.to_csv(work / "prices.csv", index=False)

    (work / "history.csv").write_text(
        "LEGACY,ROW,PRESERVED\n",
        encoding="utf-8",
    )

    def run_once(force_intraday: bool = False) -> None:
        environment = {**os.environ, "WEATHER_AI_ISOLATED_TEST": "1"}
        if force_intraday:
            environment["WEATHER_AI_FORCE_INTRADAY_TEST"] = "1"
        result = subprocess.run(
            [sys.executable, "weather_signal.py"],
            cwd=work,
            env=environment,
            text=True,
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout + "\n" + result.stderr)

    run_once()
    run_once()

    with (work / "history.csv").open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        rows = list(csv.reader(handle))

    forward_rows = [row for row in rows if row and row[0] == "FORWARD_V1"]
    row = forward_rows[0] if forward_rows else []

    duplicate_run_id = "d" * 20
    duplicate = list(row)
    duplicate[1] = duplicate_run_id
    with (work / "history.csv").open(
        "a",
        encoding="utf-8",
        newline="",
    ) as handle:
        csv.writer(handle).writerow(duplicate)

    # 次の取引日を追加し、過去判断だけが評価されることを確認。
    prices = pd.read_csv(work / "prices.csv", dtype={"Code": str})
    target = prices[prices["Code"] == "13210"].sort_values("Date")
    next_target = target.iloc[-1].copy()
    next_target["Date"] = (
        pd.to_datetime(next_target["Date"]) + pd.Timedelta(days=1)
    ).strftime("%Y-%m-%d")
    next_target["C"] = float(next_target["C"]) * 1.01
    next_target["AdjC"] = next_target["C"]
    prices = pd.concat([prices, pd.DataFrame([next_target])], ignore_index=True)
    prices.to_csv(work / "prices.csv", index=False)
    run_once(force_intraday=True)
    with (work / "history.csv").open("r", encoding="utf-8", newline="") as handle:
        intraday_rows = list(csv.reader(handle))
    intraday_outcomes = [row for row in intraday_rows if row and row[0] == "OUTCOME_V1"]
    run_once()

    with (work / "history.csv").open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        final_rows = list(csv.reader(handle))
    outcome_rows = [row for row in final_rows if row and row[0] == "OUTCOME_V1"]
    outcome = outcome_rows[0] if outcome_rows else []

    checks = {
        "isolated_filesystem": work != BASE,
        "legacy_row_preserved": rows[0] == ["LEGACY", "ROW", "PRESERVED"],
        "one_record_after_two_runs": len(forward_rows) == 1,
        "schema_has_19_fields": len(row) == 19,
        "stable_run_id_present": len(row) >= 2 and len(row[1]) == 20,
        "scope_monitoring_only": len(row) >= 12 and row[11] == "FREE_MONITORING_ONLY",
        "official_eligible_false": len(row) >= 13 and row[12] == "false",
        "data_status_recorded": len(row) >= 14 and row[13] in {"FRESH", "STALE_DATA"},
        "data_age_recorded": len(row) >= 15 and row[14].lstrip("-").isdigit(),
        "target_symbol_recorded": len(row) >= 16 and row[15] == "1321.T",
        "target_price_recorded": len(row) >= 18 and float(row[17]) > 0,
        "direction_recorded": len(row) >= 19 and row[18] in {"LONG", "SHORT", "SKIP"},
        "intraday_unfinalized_outcome_blocked": len(intraday_outcomes) == 0,
        "one_next_day_outcome": len(outcome_rows) == 1,
        "duplicate_target_date_one_outcome": len(outcome_rows) == 1,
        "latest_duplicate_selected": len(outcome) >= 2 and outcome[1] == duplicate_run_id,
        "outcome_scope_monitoring_only": len(outcome) >= 12 and outcome[11] == "FREE_MONITORING_ONLY",
        "outcome_official_eligible_false": len(outcome) >= 13 and outcome[12] == "false",
        "production_files_unchanged": production_before == {
            name: digest(BASE / name) for name in production_before
        },
    }

    print("===== MONITORING FORWARD LOG E2E =====")
    for key, passed in checks.items():
        print(f"  {key}: {passed}")
    print("RESULT:", "PASS" if all(checks.values()) else "FAIL")

    if not all(checks.values()):
        raise SystemExit(1)
