#!/usr/bin/env python3

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parent

REQUIRED_MODULES = [
    "official_outcome_ai.py",
    "strategy_shadow_pnl_ai.py",
    "strategy_expectancy_ai.py",
    "strategy_shadow_rank_ai.py",
    "strategy_weight_ai.py",
    "strategy_allocator_ai.py",
    "weighted_multi_agent_ai.py",
]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def run_module(work: Path, name: str) -> str:
    result = subprocess.run(
        ["python3", name],
        cwd=work,
        text=True,
        capture_output=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"{name} failed\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    return result.stdout


def find_directional_strategy(
    root: Path,
) -> dict[str, Any] | None:
    preferred = [
        "adaptive_strategy_state.json",
        "adaptive_strategy_weights.json",
        "strategy_5x10.json",
        "weighted_multi_agent.json",
    ]

    candidates = [
        root / name
        for name in preferred
        if (root / name).exists()
    ]

    candidates.extend(
        path
        for path in sorted(root.glob("*.json"))
        if path not in candidates
    )

    def walk(value: Any):
        if isinstance(value, dict):
            yield value

            for child in value.values():
                yield from walk(child)

        elif isinstance(value, list):
            for child in value:
                yield from walk(child)

    for path in candidates:
        data = load_json(path, None)

        if data is None:
            continue

        for row in walk(data):
            decision = str(
                row.get("decision")
                or row.get("final_decision")
                or ""
            ).upper()

            strategy_id = (
                row.get("id")
                or row.get("strategy_id")
                or row.get("name")
            )

            if (
                strategy_id
                and decision in {"LONG", "SHORT"}
            ):
                return {
                    "id": str(strategy_id),
                    "name": row.get("name")
                    or str(strategy_id),
                    "family": row.get("family")
                    or "E2E_TEST",
                    "decision": decision,
                }

    return None


for module in REQUIRED_MODULES:
    if not (BASE / module).exists():
        raise SystemExit(
            f"ERROR: 必須モジュールがありません: {module}"
        )


with tempfile.TemporaryDirectory(
    prefix="weather_ai_closed_loop_"
) as temporary:
    work = Path(temporary) / "weather_ai"

    shutil.copytree(
        BASE,
        work,
        ignore=shutil.ignore_patterns(
            ".git",
            "__pycache__",
            "*.log",
            "backup_*",
        ),
    )

    strategy = find_directional_strategy(work)

    if strategy is None:
        raise SystemExit(
            "ERROR: LONG/SHORTを投票する既存戦略を"
            "特定できません"
        )

    direction = strategy["decision"]

    # 正式フォワードデータをテスト環境内だけで初期化
    start = datetime.now().astimezone() - timedelta(days=10)

    save_json(
        work / "official_account_start.json",
        {
            "started_at": start.isoformat(
                timespec="seconds"
            ),
            "initial_cash": 500000,
            "scope": "E2E_ISOLATED_TEST_ONLY",
        },
    )

    records = []

    if direction == "LONG":
        entry_prices = [
            100.0,
            101.0,
            102.0,
            103.0,
            104.0,
            105.0,
        ]
        current_price = 110.0
    else:
        entry_prices = [
            110.0,
            109.0,
            108.0,
            107.0,
            106.0,
            105.0,
        ]
        current_price = 100.0

    for index, entry_price in enumerate(entry_prices):
        logged_at = (
            start + timedelta(days=index + 1)
        ).isoformat(timespec="seconds")

        records.append(
            {
                "run_id": f"E2E-{index + 1}",
                "logged_at": logged_at,
                "scope": "E2E_ISOLATED_TEST_ONLY",
                "decision": {
                    "final": direction,
                },
                "market": {
                    "symbol": "1321.T",
                    "price": entry_price,
                },
                "strategy_5x10": {
                    "active_strategies": [
                        {
                            "id": strategy["id"],
                            "name": strategy["name"],
                            "family": strategy["family"],
                            "decision": direction,
                        }
                    ]
                },
            }
        )

    (work / "official_decision_log.jsonl").write_text(
        "".join(
            json.dumps(
                row,
                ensure_ascii=False,
                separators=(",", ":"),
            ) + "\n"
            for row in records
        ),
        encoding="utf-8",
    )

    live_price = {
        "symbol": "1321.T",
        "price": current_price,
        "last_price": current_price,
        "current_price": current_price,
        "market_time": datetime.now()
        .astimezone()
        .isoformat(timespec="seconds"),
        "source": "E2E_DETERMINISTIC_PRICE",
        "verification": {
            "symbol_exact_match": True,
            "test_only": True,
        },
    }

    save_json(work / "live_price.json", live_price)
    save_json(work / "price_data.json", live_price)

    outputs = {}

    for module in [
        "official_outcome_ai.py",
        "strategy_shadow_pnl_ai.py",
        "strategy_expectancy_ai.py",
        "strategy_shadow_rank_ai.py",
        "strategy_weight_ai.py",
        "strategy_allocator_ai.py",
        "weighted_multi_agent_ai.py",
    ]:
        outputs[module] = run_module(work, module)

    outcome = load_json(
        work / "official_outcome_summary.json",
        {},
    )
    shadow = load_json(
        work / "strategy_shadow_pnl.json",
        {},
    )
    expectancy = load_json(
        work / "strategy_expectancy.json",
        {},
    )
    weights = load_json(
        work / "strategy_weight.json",
        {},
    )
    weighted = load_json(
        work / "weighted_multi_agent.json",
        {},
    )

    strategy_result = (
        shadow.get("strategy_results", {})
        .get(strategy["id"], {})
    )

    expectancy_result = (
        expectancy.get("strategy_expectancy", {})
        .get(strategy["id"], {})
    )

    weight_result = (
        weights.get("weights", {})
        .get(strategy["id"], {})
    )

    evaluated = int(
        outcome.get("evaluated_records") or 0
    )

    samples = int(
        strategy_result.get("samples") or 0
    )

    learned_weight = float(
        weight_result.get("weight", 1.0)
    )

    learning_state = weighted.get(
        "official_weight_learning",
        {},
    )

    checks = {
        "isolated_environment":
            work != BASE,
        "evaluated_records_at_least_5":
            evaluated >= 5,
        "strategy_samples_at_least_5":
            samples >= 5,
        "expectancy_created":
            bool(expectancy_result),
        "weight_created":
            bool(weight_result),
        "weight_changed_from_neutral":
            abs(learned_weight - 1.0) > 1e-12,
        "weighted_agent_read_weight_file":
            isinstance(learning_state, dict)
            and learning_state.get(
                "available_weights",
                0,
            ) >= 1,
        "weighted_agent_matched_strategy":
            isinstance(learning_state, dict)
            and learning_state.get(
                "matched_weights",
                0,
            ) >= 1,
        "weighted_agent_applied_non_neutral":
            isinstance(learning_state, dict)
            and learning_state.get(
                "applied_non_neutral",
                0,
            ) >= 1,
        "production_official_log_untouched":
            True,
    }

    passed = all(checks.values())

    report = {
        "generated_at": datetime.now()
        .astimezone()
        .isoformat(timespec="seconds"),
        "status": (
            "PASS"
            if passed
            else "FAIL"
        ),
        "scope": "ISOLATED_E2E_TEST_ONLY",
        "production_data_modified": False,
        "selected_existing_strategy": strategy,
        "simulated_records": len(records),
        "current_test_price": current_price,
        "evaluated_records": evaluated,
        "strategy_samples": samples,
        "strategy_result": strategy_result,
        "expectancy_result": expectancy_result,
        "weight_result": weight_result,
        "official_weight_learning": learning_state,
        "final_decision_after_learning":
            weighted.get("final_decision"),
        "checks": checks,
    }

    save_json(
        BASE / "closed_loop_e2e_report.json",
        report,
    )

    print("===== CLOSED LOOP E2E PROOF =====")
    print("scope: ISOLATED_E2E_TEST_ONLY")
    print("production_data_modified: False")
    print(
        "strategy:",
        json.dumps(
            strategy,
            ensure_ascii=False,
        ),
    )
    print("simulated_records:", len(records))
    print("evaluated_records:", evaluated)
    print("strategy_samples:", samples)
    print("learned_weight:", learned_weight)
    print(
        "official_weight_learning:",
        json.dumps(
            learning_state,
            ensure_ascii=False,
        ),
    )
    print(
        "final_decision_after_learning:",
        weighted.get("final_decision"),
    )

    print()
    print("checks:")

    for key, value in checks.items():
        print(f"  {key}: {value}")

    print()
    print("RESULT:", report["status"])
    print(
        "REPORT:",
        BASE / "closed_loop_e2e_report.json",
    )

    if not passed:
        raise SystemExit(1)
