import json
from pathlib import Path
BASE=Path("/Users/Owner/weather_ai")

def r(n,d):
    try:return json.loads((BASE/n).read_text())
    except:return d

alloc=r("strategy_allocator.json",{}).get("allocation",{})
total=sum(alloc.values()) or 1

weights={}

for k,v in alloc.items():
    weights[k]=round(v/total,4)

out={"weights":weights}

(BASE/"strategy_weight.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(out)
