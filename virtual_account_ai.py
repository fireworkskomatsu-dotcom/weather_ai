import json, os, datetime

from virtual_account_status_ai import publish_virtual_account_status

def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

now = datetime.datetime.now().isoformat(timespec="seconds")

def parse_time(value):
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed
    except (TypeError, ValueError):
        return None

def is_fresh(value, maximum_hours=24):
    parsed = parse_time(value)
    if parsed is None:
        return False
    age = datetime.datetime.now().astimezone() - parsed
    return datetime.timedelta(0) <= age <= datetime.timedelta(hours=maximum_hours)

decision = load_json("master_decision.json", {})
price_data = load_json("price_data.json", {})
price_config = load_json("price_provider_config.json", {})
price_status = load_json("price_provider_status.json", {})
canonical_price = load_json("canonical_price.json", {})
account = load_json("virtual_account.json", {
    "cash": 500000,
    "position": 0,
    "entry_price": None,
    "equity": 500000,
    "last_action": "INIT",
    "updated_at": now,
    "history": []
})

trade_log = load_json("trade_log.json", [])

signal = (
    decision.get("final_decision")
    or decision.get("decision")
    or decision.get("action")
    or "SKIP"
)

signal = str(signal).upper()

price = (
    decision.get("price")
    or decision.get("current_price")
    or price_data.get("price")
    or price_data.get("close")
    or price_data.get("current_price")
)

try:
    price = float(price)
except Exception:
    price = None

isolated_test = os.environ.get("WEATHER_AI_ISOLATED_TEST") == "1"
canonical_value = (
    canonical_price.get("price")
    or canonical_price.get("current_price")
    or canonical_price.get("last_price")
)
try:
    canonical_value = float(canonical_value)
except (TypeError, ValueError):
    canonical_value = None

decision_time = (
    decision.get("updated_at")
    or decision.get("generated_at")
    or decision.get("time")
    or decision.get("market_time")
)
canonical_time = (
    canonical_price.get("fetched_at")
    or canonical_price.get("market_time")
    or canonical_price.get("updated_at")
)
decision_fresh = is_fresh(decision_time)
canonical_fresh = is_fresh(canonical_time)

official_price_eligible = (
    price_config.get("mode") == "OFFICIAL"
    and price_config.get("provider") not in (None, "", "DISABLED")
    and price_status.get("status") == "OK"
    and canonical_price.get("official_eligible") is True
    and canonical_price.get("symbol") == "1321.T"
    and canonical_value is not None
    and canonical_value > 0
    and decision.get("symbol") == "1321.T"
    and decision_fresh
    and canonical_fresh
)

if not isolated_test:
    price = canonical_value if official_price_eligible else None

cash = float(account.get("cash", 500000))
position = int(account.get("position", 0) or 0)
entry_price = account.get("entry_price")

action_taken = (
    "NO_PRICE"
    if isolated_test or official_price_eligible
    else "BLOCKED_UNVERIFIED_OFFICIAL_PRICE"
)

if price is not None:
    action_taken = "HOLD"

    # BUY / LONG
    if signal in ["BUY", "LONG", "ENTRY_LONG"] and position == 0:
        qty = 1
        if cash >= price * qty:
            cash -= price * qty
            position = qty
            entry_price = price
            action_taken = "BUY"
            trade_log.append({
                "time": now,
                "action": "BUY",
                "price": price,
                "qty": qty,
                "reason": signal
            })
        else:
            action_taken = "BUY_BLOCKED_NO_CASH"

    # SELL / EXIT
    elif signal in ["SELL", "EXIT", "CLOSE", "EXIT_LONG"] and position > 0:
        qty = position
        pnl = (price - float(entry_price)) * qty if entry_price else 0
        cash += price * qty
        position = 0
        entry_price = None
        action_taken = "SELL"
        trade_log.append({
            "time": now,
            "action": "SELL",
            "price": price,
            "qty": qty,
            "pnl": pnl,
            "reason": signal
        })

    # SHORTは仮想口座では一旦記録のみ
    elif signal in ["SHORT", "SELL_SHORT", "ENTRY_SHORT"]:
        action_taken = "SHORT_SIGNAL_RECORDED_ONLY"
        trade_log.append({
            "time": now,
            "action": "SHORT_SIGNAL_ONLY",
            "price": price,
            "qty": 0,
            "reason": signal
        })

    elif signal == "SKIP":
        action_taken = "SKIP_NO_TRADE"

equity = cash + (position * price if price is not None else 0)

account.update({
    "cash": round(cash, 2),
    "position": position,
    "entry_price": entry_price,
    "last_price": price,
    "equity": round(equity, 2),
    "last_signal": signal,
    "last_action": action_taken,
    "price_verification": (
        "ISOLATED_TEST"
        if isolated_test
        else (
            "OFFICIAL_ELIGIBLE"
            if official_price_eligible
            else "BLOCKED"
        )
    ),
    "decision_verification": (
        "ISOLATED_TEST"
        if isolated_test
        else (
            "FRESH_OFFICIAL"
            if decision_fresh and canonical_fresh
            else "BLOCKED_STALE_OR_MISSING_TIME"
        )
    ),
    "updated_at": now
})

account.setdefault("history", [])
account["history"].append({
    "time": now,
    "signal": signal,
    "price": price,
    "cash": round(cash, 2),
    "position": position,
    "equity": round(equity, 2),
    "action": action_taken
})

account["history"] = account["history"][-300:]

save_json("virtual_account.json", account)
save_json("trade_log.json", trade_log[-1000:])
publish_virtual_account_status()

print(json.dumps({
    "status": "OK",
    "signal": signal,
    "price": price,
    "action_taken": action_taken,
    "cash": account["cash"],
    "position": position,
    "equity": account["equity"]
}, ensure_ascii=False, indent=2))
