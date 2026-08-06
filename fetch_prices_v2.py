#!/usr/bin/env python3

from __future__ import annotations

import math
import os
import tempfile
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd
import yfinance as yf


BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "prices.csv"
MAX_DATA_AGE_DAYS = 7
PERIOD = "400d"
DOWNLOAD_ATTEMPTS = 3

SYMBOLS = (
    ("1306.T", "13060", "日経ETF"),
    ("1321.T", "13210", "日経225連動型ETF"),
    ("1475.T", "14750", "TOPIX ETF"),
    ("QQQ", "88880", "NASDAQ 100 ETF"),
    ("SOXX", "77770", "半導体ETF"),
    ("^VIX", "66660", "VIX"),
    ("JPY=X", "55550", "USDJPY"),
    ("BTC-USD", "44440", "BTCUSD"),
)

COLUMNS = (
    "Date", "Code", "O", "H", "L", "C", "UL", "LL",
    "Vo", "Va", "AdjFactor", "AdjO", "AdjH", "AdjL",
    "AdjC", "AdjVo",
)


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = [
            column[0] if isinstance(column, tuple) else column
            for column in frame.columns
        ]
    return frame


def valid_number(value: object) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"有限値ではありません: {value!r}")
    return number


def rows_for_symbol(
    symbol: str,
    code: str,
    downloader: Callable[..., pd.DataFrame],
) -> list[list[object]]:
    frame = None
    errors = []
    for attempt in range(1, DOWNLOAD_ATTEMPTS + 1):
        try:
            frame = downloader(
                symbol,
                period=PERIOD,
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=False,
                timeout=30,
            )
            if frame is not None and not frame.empty:
                break
            errors.append(f"attempt {attempt}: empty")
        except Exception as error:
            errors.append(
                f"attempt {attempt}: {type(error).__name__}: {error}"
            )

        if attempt < DOWNLOAD_ATTEMPTS:
            time.sleep(attempt * 2)

    if frame is None or frame.empty:
        raise RuntimeError(
            f"価格データがありません: {symbol}: " + " | ".join(errors)
        )

    frame = normalize_columns(frame.reset_index())
    required = ("Date", "Open", "High", "Low", "Close", "Volume")
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise RuntimeError(f"必須列がありません: {symbol}: {missing}")

    rows: list[list[object]] = []
    for _, record in frame.iterrows():
        market_date = pd.to_datetime(record["Date"])
        opened = valid_number(record["Open"])
        high = valid_number(record["High"])
        low = valid_number(record["Low"])
        close = valid_number(record["Close"])
        volume = (
            valid_number(record["Volume"])
            if pd.notna(record["Volume"])
            else 0.0
        )
        if min(opened, high, low, close) <= 0:
            raise RuntimeError(f"0以下の価格です: {symbol}: {market_date}")

        rows.append([
            market_date.strftime("%Y-%m-%d"),
            code,
            opened,
            high,
            low,
            close,
            0,
            0,
            volume,
            0.0,
            1.0,
            opened,
            high,
            low,
            close,
            volume,
        ])
    return rows


def build_prices(
    downloader: Callable[..., pd.DataFrame] = yf.download,
    today: date | None = None,
) -> pd.DataFrame:
    today = today or datetime.now().date()
    rows: list[list[object]] = []

    for symbol, code, _name in SYMBOLS:
        rows.extend(rows_for_symbol(symbol, code, downloader))

    output = pd.DataFrame(rows, columns=COLUMNS)
    if output.empty:
        raise RuntimeError("価格データが0件です")

    output["Code"] = output["Code"].astype(str)
    expected_codes = {code for _symbol, code, _name in SYMBOLS}
    actual_codes = set(output["Code"].unique())
    if actual_codes != expected_codes:
        raise RuntimeError(
            f"銘柄不足: expected={sorted(expected_codes)} actual={sorted(actual_codes)}"
        )

    freshness = output.groupby("Code")["Date"].max()
    stale = {}
    for code, latest_text in freshness.items():
        latest = pd.to_datetime(latest_text).date()
        age_days = (today - latest).days
        if age_days < 0 or age_days > MAX_DATA_AGE_DAYS:
            stale[code] = {
                "latest": latest.isoformat(),
                "age_days": age_days,
            }
    if stale:
        raise RuntimeError(f"期限切れ価格データ: {stale}")

    return output.sort_values(["Code", "Date"]).reset_index(drop=True)


def atomic_save_csv(frame: pd.DataFrame, path: Path) -> None:
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
        text=True,
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        frame.to_csv(temporary, index=False)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> None:
    output = build_prices()
    atomic_save_csv(output, OUTPUT)
    latest = output.groupby("Code")["Date"].max().to_dict()
    print("prices saved")
    print("rows:", len(output))
    print("symbols:", len(latest))
    print("latest:", latest)


if __name__ == "__main__":
    main()
