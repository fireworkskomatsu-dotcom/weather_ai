#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parent
REPORT = BASE / "price_provider_e2e_report.json"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return default


def save_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def digest(path: Path) -> str | None:
    if not path.exists():
        return None

    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


production_before = {
    name: digest(BASE / name)
    for name in (
        "live_price.json",
        "price_data.json",
        "official_decision_log.jsonl",
        "official_trade_ledger.json",
        "official_performance.json",
    )
}


with tempfile.TemporaryDirectory(
    prefix="weather_ai_price_provider_"
) as temporary:
    work = Path(temporary) / "weather_ai"

    shutil.copytree(
        BASE,
        work,
        ignore=shutil.ignore_patterns(
            ".git",
            "__pycache__",
            "*.log",
            "backup_*",
        ),
    )

    for filename in (
        "canonical_price.json",
        "live_price.json",
        "price_data.json",
        "price_provider_status.json",
    ):
        path = work / filename

        if path.exists():
            path.unlink()

    env = os.environ.copy()
    env.update(
        {
            "WEATHER_AI_PRICE_PROVIDER": "TEST_FIXED",
            "WEATHER_AI_PRICE_MODE": "ISOLATED_TEST",
            "WEATHER_AI_ISOLATED_TEST": "1",
            "WEATHER_AI_TEST_PRICE": "70123",
        }
    )

    result = subprocess.run(
        ["python3", "price_provider_ai.py"],
        cwd=work,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "price_provider_ai.py failed\n"
            + result.stdout
            + "\n"
            + result.stderr
        )

    canonical = load_json(
        work / "canonical_price.json",
        {},
    )
    status = load_json(
        work / "price_provider_status.json",
        {},
    )

    checks = {
        "isolated_environment":
            work != BASE,
        "test_provider_ran":
            status.get("status") == "OK",
        "symbol_exact":
            canonical.get("symbol") == "1321.T",
        "price_exact":
            float(
                canonical.get("price") or 0
            ) == 70123.0,
        "test_mode_recorded":
            canonical.get("mode")
            == "ISOLATED_TEST",
        "official_eligible_false":
            canonical.get(
                "official_eligible"
            ) is False,
        "official_learning_blocked":
            canonical.get(
                "allow_official_learning"
            ) is False,
        "official_performance_blocked":
            canonical.get(
                "allow_official_performance"
            ) is False,
        "live_price_not_written":
            not (work / "live_price.json").exists(),
        "price_data_not_written":
            not (work / "price_data.json").exists(),
    }

    production_after = {
        name: digest(BASE / name)
        for name in production_before
    }

    checks["production_files_unchanged"] = (
        production_before == production_after
    )

    passed = all(checks.values())

    report = {
        "generated_at":
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "scope": "ISOLATED_PRICE_PROVIDER_E2E",
        "production_data_modified": False,
        "provider": "TEST_FIXED",
        "test_price": 70123.0,
        "canonical_price": canonical,
        "provider_status": status,
        "checks": checks,
        "stdout": result.stdout[-3000:],
    }

    save_json(REPORT, report)

    print("===== PRICE PROVIDER E2E =====")
    print("status:", report["status"])
    print("provider:", report["provider"])
    print("test_price:", report["test_price"])
    print(
        "production_data_modified:",
        report["production_data_modified"],
    )

    for key, value in checks.items():
        print(f"  {key}: {value}")

    if not passed:
        raise SystemExit(1)
