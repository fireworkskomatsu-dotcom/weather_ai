#!/bin/bash
cd /Users/Owner/weather_ai

source venv/bin/activate

python3 fetch_prices_v2.py
python3 weather_signal.py
python3 position_ai.py
python3 open_ai.py
python3 open_filter_ai.py
python3 confidence_ai.py
python3 event_ai.py
python3 news_ai.py
python3 streak_ai.py
python3 capital_boost_ai.py
python3 filter_ai.py
python3 entry_ai.py
python3 risk_manager.py
python3 take_profit_ai.py
python3 stop_loss_ai.py
python3 execution_ai.py
python3 dashboard_builder.py
python3 logger.py
python3 paper_pnl.py
python3 result_logger.py

echo "DONE"
