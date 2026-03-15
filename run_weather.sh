#!/bin/bash
cd /Users/Owner/weather_ai
source venv/bin/activate

python fetch_prices_v2.py > latest_run.log 2>&1
python weather_signal.py > latest_weather.txt 2>&1

WEATHER_TEXT=$(cat latest_weather.txt)

COLOR_CLASS="yellow"
if echo "$WEATHER_TEXT" | grep -q "JP=赤"; then
  COLOR_CLASS="red"
elif echo "$WEATHER_TEXT" | grep -q "JP=青"; then
  COLOR_CLASS="blue"
fi

cat > index.html <<HTML
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>JP Market Weather</title>
<style>
body {
  font-family: Arial, sans-serif;
  background: #111;
  color: #fff;
  text-align: center;
  margin-top: 80px;
}
.box {
  font-size: 28px;
  padding: 20px;
  border-radius: 10px;
  display: inline-block;
  white-space: pre-wrap;
  max-width: 90%;
}
.red { background: #c0392b; }
.blue { background: #2980b9; }
.yellow { background: #f1c40f; color: #000; }
</style>
</head>
<body>
<h1>JP Market Weather</h1>
<div class="box $COLOR_CLASS">$WEATHER_TEXT</div>
</body>
</html>
HTML

git add index.html latest_weather.txt run_weather.sh
git commit -m "embed weather into index" || true
git push
