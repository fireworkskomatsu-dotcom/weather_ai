#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parent


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


production_before = {
    name: digest(BASE / name)
    for name in (
        "virtual_account.json",
        "trade_log.json",
        "virtual_account_status.json",
        "official_trade_ledger.json",
        "official_performance.json",
    )
}


with tempfile.TemporaryDirectory(prefix="weather_ai_virtual_status_") as temporary:
    work = Path(temporary) / "weather_ai"
    work.mkdir()

    for name in (
        "virtual_account_ai.py",
        "virtual_account_status_ai.py",
    ):
        shutil.copy2(BASE / name, work / name)

    save_json(work / "official_account_start.json", {
        "initial_cash": 500000.0,
        "scope": "ISOLATED_VIRTUAL_ACCOUNT_STATUS_E2E",
    })
    save_json(work / "virtual_account.json", {
        "cash": 500000.0,
        "equity": 500000.0,
        "position": 0,
        "entry_price": None,
        "history": [{"private_test_record": True}],
    })
    save_json(work / "trade_log.json", [])

    def run(signal: str, price: float) -> dict[str, Any]:
        save_json(work / "master_decision.json", {
            "symbol": "1321.T",
            "final_decision": signal,
            "price": price,
        })
        result = subprocess.run(
            ["python3", "virtual_account_ai.py"],
            cwd=work,
            text=True,
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stdout + "\n" + result.stderr)
        return load_json(work / "virtual_account_status.json", {})

    opened = run("LONG", 100.0)
    closed = run("EXIT", 103.0)

    allowed_keys = {
        "schema_version", "account_type", "real_money", "currency",
        "initial_cash", "cash", "equity", "position", "entry_price",
        "last_price", "price_available", "data_status",
        "unrealized_virtual_pnl", "total_virtual_pnl",
        "last_signal", "last_action", "updated_at", "source",
        "history_included", "note",
    }

    checks = {
        "isolated_environment": work != BASE,
        "virtual_account_explicit": closed.get("account_type") == "VIRTUAL",
        "real_money_false": closed.get("real_money") is False,
        "history_not_included": "history" not in closed and closed.get("history_included") is False,
        "only_allowed_public_keys": set(closed) == allowed_keys,
        "open_position_recorded": opened.get("position") == 1,
        "open_entry_price_recorded": opened.get("entry_price") == 100.0,
        "closed_position_recorded": closed.get("position") == 0,
        "virtual_profit_correct": closed.get("total_virtual_pnl") == 3.0,
        "price_availability_recorded": closed.get("price_available") is True,
        "data_status_recorded": closed.get("data_status") == "CURRENT_WITH_PRICE",
        "production_files_unchanged": production_before == {
            name: digest(BASE / name) for name in production_before
        },
    }

    print("===== VIRTUAL ACCOUNT PUBLIC STATUS E2E =====")
    for key, passed in checks.items():
        print(f"  {key}: {passed}")
    print("RESULT:", "PASS" if all(checks.values()) else "FAIL")

    if not all(checks.values()):
        raise SystemExit(1)
