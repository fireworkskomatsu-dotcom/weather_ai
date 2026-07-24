import ast
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
SOURCE_JSON = BASE / "strategy_5x10.json"
SOURCE_PY = BASE / "strategy_5x10_ai.py"
OUTPUT = BASE / "strategy_skip_breakdown.json"


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def normalize_decision(value):
    value = str(value or "").upper().strip()

    aliases = {
        "BUY": "LONG",
        "ENTRY_LONG": "LONG",
        "SELL": "SHORT",
        "SELL_SHORT": "SHORT",
        "ENTRY_SHORT": "SHORT",
        "HOLD": "SKIP",
        "NO_TRADE": "SKIP",
        "NONE": "SKIP",
    }

    return aliases.get(value, value)


def number(value, default=1.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def text_reason(item):
    if not isinstance(item, dict):
        return "UNKNOWN"

    candidates = [
        item.get("skip_reason"),
        item.get("reason"),
        item.get("reasons"),
        item.get("cause"),
        item.get("label"),
        item.get("regime"),
        item.get("condition"),
        item.get("status"),
    ]

    for value in candidates:
        if isinstance(value, list) and value:
            return " | ".join(str(x) for x in value)

        if value not in (None, "", [], {}):
            return str(value)

    return "UNSPECIFIED_SKIP"


def strategy_name(item, fallback):
    if not isinstance(item, dict):
        return fallback

    for key in [
        "strategy",
        "strategy_name",
        "name",
        "id",
        "agent",
        "module",
        "family",
    ]:
        value = item.get(key)
        if value not in (None, ""):
            return str(value)

    return fallback


def extract_decision(item):
    if not isinstance(item, dict):
        return ""

    for key in [
        "final_decision",
        "decision",
        "signal",
        "vote",
        "action",
        "result",
    ]:
        if key in item:
            value = item.get(key)

            if isinstance(value, str):
                return normalize_decision(value)

            if isinstance(value, dict):
                nested = extract_decision(value)
                if nested:
                    return nested

    return ""


def extract_weight(item):
    if not isinstance(item, dict):
        return 1.0

    for key in [
        "weighted_vote",
        "vote_weight",
        "effective_weight",
        "weight",
        "score",
    ]:
        if key in item:
            return number(item.get(key), 1.0)

    return 1.0


def collect_candidates(node, location="root", output=None):
    if output is None:
        output = []

    if isinstance(node, dict):
        decision = extract_decision(node)

        if decision in {"LONG", "SHORT", "SKIP"}:
            output.append({
                "location": location,
                "name": strategy_name(node, location),
                "decision": decision,
                "weight": extract_weight(node),
                "reason": text_reason(node),
                "raw": node,
            })

        for key, value in node.items():
            collect_candidates(
                value,
                f"{location}.{key}",
                output
            )

    elif isinstance(node, list):
        for index, value in enumerate(node):
            collect_candidates(
                value,
                f"{location}[{index}]",
                output
            )

    return output


def deduplicate(rows):
    seen = set()
    result = []

    for row in rows:
        signature = (
            row["name"],
            row["decision"],
            row["weight"],
            row["reason"],
        )

        if signature in seen:
            continue

        seen.add(signature)
        result.append(row)

    return result


def static_strategy_names(path):
    if not path.exists():
        return []

    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    discovered = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            values = {}

            for key_node, value_node in zip(node.keys, node.values):
                if not isinstance(key_node, ast.Constant):
                    continue

                key = key_node.value

                if key not in {
                    "name",
                    "strategy",
                    "strategy_name",
                    "family",
                    "id",
                }:
                    continue

                if isinstance(value_node, ast.Constant):
                    values[key] = value_node.value

            for value in values.values():
                if isinstance(value, str) and value not in discovered:
                    discovered.append(value)

    return discovered


data = load_json(SOURCE_JSON, {})
rows = deduplicate(collect_candidates(data))

decision_totals = defaultdict(float)
skip_reasons = defaultdict(float)
skip_strategies = defaultdict(float)
family_skip = defaultdict(float)

for row in rows:
    decision_totals[row["decision"]] += row["weight"]

    if row["decision"] != "SKIP":
        continue

    skip_reasons[row["reason"]] += row["weight"]
    skip_strategies[row["name"]] += row["weight"]

    raw = row.get("raw", {})
    family = (
        raw.get("family")
        if isinstance(raw, dict)
        else None
    )

    if family:
        family_skip[str(family)] += row["weight"]

published_votes = (
    data.get("votes", {})
    if isinstance(data, dict)
    else {}
)

strategy_names_in_source = static_strategy_names(SOURCE_PY)

has_individual_records = len(rows) > 0
skip_record_count = sum(
    1 for row in rows
    if row["decision"] == "SKIP"
)

if has_individual_records:
    status = "OK"
    limitation = None
else:
    status = "INSUFFICIENT_SOURCE_DATA"
    limitation = (
        "strategy_5x10.jsonには個別戦略の判断・理由が保存されていません。"
        "現状は集計票だけで、SKIP寄与元を確定できません。"
    )

report = {
    "status": status,
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "source_time": (
        data.get("time")
        if isinstance(data, dict)
        else None
    ),
    "final_decision": (
        data.get("final_decision")
        if isinstance(data, dict)
        else None
    ),
    "published_votes": published_votes,
    "individual_records_found": len(rows),
    "skip_records_found": skip_record_count,
    "calculated_decision_totals": dict(
        sorted(
            decision_totals.items(),
            key=lambda x: x[1],
            reverse=True
        )
    ),
    "skip_reason_breakdown": dict(
        sorted(
            skip_reasons.items(),
            key=lambda x: x[1],
            reverse=True
        )
    ),
    "skip_strategy_breakdown": dict(
        sorted(
            skip_strategies.items(),
            key=lambda x: x[1],
            reverse=True
        )
    ),
    "skip_family_breakdown": dict(
        sorted(
            family_skip.items(),
            key=lambda x: x[1],
            reverse=True
        )
    ),
    "individual_decisions": [
        {
            "name": row["name"],
            "decision": row["decision"],
            "weight": row["weight"],
            "reason": row["reason"],
            "location": row["location"],
        }
        for row in rows
    ],
    "static_strategy_names_found": strategy_names_in_source,
    "limitation": limitation,
}

OUTPUT.write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print(json.dumps({
    "status": report["status"],
    "source_time": report["source_time"],
    "final_decision": report["final_decision"],
    "published_votes": report["published_votes"],
    "individual_records_found": report["individual_records_found"],
    "skip_records_found": report["skip_records_found"],
    "skip_reason_breakdown": report["skip_reason_breakdown"],
    "skip_strategy_breakdown": report["skip_strategy_breakdown"],
    "static_strategy_names_found": len(
        report["static_strategy_names_found"]
    ),
    "limitation": report["limitation"],
}, ensure_ascii=False, indent=2))
