#!/usr/bin/env python3

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parent
JST = ZoneInfo("Asia/Tokyo")

START_FILE = BASE / "official_account_start.json"
LEDGER_FILE = BASE / "official_trade_ledger.json"
OUT_FILE = BASE / "official_performance.json"

now = datetime.now(JST)

if START_FILE.exists():
    start = json.loads(START_FILE.read_text(encoding="utf-8"))
else:
    start = {
        "started_at": now.isoformat(timespec="seconds"),
        "initial_cash": 500000.0,
        "scope": "OFFICIAL_FORWARD_TEST_ONLY",
        "exclude": [
            "legacy trades",
            "manual tests",
            "backtests",
            "shadow trades",
            "old virtual account records"
        ]
    }
    START_FILE.write_text(
        json.dumps(start, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8"
    )

if LEDGER_FILE.exists():
    ledger = json.loads(LEDGER_FILE.read_text(encoding="utf-8"))
    if not isinstance(ledger, list):
        ledger = []
else:
    ledger = []
    LEDGER_FILE.write_text("[]\n", encoding="utf-8")

closed = [
    row for row in ledger
    if isinstance(row, dict)
    and row.get("status") == "CLOSED"
    and isinstance(row.get("realized_pnl"), (int, float))
]

wins = sum(1 for row in closed if row["realized_pnl"] > 0)
losses = sum(1 for row in closed if row["realized_pnl"] < 0)
flats = sum(1 for row in closed if row["realized_pnl"] == 0)

decisive = wins + losses
win_rate = round(wins / decisive * 100, 2) if decisive else None
total_pnl = round(sum(float(row["realized_pnl"]) for row in closed), 2)

out = {
    "updated_at": now.isoformat(timespec="seconds"),
    "scope": "OFFICIAL_FORWARD_TEST_ONLY",
    "started_at": start["started_at"],
    "initial_cash": float(start.get("initial_cash", 500000.0)),
    "closed_trades": len(closed),
    "wins": wins,
    "losses": losses,
    "flat_trades": flats,
    "win_rate": win_rate,
    "win_rate_available": decisive > 0,
    "total_realized_pnl": total_pnl,
    "legacy_data_excluded": True,
    "source": "official_trade_ledger.json"
}

OUT_FILE.write_text(
    json.dumps(out, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8"
)

print(json.dumps(out, ensure_ascii=False, indent=2))
