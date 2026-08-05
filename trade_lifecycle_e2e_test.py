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
REPORT = BASE / "trade_lifecycle_e2e_report.json"


def save_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return default


def run(work: Path, module: str) -> str:
    result = subprocess.run(
        ["python3", module],
        cwd=work,
        text=True,
        capture_output=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{module} failed\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    return result.stdout


with tempfile.TemporaryDirectory(
    prefix="weather_ai_trade_lifecycle_"
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

    now = datetime.now().astimezone()
    started_at = now - timedelta(hours=1)

    save_json(
        work / "official_account_start.json",
        {
            "started_at": started_at.isoformat(
                timespec="seconds"
            ),
            "initial_cash": 500000.0,
            "scope": "ISOLATED_TRADE_E2E_ONLY",
        },
    )

    save_json(
        work / "virtual_account.json",
        {
            "cash": 500000.0,
            "equity": 500000.0,
            "position": 0,
            "entry_price": None,
            "history": [],
            "updated_at": started_at.isoformat(
                timespec="seconds"
            ),
        },
    )

    save_json(work / "trade_log.json", [])
    save_json(work / "official_trade_ledger.json", [])

    for filename in (
        "official_ledger_writer_state.json",
        "official_ledger_writer_status.json",
        "official_trade_events.jsonl",
    ):
        path = work / filename

        if path.exists():
            path.unlink()

    entry_price = 100.0
    exit_price = 103.0

    # LONG判断
    save_json(
        work / "master_decision.json",
        {
            "symbol": "1321.T",
            "decision": "LONG",
            "final_decision": "LONG",
            "signal": "LONG",
            "price": entry_price,
            "current_price": entry_price,
            "reason": "ISOLATED_E2E_LONG",
        },
    )

    save_json(
        work / "price_data.json",
        {
            "symbol": "1321.T",
            "price": entry_price,
            "close": entry_price,
            "current_price": entry_price,
        },
    )

    entry_output = run(
        work,
        "virtual_account_ai.py",
    )

    entry_account = load_json(
        work / "virtual_account.json",
        {},
    )
    entry_log = load_json(
        work / "trade_log.json",
        [],
    )

    ledger_entry_output = run(
        work,
        "official_ledger_writer_ai.py",
    )

    ledger_after_entry = load_json(
        work / "official_trade_ledger.json",
        [],
    )

    # EXIT判断
    save_json(
        work / "master_decision.json",
        {
            "symbol": "1321.T",
            "decision": "EXIT",
            "final_decision": "EXIT",
            "signal": "EXIT",
            "price": exit_price,
            "current_price": exit_price,
            "reason": "ISOLATED_E2E_EXIT",
        },
    )

    save_json(
        work / "price_data.json",
        {
            "symbol": "1321.T",
            "price": exit_price,
            "close": exit_price,
            "current_price": exit_price,
        },
    )

    exit_output = run(
        work,
        "virtual_account_ai.py",
    )

    exit_account = load_json(
        work / "virtual_account.json",
        {},
    )
    exit_log = load_json(
        work / "trade_log.json",
        [],
    )

    ledger_exit_output = run(
        work,
        "official_ledger_writer_ai.py",
    )

    performance_output = run(
        work,
        "official_performance_ai.py",
    )

    final_ledger = load_json(
        work / "official_trade_ledger.json",
        [],
    )
    performance = load_json(
        work / "official_performance.json",
        {},
    )
    writer_status = load_json(
        work / "official_ledger_writer_status.json",
        {},
    )

    closed = [
        row
        for row in final_ledger
        if isinstance(row, dict)
        and row.get("status") == "CLOSED"
    ]

    realized_pnl = (
        float(closed[0].get("realized_pnl"))
        if closed
        and closed[0].get("realized_pnl") is not None
        else None
    )

    checks = {
        "isolated_environment":
            work != BASE,
        "entry_position_opened":
            int(entry_account.get("position") or 0) == 1,
        "entry_price_saved":
            float(
                entry_account.get("entry_price") or 0
            ) == entry_price,
        "buy_logged":
            any(
                str(row.get("action")).upper() == "BUY"
                for row in entry_log
                if isinstance(row, dict)
            ),
        "official_open_trade_created":
            any(
                row.get("status") == "OPEN"
                for row in ledger_after_entry
                if isinstance(row, dict)
            ),
        "exit_position_closed":
            int(exit_account.get("position") or 0) == 0,
        "sell_logged":
            any(
                str(row.get("action")).upper() == "SELL"
                for row in exit_log
                if isinstance(row, dict)
            ),
        "official_trade_closed":
            len(closed) == 1,
        "realized_pnl_correct":
            realized_pnl is not None
            and abs(
                realized_pnl
                - (exit_price - entry_price)
            ) < 1e-9,
        "official_performance_closed_one":
            int(
                performance.get("closed_trades") or 0
            ) == 1,
        "official_performance_wins_one":
            int(performance.get("wins") or 0) == 1,
        "official_performance_losses_zero":
            int(performance.get("losses") or 0) == 0,
        "official_total_pnl_correct":
            abs(
                float(
                    performance.get(
                        "total_realized_pnl"
                    )
                    or 0
                )
                - 3.0
            ) < 1e-9,
        "legacy_data_excluded":
            performance.get(
                "legacy_data_excluded"
            ) is True,
    }

    passed = all(checks.values())

    report = {
        "generated_at":
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds"),
        "status": "PASS" if passed else "FAIL",
        "scope": "ISOLATED_TRADE_E2E_ONLY",
        "production_data_modified": False,
        "symbol": "1321.T",
        "entry_price": entry_price,
        "exit_price": exit_price,
        "expected_realized_pnl": 3.0,
        "entry_account": entry_account,
        "exit_account": exit_account,
        "trade_log": exit_log,
        "official_ledger": final_ledger,
        "official_performance": performance,
        "ledger_writer_status": writer_status,
        "checks": checks,
        "module_outputs": {
            "entry_virtual_account":
                entry_output[-2000:],
            "entry_ledger_writer":
                ledger_entry_output[-2000:],
            "exit_virtual_account":
                exit_output[-2000:],
            "exit_ledger_writer":
                ledger_exit_output[-2000:],
            "official_performance":
                performance_output[-2000:],
        },
    }

    save_json(REPORT, report)

    print("===== TRADE LIFECYCLE E2E =====")
    print("scope: ISOLATED_TRADE_E2E_ONLY")
    print("production_data_modified: False")
    print("entry_price:", entry_price)
    print("exit_price:", exit_price)
    print("closed_trades:", len(closed))
    print("realized_pnl:", realized_pnl)
    print(
        "performance_closed_trades:",
        performance.get("closed_trades"),
    )
    print(
        "performance_wins:",
        performance.get("wins"),
    )
    print(
        "performance_total_pnl:",
        performance.get("total_realized_pnl"),
    )

    print()
    print("checks:")

    for key, value in checks.items():
        print(f"  {key}: {value}")

    print()
    print("RESULT:", report["status"])
    print("REPORT:", REPORT)

    if not passed:
        raise SystemExit(1)
