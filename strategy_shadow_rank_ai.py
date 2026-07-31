import json
from pathlib import Path
BASE=Path("/Users/Owner/weather_ai")

def r(n,d):
    try:return json.loads((BASE/n).read_text())
    except:return d

res=r("strategy_shadow_pnl.json",{}).get("strategy_results",[])

ranked=sorted(res,key=lambda x:x["shadow_pnl"],reverse=True)

out={
    "ranking":ranked
}

(BASE/"strategy_shadow_rank.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(out)
