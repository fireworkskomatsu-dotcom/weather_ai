import json
from pathlib import Path
BASE=Path("/Users/Owner/weather_ai")
def r(n,d):
    try:return json.loads((BASE/n).read_text())
    except:return d
pnl=r("shadow_pnl_engine.json",{})
success=pnl.get("pnl_yen",0)>0
out={"success_detected":success,"reason":"PROFIT_TRADE" if success else "NO_SUCCESS"}
(BASE/"success_learning.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(out)
