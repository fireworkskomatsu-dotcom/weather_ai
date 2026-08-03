#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BASE = Path(__file__).resolve().parent
JST = ZoneInfo("Asia/Tokyo")

START_FILE = BASE / "official_account_start.json"
LEDGER_FILE = BASE / "official_trade_ledger.json"
EVENT_FILE = BASE / "official_trade_events.jsonl"
STATE_FILE = BASE / "official_ledger_writer_state.json"
STATUS_FILE = BASE / "official_ledger_writer_status.json"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
        text=True,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary_name, path)

    finally:
        temporary = Path(temporary_name)

        if temporary.exists():
            temporary.unlink()


def save_json(path: Path, value: Any) -> None:
    atomic_write(
        path,
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
    )


def append_event(value: dict[str, Any]) -> None:
    with EVENT_FILE.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                value,
                ensure_ascii=False,
                separators=(",", ":"),
            ) + "\n"
        )


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        result = float(value)

        if math.isfinite(result):
            return result

    if isinstance(value, str):
        try:
            result = float(value.replace(",", ""))

            if math.isfinite(result):
                return result
        except Exception:
            return None

    return None


def integer(value: Any) -> int:
    number = numeric(value)

    if number is None:
        return 0

    return int(number)


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None

    text = str(value).strip()

    try:
        parsed = datetime.fromisoformat(
            text.replace("Z", "+00:00")
        )
    except Exception:
        for pattern in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
        ):
            try:
                parsed = datetime.strptime(text, pattern)
                break
            except Exception:
                parsed = None

        if parsed is None:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=JST)
    else:
        parsed = parsed.astimezone(JST)

    return parsed


def event_id(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).encode("utf-8")

    return hashlib.sha256(encoded).hexdigest()[:24]


def normalize_trade_log(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [
            row
            for row in data
            if isinstance(row, dict)
        ]

    if isinstance(data, dict):
        for key in (
            "trades",
            "records",
            "history",
            "items",
            "trade_log",
        ):
            value = data.get(key)

            if isinstance(value, list):
                return [
                    row
                    for row in value
                    if isinstance(row, dict)
                ]

    return []


def action_of(row: dict[str, Any]) -> str:
    return str(
        row.get("action")
        or row.get("side")
        or row.get("type")
        or ""
    ).upper()


def time_of(row: dict[str, Any]) -> datetime | None:
    for key in (
        "time",
        "timestamp",
        "updated_at",
        "executed_at",
        "closed_at",
        "opened_at",
    ):
        parsed = parse_time(row.get(key))

        if parsed is not None:
            return parsed

    return None


now = datetime.now(JST)

start_data = load_json(START_FILE, {})
started_at = parse_time(start_data.get("started_at"))

if started_at is None:
    raise SystemExit(
        "official_account_start.jsonのstarted_atが不正です"
    )

virtual = load_json(BASE / "virtual_account.json", {})
trade_rows = normalize_trade_log(
    load_json(BASE / "trade_log.json", [])
)
weighted = load_json(BASE / "weighted_multi_agent.json", {})

ledger = load_json(LEDGER_FILE, [])

if not isinstance(ledger, list):
    ledger = []

state = load_json(STATE_FILE, {})

if not isinstance(state, dict):
    state = {}

current_position = integer(
    virtual.get("position")
    or virtual.get("qty")
    or virtual.get("quantity")
)

current_entry_price = numeric(
    virtual.get("entry_price")
)

current_price = numeric(
    virtual.get("last_price")
    or virtual.get("price")
    or virtual.get("current_price")
)

current_updated_at = (
    parse_time(virtual.get("updated_at"))
    or parse_time(virtual.get("time"))
    or now
)

previous_position = integer(
    state.get("last_position")
)

processed_ids = set(
    str(value)
    for value in state.get(
        "processed_trade_event_ids",
        [],
    )
)

events_added = 0
trades_opened = 0
trades_closed = 0
ignored_legacy = 0

# 正式開始以降のtrade_logだけを処理する。
for row in trade_rows:
    row_time = time_of(row)

    if row_time is None or row_time < started_at:
        ignored_legacy += 1
        continue

    action = action_of(row)
    price = numeric(row.get("price"))
    qty = integer(
        row.get("qty")
        or row.get("quantity")
        or 1
    )

    identity = {
        "time": row_time.isoformat(timespec="seconds"),
        "action": action,
        "price": price,
        "qty": qty,
        "reason": row.get("reason"),
        "pnl": row.get("pnl"),
    }

    source_event_id = event_id(identity)

    if source_event_id in processed_ids:
        continue

    if action in {
        "BUY",
        "LONG",
        "ENTRY_LONG",
        "OPEN_LONG",
    }:
        trade_id = event_id({
            "source_event_id": source_event_id,
            "kind": "OFFICIAL_LONG_TRADE",
        })

        already_exists = any(
            isinstance(trade, dict)
            and trade.get("trade_id") == trade_id
            for trade in ledger
        )

        if not already_exists:
            trade = {
                "trade_id": trade_id,
                "scope": "OFFICIAL_FORWARD_TEST_ONLY",
                "symbol": "1321.T",
                "side": "LONG",
                "status": "OPEN",
                "opened_at": row_time.isoformat(
                    timespec="seconds"
                ),
                "entry_price": price,
                "qty": qty,
                "entry_reason": row.get("reason"),
                "source_event_id": source_event_id,
                "decision": weighted.get("final_decision"),
                "legacy_data_excluded": True,
            }

            ledger.append(trade)
            trades_opened += 1

            append_event({
                "event_id": source_event_id,
                "event_type": "OPEN",
                "logged_at": now.isoformat(
                    timespec="seconds"
                ),
                "trade": trade,
            })

            events_added += 1

    elif action in {
        "SELL",
        "EXIT",
        "CLOSE",
        "EXIT_LONG",
        "CLOSE_LONG",
    }:
        open_trade = next(
            (
                trade
                for trade in reversed(ledger)
                if isinstance(trade, dict)
                and trade.get("status") == "OPEN"
                and trade.get("side") == "LONG"
            ),
            None,
        )

        if open_trade is not None:
            entry_price = numeric(
                open_trade.get("entry_price")
            )
            realized_pnl = numeric(
                row.get("realized_pnl")
                or row.get("pnl")
            )

            if (
                realized_pnl is None
                and entry_price is not None
                and price is not None
            ):
                realized_pnl = (
                    price - entry_price
                ) * max(qty, 1)

            open_trade["status"] = "CLOSED"
            open_trade["closed_at"] = (
                row_time.isoformat(timespec="seconds")
            )
            open_trade["exit_price"] = price
            open_trade["exit_reason"] = row.get("reason")
            open_trade["realized_pnl"] = (
                round(realized_pnl, 6)
                if realized_pnl is not None
                else None
            )
            open_trade["close_source_event_id"] = (
                source_event_id
            )

            trades_closed += 1

            append_event({
                "event_id": source_event_id,
                "event_type": "CLOSE",
                "logged_at": now.isoformat(
                    timespec="seconds"
                ),
                "trade_id": open_trade.get("trade_id"),
                "exit_price": price,
                "realized_pnl":
                    open_trade.get("realized_pnl"),
                "reason": row.get("reason"),
            })

            events_added += 1

    processed_ids.add(source_event_id)

# trade_logに記録されなかった場合の位置変化を保険として検出。
# 初回実行時は既存状態を基準値にするだけで、過去ポジションを正式取引化しない。
initialized = state.get("initialized") is True

if initialized:
    if previous_position == 0 and current_position > 0:
        synthetic_identity = {
            "type": "POSITION_TRANSITION_OPEN",
            "time": current_updated_at.isoformat(
                timespec="seconds"
            ),
            "position": current_position,
            "entry_price": current_entry_price,
        }

        synthetic_id = event_id(synthetic_identity)

        if synthetic_id not in processed_ids:
            trade_id = event_id({
                "source_event_id": synthetic_id,
                "kind": "OFFICIAL_LONG_TRADE",
            })

            ledger.append({
                "trade_id": trade_id,
                "scope": "OFFICIAL_FORWARD_TEST_ONLY",
                "symbol": "1321.T",
                "side": "LONG",
                "status": "OPEN",
                "opened_at": current_updated_at.isoformat(
                    timespec="seconds"
                ),
                "entry_price": current_entry_price,
                "qty": current_position,
                "entry_reason":
                    "VIRTUAL_POSITION_TRANSITION",
                "source_event_id": synthetic_id,
                "decision": weighted.get("final_decision"),
                "legacy_data_excluded": True,
            })

            append_event({
                "event_id": synthetic_id,
                "event_type": "OPEN",
                "logged_at": now.isoformat(
                    timespec="seconds"
                ),
                "source":
                    "virtual_account_position_transition",
            })

            processed_ids.add(synthetic_id)
            trades_opened += 1
            events_added += 1

    elif previous_position > 0 and current_position == 0:
        open_trade = next(
            (
                trade
                for trade in reversed(ledger)
                if isinstance(trade, dict)
                and trade.get("status") == "OPEN"
                and trade.get("side") == "LONG"
            ),
            None,
        )

        if open_trade is not None:
            synthetic_identity = {
                "type": "POSITION_TRANSITION_CLOSE",
                "time": current_updated_at.isoformat(
                    timespec="seconds"
                ),
                "previous_position": previous_position,
                "price": current_price,
            }

            synthetic_id = event_id(synthetic_identity)

            if synthetic_id not in processed_ids:
                entry_price = numeric(
                    open_trade.get("entry_price")
                )

                realized_pnl = None

                if (
                    entry_price is not None
                    and current_price is not None
                ):
                    realized_pnl = (
                        current_price - entry_price
                    ) * max(
                        integer(open_trade.get("qty")),
                        1,
                    )

                open_trade["status"] = "CLOSED"
                open_trade["closed_at"] = (
                    current_updated_at.isoformat(
                        timespec="seconds"
                    )
                )
                open_trade["exit_price"] = current_price
                open_trade["exit_reason"] = (
                    "VIRTUAL_POSITION_TRANSITION"
                )
                open_trade["realized_pnl"] = (
                    round(realized_pnl, 6)
                    if realized_pnl is not None
                    else None
                )
                open_trade["close_source_event_id"] = (
                    synthetic_id
                )

                append_event({
                    "event_id": synthetic_id,
                    "event_type": "CLOSE",
                    "logged_at": now.isoformat(
                        timespec="seconds"
                    ),
                    "source":
                        "virtual_account_position_transition",
                    "trade_id": open_trade.get("trade_id"),
                    "realized_pnl":
                        open_trade.get("realized_pnl"),
                })

                processed_ids.add(synthetic_id)
                trades_closed += 1
                events_added += 1

save_json(LEDGER_FILE, ledger)

state = {
    "initialized": True,
    "updated_at": now.isoformat(timespec="seconds"),
    "official_started_at":
        started_at.isoformat(timespec="seconds"),
    "last_position": current_position,
    "last_entry_price": current_entry_price,
    "last_virtual_updated_at":
        current_updated_at.isoformat(timespec="seconds"),
    "processed_trade_event_ids":
        sorted(processed_ids),
}

save_json(STATE_FILE, state)

open_count = sum(
    1
    for trade in ledger
    if isinstance(trade, dict)
    and trade.get("status") == "OPEN"
)

closed_count = sum(
    1
    for trade in ledger
    if isinstance(trade, dict)
    and trade.get("status") == "CLOSED"
)

status = {
    "status": "OK",
    "updated_at": now.isoformat(timespec="seconds"),
    "official_started_at":
        started_at.isoformat(timespec="seconds"),
    "initialized": True,
    "events_added": events_added,
    "trades_opened_this_run": trades_opened,
    "trades_closed_this_run": trades_closed,
    "open_trades": open_count,
    "closed_trades": closed_count,
    "ledger_records": len(ledger),
    "ignored_legacy_records": ignored_legacy,
    "current_virtual_position": current_position,
    "legacy_data_excluded": True,
}

save_json(STATUS_FILE, status)

print("===== OFFICIAL LEDGER WRITER =====")
print("status: OK")
print("official_started_at:", status["official_started_at"])
print("events_added:", events_added)
print("trades_opened_this_run:", trades_opened)
print("trades_closed_this_run:", trades_closed)
print("open_trades:", open_count)
print("closed_trades:", closed_count)
print("ledger_records:", len(ledger))
print("ignored_legacy_records:", ignored_legacy)
print("current_virtual_position:", current_position)
