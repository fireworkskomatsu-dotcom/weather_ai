#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


BASE = Path(__file__).resolve().parent
JST = ZoneInfo("Asia/Tokyo")

SOURCE = BASE / "strategy_shadow_pnl.json"
OUTPUT = BASE / "strategy_expectancy.json"

MIN_ACTIVE_SAMPLES = 5


def load_json(path: Path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


source = load_json(SOURCE, {})
results = source.get("strategy_results", {})

if not isinstance(results, dict):
    results = {}

expectancy = {}

for strategy_id, item in results.items():
    if not isinstance(item, dict):
        continue

    samples = int(item.get("samples") or 0)
    average_return = float(
        item.get("average_return") or 0.0
    )

    # 少数標本を中立値へ縮小する。
    reliability = min(
        1.0,
        samples / 30.0,
    )

    shrunk_expectancy = (
        average_return * reliability
    )

    expectancy[strategy_id] = {
        "strategy_id": strategy_id,
        "name": item.get("name"),
        "family": item.get("family"),
        "samples": samples,
        "win_rate": item.get("win_rate"),
        "profit_factor": item.get(
            "profit_factor"
        ),
        "raw_expectancy": round(
            average_return,
            8,
        ),
        "raw_expectancy_pct": round(
            average_return * 100,
            4,
        ),
        "reliability": round(
            reliability,
            4,
        ),
        "expectancy": round(
            shrunk_expectancy,
            8,
        ),
        "expectancy_pct": round(
            shrunk_expectancy * 100,
            4,
        ),
        "eligible_for_weight_change":
            samples >= MIN_ACTIVE_SAMPLES,
    }


out = {
    "time": datetime.now(JST).isoformat(
        timespec="seconds"
    ),
    "status": "OK",
    "source": "strategy_shadow_pnl.json",
    "minimum_samples": MIN_ACTIVE_SAMPLES,
    "evaluated_records": source.get(
        "evaluated_decision_records",
        0,
    ),
    "strategy_expectancy": expectancy,
    "count": len(expectancy),
}

OUTPUT.write_text(
    json.dumps(
        out,
        ensure_ascii=False,
        indent=2,
    ) + "\n",
    encoding="utf-8",
)

print("===== STRATEGY EXPECTANCY =====")
print("status: OK")
print("count:", len(expectancy))
print(
    "eligible:",
    sum(
        1
        for item in expectancy.values()
        if item["eligible_for_weight_change"]
    ),
)
