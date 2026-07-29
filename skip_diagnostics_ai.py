#!/usr/bin/env python3

import json
import re
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "skip_diagnostics.json"
WEATHER = BASE / "latest_weather.txt"

START_MARKER = "【SKIP診断】"
END_MARKER = "【SKIP診断ここまで】"

FILES = [
    "weighted_multi_agent.json",
    "filter.json",
    "winrate_filter.json",
    "strategy_skip_breakdown.json",
    "adaptive_strategy_state.json",
    "emergency_stop.json",
    "risk_exit.json",
    "recovery_mode.json",
    "market_temperature.json",
    "news.json",
    "virtual_account.json",
]


def read_json(filename):
    path = BASE / filename

    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def flatten(value, prefix=""):
    rows = []

    if isinstance(value, dict):
        for key, child in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(flatten(child, name))

    elif isinstance(value, list):
        for index, child in enumerate(value):
            rows.extend(flatten(child, f"{prefix}[{index}]"))

    else:
        rows.append((prefix, value))

    return rows


def normalized(value):
    if isinstance(value, str):
        return value.strip().upper()

    return value


def is_true(value):
    return value is True or normalized(value) in {
        "TRUE",
        "YES",
        "ON",
        "BLOCKED",
        "STOP",
        "DANGER",
        "HIGH",
        "NOT_READY",
    }


def is_false(value):
    return value is False or normalized(value) in {
        "FALSE",
        "NO",
        "OFF",
        "DENIED",
    }


def add_finding(items, level, source, field, value, reason):
    marker = (level, source, field, str(value))

    if marker not in {
        (item["level"], item["source"], item["field"], str(item["value"]))
        for item in items
    }:
        items.append(
            {
                "level": level,
                "source": source,
                "field": field,
                "value": value,
                "reason": reason,
            }
        )


findings = []
sources = []
numeric_context = {
    "confidence": [],
    "consensus": [],
    "threshold": [],
}

for filename in FILES:
    data = read_json(filename)

    if data is None:
        continue

    sources.append(filename)

    for field, value in flatten(data):
        lower = field.lower()
        upper_value = normalized(value)

        blocking_fields = (
            "blocked",
            "trade_blocked",
            "force_skip",
            "skip_required",
            "emergency_stop",
            "risk_exit",
        )

        permission_fields = (
            "allow_trade",
            "trade_allowed",
            "can_trade",
            "entry_allowed",
            "go_live",
        )

        if any(name in lower for name in blocking_fields) and is_true(value):
            add_finding(
                findings,
                "BLOCK",
                filename,
                field,
                value,
                f"{field} が有効",
            )

        if any(name in lower for name in permission_fields) and is_false(value):
            add_finding(
                findings,
                "BLOCK",
                filename,
                field,
                value,
                f"{field} が無効",
            )

        if (
            any(name in lower for name in ("status", "state", "readiness"))
            and upper_value in {"NOT_READY", "BLOCKED", "STOP", "DENIED"}
        ):
            add_finding(
                findings,
                "BLOCK",
                filename,
                field,
                value,
                f"{field}={value}",
            )

        if "recovery_mode" in lower and is_true(value):
            add_finding(
                findings,
                "WARNING",
                filename,
                field,
                value,
                "回復モードが有効",
            )

        if "news_level" in lower and upper_value == "HIGH":
            add_finding(
                findings,
                "WARNING",
                filename,
                field,
                value,
                "ニュース危険度がHIGH",
            )

        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
        ):
            record = {
                "source": filename,
                "field": field,
                "value": value,
            }

            if "confidence" in lower:
                numeric_context["confidence"].append(record)

            if "consensus" in lower:
                numeric_context["consensus"].append(record)

            if any(
                name in lower
                for name in ("threshold", "minimum", "min_confidence")
            ):
                numeric_context["threshold"].append(record)


weighted = read_json("weighted_multi_agent.json") or {}

final_decision = (
    weighted.get("final_decision")
    or weighted.get("decision")
    or weighted.get("signal")
    or "UNKNOWN"
)

blocks = [item for item in findings if item["level"] == "BLOCK"]
warnings = [item for item in findings if item["level"] == "WARNING"]

if blocks:
    diagnosis = "明示的な停止条件を検出"
    primary_reason = blocks[0]["reason"]

elif str(final_decision).upper() == "SKIP":
    diagnosis = "合議結果はSKIPだが明示的な停止フラグは未検出"
    primary_reason = "最終合議ロジック内部の条件確認が必要"

else:
    diagnosis = "SKIPではありません"
    primary_reason = "停止条件なし"

result = {
    "updated_at": datetime.now().isoformat(timespec="seconds"),
    "final_decision": final_decision,
    "diagnosis": diagnosis,
    "primary_reason": primary_reason,
    "block_count": len(blocks),
    "warning_count": len(warnings),
    "blocks": blocks,
    "warnings": warnings,
    "numeric_context": numeric_context,
    "sources_read": sources,
}

OUTPUT.write_text(
    json.dumps(result, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

display = [
    START_MARKER,
    f"最終判断：{final_decision}",
    f"診断：{diagnosis}",
    f"主停止理由：{primary_reason}",
    f"明示的停止条件：{len(blocks)}件",
    f"警告条件：{len(warnings)}件",
]

for index, item in enumerate(blocks[:8], 1):
    display.append(
        f"停止{index}：{item['reason']}（{item['source']}）"
    )

for index, item in enumerate(warnings[:5], 1):
    display.append(
        f"警告{index}：{item['reason']}（{item['source']}）"
    )

display.append(END_MARKER)
diagnostic_text = "\n".join(display)

if WEATHER.exists():
    original = WEATHER.read_text(
        encoding="utf-8",
        errors="replace",
    )

    old_diagnostic = re.compile(
        re.escape(START_MARKER)
        + r".*?"
        + re.escape(END_MARKER),
        re.DOTALL,
    )

    original = old_diagnostic.sub("", original).rstrip()
    new_weather = original + "\n\n" + diagnostic_text + "\n"

else:
    new_weather = diagnostic_text + "\n"

WEATHER.write_text(new_weather, encoding="utf-8")

print("SKIP_DIAGNOSTICS_OK")
print(json.dumps(result, ensure_ascii=False, indent=2))
