import json
from pathlib import Path
from datetime import datetime
BASE=Path("/Users/Owner/weather_ai")
def r(n,d):
    try:return json.loads((BASE/n).read_text())
    except:return d
rank=r("strategy_shadow_rank.json",{}).get("ranking",[])
inc=r("strategy_incubator.json",{}).get("incubating_strategies",[])
inc_map={x.get("id"):x for x in inc}
rows=[]
for s in rank:
    sid=s.get("strategy")
    pnl=s.get("shadow_pnl",0)
    base=inc_map.get(sid,{}).get("expectancy",0)
    score=inc_map.get(sid,{}).get("score",50)
    expectancy=round(base + pnl/100,4)
    rows.append({"strategy":sid,"base_score":score,"estimated_expectancy":expectancy,"shadow_pnl":pnl,"status":"PROMISING" if expectancy>0 else "WATCH"})
out={"time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"strategy_expectancy":rows,"count":len(rows)}
(BASE/"strategy_expectancy.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(out)
