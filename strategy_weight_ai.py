#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


BASE = Path(__file__).resolve().parent
JST = ZoneInfo("Asia/Tokyo")

SOURCE = BASE / "strategy_expectancy.json"
OUTPUT = BASE / "strategy_weight.json"

BASE_WEIGHT = 1.0
MIN_WEIGHT = 0.75
MAX_WEIGHT = 1.25


def load_json(path: Path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


source = load_json(SOURCE, {})
items = source.get("strategy_expectancy", {})

if not isinstance(items, dict):
    items = {}

weights = {}
eligible_count = 0

for strategy_id, item in items.items():
    if not isinstance(item, dict):
        continue

    eligible = bool(
        item.get("eligible_for_weight_change")
    )

    expectancy = float(
        item.get("expectancy") or 0.0
    )

    if not eligible:
        weight = BASE_WEIGHT
        reason = "INSUFFICIENT_OFFICIAL_SAMPLES"
    else:
        eligible_count += 1

        # 期待値±1%で重みを最大±25%変える。
        adjustment = max(
            -0.25,
            min(
                0.25,
                expectancy / 0.01 * 0.25,
            ),
        )

        weight = BASE_WEIGHT + adjustment
        weight = max(
            MIN_WEIGHT,
            min(MAX_WEIGHT, weight),
        )
        reason = "OFFICIAL_EXPECTANCY_APPLIED"

    weights[strategy_id] = {
        "weight": round(weight, 6),
        "samples": item.get("samples", 0),
        "expectancy": item.get(
            "expectancy",
            0.0,
        ),
        "expectancy_pct": item.get(
            "expectancy_pct",
            0.0,
        ),
        "reason": reason,
    }


out = {
    "updated_at": datetime.now(JST).isoformat(
        timespec="seconds"
    ),
    "status": "OK",
    "source": "strategy_expectancy.json",
    "base_weight": BASE_WEIGHT,
    "minimum_weight": MIN_WEIGHT,
    "maximum_weight": MAX_WEIGHT,
    "eligible_strategy_count": eligible_count,
    "weights": weights,
}

OUTPUT.write_text(
    json.dumps(
        out,
        ensure_ascii=False,
        indent=2,
    ) + "\n",
    encoding="utf-8",
)

print("===== STRATEGY WEIGHT =====")
print("status: OK")
print("weight_count:", len(weights))
print("eligible_count:", eligible_count)
