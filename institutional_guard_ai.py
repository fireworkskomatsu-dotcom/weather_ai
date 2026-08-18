#!/usr/bin/env python3
from __future__ import annotations

import base64, csv, hashlib, json, math
from datetime import datetime
from pathlib import Path
from typing import Any

from paper_control_plane_ai import decode_payload, encode_payload

BASE = Path(__file__).resolve().parent
HISTORY = BASE / "history.csv"
REPORT = BASE / "institutional_guard_report.json"
SYMBOL = "1321.T"
SCENARIOS = (-5.0, -10.0, -20.0)
MAX_STRESSED_DRAWDOWN_PCT = 10.0

def rows_and_bytes(path: Path) -> tuple[list[list[str]], bytes]:
    raw = path.read_bytes() if path.exists() else b""
    rows = list(csv.reader(raw.decode("utf-8").splitlines())) if raw else []
    return rows, raw

def latest_payload(rows: list[list[str]], kind: str, field: int) -> dict[str, Any] | None:
    for row in reversed(rows):
        if len(row) > field and row[0] == kind:
            return decode_payload(row[field])
    return None

def previous_chain_valid(rows: list[list[str]], raw: bytes) -> tuple[bool, str]:
    previous = latest_payload(rows, "GUARD_V1", 3)
    if not previous:
        return True, "GENESIS"
    size = int(previous.get("history_prefix_bytes") or 0)
    expected = str(previous.get("history_prefix_sha256") or "")
    actual = hashlib.sha256(raw[:size]).hexdigest() if 0 <= size <= len(raw) else "INVALID_SIZE"
    return actual == expected, actual

def stress(account: dict[str, Any]) -> dict[str, Any]:
    cash = float(account.get("cash") or 0)
    position = int(account.get("position") or 0)
    close = float(account.get("last_close") or 0)
    peak = float(account.get("peak_equity") or cash + position * close)
    results = []
    for shock in SCENARIOS:
        shocked_price = max(0.0, close * (1 + shock / 100))
        equity = cash + position * shocked_price
        drawdown = (peak - equity) / peak * 100 if peak > 0 else 100.0
        results.append({"shock_pct": shock, "price": round(shocked_price, 2), "equity": round(equity, 2),
                        "drawdown_from_peak_pct": round(drawdown, 4)})
    worst = max((item["drawdown_from_peak_pct"] for item in results), default=100.0)
    return {"scenarios": results, "worst_drawdown_pct": worst,
            "limit_pct": MAX_STRESSED_DRAWDOWN_PCT,
            "status": "PASS" if worst <= MAX_STRESSED_DRAWDOWN_PCT else "BLOCK"}

def build_report(history_path: Path = HISTORY, now: str | None = None) -> dict[str, Any]:
    rows, raw = rows_and_bytes(history_path)
    chain_ok, observed = previous_chain_valid(rows, raw)
    control = latest_payload(rows, "CONTROL_V2", 4) or {}
    account = control.get("paper_account") if isinstance(control.get("paper_account"), dict) else {}
    stress_result = stress(account)
    known_bad_rows = sum(1 for row in rows if not row or not row[0])
    checks = {"append_only_chain_valid": chain_ok, "history_rows_parseable": known_bad_rows == 0,
              "paper_account_available": bool(account), "stress_limit_passed": stress_result["status"] == "PASS",
              "real_money_disconnected": control.get("real_money") is False}
    target_date = str(control.get("target_date") or max((r[1] for r in rows if len(r) > 1 and r[0] == "PROSPECTIVE_V3"), default=""))
    return {"schema_version": 1, "generated_at": now or datetime.now().astimezone().isoformat(timespec="seconds"),
            "scope": "INSTITUTIONAL_GUARD_PAPER_ONLY", "official_eligible": False, "real_money": False,
            "target_date": target_date, "status": "PASS" if all(checks.values()) else "BLOCK",
            "checks": checks, "stress": stress_result, "history_rows": len(rows),
            "previous_chain_observed_sha256": observed,
            "history_prefix_bytes": len(raw), "history_prefix_sha256": hashlib.sha256(raw).hexdigest()}

def append_public(report: dict[str, Any], path: Path = HISTORY) -> bool:
    rows, _ = rows_and_bytes(path)
    if not report["target_date"] or any(len(r) > 1 and r[0] == "GUARD_V1" and r[1] == report["target_date"] for r in rows):
        return False
    with path.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle, lineterminator="\n").writerow(["GUARD_V1", report["target_date"], report["generated_at"], encode_payload(report)])
    return True

def run(history_path: Path = HISTORY, report_path: Path | None = REPORT) -> dict[str, Any]:
    report = build_report(history_path)
    if report_path is not None:
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    append_public(report, history_path)
    return report

if __name__ == "__main__":
    result = run()
    print(json.dumps({k: result[k] for k in ("status", "target_date", "checks", "stress")}, ensure_ascii=False, indent=2))
