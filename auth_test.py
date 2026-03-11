from dotenv import load_dotenv
import os, json, requests

load_dotenv()

mail = os.getenv("JQUANTS_MAIL", "").strip()
password = os.getenv("JQUANTS_PASSWORD", "").strip()

print("MAIL =", repr(mail))
print("PASSWORD_LEN =", len(password))

url = "https://api.jquants.com/v1/token/auth_user"
payload = {
    "mailaddress": mail,
    "password": password,
}

r = requests.post(url, json=payload, timeout=30)

print("STATUS =", r.status_code)
print("BODY =", r.text)
