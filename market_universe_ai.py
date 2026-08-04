#!/usr/bin/env python3

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BASE = Path(__file__).resolve().parent
JST = ZoneInfo("Asia/Tokyo")

CARDS_FILE = BASE / "cards.json"
OUTPUT_FILE = BASE / "market_universe.json"
STATUS_FILE = BASE / "market_universe_status.json"

TRADE_SYMBOL = "1321.T"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def normalize_symbol(value: Any) -> str | None:
    if value in (None, ""):
        return None

    text = str(value).strip().upper()

    aliases = {
        "1321": "1321.T",
        "TYO:1321": "1321.T",
    }

    return aliases.get(text, text)


def first_value(
    row: dict[str, Any],
    keys: tuple[str, ...],
) -> Any:
    for key in keys:
        value = row.get(key)

        if value not in (None, ""):
            return value

    return None


def walk(value: Any, path: str = ""):
    if isinstance(value, dict):
        yield path, value

        for key, child in value.items():
            next_path = f"{path}.{key}" if path else key
            yield from walk(child, next_path)

    elif isinstance(value, list):
        for index, child in enumerate(value):
            next_path = f"{path}[{index}]"
            yield from walk(child, next_path)


cards = load_json(CARDS_FILE, [])
rows: list[dict[str, Any]] = []

seen: set[str] = set()

for source_path, row in walk(cards):
    if not isinstance(row, dict):
        continue

    symbol = normalize_symbol(
        first_value(
            row,
            (
                "symbol",
                "ticker",
                "code",
                "stock_code",
                "security_code",
            ),
        )
    )

    name = first_value(
        row,
        (
            "name",
            "title",
            "label",
            "display_name",
            "asset",
        ),
    )

    price = first_value(
        row,
        (
            "price",
            "last_price",
            "current_price",
            "close",
        ),
    )

    # 銘柄・名称・価格のどれも無い辞書は除外。
    if symbol is None and name is None and price is None:
        continue

    identity = symbol or f"NAME:{name}" or f"PATH:{source_path}"

    if identity in seen:
        continue

    seen.add(identity)

    is_trade_target = symbol == TRADE_SYMBOL

    rows.append(
        {
            "symbol": symbol,
            "name": name,
            "role": (
                "OFFICIAL_TRADE_TARGET"
                if is_trade_target
                else "MONITOR_ONLY"
            ),
            "trade_enabled": is_trade_target,
            "official_performance_enabled": is_trade_target,
            "learning_enabled": is_trade_target,
            "display_enabled": True,
            "source_path": source_path,
            "observed_price": price,
            "price_verification": (
                "OFFICIAL_FEED_REQUIRED"
                if is_trade_target
                else "UNVERIFIED_MONITOR_VALUE"
            ),
        }
    )

# cards.jsonに1321が無くても正式対象は必ず登録。
if not any(
    row.get("symbol") == TRADE_SYMBOL
    for row in rows
):
    rows.insert(
        0,
        {
            "symbol": TRADE_SYMBOL,
            "name": "NEXT FUNDS 日経225連動型上場投信",
            "role": "OFFICIAL_TRADE_TARGET",
            "trade_enabled": True,
            "official_performance_enabled": True,
            "learning_enabled": True,
            "display_enabled": True,
            "source_path": None,
            "observed_price": None,
            "price_verification": "OFFICIAL_FEED_REQUIRED",
        },
    )

trade_targets = [
    row
    for row in rows
    if row.get("trade_enabled") is True
]

if len(trade_targets) != 1:
    raise RuntimeError(
        "正式売買対象は1銘柄でなければなりません: "
        f"{len(trade_targets)}"
    )

if trade_targets[0].get("symbol") != TRADE_SYMBOL:
    raise RuntimeError(
        "正式売買対象が1321.Tではありません"
    )

out = {
    "updated_at": datetime.now(JST).isoformat(
        timespec="seconds"
    ),
    "policy": {
        "official_trade_symbol": TRADE_SYMBOL,
        "maximum_trade_symbols": 1,
        "monitor_symbols_may_not_write_official_ledger": True,
        "monitor_symbols_may_not_change_official_performance": True,
        "monitor_symbols_may_not_receive_learning_weights": True,
    },
    "summary": {
        "total_display_assets": len(rows),
        "official_trade_targets": len(trade_targets),
        "monitor_only_assets": sum(
            1
            for row in rows
            if row.get("role") == "MONITOR_ONLY"
        ),
        "unverified_monitor_values": sum(
            1
            for row in rows
            if row.get("price_verification")
            == "UNVERIFIED_MONITOR_VALUE"
        ),
    },
    "assets": rows,
}

OUTPUT_FILE.write_text(
    json.dumps(
        out,
        ensure_ascii=False,
        indent=2,
    ) + "\n",
    encoding="utf-8",
)

status = {
    "status": "OK",
    "updated_at": out["updated_at"],
    "official_trade_symbol": TRADE_SYMBOL,
    "official_trade_target_count": len(trade_targets),
    "monitor_only_count":
        out["summary"]["monitor_only_assets"],
    "display_asset_count":
        out["summary"]["total_display_assets"],
    "guard": "TRADE_AND_MONITORING_UNIVERSE_SEPARATED",
}

STATUS_FILE.write_text(
    json.dumps(
        status,
        ensure_ascii=False,
        indent=2,
    ) + "\n",
    encoding="utf-8",
)

print("===== MARKET UNIVERSE =====")
print("status: OK")
print("official_trade_symbol:", TRADE_SYMBOL)
print("official_trade_targets:", len(trade_targets))
print(
    "monitor_only_assets:",
    out["summary"]["monitor_only_assets"],
)
print(
    "display_assets:",
    out["summary"]["total_display_assets"],
)
print(
    "unverified_monitor_values:",
    out["summary"]["unverified_monitor_values"],
)
