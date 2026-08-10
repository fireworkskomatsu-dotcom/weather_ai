import json
from pathlib import Path
BASE=Path(__file__).resolve().parent

def r(n,d):
    try:return json.loads((BASE/n).read_text())
    except:return d

res=r("strategy_shadow_pnl.json",{}).get("strategy_results",{})
rows=list(res.values()) if isinstance(res,dict) else res
ranked=sorted(
    (row for row in rows if isinstance(row,dict)),
    key=lambda row: row.get("total_return",row.get("shadow_pnl",0)),
    reverse=True,
)

out={
    "ranking":ranked
}

(BASE/"strategy_shadow_rank.json").write_text(json.dumps(out,ensure_ascii=False,indent=2))
print(out)
