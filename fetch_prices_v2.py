from dotenv import load_dotenv
import os
import requests
import pandas as pd

load_dotenv()

api_key = os.getenv("JQUANTS_API_KEY", "").strip()
if not api_key:
    raise RuntimeError("JQUANTS_API_KEY がありません")

headers = {"x-api-key": api_key}
codes = ["1321", "1306", "1475"]
dfs = []

# Freeプランの取得可能期間に合わせる
FROM_DATE = "2023-12-17"
TO_DATE = "2025-12-17"

for code in codes:
    url = "https://api.jquants.com/v2/equities/bars/daily"
    params = {
        "code": code,
        "from": FROM_DATE,
        "to": TO_DATE,
    }
    r = requests.get(url, params=params, headers=headers, timeout=30)
    print("CODE", code, "STATUS", r.status_code)
    if r.status_code != 200:
        print("BODY_HEAD", r.text[:300])
        continue

    data = r.json().get("data", [])
    if data:
        df = pd.DataFrame(data)
        dfs.append(df)

if not dfs:
    raise RuntimeError("対象銘柄の価格データが取得できませんでした")

out = pd.concat(dfs, ignore_index=True)
out.to_csv("prices.csv", index=False)

print("prices.csv 保存完了")
print("行数:", len(out))
print("列名:", out.columns.tolist())
print(out.tail())
