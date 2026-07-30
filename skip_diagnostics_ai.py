#!/usr/bin/env python3

import json
from datetime import datetime
from pathlib import Path


BASE = Path(__file__).resolve().parent


def load_json(name, default=None):
    path = BASE / name

    if not path.exists():
        return {} if default is None else default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {} if default is None else default


weighted = load_json("weighted_multi_agent.json")
strategy = load_json("strategy_5x10.json")
filter_data = load_json("winrate_filter.json")
temperature = load_json("market_temperature.json")
emergency = load_json("emergency_stop.json")
recovery = load_json("recovery_mode.json")

final_decision = str(
    weighted.get("final_decision")
    or weighted.get("decision")
    or "UNKNOWN"
).upper()

votes_raw = weighted.get("weighted_votes") or {}
votes = {}

for key in ("LONG", "SHORT", "SKIP"):
    try:
        votes[key] = float(votes_raw.get(key) or 0)
    except Exception:
        votes[key] = 0.0

ranked = sorted(
    votes.items(),
    key=lambda item: item[1],
    reverse=True,
)

winner = ranked[0][0] if ranked else "UNKNOWN"
winner_vote = ranked[0][1] if ranked else 0.0
runner_up = ranked[1][0] if len(ranked) >= 2 else None
runner_up_vote = ranked[1][1] if len(ranked) >= 2 else 0.0
margin = winner_vote - runner_up_vote
total_votes = sum(votes.values())
margin_pct = (
    margin / total_votes * 100
    if total_votes > 0
    else 0.0
)

strategies = strategy.get("strategies") or []
active_skip_strategies = []
active_directional_strategies = []
abstain_count = 0

for row in strategies:
    decision = str(row.get("decision") or "UNKNOWN").upper()

    record = {
        "id": row.get("id"),
        "family": row.get("family"),
        "name": row.get("name"),
        "decision": decision,
        "score": row.get("score"),
        "weight": row.get("weight"),
        "reasons": row.get("reasons") or [],
    }

    if decision == "ABSTAIN":
        abstain_count += 1
    elif decision == "SKIP":
        active_skip_strategies.append(record)
    elif decision in {"LONG", "SHORT"}:
        active_directional_strategies.append(record)

explicit_blocks = []

if filter_data.get("blocked") is True:
    explicit_blocks.append({
        "source": "winrate_filter",
        "reason": (
            filter_data.get("reason")
            or filter_data.get("reasons")
            or "blocked=True"
        ),
    })

if emergency.get("stop") is True:
    explicit_blocks.append({
        "source": "emergency_stop",
        "reason": (
            emergency.get("reason")
            or emergency.get("reasons")
            or "stop=True"
        ),
    })

temp_value = str(
    temperature.get("temperature")
    or temperature.get("market_temperature")
    or temperature.get("status")
    or ""
).upper()

if temp_value in {"PANIC", "OVERHEAT"}:
    explicit_blocks.append({
        "source": "market_temperature",
        "reason": temp_value,
    })

if recovery.get("blocked") is True:
    explicit_blocks.append({
        "source": "recovery_mode",
        "reason": (
            recovery.get("reason")
            or "blocked=True"
        ),
    })

strategy_skip_reasons = []

for row in active_skip_strategies:
    for reason in row.get("reasons") or []:
        reason = str(reason)

        if reason not in strategy_skip_reasons:
            strategy_skip_reasons.append(reason)

if final_decision != "SKIP":
    diagnosis = "最終判断はSKIPではありません"
    primary_reason = f"最終判断={final_decision}"

elif explicit_blocks:
    diagnosis = "明示的な安全停止条件によりSKIP"
    primary_reason = str(explicit_blocks[0]["reason"])

elif active_skip_strategies:
    if margin_pct < 2:
        diagnosis = "有効な戦略票による僅差のSKIP"
    else:
        diagnosis = "有効な戦略票によりSKIP"

    primary_reason = (
        " / ".join(strategy_skip_reasons)
        if strategy_skip_reasons
        else "戦略合議によるSKIP"
    )

elif winner == "SKIP":
    diagnosis = "合議集計ではSKIPが最多"
    primary_reason = "5×10以外のAI票または合議補正によるSKIP"

else:
    diagnosis = "最終判断と最多票が一致していません"
    primary_reason = "最終決定処理の追加確認が必要"

report = {
    "updated_at": datetime.now().isoformat(timespec="seconds"),
    "final_decision": final_decision,
    "diagnosis": diagnosis,
    "primary_reason": primary_reason,
    "weighted_votes": {
        key: round(value, 6)
        for key, value in votes.items()
    },
    "vote_ranking": [
        {
            "decision": key,
            "vote": round(value, 6),
        }
        for key, value in ranked
    ],
    "winner": winner,
    "runner_up": runner_up,
    "margin": round(margin, 6),
    "margin_pct": round(margin_pct, 4),
    "explicit_blocks": explicit_blocks,
    "strategy_5x10": {
        "strategy_count": len(strategies),
        "abstain_count": abstain_count,
        "active_skip_count": len(active_skip_strategies),
        "active_directional_count": len(
            active_directional_strategies
        ),
        "active_skip_strategies": active_skip_strategies,
        "active_directional_strategies":
            active_directional_strategies,
        "skip_reasons": strategy_skip_reasons,
    },
    "weighted_reasons": weighted.get("reasons") or [],
    "filter_decision": weighted.get("filter_decision"),
}

(BASE / "skip_diagnostics.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print("===== SKIP診断 =====")
print("final_decision:", final_decision)
print("diagnosis:", diagnosis)
print("primary_reason:", primary_reason)
print(
    "weighted_votes:",
    json.dumps(report["weighted_votes"], ensure_ascii=False),
)
print("winner:", winner)
print("runner_up:", runner_up)
print("margin:", report["margin"])
print("margin_pct:", report["margin_pct"])
print("explicit_blocks:", len(explicit_blocks))
print(
    "active_skip_count:",
    len(active_skip_strategies),
)
print(
    "active_skip_reasons:",
    json.dumps(strategy_skip_reasons, ensure_ascii=False),
)
