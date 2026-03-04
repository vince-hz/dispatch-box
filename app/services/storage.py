from __future__ import annotations

from typing import Any

from ..schemas import SubscriptionCreate, SubscriptionUpdate
from .state_store import (
    DEFAULT_SUBSCRIPTION_REPLACE_MAP,
    read_provider_state,
    update_provider_state,
    utc_now,
)


def _normalize_keyword_list(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_items = [part.strip() for part in value.replace("\n", ",").split(",")]
    elif isinstance(value, list):
        raw_items = [str(item).strip() for item in value if isinstance(item, (str, int, float))]
    else:
        raw_items = []

    result: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if not item:
            continue
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        result.append(item)
    return result


def _normalize_replace_map(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return dict(DEFAULT_SUBSCRIPTION_REPLACE_MAP)

    normalized: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = str(raw_key)
        if key == "":
            continue
        normalized[key] = str(raw_value or "")

    return normalized


def _normalize_subscription_filter(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {
            "available_flags": [],
            "exclude_flags": [],
        }

    return {
        "available_flags": _normalize_keyword_list(value.get("available_flags")),
        "exclude_flags": _normalize_keyword_list(value.get("exclude_flags")),
    }


def _normalize_cached_outbounds(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag") or "").strip()
        outbound_type = str(item.get("type") or "").strip()
        if not tag or not outbound_type:
            continue

        cleaned = dict(item)
        cleaned["tag"] = tag
        cleaned["type"] = outbound_type
        result.append(cleaned)

    return result


def _normalize_subscription(item: dict[str, Any]) -> dict[str, Any]:
    cached_outbounds = _normalize_cached_outbounds(item.get("cached_outbounds"))

    return {
        "id": int(item["id"]),
        "name": str(item.get("name") or ""),
        "url": str(item.get("url") or ""),
        "enabled": bool(item.get("enabled", True)),
        "user_agent": str(item.get("user_agent") or ""),
        "rename_prefix": str(item.get("rename_prefix") or ""),
        "include_keywords": _normalize_keyword_list(item.get("include_keywords")),
        "exclude_keywords": _normalize_keyword_list(item.get("exclude_keywords")),
        "cached_outbounds": cached_outbounds,
        "node_count": len(cached_outbounds),
        "last_synced_at": item.get("last_synced_at") or None,
        "last_sync_error": str(item.get("last_sync_error") or ""),
        "note": str(item.get("note") or ""),
        "created_at": str(item.get("created_at") or utc_now()),
        "updated_at": str(item.get("updated_at") or utc_now()),
    }


def _subscriptions_section(state: dict[str, Any]) -> dict[str, Any]:
    return state


def _find_subscription(items: list[dict[str, Any]], subscription_id: int) -> tuple[int, dict[str, Any]] | None:
    for index, item in enumerate(items):
        if int(item.get("id") or 0) == subscription_id:
            return index, item
    return None


def list_subscriptions() -> list[dict[str, Any]]:
    state = read_provider_state()
    items = _subscriptions_section(state)["items"]
    rows = [_normalize_subscription(item) for item in items if isinstance(item, dict)]
    rows.sort(key=lambda item: item["updated_at"], reverse=True)
    return rows


def get_subscription(subscription_id: int) -> dict[str, Any] | None:
    state = read_provider_state()
    items = _subscriptions_section(state)["items"]
    found = _find_subscription(items, subscription_id)
    if not found:
        return None
    _, item = found
    return _normalize_subscription(item)


def get_subscription_replace_map() -> dict[str, str]:
    state = read_provider_state()
    return _normalize_replace_map(state.get("replace_map"))


def update_subscription_replace_map(replace_map: dict[str, Any]) -> dict[str, str]:
    normalized = _normalize_replace_map(replace_map)

    def mutator(state: dict[str, Any]) -> dict[str, str]:
        state["replace_map"] = normalized
        return dict(normalized)

    return update_provider_state(mutator)


def get_subscription_global_filter() -> dict[str, list[str]]:
    state = read_provider_state()
    return _normalize_subscription_filter(state.get("filter"))


def update_subscription_global_filter(filter_config: dict[str, Any]) -> dict[str, list[str]]:
    normalized = _normalize_subscription_filter(filter_config)

    def mutator(state: dict[str, Any]) -> dict[str, list[str]]:
        state["filter"] = normalized
        return dict(normalized)

    return update_provider_state(mutator)


def create_subscription(payload: SubscriptionCreate) -> dict[str, Any]:
    now = utc_now()

    def mutator(state: dict[str, Any]) -> dict[str, Any]:
        section = _subscriptions_section(state)
        next_id = int(section.get("next_id") or 1)
        item = {
            "id": next_id,
            "name": payload.name,
            "url": str(payload.url),
            "enabled": bool(payload.enabled),
            "user_agent": payload.user_agent.strip(),
            "rename_prefix": payload.rename_prefix.strip(),
            "include_keywords": _normalize_keyword_list(payload.include_keywords),
            "exclude_keywords": _normalize_keyword_list(payload.exclude_keywords),
            "cached_outbounds": [],
            "last_synced_at": None,
            "last_sync_error": "",
            "note": payload.note,
            "created_at": now,
            "updated_at": now,
        }
        section["items"].append(item)
        section["next_id"] = next_id + 1
        return _normalize_subscription(item)

    return update_provider_state(mutator)


def update_subscription(subscription_id: int, payload: SubscriptionUpdate) -> dict[str, Any] | None:
    now = utc_now()

    def mutator(state: dict[str, Any]) -> dict[str, Any] | None:
        section = _subscriptions_section(state)
        found = _find_subscription(section["items"], subscription_id)
        if not found:
            return None

        index, existing = found
        updated = {
            "id": existing["id"],
            "name": payload.name if payload.name is not None else existing.get("name", ""),
            "url": str(payload.url) if payload.url is not None else existing.get("url", ""),
            "enabled": payload.enabled if payload.enabled is not None else bool(existing.get("enabled", True)),
            "user_agent": payload.user_agent.strip()
            if payload.user_agent is not None
            else str(existing.get("user_agent") or ""),
            "rename_prefix": payload.rename_prefix.strip()
            if payload.rename_prefix is not None
            else str(existing.get("rename_prefix") or ""),
            "include_keywords": _normalize_keyword_list(payload.include_keywords)
            if payload.include_keywords is not None
            else _normalize_keyword_list(existing.get("include_keywords")),
            "exclude_keywords": _normalize_keyword_list(payload.exclude_keywords)
            if payload.exclude_keywords is not None
            else _normalize_keyword_list(existing.get("exclude_keywords")),
            "cached_outbounds": _normalize_cached_outbounds(existing.get("cached_outbounds")),
            "last_synced_at": existing.get("last_synced_at") or None,
            "last_sync_error": str(existing.get("last_sync_error") or ""),
            "note": payload.note if payload.note is not None else existing.get("note", ""),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
        }

        section["items"][index] = updated
        return _normalize_subscription(updated)

    return update_provider_state(mutator)


def delete_subscription(subscription_id: int) -> bool:
    def mutator(state: dict[str, Any]) -> bool:
        section = _subscriptions_section(state)
        items = section["items"]
        found = _find_subscription(items, subscription_id)
        if not found:
            return False
        index, _ = found
        items.pop(index)
        return True

    return update_provider_state(mutator)


def save_subscription_sync_result(
    subscription_id: int,
    *,
    outbounds: list[dict[str, Any]],
    sync_error: str = "",
) -> dict[str, Any] | None:
    now = utc_now()
    cleaned_outbounds = _normalize_cached_outbounds(outbounds)

    def mutator(state: dict[str, Any]) -> dict[str, Any] | None:
        section = _subscriptions_section(state)
        found = _find_subscription(section["items"], subscription_id)
        if not found:
            return None

        index, existing = found
        updated = {
            "id": existing["id"],
            "name": str(existing.get("name") or ""),
            "url": str(existing.get("url") or ""),
            "enabled": bool(existing.get("enabled", True)),
            "user_agent": str(existing.get("user_agent") or ""),
            "rename_prefix": str(existing.get("rename_prefix") or ""),
            "include_keywords": _normalize_keyword_list(existing.get("include_keywords")),
            "exclude_keywords": _normalize_keyword_list(existing.get("exclude_keywords")),
            "cached_outbounds": cleaned_outbounds,
            "last_synced_at": now,
            "last_sync_error": sync_error.strip(),
            "note": str(existing.get("note") or ""),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
        }

        section["items"][index] = updated
        return _normalize_subscription(updated)

    return update_provider_state(mutator)


def list_subscription_cached_outbounds(enabled_only: bool = True) -> list[dict[str, Any]]:
    state = read_provider_state()
    items = _subscriptions_section(state)["items"]
    outbounds: list[dict[str, Any]] = []
    used_tags: set[str] = set()

    for raw_item in items:
        if not isinstance(raw_item, dict):
            continue

        subscription = _normalize_subscription(raw_item)
        if enabled_only and not subscription["enabled"]:
            continue

        for raw_outbound in subscription["cached_outbounds"]:
            tag = str(raw_outbound.get("tag") or "").strip()
            outbound_type = str(raw_outbound.get("type") or "").strip()
            if not tag or not outbound_type:
                continue

            unique_tag = tag
            suffix = 2
            while unique_tag in used_tags:
                unique_tag = f"{tag}-{suffix}"
                suffix += 1
            used_tags.add(unique_tag)

            outbound = dict(raw_outbound)
            outbound["tag"] = unique_tag
            outbounds.append(outbound)

    return outbounds
