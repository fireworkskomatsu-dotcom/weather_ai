import yfinance as yf
import pandas as pd

rows = []

def normalize_columns(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    return df

def add_symbol(symbol, code):
    try:
        df = yf.download(symbol, period="400d", interval="1d", auto_adjust=False, progress=False)
        if df is None or len(df) == 0:
            print("no data:", symbol)
            return

        df = df.reset_index()
        df = normalize_columns(df)

        needed = ["Date", "Open", "High", "Low", "Close", "Volume"]
        if not all(c in df.columns for c in needed):
            print("bad columns:", symbol, df.columns.tolist())
            return

        for _, r in df.iterrows():
            rows.append([
                pd.to_datetime(r["Date"]).strftime("%Y-%m-%d"),
                str(code),
                float(r["Open"]),
                float(r["High"]),
                float(r["Low"]),
                float(r["Close"]),
                0,
                0,
                float(r["Volume"]) if pd.notna(r["Volume"]) else 0.0,
                0.0,
                1.0,
                float(r["Open"]),
                float(r["High"]),
                float(r["Low"]),
                float(r["Close"]),
                float(r["Volume"]) if pd.notna(r["Volume"]) else 0.0,
            ])
        print("ok:", symbol, len(df))
    except Exception as e:
        print("error:", symbol, e)

# 日本ETF
add_symbol("1306.T", "13060")
add_symbol("1321.T", "13210")
add_symbol("1475.T", "14750")

# 米国・為替・ボラ・BTC
add_symbol("QQQ", "88880")
add_symbol("SOXX", "77770")
add_symbol("^VIX", "66660")
add_symbol("JPY=X", "55550")
add_symbol("BTC-USD", "44440")

cols = [
    "Date","Code","O","H","L","C","UL","LL","Vo","Va",
    "AdjFactor","AdjO","AdjH","AdjL","AdjC","AdjVo"
]

out = pd.DataFrame(rows, columns=cols).sort_values(["Code", "Date"])
out.to_csv("prices.csv", index=False)
print("saved prices.csv rows =", len(out))
print(out.groupby("Code").size())
