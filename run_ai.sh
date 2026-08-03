#!/bin/bash
set +e
BASE="$HOME/weather_ai"
WEB="$HOME/fireworkskomatsu-dotcom.github.io"
run(){ [ -f "$BASE/$1" ] && python3 "$BASE/$1"; }
copy(){ [ -f "$BASE/$1" ] && cp "$BASE/$1" "$WEB/"; }

cd "$BASE" || exit

run fetch_real_price_ai.py
run trend_reversal_ai.py
run replay_analyzer_ai.py
run replay_summary_ai.py
run replay_policy_ai.py
run replay_expectancy_ai.py
run position_sizing_ai.py
run market_temperature_ai.py

# === canonical fresh decision pipeline ===
run strategy_5x10_ai.py
run adaptive_strategy_engine_ai.py
run recovery_mode_ai.py
run winrate_filter_ai.py
run emergency_stop_ai.py
run filter_ai.py

# AI organization pipeline
run signal_outcome_ai.py
run strategy_shadow_pnl_ai.py
run strategy_expectancy_ai.py
run strategy_shadow_rank_ai.py
run strategy_weight_ai.py
run strategy_allocator_ai.py
run strategy_incubator_ai.py
run strategy_promotion_ai.py
run strategy_retirement_ai.py
run success_learning_ai.py
run winrate_breakdown_ai.py
run winrate_filter_ai.py
run weighted_multi_agent_ai.py
# === end canonical fresh decision pipeline ===

run core_master_decision_ai.py
run core_exit_engine_ai.py
run shadow_broker_ai.py
run operation_readiness_ai.py
run real_go_live_ai.py
run trade_brain_ai.py
run production_lock_ai.py
run v9_dashboard_ai.py

copy core_dashboard.json
copy dashboard_summary.json
copy human_trade_view.json
copy live_price.json
copy master_decision.json
copy shadow_broker.json
copy core_exit_engine.json
copy operation_readiness.json
copy real_go_live.json
copy trade_brain.json
copy production_lock.json
copy market_temperature.json
copy filter.json
copy weighted_multi_agent.json
copy adaptive_strategy_state.json
copy adaptive_strategy_weights.json
copy replay_expectancy.json
copy replay_policy.json

cd "$WEB" || exit
git add .
git commit -m "rebuild 1321 v9 single source dashboard"
git push

(cd "$HOME/weather_ai" && python3 virtual_account_ai.py)
(cd "$HOME/weather_ai" && python3 decision_trace_ai.py)
(cd "$HOME/weather_ai" && python3 decision_trace_v2_ai.py)
(cd "$HOME/weather_ai" && python3 skip_analyzer_ai.py)
(cd "$HOME/weather_ai" && python3 ai_scoreboard_ai.py)
(cd "$HOME/weather_ai" && python3 strategy_skip_breakdown_ai.py)
(cd "$HOME/weather_ai" && python3 learning_log_ai.py)

python3 skip_diagnostics_ai.py

# ===== PUBLIC DASHBOARD SYNC =====
python3 dashboard_builder.py
python3 official_performance_ai.py
python3 dashboard_integrity_ai.py

# DASHBOARD_PUBLISH_SYNC_BEGIN
# web/dashboard.jsonを公開用ルートdashboard.jsonへ同期
if [ -f "$HOME/weather_ai/dashboard_publish_ai.py" ]; then
  python3 "$HOME/weather_ai/dashboard_publish_ai.py"
fi
# DASHBOARD_PUBLISH_SYNC_END

if [ -f history.csv ]; then
  cp -f history.csv web/history.csv
fi

if [ -f latest_weather.txt ]; then
  cp -f latest_weather.txt web/weather.txt
else
  printf '更新失敗: latest_weather.txt が存在しません\n' > web/weather.txt
fi
# ===== END PUBLIC DASHBOARD SYNC =====

python3 strategy_5x10_trace_runner.py
