from __future__ import annotations

from typing import Any

from ..schemas import StaticLadderCreate, StaticLadderUpdate
from .state_store import read_state, update_state, utc_now


def _section(state: dict[str, Any]) -> dict[str, Any]:
    return state["static_ladders"]


def _normalize_config(raw_config: Any) -> dict[str, Any]:
    if not isinstance(raw_config, dict):
        raise ValueError("config must be an object")

    config = dict(raw_config)
    tag = str(config.get("tag") or "").strip()
    outbound_type = str(config.get("type") or "").strip()

    if not tag:
        raise ValueError("config.tag is required")
    if not outbound_type:
        raise ValueError("config.type is required")

    config["tag"] = tag
    config["type"] = outbound_type
    return config


def _normalize_row(item: dict[str, Any]) -> dict[str, Any]:
    config = item.get("config")
    if not isinstance(config, dict):
        config = {}

    tag = str(item.get("tag") or config.get("tag") or "")
    outbound_type = str(item.get("type") or config.get("type") or "")

    return {
        "id": int(item["id"]),
        "tag": tag,
        "type": outbound_type,
        "config": config,
        "enabled": bool(item.get("enabled", True)),
        "note": str(item.get("note") or ""),
        "created_at": str(item.get("created_at") or utc_now()),
        "updated_at": str(item.get("updated_at") or utc_now()),
    }


def _find_by_id(items: list[dict[str, Any]], ladder_id: int) -> tuple[int, dict[str, Any]] | None:
    for index, item in enumerate(items):
        if int(item.get("id") or 0) == ladder_id:
            return index, item
    return None


def _find_by_tag(items: list[dict[str, Any]], tag: str) -> tuple[int, dict[str, Any]] | None:
    for index, item in enumerate(items):
        if str(item.get("tag") or "") == tag:
            return index, item
    return None


def list_static_ladders(*, enabled_only: bool = False) -> list[dict[str, Any]]:
    state = read_state()
    items = _section(state).get("items") or []

    rows = [_normalize_row(item) for item in items if isinstance(item, dict)]
    if enabled_only:
        rows = [row for row in rows if row["enabled"]]

    rows.sort(key=lambda item: item["updated_at"], reverse=True)
    return rows


def create_static_ladder(payload: StaticLadderCreate) -> dict[str, Any]:
    now = utc_now()

    def mutator(state: dict[str, Any]) -> dict[str, Any]:
        section = _section(state)
        items = section["items"]

        config = _normalize_config(payload.config)
        tag = str(config["tag"])

        if _find_by_tag(items, tag):
            raise RuntimeError("UNIQUE constraint failed: static_ladders.tag")

        next_id = int(section.get("next_id") or 1)
        item = {
            "id": next_id,
            "tag": tag,
            "type": str(config["type"]),
            "config": config,
            "enabled": bool(payload.enabled),
            "note": payload.note,
            "created_at": now,
            "updated_at": now,
        }

        items.append(item)
        section["next_id"] = next_id + 1
        return _normalize_row(item)

    return update_state(mutator)


def update_static_ladder(ladder_id: int, payload: StaticLadderUpdate) -> dict[str, Any] | None:
    now = utc_now()

    def mutator(state: dict[str, Any]) -> dict[str, Any] | None:
        section = _section(state)
        items = section["items"]

        found = _find_by_id(items, ladder_id)
        if not found:
            return None

        index, existing = found

        config = dict(existing.get("config") or {})
        if payload.config is not None:
            config = _normalize_config(payload.config)
        else:
            config = _normalize_config(config)

        tag = str(config["tag"])
        duplicate = _find_by_tag(items, tag)
        if duplicate and int(duplicate[1].get("id") or 0) != ladder_id:
            raise RuntimeError("UNIQUE constraint failed: static_ladders.tag")

        updated = {
            "id": existing["id"],
            "tag": tag,
            "type": str(config["type"]),
            "config": config,
            "enabled": payload.enabled if payload.enabled is not None else bool(existing.get("enabled", True)),
            "note": payload.note if payload.note is not None else str(existing.get("note") or ""),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
        }

        items[index] = updated
        return _normalize_row(updated)

    return update_state(mutator)


def delete_static_ladder(ladder_id: int) -> bool:
    def mutator(state: dict[str, Any]) -> bool:
        section = _section(state)
        items = section["items"]
        found = _find_by_id(items, ladder_id)
        if not found:
            return False

        index, _ = found
        items.pop(index)
        return True

    return update_state(mutator)


def list_static_ladder_outbounds(*, enabled_only: bool = True) -> list[dict[str, Any]]:
    rows = list_static_ladders(enabled_only=enabled_only)

    outbounds: list[dict[str, Any]] = []
    for row in rows:
        config = row.get("config")
        if not isinstance(config, dict):
            continue
        tag = str(config.get("tag") or "").strip()
        outbound_type = str(config.get("type") or "").strip()
        if not tag or not outbound_type:
            continue
        outbounds.append(dict(config))

    return outbounds
