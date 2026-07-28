import json, os, datetime

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

decision = load_json("master_decision.json", {})
price_data = load_json("price_data.json", {})
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

cash = float(account.get("cash", 500000))
position = int(account.get("position", 0) or 0)
entry_price = account.get("entry_price")

action_taken = "NO_PRICE"

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

print(json.dumps({
    "status": "OK",
    "signal": signal,
    "price": price,
    "action_taken": action_taken,
    "cash": account["cash"],
    "position": position,
    "equity": account["equity"]
}, ensure_ascii=False, indent=2))
