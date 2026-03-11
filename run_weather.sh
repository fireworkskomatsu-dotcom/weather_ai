#!/bin/bash
cd /Users/Owner/weather_ai
source venv/bin/activate

python fetch_prices_v2.py > latest_run.log 2>&1
python weather_signal.py > latest_weather.txt 2>&1

cp latest_weather.txt web/weather.txt
