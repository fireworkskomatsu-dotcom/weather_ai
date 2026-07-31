import json
from pathlib import Path
BASE=Path("/Users/Owner/weather_ai")

def r(n,d):
    try:return json.loads((BASE/n).read_text())
    except:return d

budget=r("strategy_budget.json",{}).get("strategy_budget",{})
capital=r("shadow_broker.json",{}).get("equity",1000000)

alloc={}

for k,v in budget.items():
    alloc[k]=round(capital*v/100)

out={
    "capital":capital,
    "allocation":alloc
}

(BASE/"strategy_allocator.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(out)
