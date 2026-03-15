#!/bin/bash
cd /Users/Owner/weather_ai
source venv/bin/activate

python fetch_prices_v2.py > latest_run.log 2>&1
python weather_signal.py > /dev/null 2>&1

WEATHER_TEXT=$(cat latest_weather.txt)
CARDS_JSON=$(cat cards.json)

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
RISK_LINE=$(echo "$WEATHER_TEXT" | grep "危険度")
UPDATE_LINE=$(echo "$WEATHER_TEXT" | grep "更新")

AI_COMMENT=$(awk '
/^AIコメント$/ {flag=1; next}
/^理由$/ {flag=0}
flag && NF {print}
' latest_weather.txt)

REASONS=$(awk '
/^理由$/ {flag=1; next}
/^詳細$/ {flag=0}
flag && NF {print}
' latest_weather.txt)

REASONS_HTML=$(echo "$REASONS" | sed 's/$/<br>/')

CHART_POINTS=$(tail -20 history.csv | awk -F, '
BEGIN { first=1 }
{
  if (!first) printf ","
  printf "{x:%d,y:%s}", NR, $3
  first=0
}')

cat > index.html <<HTML
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>JP Market Weather</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
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
  max-width: 920px;
  margin: 0 auto;
}
.hero {
  border-radius: 18px;
  padding: 24px 16px;
  margin-bottom: 18px;
}
.red { background: #c0392b; }
.blue { background: #2980b9; }
.yellow { background: #f1c40f; color: #000; }
h1 {
  margin: 0 0 12px 0;
  font-size: 34px;
}
.emoji {
  font-size: 54px;
  margin-bottom: 8px;
}
.status {
  font-size: 28px;
  font-weight: bold;
}
.meta {
  margin-top: 10px;
  font-size: 20px;
  line-height: 1.7;
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
.chart-card {
  background: #1c1c1c;
  border-radius: 14px;
  padding: 18px;
  margin-bottom: 16px;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin-bottom: 16px;
}
.market-card {
  background: #1c1c1c;
  border-radius: 14px;
  padding: 16px;
  text-align: left;
}
.market-name {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 10px;
}
.market-price {
  font-size: 28px;
  font-weight: bold;
  margin-bottom: 8px;
}
.market-row {
  font-size: 14px;
  color: #ccc;
  margin-bottom: 4px;
}
.footer {
  font-size: 14px;
  color: #bbb;
  margin-top: 12px;
}
canvas {
  background: #fff;
  border-radius: 10px;
}
@media (max-width: 600px) {
  h1 { font-size: 26px; }
  .status { font-size: 23px; }
  .meta { font-size: 17px; }
  .market-price { font-size: 24px; }
}
</style>
</head>
<body>
<div class="container">
  <div class="hero $COLOR_CLASS">
    <div class="emoji">$EMOJI</div>
    <h1>JP Market Weather</h1>
    <div class="status">$TITLE</div>
    <div class="meta">
      <div>$SCORE_LINE</div>
      <div>$RISK_LINE</div>
    </div>
  </div>

  <div class="card">
    <h2>AIコメント</h2>
    <div>$AI_COMMENT</div>
  </div>

  <div class="chart-card">
    <h2>スコア推移</h2>
    <canvas id="scoreChart"></canvas>
  </div>

  <div class="card">
    <h2>マーケット一覧</h2>
    <div class="grid" id="marketGrid"></div>
  </div>

  <div class="card">
    <h2>理由</h2>
    <div>$REASONS_HTML</div>
  </div>

  <div class="footer">$UPDATE_LINE</div>
</div>

<script>
const cards = $CARDS_JSON;

const grid = document.getElementById("marketGrid");
cards.forEach(c => {
  const el = document.createElement("div");
  el.className = "market-card";
  el.innerHTML = `
    <div class="market-name">${c.name}</div>
    <div class="market-price">${c.price}</div>
    <div class="market-row">5日変化: ${c.change}</div>
    <div class="market-row">25MA: ${c.ma25}</div>
    <div class="market-row">200MA: ${c.ma200}</div>
    <div class="market-row">RSI/判定: ${c.rsi_label === "-" ? c.rsi : c.rsi + " / " + c.rsi_label}</div>
  `;
  grid.appendChild(el);
});

const ctx = document.getElementById('scoreChart');
new Chart(ctx, {
  type: 'line',
  data: {
    datasets: [{
      label: 'Score',
      data: [$CHART_POINTS],
      borderWidth: 2,
      tension: 0.25
    }]
  },
  options: {
    responsive: true,
    plugins: {
      legend: { display: true }
    },
    scales: {
      x: {
        type: 'linear',
        ticks: { color: '#333' }
      },
      y: {
        min: -8,
        max: 8,
        ticks: { stepSize: 1, color: '#333' }
      }
    }
  }
});
</script>
</body>
</html>
HTML

git add index.html run_weather.sh weather_signal.py latest_weather.txt prices.csv history.csv cards.json
git commit -m "add market cards and risk level" || true
git push
