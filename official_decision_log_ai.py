#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BASE = Path(__file__).resolve().parent
JST = ZoneInfo("Asia/Tokyo")

LOG_FILE = BASE / "official_decision_log.jsonl"
STATE_FILE = BASE / "official_decision_log_state.json"
DAILY_FILE = BASE / "official_daily_summary.json"
STATUS_FILE = BASE / "official_logging_status.json"

START_FILE = BASE / "official_account_start.json"


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

    records: list[dict[str, Any]] = []

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
                records.append(value)
        except Exception:
            continue

    return records


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")

    temporary.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    temporary.replace(path)


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        result = float(value)

        if math.isfinite(result):
            return result

    return None


def first_value(
    sources: list[dict[str, Any]],
    keys: tuple[str, ...],
) -> Any:
    for source in sources:
        if not isinstance(source, dict):
            continue

        for key in keys:
            value = source.get(key)

            if value not in (None, ""):
                return value

    return None


now = datetime.now(JST)

start = load_json("official_account_start.json", {})

started_at = (
    start.get("started_at")
    or now.isoformat(timespec="seconds")
)

weighted = load_json("weighted_multi_agent.json", {})
skip = load_json("skip_diagnostics.json", {})
strategy = load_json("strategy_5x10.json", {})
filter_data = load_json("filter.json", {})
winrate_filter = load_json("winrate_filter.json", {})
news = load_json("news.json", {})
temperature = load_json("market_temperature.json", {})
volatility = load_json("volatility.json", {})
regime = load_json("regime.json", {})
confidence_data = load_json("confidence.json", {})
virtual_account = load_json("virtual_account.json", {})
official_performance = load_json("official_performance.json", {})
dashboard = load_json("web/dashboard.json", {})
price_data = load_json("live_price.json", {})
weather_data = load_json("weather.json", {})

final_decision = str(
    first_value(
        [weighted, skip, dashboard, filter_data],
        (
            "final_decision",
            "decision",
            "signal",
        ),
    )
    or "UNKNOWN"
).upper()

votes_raw = weighted.get("weighted_votes") or {}

votes: dict[str, float] = {}

for key in ("LONG", "SHORT", "SKIP"):
    value = numeric(votes_raw.get(key))
    votes[key] = value if value is not None else 0.0

vote_ranking = sorted(
    votes.items(),
    key=lambda row: row[1],
    reverse=True,
)

winner = vote_ranking[0][0] if vote_ranking else "UNKNOWN"
winner_vote = vote_ranking[0][1] if vote_ranking else 0.0
runner_up = (
    vote_ranking[1][0]
    if len(vote_ranking) >= 2
    else None
)
runner_up_vote = (
    vote_ranking[1][1]
    if len(vote_ranking) >= 2
    else 0.0
)

margin = round(winner_vote - runner_up_vote, 6)

directional_best = max(
    votes.get("LONG", 0.0),
    votes.get("SHORT", 0.0),
)

skip_advantage = round(
    votes.get("SKIP", 0.0) - directional_best,
    6,
)

nearest_direction = (
    "LONG"
    if votes.get("LONG", 0.0) >= votes.get("SHORT", 0.0)
    else "SHORT"
)

strategy_rows = strategy.get("strategies") or []

strategy_counts: Counter[str] = Counter()
strategy_weighted_votes: Counter[str] = Counter()
active_strategies: list[dict[str, Any]] = []

for row in strategy_rows:
    if not isinstance(row, dict):
        continue

    decision = str(
        row.get("decision") or "UNKNOWN"
    ).upper()

    weight = numeric(row.get("weight")) or 0.0

    strategy_counts[decision] += 1
    strategy_weighted_votes[decision] += weight

    if decision != "ABSTAIN":
        active_strategies.append(
            {
                "id": row.get("id"),
                "family": row.get("family"),
                "name": row.get("name"),
                "decision": decision,
                "score": row.get("score"),
                "weight": weight,
                "reasons": row.get("reasons") or [],
            }
        )

confidence = first_value(
    [confidence_data, dashboard.get("confidence", {}), filter_data],
    ("confidence", "score"),
)

price = first_value(
    [price_data, dashboard, weather_data],
    ("price", "last_price", "current_price"),
)

regime_value = first_value(
    [regime, filter_data, dashboard],
    ("regime", "market_regime", "state"),
)

temperature_value = first_value(
    [temperature, dashboard],
    ("temperature", "market_temperature", "status"),
)

volatility_value = first_value(
    [volatility, filter_data, dashboard],
    ("vol_mode", "volatility", "status", "level"),
)

news_level = first_value(
    [news, dashboard.get("news", {})],
    ("news_level", "level"),
)

news_score = first_value(
    [news, dashboard.get("news", {})],
    ("news_score", "score"),
)

source_time = first_value(
    [weighted, strategy, filter_data, dashboard],
    (
        "source_time",
        "time",
        "updated_at",
        "generated_at",
    ),
)

# 同一実行を重複保存しない識別子。
identity_payload = {
    "source_time": source_time,
    "decision": final_decision,
    "votes": votes,
    "price": price,
    "strategy_updated_at": strategy.get("time")
        or strategy.get("updated_at"),
}

run_id = hashlib.sha256(
    json.dumps(
        identity_payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).encode("utf-8")
).hexdigest()[:20]

existing = read_jsonl(LOG_FILE)
existing_ids = {
    str(row.get("run_id"))
    for row in existing
    if row.get("run_id")
}

record = {
    "schema_version": 1,
    "run_id": run_id,
    "logged_at": now.isoformat(timespec="seconds"),
    "official_started_at": started_at,
    "scope": "OFFICIAL_FORWARD_TEST_ONLY",
    "decision": {
        "final": final_decision,
        "diagnosis": skip.get("diagnosis"),
        "primary_reason": skip.get("primary_reason"),
        "weighted_reasons": weighted.get("reasons") or [],
        "filter_reason": (
            filter_data.get("reason")
            or winrate_filter.get("reason")
            or dashboard.get("filter", {}).get("reason")
        ),
        "filter_blocked": (
            filter_data.get("blocked")
            if "blocked" in filter_data
            else winrate_filter.get("blocked")
        ),
    },
    "vote_analysis": {
        "weighted_votes": {
            key: round(value, 6)
            for key, value in votes.items()
        },
        "winner": winner,
        "winner_vote": round(winner_vote, 6),
        "runner_up": runner_up,
        "runner_up_vote": round(runner_up_vote, 6),
        "margin": margin,
        "nearest_direction": nearest_direction,
        "skip_advantage_over_best_direction":
            skip_advantage,
    },
    "strategy_5x10": {
        "strategy_count": len(strategy_rows),
        "decision_counts": dict(strategy_counts),
        "weighted_votes": {
            key: round(value, 6)
            for key, value in strategy_weighted_votes.items()
        },
        "active_count": len(active_strategies),
        "active_strategies": active_strategies,
    },
    "market": {
        "price": price,
        "regime": regime_value,
        "temperature": temperature_value,
        "volatility": volatility_value,
        "confidence": confidence,
        "news_level": news_level,
        "news_score": news_score,
    },
    "account": {
        "cash": virtual_account.get("cash"),
        "equity": virtual_account.get("equity"),
        "position": virtual_account.get("position"),
        "entry_price": virtual_account.get("entry_price"),
        "last_action": virtual_account.get("last_action"),
        "official_closed_trades":
            official_performance.get("closed_trades", 0),
        "official_total_realized_pnl":
            official_performance.get(
                "total_realized_pnl",
                0.0,
            ),
    },
    "outcome": None,
    "legacy_data_excluded": True,
}

appended = False

if run_id not in existing_ids:
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                record,
                ensure_ascii=False,
                separators=(",", ":"),
            ) + "\n"
        )

    existing.append(record)
    appended = True

# 正式開始以降のみ。
official_records = []

try:
    start_dt = datetime.fromisoformat(started_at)
except Exception:
    start_dt = now

for row in existing:
    try:
        logged_dt = datetime.fromisoformat(
            str(row.get("logged_at"))
        )
    except Exception:
        continue

    if logged_dt >= start_dt:
        official_records.append(row)

decision_counts = Counter(
    str(row.get("decision", {}).get("final") or "UNKNOWN")
    for row in official_records
)

skip_records = [
    row
    for row in official_records
    if str(
        row.get("decision", {}).get("final")
    ).upper() == "SKIP"
]

consecutive_skip = 0

for row in reversed(official_records):
    if str(
        row.get("decision", {}).get("final")
    ).upper() == "SKIP":
        consecutive_skip += 1
    else:
        break

reason_counts: Counter[str] = Counter()

for row in skip_records:
    reason = row.get("decision", {}).get(
        "primary_reason"
    )

    if reason:
        for part in str(reason).split("/"):
            cleaned = part.strip()

            if cleaned:
                reason_counts[cleaned] += 1

daily_counts: Counter[str] = Counter()

for row in official_records:
    logged_at = str(row.get("logged_at") or "")

    if len(logged_at) >= 10:
        daily_counts[logged_at[:10]] += 1

summary = {
    "updated_at": now.isoformat(timespec="seconds"),
    "official_started_at": started_at,
    "total_logged_decisions": len(official_records),
    "decision_counts": dict(decision_counts),
    "skip_count": len(skip_records),
    "skip_rate": (
        round(
            len(skip_records)
            / len(official_records)
            * 100,
            2,
        )
        if official_records
        else None
    ),
    "consecutive_skip": consecutive_skip,
    "top_skip_reasons": [
        {
            "reason": reason,
            "count": count,
        }
        for reason, count in reason_counts.most_common(20)
    ],
    "daily_record_counts": dict(
        sorted(daily_counts.items())
    ),
    "latest_run_id": run_id,
    "latest_decision": final_decision,
    "latest_votes": record["vote_analysis"][
        "weighted_votes"
    ],
    "latest_skip_advantage":
        skip_advantage,
    "legacy_data_excluded": True,
}

atomic_json(DAILY_FILE, summary)

state = {
    "updated_at": now.isoformat(timespec="seconds"),
    "last_run_id": run_id,
    "last_appended": appended,
    "log_file": LOG_FILE.name,
    "record_count": len(official_records),
    "consecutive_skip": consecutive_skip,
}

atomic_json(STATE_FILE, state)

status = {
    "status": "OK",
    "updated_at": now.isoformat(timespec="seconds"),
    "appended": appended,
    "run_id": run_id,
    "official_record_count": len(official_records),
    "latest_decision": final_decision,
    "consecutive_skip": consecutive_skip,
    "skip_rate": summary["skip_rate"],
    "log_file": LOG_FILE.name,
    "daily_summary": DAILY_FILE.name,
}

atomic_json(STATUS_FILE, status)

print("===== OFFICIAL DECISION LOGGER =====")
print("status: OK")
print("appended:", appended)
print("run_id:", run_id)
print("decision:", final_decision)
print("votes:", json.dumps(votes, ensure_ascii=False))
print("nearest_direction:", nearest_direction)
print("skip_advantage:", skip_advantage)
print("official_record_count:", len(official_records))
print("consecutive_skip:", consecutive_skip)
print("skip_rate:", summary["skip_rate"])
