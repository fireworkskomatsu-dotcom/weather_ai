#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parent
ACCOUNT_FILE = BASE / "virtual_account.json"
ACCOUNT_START_FILE = BASE / "official_account_start.json"
STATUS_FILE = BASE / "virtual_account_status.json"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    serialized = json.dumps(
        value,
        ensure_ascii=False,
        indent=2,
    ) + "\n"

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
        text=True,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary_name, path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


def build_public_status(
    account: dict[str, Any],
    account_start: dict[str, Any],
) -> dict[str, Any]:
    initial_cash = number(account_start.get("initial_cash"), 500000.0)
    cash = number(account.get("cash"), initial_cash)
    equity = number(account.get("equity"), cash)
    position = int(number(account.get("position"), 0.0))
    entry_price = account.get("entry_price")
    last_price = account.get("last_price")

    entry_price = (
        number(entry_price)
        if entry_price is not None
        else None
    )
    last_price = (
        number(last_price)
        if last_price is not None
        else None
    )

    unrealized_pnl = 0.0
    if position and entry_price is not None and last_price is not None:
        unrealized_pnl = (last_price - entry_price) * position

    return {
        "schema_version": 1,
        "account_type": "VIRTUAL",
        "real_money": False,
        "currency": "JPY",
        "initial_cash": round(initial_cash, 2),
        "cash": round(cash, 2),
        "equity": round(equity, 2),
        "position": position,
        "entry_price": entry_price,
        "last_price": last_price,
        "price_available": last_price is not None,
        "data_status": (
            "CURRENT_WITH_PRICE"
            if last_price is not None
            else "STALE_NO_PRICE"
        ),
        "unrealized_virtual_pnl": round(unrealized_pnl, 2),
        "total_virtual_pnl": round(equity - initial_cash, 2),
        "last_signal": str(account.get("last_signal") or "UNKNOWN"),
        "last_action": str(account.get("last_action") or "UNKNOWN"),
        "price_verification": str(account.get("price_verification") or "UNKNOWN"),
        "decision_verification": str(account.get("decision_verification") or "UNKNOWN"),
        "updated_at": account.get("updated_at"),
        "source": "virtual_account.json",
        "history_included": False,
        "note": "公開用スナップショット。取引履歴は含みません。",
    }


def publish_virtual_account_status() -> dict[str, Any]:
    account = load_json(ACCOUNT_FILE, {})
    if not isinstance(account, dict) or not account:
        raise RuntimeError("virtual_account.json がありません")

    account_start = load_json(ACCOUNT_START_FILE, {})
    if not isinstance(account_start, dict):
        account_start = {}

    status = build_public_status(account, account_start)
    atomic_write(STATUS_FILE, status)
    return status


def main() -> None:
    status = publish_virtual_account_status()
    print(json.dumps({
        "status": "OK",
        "account_type": status["account_type"],
        "real_money": status["real_money"],
        "cash": status["cash"],
        "equity": status["equity"],
        "position": status["position"],
        "total_virtual_pnl": status["total_virtual_pnl"],
        "history_included": status["history_included"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
