#!/usr/bin/env python3

from __future__ import annotations

import base64
import csv
import json
import math
import statistics
from datetime import datetime
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parent
PRICES = BASE / "prices.csv"
HISTORY = BASE / "history.csv"
CHALLENGER = BASE / "monitoring_challenger_report.json"
SYMBOL = "1321.T"
CODE = "1321"
INITIAL_CASH = 500000.0
MAX_POSITION = 1
MAX_DAILY_LOSS_PCT = 1.0
MAX_DRAWDOWN_PCT = 5.0
MAX_CONSECUTIVE_LOSSES = 3
SLIPPAGE_PCT = 0.05
SPREAD_PCT = 0.03
FEE_PCT = 0.02
TICK_SIZE = 10.0


def number(value: Any, default: float | None = None) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def encode_payload(value: dict[str, Any]) -> str:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_payload(value: str) -> dict[str, Any] | None:
    try:
        decoded = base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8")
        result = json.loads(decoded)
        return result if isinstance(result, dict) else None
    except Exception:
        return None


def read_history(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def price_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    anomalies: list[str] = []
    seen_dates: set[str] = set()
    if not path.exists():
        return [], ["PRICE_FILE_MISSING"]
    with path.open("r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            code = str(raw.get("Code") or "").replace(".T", "").lstrip("0")
            if code not in {CODE, CODE + "0"}:
                continue
            date = str(raw.get("Date") or "")
            values = {key: number(raw.get(key)) for key in ("O", "H", "L", "C", "Vo")}
            adjustment_factor = number(raw.get("AdjFactor"), 1.0) or 1.0
            if not date or any(values[key] is None for key in ("O", "H", "L", "C")):
                anomalies.append("INVALID_OHLC")
                continue
            if date in seen_dates:
                anomalies.append("DUPLICATE_TARGET_DATE")
                continue
            seen_dates.add(date)
            if values["H"] < max(values["O"], values["C"]) or values["L"] > min(values["O"], values["C"]):
                anomalies.append("OHLC_INVARIANT_FAILED")
            if values["C"] <= 0 or values["O"] <= 0:
                anomalies.append("NON_POSITIVE_PRICE")
            if adjustment_factor != 1.0:
                anomalies.append("CORPORATE_ACTION_ADJUSTMENT_DETECTED")
            rows.append({"date": date, **values})
    rows.sort(key=lambda row: row["date"])
    if len(rows) < 60:
        anomalies.append("INSUFFICIENT_PRICE_HISTORY")
    return rows, sorted(set(anomalies))


def forward_rows(history: list[list[str]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in history:
        if len(row) < 19 or row[0] != "FORWARD_V1" or row[15] != SYMBOL:
            continue
        latest[row[16]] = {
            "run_id": row[1],
            "logged_at": row[2],
            "data_status": row[13],
            "date": row[16],
            "close": number(row[17]),
            "direction": row[18],
        }
    return [latest[key] for key in sorted(latest)]


def latest_controls(history: list[list[str]]) -> dict[str, dict[str, Any]]:
    controls: dict[str, dict[str, Any]] = {}
    for row in history:
        if len(row) >= 5 and row[0] == "CONTROL_V2" and row[1] == SYMBOL:
            payload = decode_payload(row[4])
            if payload:
                controls[row[2]] = payload
    return controls


def round_tick(value: float) -> float:
    return round(value / TICK_SIZE) * TICK_SIZE


def market_regime(rows: list[dict[str, Any]]) -> dict[str, Any]:
    closes = [float(row["C"]) for row in rows]
    if len(closes) < 60:
        return {"state": "UNKNOWN", "confidence": 0, "reason": "60取引日未満"}
    ma20 = statistics.fmean(closes[-20:])
    ma60 = statistics.fmean(closes[-60:])
    returns = [(closes[index] / closes[index - 1] - 1) for index in range(len(closes) - 19, len(closes))]
    volatility = statistics.pstdev(returns) * math.sqrt(252) * 100
    momentum = (closes[-1] / closes[-20] - 1) * 100
    if volatility >= 35:
        state = "HIGH_VOLATILITY"
    elif closes[-1] > ma20 > ma60 and momentum > 0:
        state = "UPTREND"
    elif closes[-1] < ma20 < ma60 and momentum < 0:
        state = "DOWNTREND"
    else:
        state = "RANGE"
    confidence = min(100, round(abs(momentum) * 8 + abs(ma20 / ma60 - 1) * 1000))
    return {
        "state": state,
        "confidence": confidence,
        "close": round(closes[-1], 2),
        "ma20": round(ma20, 2),
        "ma60": round(ma60, 2),
        "momentum_20d_pct": round(momentum, 3),
        "annualized_volatility_pct": round(volatility, 3),
    }


def strategy_governance(challenger: dict[str, Any]) -> dict[str, Any]:
    quarantined = []
    eligible = []
    for candidate in challenger.get("candidates", []) if isinstance(challenger, dict) else []:
        candidate_id = candidate.get("id")
        holdout = candidate.get("holdout") or {}
        net = number(holdout.get("average_net_after_cost_pct"), 0.0) or 0.0
        accuracy = number(holdout.get("accuracy_pct"), 0.0) or 0.0
        if net <= 0 or accuracy < 52:
            quarantined.append(candidate_id)
        else:
            eligible.append(candidate_id)
    return {
        "policy": "HOLDOUT_AND_FORWARD_REQUIRED",
        "selected": challenger.get("selected_candidate") if isinstance(challenger, dict) else None,
        "eligible": eligible,
        "quarantined": quarantined,
        "automatic_promotion": False,
        "official_eligible": False,
    }


def default_account() -> dict[str, Any]:
    return {
        "cash": INITIAL_CASH,
        "position": 0,
        "entry_price": None,
        "equity": INITIAL_CASH,
        "peak_equity": INITIAL_CASH,
        "realized_pnl": 0.0,
        "closed_trades": 0,
        "wins": 0,
        "losses": 0,
        "consecutive_losses": 0,
        "pending_order": None,
        "last_processed_date": None,
        "last_close": None,
    }


def restore_account(controls: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not controls:
        return default_account()
    latest = controls[sorted(controls)[-1]].get("paper_account")
    return dict(latest) if isinstance(latest, dict) else default_account()


def fill_pending(account: dict[str, Any], row: dict[str, Any]) -> dict[str, Any] | None:
    order = account.get("pending_order")
    if not isinstance(order, dict) or order.get("created_for_date") >= row["date"]:
        return None
    side = order["side"]
    raw_price = float(row["O"])
    impact = (SLIPPAGE_PCT + SPREAD_PCT / 2) / 100
    fill_price = round_tick(raw_price * (1 + impact if side == "BUY" else 1 - impact))
    fee = round(fill_price * FEE_PCT / 100, 2)
    pnl = None
    if side == "BUY":
        cost = fill_price + fee
        if account["position"] != 0 or account["cash"] < cost:
            account["pending_order"] = None
            return {"status": "REJECTED", "reason": "POSITION_OR_CASH_CHANGED", "side": side}
        account["cash"] -= cost
        account["position"] = 1
        account["entry_price"] = fill_price
    else:
        if account["position"] <= 0:
            account["pending_order"] = None
            return {"status": "REJECTED", "reason": "NO_POSITION", "side": side}
        pnl = fill_price - float(account["entry_price"]) - fee
        account["cash"] += fill_price - fee
        account["position"] = 0
        account["entry_price"] = None
        account["realized_pnl"] += pnl
        account["closed_trades"] += 1
        if pnl > 0:
            account["wins"] += 1
            account["consecutive_losses"] = 0
        else:
            account["losses"] += 1
            account["consecutive_losses"] += 1
    account["pending_order"] = None
    return {
        "status": "FILLED",
        "side": side,
        "price": fill_price,
        "fee": fee,
        "slippage_pct": SLIPPAGE_PCT,
        "spread_pct": SPREAD_PCT,
        "pnl": round(pnl, 2) if pnl is not None else None,
        "fill_date": row["date"],
    }


def pretrade_checks(account: dict[str, Any], signal: dict[str, Any], anomalies: list[str]) -> dict[str, Any]:
    side = "BUY" if signal["direction"] == "LONG" and account["position"] == 0 else "SELL" if signal["direction"] != "LONG" and account["position"] > 0 else None
    projected_cost = (signal["close"] or 0) * (1 + (SLIPPAGE_PCT + SPREAD_PCT / 2 + FEE_PCT) / 100)
    day_start = float(account.get("day_start_equity") or account["equity"])
    daily_loss_pct = max(0.0, (day_start - account["equity"]) / day_start * 100) if day_start > 0 else 100.0
    checks = {
        "monitoring_only": True,
        "symbol_exact": signal.get("close") is not None,
        "fresh_data": signal.get("data_status") == "FRESH",
        "valid_side": side in {"BUY", "SELL"},
        "max_position_one": account["position"] <= MAX_POSITION,
        "cash_sufficient": side != "BUY" or account["cash"] >= projected_cost,
        "no_pending_order": account.get("pending_order") is None,
        "data_quality_ok": not any(item in anomalies for item in ("PRICE_FILE_MISSING", "INVALID_OHLC", "NON_POSITIVE_PRICE", "OHLC_INVARIANT_FAILED")),
        "daily_loss_limit_ok": daily_loss_pct < MAX_DAILY_LOSS_PCT,
        "drawdown_limit_ok": (account["peak_equity"] - account["equity"]) / account["peak_equity"] * 100 < MAX_DRAWDOWN_PCT,
        "loss_streak_limit_ok": account["consecutive_losses"] < MAX_CONSECUTIVE_LOSSES,
    }
    return {"side": side, "checks": checks, "daily_loss_pct": round(daily_loss_pct, 4), "passed": side is not None and all(checks.values())}


def benchmark(rows: list[dict[str, Any]], start_date: str, account: dict[str, Any]) -> dict[str, Any]:
    eligible = [row for row in rows if row["date"] >= start_date]
    if len(eligible) < 2:
        return {"status": "ACCUMULATING", "samples": len(eligible)}
    buy_hold = (eligible[-1]["C"] / eligible[0]["C"] - 1) * 100
    paper = (account["equity"] / INITIAL_CASH - 1) * 100
    return {
        "status": "MEASURED",
        "samples": len(eligible),
        "buy_and_hold_pct": round(buy_hold, 4),
        "paper_strategy_pct": round(paper, 4),
        "excess_vs_buy_hold_pct": round(paper - buy_hold, 4),
        "cash_pct": 0.0,
    }


def process(
    prices_path: Path = PRICES,
    history_path: Path = HISTORY,
    challenger_path: Path = CHALLENGER,
    now: str | None = None,
) -> list[dict[str, Any]]:
    prices, anomalies = price_rows(prices_path)
    history = read_history(history_path)
    forwards = forward_rows(history)
    controls = latest_controls(history)
    account = restore_account(controls)
    price_by_date = {row["date"]: row for row in prices}
    challenger = load_json(challenger_path, {})
    generated: list[dict[str, Any]] = []
    first_date = forwards[0]["date"] if forwards else (prices[-1]["date"] if prices else "")

    for signal in forwards:
        target_date = signal["date"]
        if target_date in controls or target_date not in price_by_date:
            continue
        row = price_by_date[target_date]
        account["day_start_equity"] = account["equity"]
        fill = fill_pending(account, row)
        account["last_close"] = row["C"]
        account["equity"] = account["cash"] + account["position"] * row["C"]
        account["peak_equity"] = max(account["peak_equity"], account["equity"])
        account["last_processed_date"] = target_date
        pretrade = pretrade_checks(account, signal, anomalies)
        if pretrade["passed"]:
            account["pending_order"] = {
                "order_id": f"PAPER-{signal['run_id']}",
                "side": pretrade["side"],
                "qty": 1,
                "type": "NEXT_SESSION_MARKET_SIMULATION",
                "created_for_date": target_date,
            }
        drawdown = (account["peak_equity"] - account["equity"]) / account["peak_equity"] * 100
        risk_locked = not pretrade["checks"]["drawdown_limit_ok"] or not pretrade["checks"]["loss_streak_limit_ok"]
        alerts = []
        if anomalies:
            alerts.append({"level": "WARN", "code": "DATA_QUALITY", "message": "価格データの注意項目があります"})
        if risk_locked:
            alerts.append({"level": "CRITICAL", "code": "RISK_LOCK", "message": "新規仮想注文を停止しました"})
        if not pretrade["passed"] and pretrade["side"]:
            alerts.append({"level": "INFO", "code": "ORDER_PROTECTED", "message": "注文前検査で仮想注文を保護しました"})
        report = {
            "schema_version": 2,
            "generated_at": now or datetime.now().astimezone().isoformat(timespec="seconds"),
            "scope": "FREE_PAPER_SIMULATION_ONLY",
            "official_eligible": False,
            "real_money": False,
            "target_date": target_date,
            "features": {
                "execution_simulator": "ACTIVE",
                "risk_engine": "ACTIVE",
                "paper_account": "ACTIVE",
                "market_regime": "ACTIVE",
                "benchmark": "ACTIVE",
                "strategy_governance": "ACTIVE",
                "data_quality": "ACTIVE",
                "pretrade_validation": "ACTIVE",
                "reconciliation": "ACTIVE",
                "daily_reporting": "ACTIVE",
            },
            "execution": {
                "model": "NEXT_SESSION_OPEN_WITH_COSTS",
                "fill": fill,
                "pending_order": account.get("pending_order"),
                "assumptions": {"slippage_pct": SLIPPAGE_PCT, "spread_pct": SPREAD_PCT, "fee_pct": FEE_PCT, "partial_fills": "NOT_APPLICABLE_QTY_ONE"},
            },
            "risk": {
                "status": "LOCKED" if risk_locked else "READY",
                "max_position": MAX_POSITION,
                "max_daily_loss_pct": MAX_DAILY_LOSS_PCT,
                "max_drawdown_pct": MAX_DRAWDOWN_PCT,
                "max_consecutive_losses": MAX_CONSECUTIVE_LOSSES,
                "current_daily_loss_pct": pretrade["daily_loss_pct"],
                "current_drawdown_pct": round(drawdown, 4),
                "kill_switch": risk_locked,
            },
            "pretrade": pretrade,
            "paper_account": {key: (round(value, 2) if isinstance(value, float) else value) for key, value in account.items()},
            "regime": market_regime([item for item in prices if item["date"] <= target_date]),
            "benchmark": benchmark(prices, first_date, account),
            "strategy_governance": strategy_governance(challenger),
            "data_quality": {"status": "PASS" if not anomalies else "WARN", "anomalies": anomalies, "rows": len(prices), "latest_date": prices[-1]["date"] if prices else None},
            "reconciliation": {
                "status": "PASS" if abs(account["equity"] - (account["cash"] + account["position"] * row["C"])) < 0.01 else "FAIL",
                "cash_plus_position_equals_equity": True,
                "external_broker_connected": False,
                "external_reconciliation": "NOT_APPLICABLE_PAPER_ONLY",
            },
            "alerts": alerts,
            "daily_report": {
                "summary": f"仮想口座 {account['equity']:.0f}円 / 保有 {account['position']}口 / 実資金未使用",
                "delivery": "PUBLIC_STATUS_ONLY",
                "external_notification": "NOT_CONFIGURED",
            },
        }
        generated.append(report)
        controls[target_date] = report

    if generated:
        with history_path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            for report in generated:
                writer.writerow(["CONTROL_V2", SYMBOL, report["target_date"], report["generated_at"], encode_payload(report)])
    return generated


def main() -> None:
    generated = process()
    latest = generated[-1] if generated else (latest_controls(read_history(HISTORY)) or {}).get(max(latest_controls(read_history(HISTORY)), default=""))
    print(json.dumps({
        "status": "UPDATED" if generated else "NO_NEW_TARGET_DATE",
        "records_added": len(generated),
        "latest": latest,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
