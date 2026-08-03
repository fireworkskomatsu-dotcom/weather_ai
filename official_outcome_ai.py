#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import os
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BASE = Path(__file__).resolve().parent
JST = ZoneInfo("Asia/Tokyo")

LOG_FILE = BASE / "official_decision_log.jsonl"
SUMMARY_FILE = BASE / "official_outcome_summary.json"
STATUS_FILE = BASE / "official_outcome_status.json"

# 翌観測価格で0.20%以上動けば方向性ありとして採点。
MIN_MOVE_PCT = 0.002


def load_json(name: str, default: Any) -> Any:
    path = BASE / name

    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    rows: list[dict[str, Any]] = []

    for line in path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            value = json.loads(line)

            if isinstance(value, dict):
                rows.append(value)
        except Exception:
            continue

    return rows


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


def atomic_json(path: Path, value: Any) -> None:
    atomic_write(
        path,
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
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


def current_price() -> float | None:
    candidates = [
        ("live_price.json", ("price", "last_price", "current_price")),
        ("web/dashboard.json", ("price", "last_price", "current_price")),
        ("dashboard.json", ("price", "last_price", "current_price")),
        ("virtual_account.json", ("last_price", "price")),
    ]

    for filename, keys in candidates:
        data = load_json(filename, {})

        if not isinstance(data, dict):
            continue

        for key in keys:
            value = numeric(data.get(key))

            if value is not None and value > 0:
                return value

        market = data.get("market")

        if isinstance(market, dict):
            for key in keys:
                value = numeric(market.get(key))

                if value is not None and value > 0:
                    return value

    return None


def classify(
    decision: str,
    nearest_direction: str,
    market_return: float,
) -> tuple[str, bool | None]:
    decision = decision.upper()
    nearest_direction = nearest_direction.upper()

    if abs(market_return) < MIN_MOVE_PCT:
        if decision == "SKIP":
            return "SKIP_FLAT", True

        return f"{decision}_FLAT", None

    if decision == "LONG":
        correct = market_return > 0
        return (
            "LONG_WIN" if correct else "LONG_LOSS",
            correct,
        )

    if decision == "SHORT":
        correct = market_return < 0
        return (
            "SHORT_WIN" if correct else "SHORT_LOSS",
            correct,
        )

    if decision == "SKIP":
        if nearest_direction == "LONG":
            if market_return > 0:
                return "SKIP_MISSED_LONG", False

            return "SKIP_PROTECTED_LOSS", True

        if nearest_direction == "SHORT":
            if market_return < 0:
                return "SKIP_MISSED_SHORT", False

            return "SKIP_PROTECTED_LOSS", True

        return "SKIP_DIRECTION_UNKNOWN", None

    return "UNKNOWN_DECISION", None


now = datetime.now(JST)
price_now = current_price()
records = read_jsonl(LOG_FILE)

evaluated_now = 0
waiting = 0
changed = False

if price_now is not None:
    for row in records:
        if not isinstance(row, dict):
            continue

        if row.get("outcome") is not None:
            continue

        entry_price = numeric(
            row.get("market", {}).get("price")
        )

        if entry_price is None or entry_price <= 0:
            waiting += 1
            continue

        # 同じ価格では評価しない。
        if abs(price_now - entry_price) < 1e-9:
            waiting += 1
            continue

        decision_data = row.get("decision") or {}
        vote_data = row.get("vote_analysis") or {}

        decision = str(
            decision_data.get("final") or "UNKNOWN"
        ).upper()

        nearest_direction = str(
            vote_data.get("nearest_direction") or "UNKNOWN"
        ).upper()

        market_return = (
            price_now - entry_price
        ) / entry_price

        if nearest_direction == "SHORT":
            shadow_direction_return = -market_return
        else:
            shadow_direction_return = market_return

        classification, correct = classify(
            decision,
            nearest_direction,
            market_return,
        )

        row["outcome"] = {
            "evaluation_method":
                "NEXT_DISTINCT_OFFICIAL_PRICE",
            "evaluated_at":
                now.isoformat(timespec="seconds"),
            "entry_price": round(entry_price, 4),
            "next_price": round(price_now, 4),
            "market_return":
                round(market_return, 8),
            "market_return_pct":
                round(market_return * 100, 4),
            "nearest_direction": nearest_direction,
            "shadow_direction_return":
                round(shadow_direction_return, 8),
            "shadow_direction_return_pct":
                round(
                    shadow_direction_return * 100,
                    4,
                ),
            "classification": classification,
            "correct": correct,
            "minimum_move_pct":
                MIN_MOVE_PCT * 100,
        }

        evaluated_now += 1
        changed = True

if changed:
    atomic_write(
        LOG_FILE,
        "".join(
            json.dumps(
                row,
                ensure_ascii=False,
                separators=(",", ":"),
            ) + "\n"
            for row in records
        ),
    )

evaluated = [
    row
    for row in records
    if isinstance(row.get("outcome"), dict)
]

classifications = Counter(
    str(row["outcome"].get("classification"))
    for row in evaluated
)

correct_count = sum(
    1
    for row in evaluated
    if row["outcome"].get("correct") is True
)

incorrect_count = sum(
    1
    for row in evaluated
    if row["outcome"].get("correct") is False
)

scorable_count = correct_count + incorrect_count

accuracy = (
    round(correct_count / scorable_count * 100, 2)
    if scorable_count
    else None
)

skip_evaluated = [
    row
    for row in evaluated
    if str(
        row.get("decision", {}).get("final")
    ).upper() == "SKIP"
]

skip_protected = sum(
    1
    for row in skip_evaluated
    if row["outcome"].get("classification")
    == "SKIP_PROTECTED_LOSS"
)

skip_missed = sum(
    1
    for row in skip_evaluated
    if str(
        row["outcome"].get("classification")
    ).startswith("SKIP_MISSED")
)

skip_flat = sum(
    1
    for row in skip_evaluated
    if row["outcome"].get("classification")
    == "SKIP_FLAT"
)

skip_effectiveness = (
    round(
        (skip_protected + skip_flat)
        / len(skip_evaluated)
        * 100,
        2,
    )
    if skip_evaluated
    else None
)

missed_returns = [
    abs(
        numeric(
            row["outcome"].get(
                "shadow_direction_return_pct"
            )
        )
        or 0.0
    )
    for row in skip_evaluated
    if str(
        row["outcome"].get("classification")
    ).startswith("SKIP_MISSED")
]

average_missed_move_pct = (
    round(sum(missed_returns) / len(missed_returns), 4)
    if missed_returns
    else None
)

summary = {
    "updated_at": now.isoformat(timespec="seconds"),
    "status": "OK",
    "evaluation_method":
        "NEXT_DISTINCT_OFFICIAL_PRICE",
    "minimum_move_pct":
        MIN_MOVE_PCT * 100,
    "current_price": price_now,
    "total_records": len(records),
    "evaluated_records": len(evaluated),
    "waiting_records":
        len(records) - len(evaluated),
    "evaluated_this_run": evaluated_now,
    "scorable_records": scorable_count,
    "correct": correct_count,
    "incorrect": incorrect_count,
    "accuracy": accuracy,
    "classifications":
        dict(classifications),
    "skip_analysis": {
        "evaluated_skip_records":
            len(skip_evaluated),
        "protected_loss": skip_protected,
        "missed_opportunity": skip_missed,
        "flat": skip_flat,
        "effectiveness":
            skip_effectiveness,
        "average_missed_move_pct":
            average_missed_move_pct,
    },
    "legacy_data_excluded": True,
}

atomic_json(SUMMARY_FILE, summary)

status = {
    "status": "OK",
    "updated_at": now.isoformat(timespec="seconds"),
    "current_price": price_now,
    "evaluated_this_run": evaluated_now,
    "evaluated_records": len(evaluated),
    "waiting_records":
        len(records) - len(evaluated),
    "latest_classification": (
        evaluated[-1]["outcome"].get("classification")
        if evaluated
        else None
    ),
    "accuracy": accuracy,
    "skip_effectiveness":
        skip_effectiveness,
}

atomic_json(STATUS_FILE, status)

print("===== OFFICIAL OUTCOME EVALUATOR =====")
print("status: OK")
print("current_price:", price_now)
print("total_records:", len(records))
print("evaluated_this_run:", evaluated_now)
print("evaluated_records:", len(evaluated))
print(
    "waiting_records:",
    len(records) - len(evaluated),
)
print("accuracy:", accuracy)
print(
    "classifications:",
    json.dumps(
        dict(classifications),
        ensure_ascii=False,
    ),
)
print(
    "skip_effectiveness:",
    skip_effectiveness,
)
print(
    "average_missed_move_pct:",
    average_missed_move_pct,
)
