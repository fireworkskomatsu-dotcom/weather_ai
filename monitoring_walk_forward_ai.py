#!/usr/bin/env python3

from __future__ import annotations

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


BASE = Path(__file__).resolve().parent
PRICES = BASE / "prices.csv"
REPORT = BASE / "monitoring_walk_forward_report.json"
TARGET_CODE = "13210"
DOMESTIC_CODES = ("13060", "13210")
OVERSEAS_CODES = ("88880", "77770")
ROUND_TRIP_COST_PCT = 0.10


def stats(frame: pd.DataFrame) -> dict[str, float] | None:
    if len(frame) < 200:
        return None
    close = frame["C"].astype(float)
    return {
        "last": float(close.iloc[-1]),
        "change5": float((close.iloc[-1] / close.iloc[-5] - 1) * 100),
        "ma25": float(close.tail(25).mean()),
        "ma200": float(close.tail(200).mean()),
    }


def available(
    data: pd.DataFrame,
    code: str,
    decision_date: str,
    same_day_allowed: bool,
) -> pd.DataFrame:
    rows = data[data["Code"] == code].sort_values("Date")
    if same_day_allowed:
        return rows[rows["Date"] <= decision_date]
    return rows[rows["Date"] < decision_date]


def signal_for_date(
    data: pd.DataFrame,
    decision_date: str,
) -> dict[str, Any] | None:
    score = 0
    for code in DOMESTIC_CODES + OVERSEAS_CODES:
        result = stats(available(
            data,
            code,
            decision_date,
            same_day_allowed=code in DOMESTIC_CODES,
        ))
        if result is None:
            return None

        if result["change5"] > 1:
            score += 1
        elif result["change5"] < -1:
            score -= 1
        score += 1 if result["last"] > result["ma25"] else -1
        score += 1 if result["last"] > result["ma200"] else -1

    risk = "MEDIUM"
    vix = stats(available(data, "66660", decision_date, False))
    fx = stats(available(data, "55550", decision_date, False))
    btc = stats(available(data, "44440", decision_date, False))
    if vix is None or fx is None or btc is None:
        return None

    if vix["last"] >= 25:
        score -= 1
        risk = "HIGH"
    elif vix["last"] <= 15:
        score += 1
        risk = "LOW"

    if fx["change5"] > 0.5:
        score += 1
    elif fx["change5"] < -0.5:
        score -= 1

    probability_up = 50 + score * 5
    probability_up += -5 if risk == "HIGH" else 5 if risk == "LOW" else 0
    if fx["change5"] > 0.5:
        probability_up += 3
    if stats(available(data, "88880", decision_date, False))["change5"] < -1:
        probability_up -= 3
    if stats(available(data, "77770", decision_date, False))["change5"] < -1:
        probability_up -= 3
    probability_up += 2 if btc["change5"] > 1 else -2 if btc["change5"] < -1 else 0
    probability_up = max(5, min(95, int(round(probability_up))))

    direction = "LONG" if probability_up >= 55 else "SHORT" if probability_up <= 45 else "SKIP"
    return {
        "score": score,
        "risk": risk,
        "probability_up": probability_up,
        "direction": direction,
    }


def evaluate(
    data: pd.DataFrame,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    data = data.copy()
    data["Code"] = data["Code"].astype(str)
    data["Date"] = data["Date"].astype(str)
    target = data[data["Code"] == TARGET_CODE].sort_values("Date")
    if end_date is not None:
        target = target[target["Date"] <= end_date]

    records = []
    rows = list(target[["Date", "C"]].itertuples(index=False, name=None))
    for index in range(len(rows) - 1):
        decision_date, entry_price = rows[index]
        exit_date, exit_price = rows[index + 1]
        signal = signal_for_date(data, str(decision_date))
        if signal is None:
            continue

        market_return = (float(exit_price) / float(entry_price) - 1) * 100
        direction = signal["direction"]
        gross = market_return if direction == "LONG" else -market_return if direction == "SHORT" else 0.0
        net = gross - ROUND_TRIP_COST_PCT if direction != "SKIP" else 0.0
        result = "CORRECT" if gross > 0 else "INCORRECT" if gross < 0 else "SKIP_OR_FLAT"
        records.append({
            "decision_date": str(decision_date),
            "outcome_date": str(exit_date),
            "entry_price": round(float(entry_price), 6),
            "exit_price": round(float(exit_price), 6),
            "score": signal["score"],
            "risk": signal["risk"],
            "probability_up": signal["probability_up"],
            "direction": direction,
            "market_return_pct": round(market_return, 6),
            "gross_directional_return_pct": round(gross, 6),
            "net_after_cost_pct": round(net, 6),
            "result": result,
        })
    return records


def build_report(data: pd.DataFrame) -> dict[str, Any]:
    records = evaluate(data)

    def summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
        directional = [row for row in rows if row["direction"] != "SKIP"]
        correct = sum(row["result"] == "CORRECT" for row in directional)
        incorrect = sum(row["result"] == "INCORRECT" for row in directional)
        accuracy = correct / len(directional) * 100 if directional else None
        average_net = (
            sum(row["net_after_cost_pct"] for row in directional) / len(directional)
            if directional else None
        )
        return {
            "samples": len(rows),
            "directional_samples": len(directional),
            "correct": correct,
            "incorrect": incorrect,
            "accuracy_pct": round(accuracy, 4) if accuracy is not None else None,
            "average_net_after_cost_pct": round(average_net, 6) if average_net is not None else None,
            "first_decision_date": rows[0]["decision_date"] if rows else None,
            "last_outcome_date": rows[-1]["outcome_date"] if rows else None,
        }

    split_index = int(len(records) * 0.6)
    development = records[:split_index]
    holdout = records[split_index:]
    overall = summary(records)
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "status": "OK",
        "scope": "RESEARCH_WALK_FORWARD_ONLY",
        "official_eligible": False,
        "target_symbol": "1321.T",
        "anti_leakage_policy": {
            "domestic_data": "decision_date_or_earlier",
            "overseas_fx_crypto_data": "strictly_before_decision_date",
            "outcome": "next_target_trading_session",
        },
        "assumed_round_trip_cost_pct": ROUND_TRIP_COST_PCT,
        **overall,
        "chronological_split": "first_60_percent_development_last_40_percent_holdout",
        "development_segment": summary(development),
        "holdout_segment": summary(holdout),
        "records_sha256": hashlib.sha256(
            json.dumps(
                records,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }


def main() -> None:
    data = pd.read_csv(PRICES, dtype={"Code": str})
    report = build_report(data)
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        key: report[key]
        for key in (
            "status", "scope", "samples", "directional_samples",
            "accuracy_pct", "average_net_after_cost_pct",
        )
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
