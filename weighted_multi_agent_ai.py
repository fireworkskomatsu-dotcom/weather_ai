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

if not isinstance(official_weights, dict):
    official_weights = {}

weight_applied_count = 0
weight_effective_count = 0
weight_match_count = 0
weight_match_details = []
seen_strategy_keys = set()
raw_before_learning = {
    "LONG": 0.0,
    "SHORT": 0.0,
    "SKIP": 0.0,
}

adaptive_strategies = adaptive_data.get(
    "strategies",
    [],
)

adaptive_strategy_source = "adaptive_data.strategies"

if not isinstance(adaptive_strategies, list) or not adaptive_strategies:
    adaptive_strategies = adaptive_data.get(
        "weights",
        [],
    )
    adaptive_strategy_source = "adaptive_data.weights"

if not isinstance(adaptive_strategies, list) or not adaptive_strategies:
    strategy_5x10_path = BASE / "strategy_5x10.json"
    strategy_5x10_data = {}

    if strategy_5x10_path.exists():
        try:
            strategy_5x10_data = json.loads(
                strategy_5x10_path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            strategy_5x10_data = {}

    adaptive_strategies = strategy_5x10_data.get(
        "strategies",
        [],
    )
    adaptive_strategy_source = "strategy_5x10.json.strategies"

if not isinstance(adaptive_strategies, list):
    adaptive_strategies = []
    adaptive_strategy_source = "NONE"

weighted_strategy_raw = {
    "LONG": 0.0,
    "SHORT": 0.0,
    "SKIP": 0.0,
}

usable_rows = 0


def official_strategy_keys(row):
    values = [
        row.get("id"),
        row.get("strategy_id"),
        row.get("name"),
    ]

    keys = []

    for value in values:
        if value in (None, ""):
            continue

        key = str(value).strip()

        if key and key not in keys:
            keys.append(key)

    return keys


def official_learned_weight(row):
    candidate_keys = official_strategy_keys(row)

    for key in candidate_keys:
        learned = official_weights.get(key)

        if not isinstance(learned, dict):
            continue

        try:
            value = float(
                learned.get("weight", 1.0)
            )
        except (TypeError, ValueError):
            value = 1.0

        return value, key, candidate_keys

    normalized = {
        str(source_key).strip().lower(): source_key
        for source_key in official_weights
    }

    for key in candidate_keys:
        source_key = normalized.get(key.lower())

        if source_key is None:
            continue

        learned = official_weights.get(
            source_key,
            {},
        )

        try:
            value = float(
                learned.get("weight", 1.0)
            )
        except (TypeError, ValueError):
            value = 1.0

        return value, source_key, candidate_keys

    return 1.0, None, candidate_keys


for row in adaptive_strategies:
    if not isinstance(row, dict):
        continue

    decision = normalize(
        row.get("decision")
        or row.get("final_decision")
    )

    if decision not in weighted_strategy_raw:
        continue

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

    learned_weight, matched_key, candidate_keys = (
        official_learned_weight(row)
    )

    canonical_key = (
        matched_key
        or (
            candidate_keys[0]
            if candidate_keys
            else None
        )
    )

    # 同じ戦略IDが複数配列に重複していても一度だけ数える。
    if canonical_key is not None:
        canonical_key = str(canonical_key).strip().lower()

        if canonical_key in seen_strategy_keys:
            continue

        seen_strategy_keys.add(canonical_key)

    raw_before_learning[decision] += base_vote

    weighted_vote = base_vote * learned_weight
    vote_delta = weighted_vote - base_vote

    weighted_strategy_raw[decision] += weighted_vote
    usable_rows += 1

    if matched_key is not None:
        weight_match_count += 1

        weight_match_details.append({
            "matched_key": matched_key,
            "candidate_keys": candidate_keys,
            "decision": decision,
            "base_vote": round(base_vote, 8),
            "learned_weight": round(
                learned_weight,
                8,
            ),
            "weighted_vote": round(
                weighted_vote,
                8,
            ),
            "vote_delta": round(
                vote_delta,
                8,
            ),
        })

    if abs(learned_weight - 1.0) > 1e-12:
        weight_applied_count += 1

        if abs(vote_delta) > 1e-12:
            weight_effective_count += 1

if usable_rows > 0:
    strategy_raw = weighted_strategy_raw

    if weight_applied_count > 0:
        reasons.append(
            "OFFICIAL_STRATEGY_WEIGHTS_APPLIED"
        )
    elif weight_match_count > 0:
        reasons.append(
            "OFFICIAL_STRATEGY_WEIGHTS_MATCHED_NEUTRAL"
        )
    else:
        reasons.append(
            "OFFICIAL_STRATEGY_WEIGHTS_NO_MATCH"
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

# OFFICIAL_WEIGHT_DIAGNOSTIC_BEGIN
out["official_weight_learning"] = {
    "source": "strategy_weight.json",
    "strategy_vote_source": adaptive_strategy_source,
    "strategy_rows_seen": len(adaptive_strategies),
    "available_weights": len(official_weights),
    "matched_weights": weight_match_count,
    "applied_non_neutral": weight_applied_count,
    "effective_non_zero": weight_effective_count,
    "raw_votes_before_learning": {
        key: round(value, 8)
        for key, value in raw_before_learning.items()
    },
    "raw_votes_after_learning": {
        key: round(value, 8)
        for key, value in weighted_strategy_raw.items()
    },
    "match_details": weight_match_details[:20],
}
# OFFICIAL_WEIGHT_DIAGNOSTIC_END
(BASE / "weighted_multi_agent.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(json.dumps(out, ensure_ascii=False))
