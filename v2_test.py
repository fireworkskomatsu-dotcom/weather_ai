from dotenv import load_dotenv
import os
import requests

load_dotenv()

api_key = os.getenv("JQUANTS_API_KEY", "").strip()
if not api_key:
    raise RuntimeError("JQUANTS_API_KEY がありません")

url = "https://api.jquants.com/v2/equities/bars/daily"
params = {
    "code": "1321",
    "from": "2024-01-01",
    "to": "2024-12-31",
}
headers = {
    "x-api-key": api_key
}

r = requests.get(url, params=params, headers=headers, timeout=30)

print("STATUS =", r.status_code)
print("BODY_HEAD =", r.text[:500])
