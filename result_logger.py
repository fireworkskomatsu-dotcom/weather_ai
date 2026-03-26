import json
from pathlib import Path
from datetime import datetime

BASE = Path("/Users/Owner/weather_ai")

EXEC_FILE = BASE / "execution.json"
RESULT_FILE = BASE / "signal_log.csv"

def read_json(path, default):
    try:
        return json.loads(path.read_text())
    except:
        return default

def main():
    exec_data = read_json(EXEC_FILE, {})

    action = exec_data.get("action")
    side = exec_data.get("side")
    size = exec_data.get("size")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    line = f"{now},{action},{side},{size}\n"

    if not RESULT_FILE.exists():
        RESULT_FILE.write_text("time,action,side,size\n")

    with open(RESULT_FILE, "a") as f:
        f.write(line)

    print("logged:", line)

if __name__ == "__main__":
    main()
