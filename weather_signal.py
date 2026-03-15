import pandas as pd
from datetime import datetime
import json

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

df = pd.read_csv("prices.csv")
df["Code"] = df["Code"].astype(str)

targets = {
    "13060": "日経ETF",
    "13210": "TOPIX",
    "14750": "半導体ETF"
}

score = 0
reasons = []
details = []
cards = []

signals = {
    "up_5d": 0,
    "down_5d": 0,
    "above_25": 0,
    "below_25": 0,
    "above_200": 0,
    "below_200": 0,
    "usd_jpy_support": False,
    "us_weak": False,
    "us_strong": False,
    "semi_us_weak": False,
    "semi_us_strong": False,
    "risk_off": False,
    "risk_on": False,
}

for code, name in targets.items():

    sub = df[df["Code"] == code].copy()

    if len(sub) < 200:
        reasons.append(f"{name} データ不足 0")
        continue

    sub = sub.sort_values("Date")
    close = sub["C"].astype(float)

    last_close = close.iloc[-1]
    change5 = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100
    ma25 = close.tail(25).mean()
    ma200 = close.tail(200).mean()
    rsi14 = calc_rsi(close, 14).iloc[-1]

    local_score = 0

    if change5 > 1:
        local_score += 1
        reasons.append(f"{name} 5日上昇 +1")
        signals["up_5d"] += 1
    elif change5 < -1:
        local_score -= 1
        reasons.append(f"{name} 5日下降 -1")
        signals["down_5d"] += 1
    else:
        reasons.append(f"{name} 5日横ばい 0")

    if last_close > ma25:
        local_score += 1
        reasons.append(f"{name} 25日線上 +1")
        signals["above_25"] += 1
    else:
        local_score -= 1
        reasons.append(f"{name} 25日線下 -1")
        signals["below_25"] += 1

    if last_close > ma200:
        local_score += 1
        reasons.append(f"{name} 200日線上 +1")
        signals["above_200"] += 1
    else:
        local_score -= 1
        reasons.append(f"{name} 200日線下 -1")
        signals["below_200"] += 1

    score += local_score

    details.append(
        f"{name}: 終値={last_close:.2f}, 5日騰落率={change5:.2f}%, 25MA={ma25:.2f}, 200MA={ma200:.2f}, RSI={rsi14:.1f}"
    )

    cards.append({
        "name": name,
        "price": round(last_close,2),
        "change": round(change5,2),
        "ma25": round(ma25,2),
        "ma200": round(ma200,2),
        "rsi": round(rsi14,1)
    })

vix = df[df["Code"] == "66660"].copy()

risk_level = "MEDIUM"

if len(vix) >= 1:

    vix = vix.sort_values("Date")
    vix_last = float(vix["C"].iloc[-1])

    if vix_last >= 25:
        score -= 1
        risk_level = "HIGH"
        reasons.append("VIX 高い -1")

    elif vix_last <= 15:
        score += 1
        risk_level = "LOW"
        reasons.append("VIX 低い +1")

    details.append(f"VIX: 終値={vix_last:.2f}")

    cards.append({
        "name":"VIX",
        "price":round(vix_last,2),
        "change":"-",
        "ma25":"-",
        "ma200":"-",
        "rsi":"-"
    })

if score >= 6:
    weather = "赤"
elif score <= -6:
    weather = "青"
else:
    weather = "黄"

now = datetime.now().strftime("%Y-%m-%d %H:%M")

text = f"""天気：JP={weather}
スコア：{score}
危険度：{risk_level}

理由
"""

for r in reasons:
    text += r + "\n"

text += "\n詳細\n"

for d in details:
    text += d + "\n"

text += f"\n更新 {now}"

with open("latest_weather.txt","w") as f:
    f.write(text)

with open("cards.json","w") as f:
    json.dump(cards,f,ensure_ascii=False,indent=2)

print(text)
