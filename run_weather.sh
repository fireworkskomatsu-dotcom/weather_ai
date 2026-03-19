#!/bin/bash
cd /Users/Owner/weather_ai

source venv/bin/activate

python fetch_prices_v2.py > latest_run.log 2>&1
python weather_signal.py > latest_weather.txt 2>&1

python position_ai.py
python open_ai.py
python confidence_ai.py
python event_ai.py
python filter_ai.py
python dashboard_builder.py
python logger.py
python paper_pnl.py

python3 <<'INNERPY'
from pathlib import Path

src = Path("/Users/Owner/weather_ai/history.csv")
dst = Path("/Users/Owner/weather_ai/web/chart_history.csv")

rows = []
for line in src.read_text(encoding="utf-8").splitlines():
    parts = [p.strip() for p in line.split(",")]
    if len(parts) < 3:
        continue
    dt = parts[0]
    score = parts[2]
    try:
        float(score)
    except:
        continue
    rows.append((dt, score))

with dst.open("w", encoding="utf-8") as f:
    f.write("date,score\n")
    for dt, score in rows:
        f.write(f"{dt},{score}\n")
INNERPY

cp latest_weather.txt web/weather.txt
cp web/dashboard.json dashboard.json

echo "DONE"
