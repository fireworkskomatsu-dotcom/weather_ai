import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent


def read_json(name, default):
    try:
        return json.loads(
            (BASE / name).read_text(encoding="utf-8")
        )
    except Exception:
        return default


def normalize(value):
    value = str(value or "SKIP").upper().strip()

    mapping = {
        "BUY": "LONG",
        "SELL": "SHORT",
        "HOLD": "SKIP",
        "NO_TRADE": "SKIP",
        "WAIT": "SKIP",
    }

    return mapping.get(value, value)


filter_data = read_json("filter.json", {})
confidence_data = read_json("confidence.json", {})
risk_data = read_json("dynamic_risk_exit.json", {})
temperature_data = read_json("market_temperature.json", {})
adaptive_data = read_json("adaptive_strategy_weights.json", {})

strategies = adaptive_data.get("weights", [])

votes = {
    "LONG": 0.0,
    "SHORT": 0.0,
    "SKIP": 0.0,
}

reasons = []

strategy_raw = {
    "LONG": 0.0,
    "SHORT": 0.0,
    "SKIP": 0.0,
}

strategy_count = {
    "LONG": 0,
    "SHORT": 0,
    "SKIP": 0,
}

for item in strategies:
    decision = normalize(item.get("decision"))

    if decision not in strategy_raw:
        continue

    try:
        weight = float(
            item.get(
                "effective_weight",
                item.get("base_weight", 0.0),
            )
            or 0.0
        )
    except (TypeError, ValueError):
        weight = 0.0

    weight = max(0.0, weight)
    strategy_raw[decision] += weight
    strategy_count[decision] += 1

raw_total = sum(strategy_raw.values())
parliament_cap = 2.5

if raw_total > 0:
    for decision in strategy_raw:
        votes[decision] += (
            parliament_cap
            * strategy_raw[decision]
            / raw_total
        )

    reasons.append("ADAPTIVE_STRATEGY_PARLIAMENT")
else:
    reasons.append("NO_ADAPTIVE_STRATEGY_VOTES")

filter_decision = normalize(
    filter_data.get("decision", "SKIP")
)

if filter_decision in {"LONG", "SHORT"}:
    votes[filter_decision] += 2.0
    reasons.append(f"FILTER_{filter_decision}")
elif (
    filter_decision == "SKIP"
    and filter_data.get("blocked") is True
):
    votes["SKIP"] += 2.0
    reasons.append("FILTER_BLOCKED_SKIP")
elif filter_decision == "SKIP":
    reasons.append("FILTER_NEUTRAL_SKIP_NO_EXTRA_VOTE")
replay_key = str(filter_data.get("replay_key", ""))

if "LONG" in replay_key:
    votes["LONG"] += 1.2
elif "SHORT" in replay_key:
    votes["SHORT"] += 1.2

if filter_data.get("replay_policy_action") == "BOOST":
    if "LONG" in replay_key:
        votes["LONG"] += 1.0
    elif "SHORT" in replay_key:
        votes["SHORT"] += 1.0

if filter_data.get("replay_expectancy_action") == "BOOST":
    if "LONG" in replay_key:
        votes["LONG"] += 1.0
    elif "SHORT" in replay_key:
        votes["SHORT"] += 1.0

try:
    confidence = float(
        confidence_data.get("confidence")
        or filter_data.get("confidence")
        or 0
    )
except (TypeError, ValueError):
    confidence = 0.0

if confidence < 40:
    votes["SKIP"] += 1.5
    reasons.append("LOW_CONFIDENCE")

hard_veto = False

if risk_data.get("exit_now") is True:
    votes["SKIP"] += 4.0
    reasons.append("RISK_EXIT_HARD_VETO")
    hard_veto = True

temperature = str(
    temperature_data.get("temperature", "")
).upper()

if temperature in {"PANIC", "OVERHEAT"}:
    votes["SKIP"] += 3.0
    reasons.append("TEMP_BLOCK_HARD_VETO")
    hard_veto = True

if hard_veto:
    final = "SKIP"
else:
    final = max(
        ("LONG", "SHORT", "SKIP"),
        key=lambda key: votes[key],
    )

out = {
    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "final_decision": final,
    "weighted_votes": {
        key: round(value, 6)
        for key, value in votes.items()
    },
    "strategy_parliament": {
        "raw_votes": {
            key: round(value, 6)
            for key, value in strategy_raw.items()
        },
        "strategy_count": strategy_count,
        "influence_cap": parliament_cap,
        "adaptive_status": adaptive_data.get("status"),
        "adaptive_strategy_count": adaptive_data.get(
            "strategy_count",
            0,
        ),
    },
    "hard_veto": hard_veto,
    "reasons": reasons,
    "source": "weighted_multi_agent_ai.py",
    "mode": "ADAPTIVE_PARLIAMENT_V1",
}

(BASE / "weighted_multi_agent.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(json.dumps(out, ensure_ascii=False))
