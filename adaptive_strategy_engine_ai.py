import json
import math
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
STRATEGY_FILE = BASE / "strategy_5x10.json"
PRICE_FILES = [
    BASE / "live_price.json",
    BASE / "current_price.json",
    BASE / "market_data.json",
    BASE / "master_decision.json",
]
STATE_FILE = BASE / "adaptive_strategy_state.json"
OUTPUT_FILE = BASE / "adaptive_strategy_weights.json"
HISTORY_FILE = BASE / "adaptive_strategy_history.jsonl"

MOVE_THRESHOLD = 0.0025
ALPHA = 0.20
MIN_MULTIPLIER = 0.70
MAX_MULTIPLIER = 1.30


def read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def as_float(value, default=None):
    try:
        value = float(value)
        return value if math.isfinite(value) else default
    except (TypeError, ValueError):
        return default


def find_price(data):
    if not isinstance(data, dict):
        return None

    for key in (
        "price",
        "current_price",
        "close",
        "last",
        "latest_price",
        "market_price",
    ):
        value = as_float(data.get(key))
        if value and value > 0:
            return value

    for value in data.values():
        if isinstance(value, dict):
            found = find_price(value)
            if found:
                return found

    return None


def current_price():
    for path in PRICE_FILES:
        data = read_json(path, {})
        value = find_price(data)
        if value:
            return value, path.name
    return None, None


def normalize_decision(value):
    value = str(value or "SKIP").upper().strip()
    mapping = {
        "BUY": "LONG",
        "SELL": "SHORT",
        "HOLD": "SKIP",
        "NO_TRADE": "SKIP",
        "WAIT": "SKIP",
    }
    return mapping.get(value, value)


def flatten_strategies(value, rows=None):
    if rows is None:
        rows = []

    if isinstance(value, dict):
        decision = value.get("decision")
        name = value.get("name") or value.get("id") or value.get("strategy")

        if decision is not None and name is not None:
            rows.append(value)

        for child in value.values():
            if isinstance(child, (dict, list)):
                flatten_strategies(child, rows)

    elif isinstance(value, list):
        for child in value:
            flatten_strategies(child, rows)

    return rows


def score_decision(decision, move):
    decision = normalize_decision(decision)

    if decision == "LONG":
        return max(-1.0, min(1.0, move / MOVE_THRESHOLD))

    if decision == "SHORT":
        return max(-1.0, min(1.0, -move / MOVE_THRESHOLD))

    magnitude = abs(move)

    if magnitude <= MOVE_THRESHOLD * 0.5:
        return 0.50

    if magnitude <= MOVE_THRESHOLD:
        return 0.10

    return max(-1.0, 1.0 - magnitude / MOVE_THRESHOLD)


def multiplier_from_ema(ema, samples):
    raw = 1.0 + 0.30 * max(-1.0, min(1.0, ema))

    if samples < 3:
        raw = max(0.90, min(1.10, raw))
    elif samples < 10:
        raw = max(0.80, min(1.20, raw))

    return round(max(MIN_MULTIPLIER, min(MAX_MULTIPLIER, raw)), 4)


strategy_data = read_json(STRATEGY_FILE, {})
strategies = flatten_strategies(strategy_data)

source_time = None
if isinstance(strategy_data, dict):
    source_time = (
        strategy_data.get("time")
        or strategy_data.get("generated_at")
        or strategy_data.get("timestamp")
    )

price, price_source = current_price()

state = read_json(
    STATE_FILE,
    {
        "version": 1,
        "strategies": {},
        "last_snapshot": {},
    },
)

state.setdefault("strategies", {})
previous = state.get("last_snapshot") or {}
evaluation = None

previous_source = previous.get("source_time")
new_snapshot = source_time != previous_source

if previous and price and previous.get("price") and new_snapshot:
    entry = as_float(previous.get("price"))

    if entry and entry > 0:
        move = (price - entry) / entry
        evaluated = 0

        for item in previous.get("strategies", []):
            sid = str(item.get("id") or item.get("name") or "UNKNOWN")
            result = score_decision(item.get("decision"), move)

            rec = state["strategies"].setdefault(
                sid,
                {
                    "name": item.get("name", sid),
                    "family": item.get("family", "UNKNOWN"),
                    "samples": 0,
                    "ema_score": 0.0,
                    "wins": 0,
                    "losses": 0,
                    "flats": 0,
                },
            )

            old_ema = as_float(rec.get("ema_score"), 0.0) or 0.0
            rec["samples"] = int(rec.get("samples", 0) or 0) + 1
            rec["ema_score"] = round(
                (1.0 - ALPHA) * old_ema + ALPHA * result,
                6,
            )

            if result > 0.15:
                rec["wins"] = int(rec.get("wins", 0) or 0) + 1
            elif result < -0.15:
                rec["losses"] = int(rec.get("losses", 0) or 0) + 1
            else:
                rec["flats"] = int(rec.get("flats", 0) or 0) + 1

            rec["last_result"] = round(result, 6)
            rec["last_decision"] = normalize_decision(item.get("decision"))
            rec["last_market_move_pct"] = round(move * 100, 5)
            rec["updated_at"] = datetime.now().isoformat(timespec="seconds")
            evaluated += 1

        evaluation = {
            "previous_source_time": previous_source,
            "entry_price": entry,
            "current_price": price,
            "market_move_pct": round(move * 100, 5),
            "strategies_evaluated": evaluated,
        }

rows = []

for index, item in enumerate(strategies, start=1):
    sid = str(
        item.get("id")
        or item.get("name")
        or item.get("strategy")
        or f"strategy_{index}"
    )

    name = str(item.get("name") or item.get("strategy") or sid)
    family = str(item.get("family") or item.get("group") or "UNKNOWN")

    rec = state["strategies"].setdefault(
        sid,
        {
            "name": name,
            "family": family,
            "samples": 0,
            "ema_score": 0.0,
            "wins": 0,
            "losses": 0,
            "flats": 0,
        },
    )

    samples = int(rec.get("samples", 0) or 0)
    ema = as_float(rec.get("ema_score"), 0.0) or 0.0
    multiplier = multiplier_from_ema(ema, samples)

    score_weight = as_float(item.get("score"))
    default_weight = score_weight / 100.0 if score_weight is not None else 0.5
    base_weight = as_float(item.get("weight"), default_weight) or 0.5
    base_weight = max(0.01, base_weight)

    effective_weight = round(
        max(0.05, base_weight * multiplier),
        4,
    )

    status = "LEARNING"

    if samples >= 10 and ema >= 0.25:
        status = "PROMOTION_CANDIDATE"
    elif samples >= 10 and ema <= -0.25:
        status = "QUARANTINE_CANDIDATE"

    rows.append(
        {
            "id": sid,
            "name": name,
            "family": family,
            "decision": normalize_decision(item.get("decision")),
            "reason": item.get("reason"),
            "base_weight": round(base_weight, 4),
            "adaptive_multiplier": multiplier,
            "effective_weight": effective_weight,
            "samples": samples,
            "ema_score": round(ema, 6),
            "wins": int(rec.get("wins", 0) or 0),
            "losses": int(rec.get("losses", 0) or 0),
            "flats": int(rec.get("flats", 0) or 0),
            "status": status,
        }
    )

state["last_snapshot"] = {
    "source_time": source_time,
    "captured_at": datetime.now().isoformat(timespec="seconds"),
    "price": price,
    "price_source": price_source,
    "strategies": [
        {
            "id": row["id"],
            "name": row["name"],
            "family": row["family"],
            "decision": row["decision"],
        }
        for row in rows
    ],
}

state["updated_at"] = datetime.now().isoformat(timespec="seconds")

STATE_FILE.write_text(
    json.dumps(state, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

out = {
    "status": "ACTIVE" if rows else "NO_STRATEGIES",
    "mode": "ADAPTIVE_WEIGHT_ENGINE_V1",
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "source_time": source_time,
    "price": price,
    "price_source": price_source,
    "evaluation": evaluation,
    "strategy_count": len(rows),
    "promotion_candidates": [
        row["id"]
        for row in rows
        if row["status"] == "PROMOTION_CANDIDATE"
    ],
    "quarantine_candidates": [
        row["id"]
        for row in rows
        if row["status"] == "QUARANTINE_CANDIDATE"
    ],
    "weights": rows,
    "safety": {
        "live_weight_range": [
            MIN_MULTIPLIER,
            MAX_MULTIPLIER,
        ],
        "minimum_samples_for_full_range": 10,
        "direct_retirement": False,
        "hard_risk_veto_preserved": True,
    },
}

OUTPUT_FILE.write_text(
    json.dumps(out, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

with HISTORY_FILE.open("a", encoding="utf-8") as fh:
    fh.write(
        json.dumps(
            {
                "generated_at": out["generated_at"],
                "source_time": source_time,
                "price": price,
                "evaluation": evaluation,
                "promotion_candidates": out["promotion_candidates"],
                "quarantine_candidates": out["quarantine_candidates"],
            },
            ensure_ascii=False,
        )
        + "\n"
    )

print(
    json.dumps(
        {
            "status": out["status"],
            "strategy_count": len(rows),
            "evaluation": evaluation,
            "promotion": len(out["promotion_candidates"]),
            "quarantine": len(out["quarantine_candidates"]),
        },
        ensure_ascii=False,
    )
)
