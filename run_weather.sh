#!/bin/bash
cd /Users/Owner/weather_ai
source venv/bin/activate

python fetch_prices_v2.py > latest_run.log 2>&1
python weather_signal.py > /dev/null 2>&1

WEATHER_TEXT=$(cat latest_weather.txt)

COLOR_CLASS="yellow"
EMOJI="🟡"
TITLE="NEUTRAL"

if echo "$WEATHER_TEXT" | grep -q "JP=赤"; then
  COLOR_CLASS="red"
  EMOJI="🔴"
  TITLE="BULLISH"
elif echo "$WEATHER_TEXT" | grep -q "JP=青"; then
  COLOR_CLASS="blue"
  EMOJI="🔵"
  TITLE="BEARISH"
fi

SCORE_LINE=$(echo "$WEATHER_TEXT" | grep "スコア")
UPDATE_LINE=$(echo "$WEATHER_TEXT" | grep "更新")

REASONS=$(awk '
/^理由$/ {flag=1; next}
/^詳細$/ {flag=0}
flag && NF {print}
' latest_weather.txt)

DETAILS=$(awk '
/^詳細$/ {flag=1; next}
/^更新/ {flag=0}
flag && NF {print}
' latest_weather.txt)

REASONS_HTML=$(echo "$REASONS" | sed 's/$/<br>/')
DETAILS_HTML=$(echo "$DETAILS" | sed 's/$/<br>/')

cat > index.html <<HTML
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JP Market Weather</title>
<style>
body {
  margin: 0;
  font-family: Arial, sans-serif;
  background: #111;
  color: #fff;
  text-align: center;
  padding: 20px;
}
.container {
  max-width: 720px;
  margin: 0 auto;
}
.hero {
  border-radius: 16px;
  padding: 24px 16px;
  margin-bottom: 20px;
}
.red { background: #c0392b; }
.blue { background: #2980b9; }
.yellow { background: #f1c40f; color: #000; }
h1 {
  margin: 0 0 12px 0;
  font-size: 32px;
}
.emoji {
  font-size: 52px;
  margin-bottom: 10px;
}
.status {
  font-size: 28px;
  font-weight: bold;
}
.score {
  font-size: 22px;
  margin-top: 10px;
}
.card {
  background: #1c1c1c;
  border-radius: 14px;
  padding: 18px;
  margin-bottom: 16px;
  text-align: left;
  line-height: 1.8;
}
.card h2 {
  margin-top: 0;
  font-size: 20px;
}
.footer {
  font-size: 14px;
  color: #bbb;
  margin-top: 12px;
}
@media (max-width: 600px) {
  h1 { font-size: 26px; }
  .status { font-size: 24px; }
  .score { font-size: 18px; }
}
</style>
</head>
<body>
<div class="container">
  <div class="hero $COLOR_CLASS">
    <div class="emoji">$EMOJI</div>
    <h1>JP Market Weather</h1>
    <div class="status">$TITLE</div>
    <div class="score">$SCORE_LINE</div>
  </div>

  <div class="card">
    <h2>理由</h2>
    <div>$REASONS_HTML</div>
  </div>

  <div class="card">
    <h2>詳細</h2>
    <div>$DETAILS_HTML</div>
  </div>

  <div class="footer">$UPDATE_LINE</div>
</div>
</body>
</html>
HTML

git add index.html run_weather.sh latest_weather.txt prices.csv history.csv
git commit -m "improve mobile dashboard" || true
git push
