#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parent
NOW = datetime.now().astimezone()


def save_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


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


with tempfile.TemporaryDirectory(prefix="weather_ai_price_guard_") as temporary:
    work = Path(temporary) / "weather_ai"
    work.mkdir()

    for name in ("virtual_account_ai.py", "virtual_account_status_ai.py"):
        shutil.copy2(BASE / name, work / name)

    save_json(work / "price_provider_config.json", {
        "provider": "DISABLED",
        "mode": "OFFICIAL",
        "symbol": "1321.T",
    })
    save_json(work / "price_provider_status.json", {
        "status": "BLOCKED",
        "provider": "DISABLED",
        "mode": "OFFICIAL",
        "price_written": False,
    })
    save_json(work / "master_decision.json", {
        "symbol": "1321.T",
        "final_decision": "LONG",
        "price": 99999.0,
        "reason": "STALE_UNVERIFIED_PRICE_MUST_NOT_TRADE",
        "updated_at": (NOW - timedelta(days=10)).isoformat(),
    })
    save_json(work / "price_data.json", {
        "symbol": "1321.T",
        "price": 99999.0,
    })
    save_json(work / "virtual_account.json", {
        "cash": 500000.0,
        "equity": 500000.0,
        "position": 0,
        "entry_price": None,
        "history": [],
    })
    save_json(work / "trade_log.json", [])

    result = subprocess.run(
        ["python3", "virtual_account_ai.py"],
        cwd=work,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + "\n" + result.stderr)

    account = load_json(work / "virtual_account.json", {})
    trade_log = load_json(work / "trade_log.json", [])
    public_status = load_json(work / "virtual_account_status.json", {})

    blocked_account = dict(account)
    blocked_trade_log = list(trade_log)
    blocked_public_status = dict(public_status)

    # 公式適格時も、判断ファイル内の価格ではなく
    # canonical_price.json の検証済み価格だけを使用する。
    save_json(work / "price_provider_config.json", {
        "provider": "VERIFIED_OFFICIAL_TEST_DOUBLE",
        "mode": "OFFICIAL",
        "symbol": "1321.T",
    })
    save_json(work / "price_provider_status.json", {
        "status": "OK",
        "provider": "VERIFIED_OFFICIAL_TEST_DOUBLE",
        "mode": "OFFICIAL",
        "price_written": True,
    })
    save_json(work / "canonical_price.json", {
        "symbol": "1321.T",
        "price": 100.0,
        "official_eligible": True,
        "fetched_at": NOW.isoformat(),
    })
    save_json(work / "master_decision.json", {
        "symbol": "1321.T",
        "final_decision": "LONG",
        "price": 99999.0,
        "updated_at": NOW.isoformat(),
    })
    save_json(work / "virtual_account.json", {
        "cash": 500000.0,
        "equity": 500000.0,
        "position": 0,
        "entry_price": None,
        "history": [],
    })
    save_json(work / "trade_log.json", [])

    official_result = subprocess.run(
        ["python3", "virtual_account_ai.py"],
        cwd=work,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if official_result.returncode != 0:
        raise RuntimeError(official_result.stdout + "\n" + official_result.stderr)

    official_account = load_json(work / "virtual_account.json", {})
    official_trade_log = load_json(work / "trade_log.json", [])

    # 公式価格が新しくても、判断時刻が古ければ取引しない。
    save_json(work / "master_decision.json", {
        "symbol": "1321.T",
        "final_decision": "LONG",
        "price": 99999.0,
        "updated_at": (NOW - timedelta(days=2)).isoformat(),
    })
    save_json(work / "virtual_account.json", {
        "cash": 500000.0,
        "equity": 500000.0,
        "position": 0,
        "entry_price": None,
        "history": [],
    })
    save_json(work / "trade_log.json", [])
    stale_decision_result = subprocess.run(
        ["python3", "virtual_account_ai.py"],
        cwd=work,
        text=True,
        capture_output=True,
        timeout=60,
    )
    if stale_decision_result.returncode != 0:
        raise RuntimeError(
            stale_decision_result.stdout + "\n" + stale_decision_result.stderr
        )
    stale_decision_account = load_json(work / "virtual_account.json", {})
    stale_decision_trades = load_json(work / "trade_log.json", [])

    checks = {
        "isolated_filesystem": work != BASE,
        "stale_long_blocked": blocked_account.get("position") == 0,
        "cash_unchanged": blocked_account.get("cash") == 500000.0,
        "equity_unchanged": blocked_account.get("equity") == 500000.0,
        "unverified_price_discarded": blocked_account.get("last_price") is None,
        "block_reason_recorded": blocked_account.get("last_action") == "BLOCKED_UNVERIFIED_OFFICIAL_PRICE",
        "verification_blocked": blocked_account.get("price_verification") == "BLOCKED",
        "trade_log_unchanged": blocked_trade_log == [],
        "public_status_blocked": blocked_public_status.get("price_verification") == "BLOCKED",
        "real_money_false": blocked_public_status.get("real_money") is False,
        "official_trade_uses_canonical_price": official_account.get("entry_price") == 100.0,
        "stale_decision_price_ignored": official_account.get("entry_price") != 99999.0,
        "official_trade_logged_at_canonical_price": bool(official_trade_log) and official_trade_log[0].get("price") == 100.0,
        "official_verification_recorded": official_account.get("price_verification") == "OFFICIAL_ELIGIBLE",
        "fresh_decision_recorded": official_account.get("decision_verification") == "FRESH_OFFICIAL",
        "stale_official_decision_blocked": stale_decision_account.get("position") == 0,
        "stale_decision_reason_recorded": stale_decision_account.get("decision_verification") == "BLOCKED_STALE_OR_MISSING_TIME",
        "stale_decision_trade_log_empty": stale_decision_trades == [],
        "production_files_unchanged": production_before == {
            name: digest(BASE / name) for name in production_before
        },
    }

    print("===== VIRTUAL ACCOUNT PRICE GUARD E2E =====")
    for key, passed in checks.items():
        print(f"  {key}: {passed}")
    print("RESULT:", "PASS" if all(checks.values()) else "FAIL")

    if not all(checks.values()):
        raise SystemExit(1)
