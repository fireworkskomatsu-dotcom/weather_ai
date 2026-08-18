#!/usr/bin/env python3

from __future__ import annotations

import hashlib
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

import fetch_prices_v2 as target


BASE = Path(__file__).resolve().parent


def digest(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


production_before = {
    name: digest(BASE / name)
    for name in (
        "prices.csv",
        "history.csv",
        "latest_weather.txt",
        "cards.json",
        "official_decision_log.jsonl",
        "virtual_account.json",
    )
}

today = date(2026, 8, 6)


def fake_download(
    symbol: str,
    **_kwargs: object,
) -> pd.DataFrame:
    dates = pd.date_range(today - timedelta(days=30), today, freq="D")
    base = 100.0 + next(
        index
        for index, (candidate, _code, _name) in enumerate(target.SYMBOLS)
        if candidate == symbol
    )
    return pd.DataFrame({
        "Open": [base] * len(dates),
        "High": [base + 2] * len(dates),
        "Low": [base - 2] * len(dates),
        "Close": [base + 1] * len(dates),
        "Volume": [1000.0] * len(dates),
    }, index=pd.DatetimeIndex(dates, name="Date"))


retry_calls = {"count": 0}


def transient_download(symbol: str, **kwargs: object) -> pd.DataFrame:
    retry_calls["count"] += 1
    if retry_calls["count"] < 3:
        raise ConnectionError("temporary test failure")
    return fake_download(symbol, **kwargs)


retry_rows = target.rows_for_symbol(
    target.SYMBOLS[0][0],
    target.SYMBOLS[0][1],
    transient_download,
)


fresh = target.build_prices(fake_download, today=today)


def one_nan_download(symbol: str, **kwargs: object) -> pd.DataFrame:
    frame = fake_download(symbol, **kwargs)
    frame.iloc[-2, frame.columns.get_loc("Close")] = float("nan")
    return frame


nan_tolerant = target.build_prices(one_nan_download, today=today)


def stale_download(symbol: str, **kwargs: object) -> pd.DataFrame:
    frame = fake_download(symbol, **kwargs)
    frame.index = frame.index - pd.Timedelta(days=30)
    return frame


stale_blocked = False
try:
    target.build_prices(stale_download, today=today)
except RuntimeError as error:
    stale_blocked = "期限切れ価格データ" in str(error)


checks = {
    "all_eight_symbols_present": fresh["Code"].nunique() == 8,
    "expected_schema": tuple(fresh.columns) == target.COLUMNS,
    "fresh_latest_date": fresh["Date"].max() == today.isoformat(),
    "positive_prices_only": bool((fresh[["O", "H", "L", "C"]] > 0).all().all()),
    "single_invalid_row_skipped": len(nan_tolerant) == len(fresh) - len(target.SYMBOLS),
    "transient_failure_retried": retry_calls["count"] == 3 and bool(retry_rows),
    "stale_download_blocked": stale_blocked,
    "production_files_unchanged": production_before == {
        name: digest(BASE / name) for name in production_before
    },
}

print("===== FREE PRICE FETCH E2E =====")
for key, passed in checks.items():
    print(f"  {key}: {passed}")
print("RESULT:", "PASS" if all(checks.values()) else "FAIL")

if not all(checks.values()):
    raise SystemExit(1)
