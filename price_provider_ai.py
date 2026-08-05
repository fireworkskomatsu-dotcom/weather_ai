#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


BASE = Path(__file__).resolve().parent
JST = ZoneInfo("Asia/Tokyo")

CONFIG_FILE = BASE / "price_provider_config.json"
LOCAL_INPUT_FILE = BASE / "provisional_price_input.json"

CANONICAL_FILE = BASE / "canonical_price.json"
LIVE_PRICE_FILE = BASE / "live_price.json"
PRICE_DATA_FILE = BASE / "price_data.json"
STATUS_FILE = BASE / "price_provider_status.json"

SYMBOL = "1321.T"

OFFICIAL_ALLOWED_PROVIDERS = {
    "JQUANTS",
}

TEST_ONLY_PROVIDERS = {
    "TEST_FIXED",
}

PROVISIONAL_PROVIDERS = {
    "LOCAL_INPUT",
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except Exception:
        return default


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        dir=str(path.parent),
        text=True,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(
                value,
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary_name, path)

    finally:
        temporary = Path(temporary_name)

        if temporary.exists():
            temporary.unlink()


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None

    try:
        number = float(str(value).replace(",", ""))
    except Exception:
        return None

    if not math.isfinite(number):
        return None

    if not 1_000 <= number <= 200_000:
        return None

    return number


def write_status(
    *,
    status: str,
    provider: str,
    mode: str,
    reason: str,
    price_written: bool,
    extra: dict[str, Any] | None = None,
) -> None:
    payload = {
        "status": status,
        "updated_at": datetime.now(JST).isoformat(
            timespec="seconds"
        ),
        "symbol": SYMBOL,
        "provider": provider,
        "mode": mode,
        "reason": reason,
        "price_written": price_written,
    }

    if extra:
        payload.update(extra)

    atomic_json(STATUS_FILE, payload)


config = load_json(
    CONFIG_FILE,
    {
        "provider": "DISABLED",
        "mode": "OFFICIAL",
    },
)

provider = str(
    os.environ.get(
        "WEATHER_AI_PRICE_PROVIDER",
        config.get("provider", "DISABLED"),
    )
).strip().upper()

mode = str(
    os.environ.get(
        "WEATHER_AI_PRICE_MODE",
        config.get("mode", "OFFICIAL"),
    )
).strip().upper()

now = datetime.now(JST)

if mode not in {
    "OFFICIAL",
    "PROVISIONAL",
    "ISOLATED_TEST",
}:
    raise RuntimeError(
        f"不正な価格モードです: {mode}"
    )


if mode == "OFFICIAL":
    if provider not in OFFICIAL_ALLOWED_PROVIDERS:
        write_status(
            status="BLOCKED",
            provider=provider,
            mode=mode,
            reason=(
                "正式モードでは検証済み公式プロバイダー以外を"
                "使用できません"
            ),
            price_written=False,
        )

        print("===== PRICE PROVIDER =====")
        print("status: BLOCKED")
        print("mode: OFFICIAL")
        print("provider:", provider)
        print("price_written: False")
        raise SystemExit(0)

    if provider == "JQUANTS":
        write_status(
            status="NOT_CONFIGURED",
            provider=provider,
            mode=mode,
            reason="J-Quants接続は未設定です",
            price_written=False,
        )

        print("===== PRICE PROVIDER =====")
        print("status: NOT_CONFIGURED")
        print("provider: JQUANTS")
        print("price_written: False")
        raise SystemExit(0)


if provider == "TEST_FIXED":
    if mode != "ISOLATED_TEST":
        raise RuntimeError(
            "TEST_FIXEDはISOLATED_TESTでしか使えません"
        )

    if os.environ.get(
        "WEATHER_AI_ISOLATED_TEST"
    ) != "1":
        raise RuntimeError(
            "隔離テストフラグがありません"
        )

    price = numeric(
        os.environ.get("WEATHER_AI_TEST_PRICE")
    )

    if price is None:
        raise RuntimeError(
            "有効なWEATHER_AI_TEST_PRICEがありません"
        )

    market_time = now
    source = "TEST_FIXED"
    verification_level = "ISOLATED_TEST_ONLY"
    official_eligible = False


elif provider == "LOCAL_INPUT":
    if mode != "PROVISIONAL":
        raise RuntimeError(
            "LOCAL_INPUTはPROVISIONAL専用です"
        )

    data = load_json(LOCAL_INPUT_FILE, {})

    if not isinstance(data, dict):
        raise RuntimeError(
            "provisional_price_input.jsonが不正です"
        )

    returned_symbol = str(
        data.get("symbol") or ""
    ).strip().upper()

    if returned_symbol != SYMBOL:
        raise RuntimeError(
            "仮入力の銘柄が1321.Tではありません"
        )

    price = numeric(data.get("price"))

    if price is None:
        raise RuntimeError(
            "仮入力価格が不正です"
        )

    source_time = data.get("market_time")

    if not source_time:
        raise RuntimeError(
            "仮入力にmarket_timeがありません"
        )

    try:
        market_time = datetime.fromisoformat(
            str(source_time)
        )

        if market_time.tzinfo is None:
            market_time = market_time.replace(
                tzinfo=JST
            )

        market_time = market_time.astimezone(JST)

    except Exception as exc:
        raise RuntimeError(
            f"market_timeが不正です: {exc}"
        )

    age_seconds = (
        now - market_time
    ).total_seconds()

    if age_seconds < -300:
        raise RuntimeError(
            "仮入力の時刻が未来です"
        )

    if age_seconds > 7 * 24 * 60 * 60:
        raise RuntimeError(
            "仮入力価格が7日以上古いです"
        )

    source = "LOCAL_INPUT"
    verification_level = "PROVISIONAL_UNVERIFIED"
    official_eligible = False


else:
    write_status(
        status="BLOCKED",
        provider=provider,
        mode=mode,
        reason="利用可能な価格プロバイダーではありません",
        price_written=False,
    )

    print("===== PRICE PROVIDER =====")
    print("status: BLOCKED")
    print("provider:", provider)
    print("mode:", mode)
    print("price_written: False")
    raise SystemExit(0)


payload = {
    "schema_version": 1,
    "symbol": SYMBOL,
    "price": round(price, 4),
    "last_price": round(price, 4),
    "current_price": round(price, 4),
    "currency": "JPY",
    "market_time": market_time.isoformat(
        timespec="seconds"
    ),
    "fetched_at": now.isoformat(
        timespec="seconds"
    ),
    "provider": provider,
    "source": source,
    "mode": mode,
    "verification_level": verification_level,
    "official_eligible": official_eligible,
    "allow_official_performance": False,
    "allow_official_learning": False,
    "verification": {
        "symbol_exact_match": True,
        "price_range_verified": True,
        "official_source_verified": False,
    },
}

# 仮価格・テスト価格はcanonical_priceだけへ保存する。
# live_price.json / price_data.jsonへは流さない。
atomic_json(CANONICAL_FILE, payload)

write_status(
    status="OK",
    provider=provider,
    mode=mode,
    reason="価格プロバイダー契約を満たしました",
    price_written=True,
    extra={
        "price": payload["price"],
        "market_time": payload["market_time"],
        "verification_level": verification_level,
        "official_eligible": official_eligible,
        "canonical_file": CANONICAL_FILE.name,
        "official_files_written": False,
    },
)

print("===== PRICE PROVIDER =====")
print("status: OK")
print("symbol:", SYMBOL)
print("price:", payload["price"])
print("provider:", provider)
print("mode:", mode)
print("verification_level:", verification_level)
print("official_eligible:", official_eligible)
print("canonical_file:", CANONICAL_FILE.name)
print("official_files_written: False")
