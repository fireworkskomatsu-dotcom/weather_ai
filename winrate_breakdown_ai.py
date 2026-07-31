import json, math
from pathlib import Path
from datetime import datetime

BASE = Path("/Users/Owner/weather_ai")
OUT = BASE / "winrate_breakdown.json"

def r(n,d):
    try:
        return json.loads((BASE/n).read_text())
    except:
        return d

broker = r("shadow_broker_v2.json", r("shadow_broker.json", {}))
perf = r("shadow_performance.json", {})
hist = r("shadow_trade_history.json", [])
curve = r("shadow_equity_curve.json", [])
brain = r("brain_decision.json", {})
fund = r("fund_master_brain.json", {})
risk = r("risk_council.json", {})
strategy = r("strategy_rotation.json", {})
memory = r("memory_score.json", {})
market = r("market_brain_v2.json", {})

start = broker.get("start_capital", 1000000) or 1000000
equity = broker.get("equity", broker.get("cash", start)) or start
return_pct = round((equity-start)/start*100,2)

closed = [x for x in hist if x.get("event") in ["TAKE_PROFIT","STOP_LOSS"]]
wins = [x for x in closed if x.get("event") == "TAKE_PROFIT"]
losses = [x for x in closed if x.get("event") == "STOP_LOSS"]
win_rate = round(len(wins)/len(closed)*100,1) if closed else 0

pnl_list = [x.get("pnl_pct",0) for x in closed]
expectancy = round(sum(pnl_list)/len(pnl_list),4) if pnl_list else 0
gross_profit = sum(x.get("pnl_pct",0) for x in wins)
gross_loss = abs(sum(x.get("pnl_pct",0) for x in losses))
profit_factor = round(gross_profit/gross_loss,2) if gross_loss else (999 if gross_profit>0 else 0)

returns = []
for i in range(1,len(curve)):
    prev = curve[i-1].get("equity",0)
    cur = curve[i].get("equity",0)
    if prev:
        returns.append((cur-prev)/prev)

avg = sum(returns)/len(returns) if returns else 0
std = (sum((x-avg)**2 for x in returns)/len(returns))**0.5 if returns else 0
sharpe = round((avg/std)*(252**0.5),2) if std else 0

downside = [x for x in returns if x<0]
down_std = (sum(x*x for x in downside)/len(downside))**0.5 if downside else 0
sortino = round((avg/down_std)*(252**0.5),2) if down_std else 0

peak = start
max_dd = 0
for x in curve:
    eq = x.get("equity", start)
    peak = max(peak, eq)
    if peak:
        max_dd = min(max_dd, (eq-peak)/peak*100)

calmar = round(return_pct/abs(max_dd),2) if max_dd else 0

score = 50
score += return_pct*3
score += win_rate*0.2
score += expectancy*100
score += min(sharpe,5)*5
score += max_dd
score = round(max(0,min(100,score)),1)

out = {
    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "module": "winrate_breakdown_ai.py",
    "status": "ACTIVE",
    "fund_name": "1321 AI FUND",
    "equity": round(equity,0),
    "start_capital": start,
    "return_pct": return_pct,
    "trades": len(hist),
    "closed_trades": len(closed),
    "wins": len(wins),
    "losses": len(losses),
    "win_rate": win_rate,
    "expectancy_pct": expectancy,
    "profit_factor": profit_factor,
    "sharpe": sharpe,
    "sortino": sortino,
    "calmar": calmar,
    "max_drawdown_pct": round(max_dd,2),
    "alpha_pct": return_pct,
    "beta": 0,
    "capital_usage": "LOW" if not broker.get("position") else "ACTIVE",
    "best_source": strategy.get("active_strategy", "NONE"),
    "profit_source": "NO_CLOSED_PROFIT" if not wins else "TAKE_PROFIT",
    "loss_source": "NO_CLOSED_LOSS" if not losses else "STOP_LOSS",
    "brain_decision": brain.get("brain_decision"),
    "fund_action": fund.get("fund_action"),
    "risk_mode": risk.get("risk_mode"),
    "memory_score": memory.get("memory_score"),
    "market_brain_decision": market.get("market_brain_v2_decision"),
    "fund_score": score,
    "summary": f"equity={round(equity,0)} return={return_pct}% win={win_rate}% dd={round(max_dd,2)} score={score}",
    "mode": "PERFORMANCE_INTELLIGENCE"
}

OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2))
print(out)
