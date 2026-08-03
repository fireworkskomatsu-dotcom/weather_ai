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

# OFFICIAL_STRATEGY_WEIGHT_BEGIN
weight_path = BASE / "strategy_weight.json"
official_weight_data = {}

if weight_path.exists():
    try:
        official_weight_data = json.loads(
            weight_path.read_text(encoding="utf-8")
        )
    except Exception:
        official_weight_data = {}

official_weights = official_weight_data.get(
    "weights",
    {},
)

weight_applied_count = 0

adaptive_strategies = adaptive_data.get(
    "strategies",
    [],
)

if isinstance(adaptive_strategies, list):
    weighted_strategy_raw = {
        "LONG": 0.0,
        "SHORT": 0.0,
        "SKIP": 0.0,
    }

    usable_rows = 0

    for row in adaptive_strategies:
        if not isinstance(row, dict):
            continue

        decision = normalize(
            row.get("decision")
            or row.get("final_decision")
        )

        if decision not in weighted_strategy_raw:
            continue

        strategy_id = str(
            row.get("id")
            or row.get("strategy_id")
            or row.get("name")
            or ""
        )

        try:
            base_vote = float(
                row.get("weight")
                or row.get("score")
                or 0.0
            )
        except (TypeError, ValueError):
            base_vote = 0.0

        if base_vote > 1.5:
            base_vote = base_vote / 100.0

        learned = official_weights.get(
            strategy_id,
            {},
        )

        try:
            learned_weight = float(
                learned.get("weight", 1.0)
            )
        except (TypeError, ValueError):
            learned_weight = 1.0

        weighted_strategy_raw[decision] += (
            base_vote * learned_weight
        )

        usable_rows += 1

        if abs(learned_weight - 1.0) > 1e-12:
            weight_applied_count += 1

    if usable_rows > 0:
        strategy_raw = weighted_strategy_raw

        if weight_applied_count > 0:
            reasons.append(
                "OFFICIAL_STRATEGY_WEIGHTS_APPLIED"
            )
        else:
            reasons.append(
                "OFFICIAL_STRATEGY_WEIGHTS_NEUTRAL"
            )
# OFFICIAL_STRATEGY_WEIGHT_END

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
"official_weight_learning": {
    "source": "strategy_weight.json",
    "available_weights": len(official_weights),
    "applied_non_neutral": weight_applied_count,
},
    "reasons": reasons,
    "source": "weighted_multi_agent_ai.py",
    "mode": "ADAPTIVE_PARLIAMENT_V1",
}

(BASE / "weighted_multi_agent.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(json.dumps(out, ensure_ascii=False))
