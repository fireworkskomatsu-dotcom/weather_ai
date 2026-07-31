#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "web" / "dashboard.json"
ROOT_ALIAS = ROOT / "dashboard.json"
REPORT = ROOT / "dashboard_publish.json"


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
        text=True,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary_name, path)

    finally:
        temporary = Path(temporary_name)

        if temporary.exists():
            temporary.unlink()


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"公開元がありません: {SOURCE}"
        )

    data = json.loads(SOURCE.read_text(encoding="utf-8"))

    integrity = data.get("data_integrity", {})

    if integrity.get("status") != "OK":
        raise RuntimeError(
            "data_integrity.status がOKではないため公開しません: "
            f"{integrity.get('status')!r}"
        )

    pnl = data.get("pnl_stats", {})

    required = (
        "trade_count",
        "wins",
        "losses",
        "win_rate",
    )

    missing = [
        key
        for key in required
        if key not in pnl
    ]

    if missing:
        raise RuntimeError(
            "pnl_stats必須項目がありません: "
            + ", ".join(missing)
        )

    serialized = json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    ) + "\n"

    atomic_write(ROOT_ALIAS, serialized)

    now = datetime.now(
        ZoneInfo("Asia/Tokyo")
    ).isoformat(timespec="seconds")

    report = {
        "published_at": now,
        "status": "OK",
        "canonical_dashboard": "web/dashboard.json",
        "root_compatibility_alias": "dashboard.json",
        "updated_at": data.get("updated_at"),
        "trade_count": pnl.get("trade_count"),
        "wins": pnl.get("wins"),
        "losses": pnl.get("losses"),
        "win_rate": pnl.get("win_rate"),
        "filter_reason": data.get(
            "filter",
            {},
        ).get("reason"),
        "data_integrity_status": integrity.get("status"),
    }

    atomic_write(
        REPORT,
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
    )

    print("dashboard_publish: OK")
    print("source:", SOURCE.relative_to(ROOT))
    print("alias:", ROOT_ALIAS.relative_to(ROOT))
    print("updated_at:", report["updated_at"])
    print("trade_count:", report["trade_count"])
    print("wins:", report["wins"])
    print("losses:", report["losses"])
    print("win_rate:", report["win_rate"])
    print("reason:", report["filter_reason"])


if __name__ == "__main__":
    main()
