import yfinance as yf
import pandas as pd

rows = []
def add(symbol, code):
    df = yf.download(symbol, period="400d", interval="1d", progress=False)
    if df is None or len(df) == 0:
        print("no data:", symbol)
        return

    df = df.reset_index()

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]

    for _, r in df.iterrows():
        date_value = pd.to_datetime(r["Date"])
        if hasattr(date_value, "iloc"):
            date_value = date_value.iloc[0]

        rows.append([
            date_value.strftime("%Y-%m-%d"),
            str(code),
            float(r["Open"]),
            float(r["High"]),
            float(r["Low"]),
            float(r["Close"]),
            0, 0,
            float(r["Volume"]) if pd.notna(r["Volume"]) else 0.0,
            0,
            1,
            float(r["Open"]),
            float(r["High"]),
            float(r["Low"]),
            float(r["Close"]),
            float(r["Volume"]) if pd.notna(r["Volume"]) else 0.0
        ])
