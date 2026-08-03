#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import os
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BASE = Path(__file__).resolve().parent
JST = ZoneInfo("Asia/Tokyo")

SOURCE = BASE / "official_decision_log.jsonl"
OUTPUT = BASE / "strategy_shadow_pnl.json"

MIN_MOVE = 0.002


def atomic_json(path: Path, value: Any) -> None:
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
        text=True,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                value,
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary_name, path)

    finally:
        temporary = Path(temporary_name)

        if temporary.exists():
            temporary.unlink()


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        result = float(value)

        if math.isfinite(result):
            return result

    return None


def strategy_return(
    decision: str,
    market_return: float,
) -> float:
    decision = decision.upper()

    if decision == "LONG":
        return market_return

    if decision == "SHORT":
        return -market_return

    if decision == "SKIP":
        return 0.0

    return 0.0


records: list[dict[str, Any]] = []

if SOURCE.exists():
    for line in SOURCE.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            row = json.loads(line)

            if isinstance(row, dict):
                records.append(row)
        except Exception:
            continue


stats: dict[str, dict[str, Any]] = defaultdict(
    lambda: {
        "strategy_id": None,
        "name": None,
        "family": None,
        "samples": 0,
        "wins": 0,
        "losses": 0,
        "flats": 0,
        "total_return": 0.0,
        "returns": [],
        "correct": 0,
        "incorrect": 0,
    }
)

evaluated_records = 0

for row in records:
    outcome = row.get("outcome")

    if not isinstance(outcome, dict):
        continue

    market_return = numeric(outcome.get("market_return"))

    if market_return is None:
        continue

    evaluated_records += 1

    active = (
        row.get("strategy_5x10", {})
        .get("active_strategies", [])
    )

    if not isinstance(active, list):
        continue

    for strategy in active:
        if not isinstance(strategy, dict):
            continue

        strategy_id = str(
            strategy.get("id")
            or strategy.get("name")
            or "UNKNOWN"
        )

        decision = str(
            strategy.get("decision")
            or "ABSTAIN"
        ).upper()

        if decision == "ABSTAIN":
            continue

        realized = strategy_return(
            decision,
            market_return,
        )

        item = stats[strategy_id]
        item["strategy_id"] = strategy_id
        item["name"] = strategy.get("name")
        item["family"] = strategy.get("family")
        item["samples"] += 1
        item["total_return"] += realized
        item["returns"].append(realized)

        if abs(realized) < MIN_MOVE:
            item["flats"] += 1
        elif realized > 0:
            item["wins"] += 1
            item["correct"] += 1
        else:
            item["losses"] += 1
            item["incorrect"] += 1


results = {}

for strategy_id, item in stats.items():
    samples = int(item["samples"])
    decisive = item["wins"] + item["losses"]

    returns = item.pop("returns")

    average_return = (
        sum(returns) / len(returns)
        if returns
        else 0.0
    )

    win_rate = (
        item["wins"] / decisive * 100
        if decisive
        else None
    )

    gross_profit = sum(
        value
        for value in returns
        if value > 0
    )

    gross_loss = abs(
        sum(
            value
            for value in returns
            if value < 0
        )
    )

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else (
            None
            if gross_profit == 0
            else 999.0
        )
    )

    results[strategy_id] = {
        **item,
        "samples": samples,
        "total_return": round(
            item["total_return"],
            8,
        ),
        "total_return_pct": round(
            item["total_return"] * 100,
            4,
        ),
        "average_return": round(
            average_return,
            8,
        ),
        "average_return_pct": round(
            average_return * 100,
            4,
        ),
        "win_rate": (
            round(win_rate, 2)
            if win_rate is not None
            else None
        ),
        "profit_factor": (
            round(profit_factor, 4)
            if profit_factor is not None
            else None
        ),
    }


out = {
    "updated_at": datetime.now(JST).isoformat(
        timespec="seconds"
    ),
    "status": "OK",
    "source": "official_decision_log.jsonl",
    "scope": "OFFICIAL_FORWARD_TEST_ONLY",
    "evaluated_decision_records": evaluated_records,
    "strategy_count": len(results),
    "strategy_results": results,
    "legacy_data_excluded": True,
}

atomic_json(OUTPUT, out)

print("===== STRATEGY SHADOW PNL =====")
print("status: OK")
print("evaluated_records:", evaluated_records)
print("strategy_count:", len(results))
