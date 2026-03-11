from dotenv import load_dotenv
import os
import json
import requests
import pandas as pd

load_dotenv()

mail = os.getenv("JQUANTS_MAIL")
password = os.getenv("JQUANTS_PASSWORD")

if not mail or not password:
    raise RuntimeError("JQUANTS_MAIL / JQUANTS_PASSWORD が .env にありません")

# 1. refresh token
auth_user_url = "https://api.jquants.com/v1/token/auth_user"
payload = json.dumps({
    "mailaddress": mail,
    "password": password,
})
r = requests.post(auth_user_url, data=payload)
r.raise_for_status()
refresh_token = r.json()["refreshToken"]

# 2. id token
auth_refresh_url = f"https://api.jquants.com/v1/token/auth_refresh?refreshtoken={refresh_token}"
r = requests.post(auth_refresh_url)
r.raise_for_status()
id_token = r.json()["idToken"]

headers = {"Authorization": f"Bearer {id_token}"}

# 3. daily quotes for target codes
codes = ["1321", "1306", "1475"]
dfs = []

for code in codes:
    url = f"https://api.jquants.com/v1/prices/daily_quotes?code={code}&from=2024-01-01&to=2026-12-31"
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()

    # レスポンスのキー名差異に備える
    quotes = data.get("daily_quotes") or data.get("DailyQuotes") or data.get("dailyQuotes") or []
    if quotes:
        df = pd.DataFrame(quotes)
        dfs.append(df)

if not dfs:
    raise RuntimeError("対象銘柄の価格データが取得できませんでした")

out = pd.concat(dfs, ignore_index=True)
out.to_csv("prices.csv", index=False)

print("prices.csv 保存完了")
print("行数:", len(out))
print("列名:", out.columns.tolist())
print(out.tail())
