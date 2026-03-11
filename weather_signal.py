import pandas as pd

df = pd.read_csv("prices.csv")
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values(["Code", "Date"]).copy()

results = []

for code, g in df.groupby("Code"):
    g = g.sort_values("Date").copy()

    g["ma5"] = g["AdjC"].rolling(5).mean()
    g["mom5"] = g["AdjC"] - g["AdjC"].shift(5)
    g["candle"] = g["AdjC"] - g["AdjO"]

    latest = g.iloc[-1]
    signal = "黄"

    if pd.notna(latest["ma5"]) and pd.notna(latest["mom5"]):
        score_up = 0
        score_down = 0

        if latest["AdjC"] > latest["ma5"]:
            score_up += 1
        elif latest["AdjC"] < latest["ma5"]:
            score_down += 1

        if latest["candle"] > 0:
            score_up += 1
        elif latest["candle"] < 0:
            score_down += 1

        if latest["mom5"] > 0:
            score_up += 1
        elif latest["mom5"] < 0:
            score_down += 1

        if score_up >= 2:
            signal = "青"
        elif score_down >= 2:
            signal = "赤"

    results.append((str(code)[:4], signal))

blue_codes = [code for code, s in results if s == "青"]
red_codes = [code for code, s in results if s == "赤"]

if len(blue_codes) >= 2:
    print(f"天気：JP=青 | 実行={','.join(blue_codes)}")
elif len(red_codes) >= 2:
    print(f"天気：JP=赤 | 実行={','.join(red_codes)}")
else:
    print("天気：JP=黄")

print("詳細:", results)
