from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any, Callable, TypeVar

from ..config import DATA_DIR

STATE_PATH = Path(DATA_DIR) / "dispatch_state.json"
PROVIDER_PATH = Path(DATA_DIR) / "provider.json"

StateT = dict[str, Any]
ResultT = TypeVar("ResultT")

_STATE_LOCK = RLock()
_PROVIDER_LOCK = RLock()

DEFAULT_SUBSCRIPTION_REPLACE_MAP: dict[str, str] = {
    "CN |": "",
    "SG |": "",
    "CN": "",
    "IEPL": "",
    "专线": "",
    " ": "",
    "香港": "HK",
    "Hong Kong": "HK",
    "HKG": "HK",
    "HongKong": "HK",
    "新加坡": "SG",
    "Singapore": "SG",
    "SGP": "SG",
}

DEFAULT_SUBSCRIPTION_FILTER: dict[str, list[str]] = {
    "available_flags": [],
    "exclude_flags": [],
}


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _default_state() -> StateT:
    return {
        "version": 1,
        "outbounds": {
            "next_id": 1,
            "items": [],
        },
        "static_ladders": {
            "next_id": 1,
            "items": [],
        },
    }


def _default_provider_state() -> StateT:
    return {
        "version": 1,
        "next_id": 1,
        "items": [],
        "static_ladders": {
            "next_id": 1,
            "items": [],
        },
        "replace_map": dict(DEFAULT_SUBSCRIPTION_REPLACE_MAP),
        "filter": _normalize_provider_filter(None),
    }


def _normalize_provider_replace_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return dict(DEFAULT_SUBSCRIPTION_REPLACE_MAP)

    result: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        if key == "":
            continue
        result[key] = str(raw_value or "")

    return result


def _normalize_provider_filter_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    result: list[str] = []
    seen: set[str] = set()
    for raw_item in value:
        text = str(raw_item or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(text)
    return result


def _normalize_provider_filter(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {
            "available_flags": list(DEFAULT_SUBSCRIPTION_FILTER.get("available_flags") or []),
            "exclude_flags": list(DEFAULT_SUBSCRIPTION_FILTER.get("exclude_flags") or []),
        }

    return {
        "available_flags": _normalize_provider_filter_list(value.get("available_flags")),
        "exclude_flags": _normalize_provider_filter_list(value.get("exclude_flags")),
    }


def _ensure_state_shape(state: Any) -> StateT:
    base = _default_state()
    if not isinstance(state, dict):
        return base

    normalized = dict(base)

    for section in ("outbounds", "static_ladders"):
        raw_section = state.get(section)
        if not isinstance(raw_section, dict):
            continue

        items = raw_section.get("items")
        next_id = raw_section.get("next_id")

        if not isinstance(items, list):
            items = []

        if not isinstance(next_id, int) or next_id < 1:
            max_id = max(
                [int(item.get("id") or 0) for item in items if isinstance(item, dict)],
                default=0,
            )
            next_id = max_id + 1 if max_id > 0 else 1

        normalized[section] = {
            "next_id": next_id,
            "items": items,
        }

    version = state.get("version")
    if isinstance(version, int) and version > 0:
        normalized["version"] = version

    return normalized


def _ensure_provider_state_shape(state: Any) -> StateT:
    base = _default_provider_state()
    if not isinstance(state, dict):
        return base

    items = state.get("items")
    if not isinstance(items, list):
        items = []

    next_id = state.get("next_id")
    if not isinstance(next_id, int) or next_id < 1:
        max_id = max(
            [int(item.get("id") or 0) for item in items if isinstance(item, dict)],
            default=0,
        )
        next_id = max_id + 1 if max_id > 0 else 1

    version = state.get("version")
    if not isinstance(version, int) or version <= 0:
        version = 1

    replace_map = _normalize_provider_replace_map(state.get("replace_map"))
    filter_config = _normalize_provider_filter(state.get("filter"))
    static_ladders_raw = state.get("static_ladders")
    if isinstance(static_ladders_raw, dict):
        static_ladder_items = static_ladders_raw.get("items")
        static_ladder_next_id = static_ladders_raw.get("next_id")
    else:
        static_ladder_items = []
        static_ladder_next_id = 1
    if not isinstance(static_ladder_items, list):
        static_ladder_items = []
    if not isinstance(static_ladder_next_id, int) or static_ladder_next_id < 1:
        max_ladder_id = max(
            [int(item.get("id") or 0) for item in static_ladder_items if isinstance(item, dict)],
            default=0,
        )
        static_ladder_next_id = max_ladder_id + 1 if max_ladder_id > 0 else 1

    return {
        "version": version,
        "next_id": next_id,
        "items": items,
        "static_ladders": {
            "next_id": static_ladder_next_id,
            "items": static_ladder_items,
        },
        "replace_map": replace_map,
        "filter": filter_config,
    }


def _load_state_unlocked() -> StateT:
    if not STATE_PATH.exists():
        return _default_state()

    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _default_state()

    return _ensure_state_shape(raw)


def _load_provider_state_unlocked() -> StateT:
    if not PROVIDER_PATH.exists():
        return _default_provider_state()

    try:
        raw = json.loads(PROVIDER_PATH.read_text(encoding="utf-8"))
    except Exception:
        return _default_provider_state()

    return _ensure_provider_state_shape(raw)


def _save_state_unlocked(state: StateT) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    normalized = _ensure_state_shape(state)
    tmp_path = STATE_PATH.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(STATE_PATH)


def _save_provider_state_unlocked(state: StateT) -> None:
    PROVIDER_PATH.parent.mkdir(parents=True, exist_ok=True)
    normalized = _ensure_provider_state_shape(state)
    tmp_path = PROVIDER_PATH.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(PROVIDER_PATH)


def read_state() -> StateT:
    with _STATE_LOCK:
        return _load_state_unlocked()


def update_state(mutator: Callable[[StateT], ResultT]) -> ResultT:
    with _STATE_LOCK:
        state = _load_state_unlocked()
        result = mutator(state)
        _save_state_unlocked(state)
        return result


def read_provider_state() -> StateT:
    with _PROVIDER_LOCK:
        return _load_provider_state_unlocked()


def update_provider_state(mutator: Callable[[StateT], ResultT]) -> ResultT:
    with _PROVIDER_LOCK:
        state = _load_provider_state_unlocked()
        result = mutator(state)
        _save_provider_state_unlocked(state)
        return result
