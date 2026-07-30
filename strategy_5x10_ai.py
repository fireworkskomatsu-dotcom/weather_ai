import json
from pathlib import Path
from datetime import datetime

BASE=Path("/Users/Owner/weather_ai")

def r(n,d):
    try:
        return json.loads((BASE/n).read_text())
    except:
        return d

f=r("filter.json",{})
conf=r("confidence.json",{})
broker=r("shadow_broker.json",{})
exit_engine=r("core_exit_engine.json",{})
archive=r("experience_archive.json",[])
real_log=r("real_trade_log.json",[])

regime=f.get("regime","UNKNOWN")
vol=f.get("vol_mode","NORMAL")
temp=f.get("market_temperature","NORMAL")
rk=f.get("replay_key","")
base=f.get("decision","SKIP")
confidence=float(conf.get("confidence") or f.get("confidence") or 50)
replay_exp=float(f.get("replay_expectancy") or 0)
replay_trades=int(f.get("replay_expectancy_trades") or 0)
position_side=broker.get("side")
unreal=float(broker.get("unrealized_pct") or 0)
shadow_return=float(broker.get("return_pct") or 0)

exits=[x for x in real_log if x.get("type")=="EXIT"]
wins=[x for x in exits if float(x.get("pnl",0))>0]
losses=[x for x in exits if float(x.get("pnl",0))<=0]
winrate=(len(wins)/len(exits)*100) if exits else 0
total_pnl=sum(float(x.get("pnl",0)) for x in exits)

votes={"LONG":0.0,"SHORT":0.0,"SKIP":0.0,"HOLD":0.0}
strategies=[]

def add(sid,family,name,decision,score,reasons):
    # 以下は停止命令ではなく、既存判断を補足する情報系シグナル。
    # baseがSKIPのときに独立したSKIP票として重複加算しない。
    informational_reasons = {
        "HIGH_CONFIDENCE",
        "HIGH_CONF",
        "LIFECYCLE_SYNC",
        "LOW_EXPERIENCE",
        "BEGINNER_SMALL_LOT",
    }

    normalized_reasons = set()

    if isinstance(reasons, list):
        normalized_reasons = {str(x) for x in reasons}
    elif reasons is not None:
        normalized_reasons = {str(reasons)}

    if (
        decision == "SKIP"
        and normalized_reasons
        and normalized_reasons.issubset(informational_reasons)
    ):
        decision = "ABSTAIN"
        score = 0

    score=round(max(0,min(100,score)),2)
    weight=round(score/100,4)
    if decision in votes:
        votes[decision]+=weight
    strategies.append({
        "id":sid,
        "family":family,
        "name":name,
        "decision":decision,
        "score":score,
        "weight":weight,
        "reasons":reasons,
        "regime":regime,
        "vol_mode":vol,
        "replay_key":rk,
        "status":"ACTIVE_SHADOW"
    })

# 1 TREND x10
trend_rules=[
("trend_follow", regime=="TREND_UP", "LONG", 72, ["TREND_UP"]),
("trend_pullback", regime=="TREND_UP" and temp=="NORMAL", "LONG", 70, ["TREND_UP_NORMAL"]),
("trend_breakout", regime=="TREND_UP" and confidence>=70, "LONG", 76, ["TREND_CONFIRMED"]),
("trend_reversal_up", f.get("reversal_mode")=="REVERSAL_UP", "LONG", 68, ["REVERSAL_UP"]),
("trend_memory", "TREND_UP" in rk, "LONG", 71, ["REPLAY_TREND_MATCH"]),
("trend_confidence", confidence>=80, base, 74, ["HIGH_CONFIDENCE"]),
("trend_vol_adjust", regime=="TREND_UP" and vol!="DANGER", "LONG", 73, ["VOL_OK"]),
("trend_vol_danger_small", regime=="TREND_UP" and vol=="DANGER", "LONG", 62, ["VOL_DANGER_SMALL"]),
("trend_hold", position_side=="LONG", "HOLD", 70, ["HOLD_EXISTING_LONG"]),
("trend_skip_if_no_edge", regime not in ["TREND_UP","TREND_DOWN"], "SKIP", 65, ["NO_TREND_EDGE"])
]
for i,(name,cond,dec,score,rs) in enumerate(trend_rules,1):
    add(f"TREND_{i:02d}","TREND",name,dec if cond else "ABSTAIN",score if cond else 0,rs if cond else ["CONDITION_FALSE"])

# 2 REPLAY x10 本物分解
replay_rules=[
("expectancy_positive", replay_exp>0, "LONG" if "LONG" in rk else "SHORT", 82, ["EXPECTANCY_POSITIVE"]),
("sample_over_30", replay_trades>=30, "LONG" if "LONG" in rk else base, 78, ["REPLAY_SAMPLE_30_PLUS"]),
("policy_boost", f.get("replay_policy_action")=="BOOST", "LONG" if "LONG" in rk else base, 80, ["POLICY_BOOST"]),
("expectancy_boost", f.get("replay_expectancy_action")=="BOOST", "LONG" if "LONG" in rk else base, 81, ["EXPECTANCY_BOOST"]),
("key_exact_match", rk=="TREND_UP_LONG", "LONG", 84, ["TREND_UP_LONG_EXACT"]),
("size_boost", float(f.get("replay_size_mult") or 1) > 1, "LONG" if f.get("replay_action")=="BOOST_SIZE" else base, 66, ["SIZE_CHECK"]),
("low_pnl_warning", total_pnl<0, "SKIP", 62, ["REAL_PNL_NEGATIVE"]),
("winrate_warning", len(exits)>=2 and winrate<50, "SKIP", 64, ["REAL_WINRATE_LOW"]),
("shadow_profit_override", shadow_return>5, "LONG", 79, ["SHADOW_PROFIT_POSITIVE"]),
("replay_conflict_guard", replay_exp>0 and total_pnl<0, "LONG", 60, ["REPLAY_POSITIVE_REAL_NEGATIVE_SMALL"])
]
for i,(name,cond,dec,score,rs) in enumerate(replay_rules,1):
    add(f"REPLAY_{i:02d}","REPLAY",name,dec if cond else "ABSTAIN",score if cond else 0,rs if cond else ["CONDITION_FALSE"])

# 3 RISK x10
risk_rules=[
("temp_block", temp in ["PANIC","OVERHEAT"], "SKIP", 90, ["TEMP_BLOCK"]),
("vol_danger_guard", vol=="DANGER", "SKIP", 72, ["VOL_DANGER"]),
("vol_danger_but_replay", vol=="DANGER" and replay_exp>0, "LONG", 58, ["VOL_DANGER_REPLAY_OVERRIDE"]),
("confidence_low", confidence<40, "SKIP", 85, ["LOW_CONF"]),
("confidence_high", confidence>=80, base, 72, ["HIGH_CONF"]),
("position_exists", position_side in ["LONG","SHORT"], "HOLD", 75, ["POSITION_EXISTS"]),
("exit_now", exit_engine.get("exit_now") is True, "SKIP", 95, ["EXIT_NOW"]),
("small_sample", len(archive)<50, "SKIP", 55, ["LOW_SAMPLE_CAUTION"]),
("shadow_profit_safe", shadow_return>5, "HOLD" if position_side else base, 68, ["SHADOW_PROFIT_SAFE"]),
("capital_protect", total_pnl<0 and len(exits)>=2, "SKIP", 70, ["CAPITAL_PROTECT"])
]
for i,(name,cond,dec,score,rs) in enumerate(risk_rules,1):
    add(f"RISK_{i:02d}","RISK",name,dec if cond else "ABSTAIN",score if cond else 0,rs if cond else ["CONDITION_FALSE"])

# 4 EXIT x10
exit_rules=[
("take_profit_check", unreal>=2.2, "SKIP", 90, ["TAKE_PROFIT_ZONE"]),
("stop_loss_check", unreal<=-1.0, "SKIP", 95, ["STOP_LOSS_ZONE"]),
("hold_flat_pnl", position_side and abs(unreal)<0.3, "HOLD", 68, ["FLAT_HOLD"]),
("hold_winner", position_side=="LONG" and unreal>0, "HOLD", 78, ["WINNER_HOLD"]),
("cut_loser", position_side=="LONG" and unreal<0, "HOLD", 58, ["LOSER_MONITOR"]),
("no_position_entry", not position_side and base=="LONG", "LONG", 70, ["NO_POSITION_ENTRY"]),
("vol_tight_exit", vol=="DANGER", "HOLD" if position_side else base, 62, ["VOL_TIGHT_EXIT"]),
("exit_engine_hold", exit_engine.get("exit_reason")=="HOLD", "HOLD" if position_side else base, 73, ["EXIT_ENGINE_HOLD"]),
("exit_engine_signal", exit_engine.get("exit_now") is True, "SKIP", 92, ["EXIT_ENGINE_EXIT"]),
("lifecycle_sync", True, "HOLD" if position_side else base, 66, ["LIFECYCLE_SYNC"])
]
for i,(name,cond,dec,score,rs) in enumerate(exit_rules,1):
    add(f"EXIT_{i:02d}","EXIT",name,dec if cond else "ABSTAIN",score if cond else 0,rs if cond else ["CONDITION_FALSE"])

# 5 MEMORY x10
memory_rules=[
("experience_under_50", len(archive)<50, "SKIP", 56, ["LOW_EXPERIENCE"]),
("experience_growth", len(archive)>=7, base, 62, ["EXPERIENCE_GROWING"]),
("shadow_win_memory", shadow_return>0, "LONG" if "LONG" in rk else base, 74, ["SHADOW_WIN_MEMORY"]),
("real_loss_memory", total_pnl<0, "SKIP", 65, ["REAL_LOSS_MEMORY"]),
("trend_up_long_memory", rk=="TREND_UP_LONG", "LONG", 78, ["DNA_MEMORY_MATCH"]),
("mistake_avoid", len(losses)>=2, "SKIP", 64, ["LOSS_AVOID"]),
("success_pattern", len(wins)>=1, base, 70, ["SUCCESS_PATTERN"]),
("sample_growth", len(archive)>=10, base, 68, ["SAMPLE_GROWTH"]),
("priority_replay", replay_exp>0 and replay_trades>=30, "LONG", 80, ["REPLAY_PRIORITY_MEMORY"]),
("beginner_limit", len(archive)<30, "LONG" if base=="LONG" else "SKIP", 58, ["BEGINNER_SMALL_LOT"])
]
for i,(name,cond,dec,score,rs) in enumerate(memory_rules,1):
    add(f"MEMORY_{i:02d}","MEMORY",name,dec if cond else "ABSTAIN",score if cond else 0,rs if cond else ["CONDITION_FALSE"])

final=max(votes,key=votes.get)

family_summary={}
for fam in ["TREND","REPLAY","RISK","EXIT","MEMORY"]:
    fs=[s for s in strategies if s["family"]==fam]
    family_summary[fam]={
        "top_score":max(s["score"] for s in fs),
        "longs":len([s for s in fs if s["decision"]=="LONG"]),
        "skips":len([s for s in fs if s["decision"]=="SKIP"]),
        "holds":len([s for s in fs if s["decision"]=="HOLD"])
    }

out={
 "time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
 "mode":"REAL_5x10_EVOLUTION",
 "strategy_count":50,
 "votes":{k:round(v,4) for k,v in votes.items()},
 "final_decision":final,
 "family_summary":family_summary,
 "top10":sorted(strategies,key=lambda x:x["score"],reverse=True)[:10],
 "strategies":strategies
}

(BASE/"strategy_5x10.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print({"strategy_count":50,"final_decision":final,"votes":out["votes"],"family_summary":family_summary})
