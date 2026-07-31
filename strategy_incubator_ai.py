import json
from pathlib import Path
from datetime import datetime

BASE=Path("/Users/Owner/weather_ai")

def r(n,d):
    try:return json.loads((BASE/n).read_text())
    except:return d

alpha=r("alpha_discovery.json",{}).get("alpha_candidates",[])
old=r("strategy_incubator.json",{}).get("incubating_strategies",[])

existing={x.get("id") for x in old}

for a in alpha:
    if a.get("id") not in existing:
        old.append({
          "id":a.get("id"),
          "name":a.get("name"),
          "stage":"SHADOW_INCUBATION",
          "score":a.get("score"),
          "expectancy":a.get("expectancy"),
          "created":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
          "real_trade":False
        })

out={
  "time":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
  "incubating_strategies":old[-50:],
  "count":len(old[-50:])
}

(BASE/"strategy_incubator.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(out)
