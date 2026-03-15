import pandas as pd
from datetime import datetime

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

signals = {
    "up_5d": 0,
    "down_5d": 0,
    "above_25": 0,
    "below_25": 0,
    "usd_jpy_support": False,
    "us_weak": False,
    "us_strong": False,
}

for code, name in targets.items():
    sub = df[df["Code"] == code].copy()
    if len(sub) < 25:
        reasons.append(f"{name} データ不足 0")
        continue

    sub = sub.sort_values("Date")
    close = sub["C"].astype(float)

    last_close = close.iloc[-1]
    change5 = (close.iloc[-1] - close.iloc[-5]) / close.iloc[-5] * 100
    ma25 = close.tail(25).mean()

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

    score += local_score

    details.append(
        f"{name}: 終値={last_close:.2f}, 5日騰落率={change5:.2f}%, 25MA={ma25:.2f}"
    )

# ドル円
fx = df[df["Code"] == "99990"].copy()
if len(fx) >= 5:
    fx = fx.sort_values("Date")
    fx_close = fx["C"].astype(float)

    fx_last = fx_close.iloc[-1]
    fx_change5 = (fx_close.iloc[-1] - fx_close.iloc[-5]) / fx_close.iloc[-5] * 100

    if fx_change5 > 0.5:
        score += 1
        reasons.append("ドル円 円安 +1")
        signals["usd_jpy_support"] = True
    elif fx_change5 < -0.5:
        score -= 1
        reasons.append("ドル円 円高 -1")
    else:
        reasons.append("ドル円 横ばい 0")

    details.append(f"ドル円: 終値={fx_last:.2f}, 5日変化={fx_change5:.2f}%")
else:
    reasons.append("ドル円 データ不足 0")

# QQQ
us = df[df["Code"] == "88880"].copy()
if len(us) >= 5:
    us = us.sort_values("Date")
    us_close = us["C"].astype(float)

    us_last = us_close.iloc[-1]
    us_change5 = (us_close.iloc[-1] - us_close.iloc[-5]) / us_close.iloc[-5] * 100

    if us_change5 > 1:
        score += 1
        reasons.append("QQQ 上昇 +1")
        signals["us_strong"] = True
    elif us_change5 < -1:
        score -= 1
        reasons.append("QQQ 下降 -1")
        signals["us_weak"] = True
    else:
        reasons.append("QQQ 横ばい 0")

    details.append(f"QQQ: 終値={us_last:.2f}, 5日変化={us_change5:.2f}%")
else:
    reasons.append("QQQ データ不足 0")

if score >= 4:
    weather = "赤"
elif score <= -4:
    weather = "青"
else:
    weather = "黄"

# AIコメント生成
comment_lines = []

if signals["up_5d"] >= 2:
    comment_lines.append("短期は反発基調です。")
elif signals["down_5d"] >= 2:
    comment_lines.append("短期は弱含みです。")
else:
    comment_lines.append("短期の方向感はまだ限定的です。")

if signals["below_25"] >= 2:
    comment_lines.append("25日線を下回る指数が多く、中期では戻り売りに注意です。")
elif signals["above_25"] >= 2:
    comment_lines.append("25日線を上回る指数が多く、中期の地合いは改善しています。")

if signals["usd_jpy_support"]:
    comment_lines.append("ドル円の円安は日本株に追い風です。")

if signals["us_weak"]:
    comment_lines.append("米国ハイテクの弱さは日本市場の上値を抑えやすいです。")
elif signals["us_strong"]:
    comment_lines.append("米国ハイテクの強さは日本市場の支援材料です。")

ai_comment = " ".join(comment_lines)

now = datetime.now().strftime("%Y-%m-%d %H:%M")

text = f"""天気：JP={weather}
スコア：{score}

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

with open("history.csv", "a") as f:
    f.write(f"{now},{weather},{score}\n")

print(text)
