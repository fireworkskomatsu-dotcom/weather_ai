from dotenv import load_dotenv
import os

load_dotenv()

mail = os.getenv("JQUANTS_MAIL", "")
password = os.getenv("JQUANTS_PASSWORD", "")

print("MAIL_REPR =", repr(mail))
print("MAIL_HAS_AT =", "@" in mail)
print("MAIL_START_END_SPACES =", mail != mail.strip())
print("PASSWORD_LEN =", len(password))
print("PASSWORD_START_END_SPACES =", password != password.strip())
