#!/usr/bin/env python3

import json
import math
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo


BASE = Path(__file__).resolve().parent
JST = ZoneInfo("Asia/Tokyo")


def load_json(path: Path, default):
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def numeric(value):
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        value = float(value)

        if math.isfinite(value):
            return value

    return None


def extract_realized_pnl(record):
    if not isinstance(record, dict):
        return None

    direct_keys = (
        "realized_pnl",
        "realized_profit",
        "closed_pnl",
        "net_pnl",
        "pnl_pct",
        "return_pct",
        "profit_pct",
        "pnl",
        "profit",
    )

    for key in direct_keys:
        value = numeric(record.get(key))

        if value is not None:
            return value

    result = record.get("result")

    if isinstance(result, dict):
        for key in direct_keys:
            value = numeric(result.get(key))

            if value is not None:
                return value

    return None


dashboard_path = BASE / "web" / "dashboard.json"
dashboard = load_json(dashboard_path, {})

if not isinstance(dashboard, dict):
    raise SystemExit("web/dashboard.json is not a JSON object")

now = datetime.now(JST)
changes = []
warnings = []

# ------------------------------------------------------------
# 1. 時間限定理由の失効処理
# ------------------------------------------------------------

filter_data = dashboard.get("filter")

if not isinstance(filter_data, dict):
    filter_data = {}
    dashboard["filter"] = filter_data

reason = str(filter_data.get("reason") or "")
time_reason_expired = False

if "09:15" in reason and now.time() >= time(9, 15):
    time_reason_expired = True

if "寄り危険" in reason and now.time() >= time(9, 15):
    time_reason_expired = True

if time_reason_expired:
    diagnostics = load_json(
        BASE / "skip_diagnostics.json",
        {},
    )

    diagnosis = str(
        diagnostics.get("diagnosis")
        or "時間制限以外の最終判断を参照"
    )
    primary = str(
        diagnostics.get("primary_reason")
        or "詳細理由なし"
    )

    filter_data["reason"] = (
        f"{diagnosis}：{primary}"
    )
    filter_data["intraday_reason_expired"] = True
    filter_data["intraday_reason_checked_at"] = (
        now.isoformat(timespec="seconds")
    )

    changes.append(
        "expired_open_wait_reason_removed"
    )

# ------------------------------------------------------------
# 2. 実決済ログからのみ勝率を計算
# ------------------------------------------------------------

trade_log = load_json(BASE / "trade_log.json", [])

if isinstance(trade_log, dict):
    for key in ("trades", "records", "history", "items"):
        if isinstance(trade_log.get(key), list):
            trade_log = trade_log[key]
            break

if not isinstance(trade_log, list):
    trade_log = []

realized = []

for index, record in enumerate(trade_log):
    pnl = extract_realized_pnl(record)

    if pnl is None:
        continue

    realized.append(
        {
            "index": index,
            "pnl": pnl,
        }
    )

pnl_stats = dashboard.get("pnl_stats")

if not isinstance(pnl_stats, dict):
    pnl_stats = {}
    dashboard["pnl_stats"] = pnl_stats

old_trade_count = pnl_stats.get("trade_count")
old_win_rate = pnl_stats.get("win_rate")

closed_count = len(realized)
wins = sum(1 for row in realized if row["pnl"] > 0)
losses = sum(1 for row in realized if row["pnl"] < 0)
flats = sum(1 for row in realized if row["pnl"] == 0)

pnl_stats["trade_count"] = closed_count
pnl_stats["wins"] = wins
pnl_stats["losses"] = losses
pnl_stats["flat_trades"] = flats
pnl_stats["source"] = "trade_log.json_explicit_realized_pnl_only"
pnl_stats["raw_previous_trade_count"] = old_trade_count
pnl_stats["raw_previous_win_rate"] = old_win_rate

if wins + losses > 0:
    pnl_stats["win_rate"] = round(
        wins / (wins + losses) * 100,
        2,
    )
    pnl_stats["win_rate_available"] = True
else:
    pnl_stats["win_rate"] = 0.0
    pnl_stats["win_rate_available"] = False
    warnings.append(
        "明示的な実現損益を持つ勝敗データがないため、"
        "勝率は未算出です"
    )

if old_trade_count != closed_count:
    changes.append(
        f"trade_count_corrected:{old_trade_count}->{closed_count}"
    )

# ------------------------------------------------------------
# 3. データ整合性情報
# ------------------------------------------------------------

# OFFICIAL_PERFORMANCE_BEGIN
official = load_json(BASE / "official_performance.json", {})

if official:
    pnl_stats["trade_count"] = official.get("closed_trades", 0)
    pnl_stats["wins"] = official.get("wins", 0)
    pnl_stats["losses"] = official.get("losses", 0)
    pnl_stats["flat_trades"] = official.get("flat_trades", 0)
    pnl_stats["win_rate"] = official.get("win_rate")
    pnl_stats["win_rate_available"] = official.get(
        "win_rate_available", False
    )
    pnl_stats["total_realized_pnl"] = official.get(
        "total_realized_pnl", 0.0
    )
    pnl_stats["source"] = "official_trade_ledger.json"
    pnl_stats["scope"] = "OFFICIAL_FORWARD_TEST_ONLY"
    pnl_stats["legacy_data_excluded"] = True
# OFFICIAL_PERFORMANCE_END

dashboard["updated_at"] = now.strftime("%Y-%m-%d %H:%M")
dashboard["data_integrity"] = {
    "checked_at": now.isoformat(timespec="seconds"),
    "status": "WARNING" if warnings else "OK",
    "changes": changes,
    "warnings": warnings,
    "dashboard_source": "web/dashboard.json",
    "trade_log_records": len(trade_log),
    "realized_pnl_records": closed_count,
    "stale_root_dashboard_ignored": True,
}

save_json(dashboard_path, dashboard)

report = {
    "checked_at": now.isoformat(timespec="seconds"),
    "changes": changes,
    "warnings": warnings,
    "filter": dashboard.get("filter"),
    "pnl_stats": dashboard.get("pnl_stats"),
}

save_json(
    BASE / "dashboard_integrity.json",
    report,
)

print("===== Dashboard Integrity =====")
print("updated_at:", dashboard.get("updated_at"))
print("filter_reason:", filter_data.get("reason"))
print("trade_log_records:", len(trade_log))
print("realized_pnl_records:", closed_count)
print("trade_count:", pnl_stats.get("trade_count"))
print("wins:", wins)
print("losses:", losses)
print("flat_trades:", flats)
print("win_rate:", pnl_stats.get("win_rate"))
print(
    "win_rate_available:",
    pnl_stats.get("win_rate_available"),
)
print(
    "changes:",
    json.dumps(changes, ensure_ascii=False),
)
print(
    "warnings:",
    json.dumps(warnings, ensure_ascii=False),
)
