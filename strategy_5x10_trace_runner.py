#!/usr/bin/env python3

import json
import runpy
import sys
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
TARGET = BASE / "strategy_5x10_ai.py"
RESULT = BASE / "strategy_5x10.json"
TRACE_OUT = BASE / "strategy_5x10_trace.json"

DECISIONS = {
    "LONG", "SHORT", "SKIP",
    "BUY", "SELL", "HOLD",
    "ENTRY_LONG", "ENTRY_SHORT",
}

NAME_KEYS = (
    "strategy_name",
    "strategy_id",
    "strategy",
    "name",
    "agent_name",
    "agent",
    "model_name",
    "model",
)

DECISION_KEYS = (
    "decision",
    "signal",
    "action",
    "side",
    "vote",
    "final_decision",
)

REASON_KEYS = (
    "reason",
    "reasons",
    "why",
    "explanation",
    "status",
    "message",
)

SCORE_KEYS = (
    "score",
    "confidence",
    "weight",
    "expectancy",
    "win_rate",
    "probability",
)

events = []
seen = set()


def safe_value(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, (list, tuple)):
        return [safe_value(item) for item in list(value)[:20]]

    if isinstance(value, dict):
        result = {}

        for index, (key, child) in enumerate(value.items()):
            if index >= 30:
                break

            result[str(key)] = safe_value(child)

        return result

    return repr(value)[:500]


def find_value(local_vars, keys):
    for key in keys:
        if key in local_vars:
            return local_vars[key]

    for local_key, value in local_vars.items():
        lower = str(local_key).lower()

        if any(key in lower for key in keys):
            return value

    return None


def normalize_decision(value):
    if isinstance(value, str):
        upper = value.strip().upper()

        if upper in DECISIONS:
            if upper in {"BUY", "ENTRY_LONG"}:
                return "LONG"

            if upper in {"SELL", "ENTRY_SHORT"}:
                return "SHORT"

            if upper == "HOLD":
                return "SKIP"

            return upper

    return None


def detect_dict_decisions(value, path=""):
    found = []

    if isinstance(value, dict):
        direct_decision = None

        for key in DECISION_KEYS:
            if key in value:
                direct_decision = normalize_decision(value[key])

                if direct_decision:
                    break

        if direct_decision:
            name = None

            for key in NAME_KEYS:
                if key in value:
                    name = value[key]
                    break

            reason = None

            for key in REASON_KEYS:
                if key in value:
                    reason = value[key]
                    break

            scores = {}

            for key, child in value.items():
                lower = str(key).lower()

                if any(score_key in lower for score_key in SCORE_KEYS):
                    scores[str(key)] = safe_value(child)

            found.append(
                {
                    "path": path or "dict",
                    "strategy": safe_value(name),
                    "decision": direct_decision,
                    "reason": safe_value(reason),
                    "metrics": scores,
                }
            )

        for key, child in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            found.extend(detect_dict_decisions(child, child_path))

    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = f"{path}[{index}]"
            found.extend(detect_dict_decisions(child, child_path))

    return found


def tracer(frame, event, arg):
    try:
        filename = Path(frame.f_code.co_filename).resolve()

        if filename != TARGET.resolve():
            return tracer

        if event not in {"line", "return"}:
            return tracer

        local_vars = frame.f_locals

        strategy = find_value(local_vars, NAME_KEYS)
        raw_decision = find_value(local_vars, DECISION_KEYS)
        decision = normalize_decision(raw_decision)
        reason = find_value(local_vars, REASON_KEYS)

        metrics = {}

        for key, value in local_vars.items():
            lower = str(key).lower()

            if any(metric_key in lower for metric_key in SCORE_KEYS):
                if isinstance(value, (int, float, str, bool)) or value is None:
                    metrics[str(key)] = safe_value(value)

        if decision:
            record = {
                "line": frame.f_lineno,
                "function": frame.f_code.co_name,
                "strategy": safe_value(strategy),
                "decision": decision,
                "raw_decision": safe_value(raw_decision),
                "reason": safe_value(reason),
                "metrics": metrics,
            }

            marker = json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )

            if marker not in seen:
                seen.add(marker)
                events.append(record)

        for key, value in list(local_vars.items()):
            if isinstance(value, (dict, list)):
                for detected in detect_dict_decisions(value, str(key)):
                    record = {
                        "line": frame.f_lineno,
                        "function": frame.f_code.co_name,
                        **detected,
                    }

                    marker = json.dumps(
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                        default=str,
                    )

                    if marker not in seen:
                        seen.add(marker)
                        events.append(record)

    except Exception:
        pass

    return tracer


started_at = datetime.now().isoformat(timespec="seconds")
execution_error = None

if not TARGET.exists():
    execution_error = f"{TARGET.name} が存在しません"

else:
    try:
        sys.settrace(tracer)

        runpy.run_path(
            str(TARGET),
            run_name="__main__",
        )

    except SystemExit as exc:
        if exc.code not in (None, 0):
            execution_error = f"SystemExit: {exc.code}"

    except Exception:
        execution_error = traceback.format_exc()

    finally:
        sys.settrace(None)


# 同一戦略・判断の過剰な重複を整理
cleaned = []
cleaned_seen = set()

for event in events:
    marker = (
        str(event.get("strategy")),
        str(event.get("decision")),
        str(event.get("reason")),
        str(event.get("function")),
        json.dumps(
            event.get("metrics", {}),
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ),
    )

    if marker not in cleaned_seen:
        cleaned_seen.add(marker)
        cleaned.append(event)


decision_counts = Counter(
    event.get("decision")
    for event in cleaned
    if event.get("decision")
)

reason_counts = Counter(
    str(event.get("reason"))
    for event in cleaned
    if event.get("reason") not in (None, "", [], {})
)

named_count = sum(
    1
    for event in cleaned
    if event.get("strategy") not in (None, "", "None")
)

if cleaned:
    status = "TRACE_CAPTURED"

elif execution_error:
    status = "EXECUTION_ERROR"

else:
    status = "NO_RUNTIME_DECISIONS_CAPTURED"


report = {
    "updated_at": datetime.now().isoformat(timespec="seconds"),
    "started_at": started_at,
    "status": status,
    "target": TARGET.name,
    "execution_error": execution_error,
    "event_count": len(cleaned),
    "named_strategy_count": named_count,
    "decision_counts": dict(decision_counts),
    "reason_counts": dict(reason_counts.most_common(30)),
    "events": cleaned[:500],
}

TRACE_OUT.write_text(
    json.dumps(report, ensure_ascii=False, indent=2),
    encoding="utf-8",
)


# 元のstrategy_5x10.jsonは壊さず、診断情報だけ追加
if RESULT.exists():
    try:
        existing = json.loads(
            RESULT.read_text(encoding="utf-8")
        )

        if not isinstance(existing, dict):
            existing = {
                "original_result": existing,
            }

        existing["decision_trace"] = {
            "status": status,
            "event_count": len(cleaned),
            "named_strategy_count": named_count,
            "decision_counts": dict(decision_counts),
            "reason_counts": dict(reason_counts.most_common(30)),
            "trace_file": TRACE_OUT.name,
            "updated_at": report["updated_at"],
        }

        RESULT.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    except Exception as exc:
        report["result_update_error"] = str(exc)

        TRACE_OUT.write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


print("===== STRATEGY 5x10 TRACE =====")
print(f"status: {status}")
print(f"events: {len(cleaned)}")
print(f"named_strategies: {named_count}")
print(
    "decision_counts:",
    json.dumps(
        dict(decision_counts),
        ensure_ascii=False,
    ),
)

if reason_counts:
    print("top_reasons:")

    for reason, count in reason_counts.most_common(10):
        print(f"  {count}: {reason}")

if execution_error:
    print("execution_error:")
    print(execution_error)
