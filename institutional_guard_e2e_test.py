#!/usr/bin/env python3
import csv, hashlib, tempfile
from pathlib import Path
import institutional_guard_ai as target

BASE = Path(__file__).resolve().parent
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
protected = ["prices.csv", "history.csv", "official_performance.json", "official_decision_log.jsonl"]
before = {name: digest(BASE / name) for name in protected}
with tempfile.TemporaryDirectory() as folder:
    history = Path(folder) / "history.csv"
    history.write_bytes((BASE / "history.csv").read_bytes())
    first = target.build_report(history, now="2026-08-18T19:00:00+09:00")
    target.append_public(first, history)
    second = target.build_report(history, now="2026-08-19T19:00:00+09:00")
    original = history.read_bytes()
    history.write_bytes(b"X" + original[1:])
    tampered = target.build_report(history)
checks = {
    "paper_only": first["real_money"] is False and first["official_eligible"] is False,
    "three_crash_scenarios": [x["shock_pct"] for x in first["stress"]["scenarios"]] == [-5.0, -10.0, -20.0],
    "stress_limit_enforced": first["stress"]["limit_pct"] == 10.0,
    "genesis_valid": first["checks"]["append_only_chain_valid"] is True,
    "next_checkpoint_valid": second["checks"]["append_only_chain_valid"] is True,
    "tampering_detected": tampered["checks"]["append_only_chain_valid"] is False and tampered["status"] == "BLOCK",
    "production_files_unchanged": before == {name: digest(BASE / name) for name in protected},
}
for name, passed in checks.items(): print(f"{name}: {passed}")
print("RESULT:", "PASS" if all(checks.values()) else "FAIL")
if not all(checks.values()): raise SystemExit(1)
