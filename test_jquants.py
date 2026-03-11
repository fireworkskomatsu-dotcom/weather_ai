from dotenv import load_dotenv
import os
import jquantsapi

load_dotenv()

mail = os.getenv("JQUANTS_MAIL")
password = os.getenv("JQUANTS_PASSWORD")

cli = jquantsapi.Client(mail_address=mail, password=password)

print("接続成功")
