import yfinance as yf
import pandas as pd

rows = []

def add(symbol, code):
    df = yf.download(symbol, period="400d", interval="1d", progress=False)
    if df is None or len(df) == 0:
        print("no data:", symbol)
        return

    df = df.reset_index()

    for _, r in df.iterrows():
        rows.append([
            r["Date"].strftime("%Y-%m-%d"),
            str(code),
            r["Open"],
            r["High"],
            r["Low"],
            r["Close"],
            0,0,
            r["Volume"],
            0,
            1,
            r["Open"],
            r["High"],
            r["Low"],
            r["Close"],
            r["Volume"]
        ])

add("1306.T","13060")
add("1321.T","13210")
add("1475.T","14750")
add("QQQ","88880")
add("SOXX","77770")
add("^VIX","66660")
add("JPY=X","55550")
add("BTC-USD","44440")

cols=[
"Date","Code","O","H","L","C","UL","LL","Vo","Va",
"AdjFactor","AdjO","AdjH","AdjL","AdjC","AdjVo"
]

pd.DataFrame(rows,columns=cols).to_csv("prices.csv",index=False)

print("prices saved")
