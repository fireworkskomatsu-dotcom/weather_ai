#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import tempfile
from datetime import date, timedelta
from pathlib import Path

from paper_control_plane_ai import decode_payload, process


BASE = Path(__file__).resolve().parent
production_before = (BASE / "history.csv").read_bytes()


with tempfile.TemporaryDirectory(prefix="weather_ai_control_v2_") as temporary:
    root = Path(temporary)
    prices = root / "prices.csv"
    history = root / "history.csv"
    challenger = root / "monitoring_challenger_report.json"

    trading_days = []
    current = date(2026, 1, 2)
    while len(trading_days) < 85:
        if current.weekday() < 5:
            trading_days.append(current.isoformat())
        current += timedelta(days=1)

    with prices.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Date", "Code", "O", "H", "L", "C", "Vo"])
        for index, day in enumerate(trading_days):
            close = 50000 + index * 100
            writer.writerow([day, "1321", close - 20, close + 80, close - 100, close, 10000 + index])

    targets = trading_days[-3:]
    directions = ["LONG", "SKIP", "LONG"]
    with history.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for index, (day, direction) in enumerate(zip(targets, directions), start=1):
            writer.writerow([
                "FORWARD_V1", f"run-{index}", f"{day} 16:00+0900", day,
                "赤", "10", "LOW", "HOT", "TEST", "60", "40",
                "FREE_MONITORING_ONLY", "false", "FRESH", "0", "1321.T",
                day, str(50000 + (82 + index - 1) * 100), direction,
            ])

    challenger.write_text(json.dumps({
        "selected_candidate": "CHAMPION_55",
        "candidates": [
            {"id": "CHAMPION_55", "holdout": {"accuracy_pct": 49, "average_net_after_cost_pct": -0.1}},
            {"id": "ROBUST", "holdout": {"accuracy_pct": 55, "average_net_after_cost_pct": 0.2}},
        ],
    }), encoding="utf-8")

    generated = process(prices, history, challenger, now="2026-05-01T18:00:00+09:00")
    second_run = process(prices, history, challenger, now="2026-05-01T18:01:00+09:00")
    rows = list(csv.reader(history.open(encoding="utf-8")))
    control_rows = [row for row in rows if row and row[0] == "CONTROL_V2"]
    latest = decode_payload(control_rows[-1][4])
    features = latest["features"]
    account = latest["paper_account"]

    checks = {
        "isolated_filesystem": True,
        "three_target_dates_processed": len(generated) == 3,
        "idempotent_second_run": second_run == [] and len(control_rows) == 3,
        "all_ten_features_active": len(features) == 10 and all(value == "ACTIVE" for value in features.values()),
        "next_session_fill_used": generated[1]["execution"]["fill"]["fill_date"] == targets[1],
        "costs_modeled": generated[1]["execution"]["fill"]["fee"] > 0 and generated[1]["execution"]["fill"]["slippage_pct"] > 0,
        "paper_account_round_trip": account["closed_trades"] == 1 and account["position"] == 0,
        "risk_limits_active": latest["risk"]["max_position"] == 1 and latest["risk"]["kill_switch"] is False,
        "pretrade_fail_closed": isinstance(latest["pretrade"]["checks"], dict),
        "regime_classified": latest["regime"]["state"] in {"UPTREND", "DOWNTREND", "RANGE", "HIGH_VOLATILITY"},
        "benchmark_measured": latest["benchmark"]["status"] == "MEASURED",
        "losing_strategy_quarantined": "CHAMPION_55" in latest["strategy_governance"]["quarantined"],
        "eligible_strategy_not_quarantined": "ROBUST" in latest["strategy_governance"]["eligible"],
        "data_quality_checked": latest["data_quality"]["status"] == "PASS",
        "reconciliation_passed": latest["reconciliation"]["status"] == "PASS",
        "public_report_only": latest["daily_report"]["delivery"] == "PUBLIC_STATUS_ONLY",
        "real_money_false": latest["real_money"] is False and latest["official_eligible"] is False,
        "production_files_unchanged": (BASE / "history.csv").read_bytes() == production_before,
    }

    if not all(checks.values()):
        raise SystemExit(json.dumps(checks, ensure_ascii=False, indent=2))

    print("===== PAPER CONTROL PLANE E2E =====")
    for name, passed in checks.items():
        print(f"  {name}: {passed}")
    print("RESULT: PASS")
