import pandas as pd

df = pd.read_csv("prices.csv")
df["Date"] = pd.to_datetime(df["Date"])
df = df.sort_values(["Code", "Date"]).copy()

target_codes = ["1306", "1321"]

results = []

for raw_code, g in df.groupby("Code"):
    code = str(raw_code)[:4]
    if code not in target_codes:
        continue

    g = g.sort_values("Date").copy()

    g["ma20"] = g["AdjC"].rolling(20).mean()
    g["ret5"] = g["AdjC"] / g["AdjC"].shift(5) - 1.0

    latest = g.iloc[-1]

    signal = "黄"

    if pd.notna(latest["ma20"]) and pd.notna(latest["ret5"]):
        is_above_ma20 = latest["AdjC"] > latest["ma20"]
        is_positive_5d = latest["ret5"] > 0

        is_below_ma20 = latest["AdjC"] < latest["ma20"]
        is_negative_5d = latest["ret5"] < 0

        if is_above_ma20 and is_positive_5d:
            signal = "青"
        elif is_below_ma20 and is_negative_5d:
            signal = "赤"

    results.append((code, signal, round(float(latest["AdjC"]), 2), round(float(latest["ret5"] * 100), 2)))

blue_codes = [code for code, signal, _, _ in results if signal == "青"]
red_codes = [code for code, signal, _, _ in results if signal == "赤"]

if len(blue_codes) == 2:
    print("天気：JP=青")
elif len(red_codes) == 2:
    print("天気：JP=赤")
else:
    print("天気：JP=黄")

print("詳細:")
for code, signal, price, ret5 in results:
    print(f"{code}: {signal}, 終値={price}, 5日騰落率={ret5}%")
