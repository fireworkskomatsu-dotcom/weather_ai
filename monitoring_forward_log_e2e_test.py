#!/usr/bin/env python3

from __future__ import annotations

import csv
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


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

    (work / "history.csv").write_text(
        "LEGACY,ROW,PRESERVED\n",
        encoding="utf-8",
    )

    def run_once() -> None:
        result = subprocess.run(
            [sys.executable, "weather_signal.py"],
            cwd=work,
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

    checks = {
        "isolated_filesystem": work != BASE,
        "legacy_row_preserved": rows[0] == ["LEGACY", "ROW", "PRESERVED"],
        "one_record_after_two_runs": len(forward_rows) == 1,
        "schema_has_13_fields": len(row) == 13,
        "stable_run_id_present": len(row) >= 2 and len(row[1]) == 20,
        "scope_monitoring_only": len(row) >= 12 and row[11] == "FREE_MONITORING_ONLY",
        "official_eligible_false": len(row) >= 13 and row[12] == "false",
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
