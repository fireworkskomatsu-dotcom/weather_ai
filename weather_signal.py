import pandas as pd
from datetime import datetime
import json
from pathlib import Path

def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def get_close_stats(df, code):
    sub = df[df["Code"] == code].copy()
    if len(sub) < 25:
        return None
    sub = sub.sort_values("Date")
    close = sub["C"].astype(float)
    last = close.iloc[-1]
    change5 = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100
    ma25 = close.tail(25).mean()
    ma200 = close.tail(200).mean() if len(close) >= 200 else None
    rsi14 = calc_rsi(close, 14).iloc[-1] if len(close) >= 14 else None
    return {
        "last": last,
        "change5": change5,
        "ma25": ma25,
        "ma200": ma200,
        "rsi14": rsi14,
    }

df = pd.read_csv("prices.csv")
df["Code"] = df["Code"].astype(str)

targets = {
    "13060": "日経ETF",
    "13210": "TOPIX",
    "14750": "半導体ETF",
    "88880": "QQQ",
    "77770": "SOXX",
}

score = 0
reasons = []
details = []
cards = []

up_5d = 0
down_5d = 0
above_25 = 0
below_25 = 0
above_200 = 0
below_200 = 0

for code, name in targets.items():
    stats = get_close_stats(df, code)

    if stats is None:
        reasons.append(f"{name} データ不足 0")
        continue

    last_close = stats["last"]
    change5 = stats["change5"]
    ma25 = stats["ma25"]
    ma200 = stats["ma200"]
    rsi14 = stats["rsi14"]

    local_score = 0

    if change5 > 1:
        local_score += 1
        reasons.append(f"{name} 5日上昇 +1")
        up_5d += 1
    elif change5 < -1:
        local_score -= 1
        reasons.append(f"{name} 5日下降 -1")
        down_5d += 1
    else:
        reasons.append(f"{name} 5日横ばい 0")

    if last_close > ma25:
        local_score += 1
        reasons.append(f"{name} 25日線上 +1")
        above_25 += 1
    else:
        local_score -= 1
        reasons.append(f"{name} 25日線下 -1")
        below_25 += 1

    if ma200 is not None:
        if last_close > ma200:
            local_score += 1
            reasons.append(f"{name} 200日線上 +1")
            above_200 += 1
        else:
            local_score -= 1
            reasons.append(f"{name} 200日線下 -1")
            below_200 += 1

    score += local_score

    ma200_text = f"{ma200:.2f}" if ma200 is not None else "-"
    rsi_text = f"{rsi14:.1f}" if rsi14 is not None and pd.notna(rsi14) else "-"

    details.append(
        f"{name}: 終値={last_close:.2f}, 5日騰落率={change5:.2f}%, 25MA={ma25:.2f}, 200MA={ma200_text}, RSI={rsi_text}"
    )

    cards.append({
        "name": name,
        "price": round(last_close, 2),
        "change": round(change5, 2),
        "ma25": round(ma25, 2),
        "ma200": round(ma200, 2) if ma200 is not None else "-",
        "rsi": round(rsi14, 1) if rsi14 is not None and pd.notna(rsi14) else "-",
    })

risk_level = "MEDIUM"

# VIX
vix_stats = get_close_stats(df, "66660")
if vix_stats is not None:
    vix_last = vix_stats["last"]

    if vix_last >= 25:
        score -= 1
        risk_level = "HIGH"
        reasons.append("VIX 高い -1")
    elif vix_last <= 15:
        score += 1
        risk_level = "LOW"
        reasons.append("VIX 低い +1")
    else:
        reasons.append("VIX 中立 0")

    details.append(f"VIX: 終値={vix_last:.2f}")

    cards.append({
        "name": "VIX",
        "price": round(vix_last, 2),
        "change": "-",
        "ma25": "-",
        "ma200": "-",
        "rsi": "-",
    })
else:
    reasons.append("VIX データ不足 0")

# USDJPY
fx_stats = get_close_stats(df, "55550")
if fx_stats is not None:
    fx_last = fx_stats["last"]
    fx_change5 = fx_stats["change5"]

    if fx_change5 > 0.5:
        score += 1
        reasons.append("USDJPY 円安 +1")
    elif fx_change5 < -0.5:
        score -= 1
        reasons.append("USDJPY 円高 -1")
    else:
        reasons.append("USDJPY 中立 0")

    details.append(f"USDJPY: 終値={fx_last:.2f}, 5日変化={fx_change5:.2f}%")

    cards.append({
        "name": "USDJPY",
        "price": round(fx_last, 2),
        "change": round(fx_change5, 2),
        "ma25": "-",
        "ma200": "-",
        "rsi": "-",
    })

# BTC
btc_change5 = None
btc_stats = get_close_stats(df, "44440")
if btc_stats is not None:
    btc_last = btc_stats["last"]
    btc_change5 = btc_stats["change5"]

    details.append(f"BTC: 終値={btc_last:.2f}, 5日変化={btc_change5:.2f}%")

    cards.append({
        "name": "BTC",
        "price": round(btc_last, 2),
        "change": round(btc_change5, 2),
        "ma25": "-",
        "ma200": "-",
        "rsi": "-",
    })

if score >= 6:
    weather = "赤"
elif score <= -6:
    weather = "青"
else:
    weather = "黄"

if score >= 5:
    market_temp = "HOT"
elif score <= -5:
    market_temp = "COLD"
else:
    market_temp = "NORMAL"

comment_lines = []

if up_5d >= 2:
    comment_lines.append("短期は反発基調です。")
elif down_5d >= 2:
    comment_lines.append("短期は弱含みです。")
else:
    comment_lines.append("短期の方向感はまだ限定的です。")

if below_25 >= 2:
    comment_lines.append("25日線を下回る指数が多く、戻り売りに注意です。")
elif above_25 >= 2:
    comment_lines.append("25日線を上回る指数が多く、地合いは改善しています。")

if below_200 >= 2:
    comment_lines.append("長期トレンドはまだ弱いです。")
elif above_200 >= 2:
    comment_lines.append("長期トレンドは維持されています。")

if risk_level == "HIGH":
    comment_lines.append("VIXが高く、リスク管理が必要な地合いです。")
elif risk_level == "LOW":
    comment_lines.append("VIXは低く、投資家心理は安定しています。")

if score >= 5:
    trade_judgement = "押し目買い優勢"
elif score >= 2:
    trade_judgement = "強気寄りだが慎重"
elif score <= -5:
    trade_judgement = "戻り売り優勢"
elif score <= -2:
    trade_judgement = "弱気寄りで注意"
else:
    trade_judgement = "様子見・ノーポジ寄り"

# 上昇確率AI
prob_up = 50 + score * 5

if risk_level == "HIGH":
    prob_up -= 5
elif risk_level == "LOW":
    prob_up += 5

reason_text = " ".join(reasons)

if "USDJPY 円安 +1" in reason_text:
    prob_up += 3
if "QQQ 5日下降 -1" in reason_text:
    prob_up -= 3
if "SOXX 5日下降 -1" in reason_text:
    prob_up -= 3

if btc_change5 is not None:
    if btc_change5 > 1:
        prob_up += 2
    elif btc_change5 < -1:
        prob_up -= 2

prob_up = max(5, min(95, int(round(prob_up))))
prob_down = 100 - prob_up

ai_comment = " ".join(comment_lines)

now = datetime.now().strftime("%Y-%m-%d %H:%M")

text = f"""天気：JP={weather}
スコア：{score}
危険度：{risk_level}
市場温度：{market_temp}
売買判断：{trade_judgement}
上昇確率：{prob_up}%
下落確率：{prob_down}%

AIコメント
{ai_comment}

理由
"""

for r in reasons:
    text += r + "\n"

text += "\n詳細\n"
for d in details:
    text += d + "\n"

text += f"\n更新 {now}"

with open("latest_weather.txt", "w") as f:
    f.write(text)

with open("cards.json", "w") as f:
    json.dump(cards, f, ensure_ascii=False, indent=2)

history_path = Path("history.csv")
if not history_path.exists():
    with open("history.csv", "w") as f:
        f.write("datetime,weather,score,risk,temp,judgement,prob_up,prob_down\n")

with open("history.csv", "a") as f:
    f.write(f"{now},{weather},{score},{risk_level},{market_temp},{trade_judgement},{prob_up},{prob_down}\n")

print(text)
import datetime
import os

score = -5

history_file = "history.csv"

line = f"{datetime.date.today()},{score}\n"

if not os.path.exists(history_file):
    with open(history_file,"w") as f:
        f.write("date,score\n")

with open(history_file,"a") as f:
    f.write(line)
