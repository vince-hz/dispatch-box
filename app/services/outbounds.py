from __future__ import annotations

from typing import Any

from ..schemas import OutboundCreate, OutboundUpdate
from .state_store import read_state, update_state, utc_now

AGGREGATE_OUTBOUND_TYPES = {"selector", "urltest", "direct"}


def _normalize_outbound_type(raw: Any) -> str:
    value = str(raw or "").strip().lower()
    if value == "url-test":
        return "urltest"
    return value


def _is_aggregate_outbound_item(item: dict[str, Any]) -> bool:
    return _normalize_outbound_type(item.get("type")) in AGGREGATE_OUTBOUND_TYPES


def _validate_aggregate_outbound_type(raw: Any) -> str:
    outbound_type = _normalize_outbound_type(raw)
    if outbound_type not in AGGREGATE_OUTBOUND_TYPES:
        allowed = ", ".join(sorted(AGGREGATE_OUTBOUND_TYPES))
        raise ValueError(f"Only aggregate outbounds are supported: {allowed}")
    return outbound_type


def _parse_bool(raw: Any, default: bool = False) -> bool:
    if isinstance(raw, bool):
        return raw
    if raw is None:
        return default
    if isinstance(raw, (int, float)):
        return raw != 0
    value = str(raw).strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _normalize_tag_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        tag = str(item or "").strip()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        result.append(tag)
    return result


def _outbounds_section(state: dict[str, Any]) -> dict[str, Any]:
    return state["outbounds"]


def _normalize_outbound(item: dict[str, Any]) -> dict[str, Any]:
    payload = item.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    return {
        "id": int(item["id"]),
        "tag": str(item.get("tag") or ""),
        "type": _normalize_outbound_type(item.get("type")),
        "payload": payload,
        "enabled": bool(item.get("enabled", True)),
        "note": str(item.get("note") or ""),
        "created_at": str(item.get("created_at") or utc_now()),
        "updated_at": str(item.get("updated_at") or utc_now()),
    }


def _find_outbound(items: list[dict[str, Any]], outbound_id: int) -> tuple[int, dict[str, Any]] | None:
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not _is_aggregate_outbound_item(item):
            continue
        if int(item.get("id") or 0) == outbound_id:
            return index, item
    return None


def _find_outbound_by_tag(items: list[dict[str, Any]], tag: str) -> tuple[int, dict[str, Any]] | None:
    for index, item in enumerate(items):
        if not isinstance(item, dict) or not _is_aggregate_outbound_item(item):
            continue
        if item.get("tag") == tag:
            return index, item
    return None


def list_outbounds() -> list[dict[str, Any]]:
    state = read_state()
    items = _outbounds_section(state)["items"]
    rows = [_normalize_outbound(item) for item in items if isinstance(item, dict) and _is_aggregate_outbound_item(item)]
    rows.sort(key=lambda item: int(item.get("id") or 0))
    return rows


def get_outbound(outbound_id: int) -> dict[str, Any] | None:
    state = read_state()
    items = _outbounds_section(state)["items"]
    found = _find_outbound(items, outbound_id)
    if not found:
        return None
    _, item = found
    return _normalize_outbound(item)


def get_outbound_by_tag(tag: str) -> dict[str, Any] | None:
    state = read_state()
    items = _outbounds_section(state)["items"]
    found = _find_outbound_by_tag(items, tag)
    if not found:
        return None
    _, item = found
    return _normalize_outbound(item)


def create_outbound(payload: OutboundCreate) -> dict[str, Any]:
    now = utc_now()
    outbound_type = _validate_aggregate_outbound_type(payload.type)
    tag = payload.tag.strip()
    if not tag:
        raise ValueError("outbound tag is required")

    def mutator(state: dict[str, Any]) -> dict[str, Any]:
        section = _outbounds_section(state)
        if _find_outbound_by_tag(section["items"], tag):
            raise RuntimeError("UNIQUE constraint failed: outbounds.tag")

        next_id = int(section.get("next_id") or 1)
        item = {
            "id": next_id,
            "tag": tag,
            "type": outbound_type,
            "payload": dict(payload.payload),
            "enabled": bool(payload.enabled),
            "note": payload.note,
            "created_at": now,
            "updated_at": now,
        }
        section["items"].append(item)
        section["next_id"] = next_id + 1
        return _normalize_outbound(item)

    return update_state(mutator)


def update_outbound(outbound_id: int, payload: OutboundUpdate) -> dict[str, Any] | None:
    now = utc_now()

    def mutator(state: dict[str, Any]) -> dict[str, Any] | None:
        section = _outbounds_section(state)
        found = _find_outbound(section["items"], outbound_id)
        if not found:
            return None

        index, existing = found
        tag = payload.tag.strip() if payload.tag is not None else str(existing.get("tag") or "").strip()
        if not tag:
            raise ValueError("outbound tag is required")
        outbound_type = (
            _validate_aggregate_outbound_type(payload.type)
            if payload.type is not None
            else _validate_aggregate_outbound_type(existing.get("type"))
        )
        duplicate = _find_outbound_by_tag(section["items"], tag)
        if duplicate and int(duplicate[1].get("id") or 0) != outbound_id:
            raise RuntimeError("UNIQUE constraint failed: outbounds.tag")

        updated = {
            "id": existing["id"],
            "tag": tag,
            "type": outbound_type,
            "payload": payload.payload if payload.payload is not None else dict(existing.get("payload") or {}),
            "enabled": payload.enabled if payload.enabled is not None else bool(existing.get("enabled", True)),
            "note": payload.note if payload.note is not None else existing.get("note", ""),
            "created_at": existing.get("created_at") or now,
            "updated_at": now,
        }
        section["items"][index] = updated
        return _normalize_outbound(updated)

    return update_state(mutator)


def delete_outbound(outbound_id: int) -> bool:
    def mutator(state: dict[str, Any]) -> bool:
        section = _outbounds_section(state)
        items = section["items"]
        found = _find_outbound(items, outbound_id)
        if not found:
            return False
        index, _ = found
        items.pop(index)
        return True

    return update_state(mutator)


def clear_outbounds() -> int:
    def mutator(state: dict[str, Any]) -> int:
        section = _outbounds_section(state)
        count = len(section["items"])
        section["items"] = []
        return count

    return update_state(mutator)


def purge_non_aggregate_outbounds() -> int:
    def mutator(state: dict[str, Any]) -> int:
        section = _outbounds_section(state)
        items = section.get("items")
        if not isinstance(items, list):
            section["items"] = []
            section["next_id"] = 1
            return 0

        changed = False
        removed = 0
        kept: list[dict[str, Any]] = []
        for raw_item in items:
            if not isinstance(raw_item, dict):
                changed = True
                removed += 1
                continue
            outbound_type = _normalize_outbound_type(raw_item.get("type"))
            if outbound_type not in AGGREGATE_OUTBOUND_TYPES:
                changed = True
                removed += 1
                continue
            normalized_item = dict(raw_item)
            if normalized_item.get("type") != outbound_type:
                changed = True
                normalized_item["type"] = outbound_type
            kept.append(normalized_item)

        if changed:
            section["items"] = kept
            max_id = max((int(item.get("id") or 0) for item in kept), default=0)
            next_id = int(section.get("next_id") or 1)
            section["next_id"] = max(next_id, max_id + 1, 1)
        return removed

    return update_state(mutator)


def migrate_include_all_nodes_markers() -> int:
    def mutator(state: dict[str, Any]) -> int:
        section = _outbounds_section(state)
        items = section.get("items")
        if not isinstance(items, list):
            return 0

        aggregate_tag_set = {
            str(item.get("tag") or "").strip()
            for item in items
            if isinstance(item, dict) and _is_aggregate_outbound_item(item) and str(item.get("tag") or "").strip()
        }

        changed_rows = 0
        now = utc_now()

        for item in items:
            if not isinstance(item, dict) or not _is_aggregate_outbound_item(item):
                continue

            outbound_type = _normalize_outbound_type(item.get("type"))
            if outbound_type not in {"selector", "urltest"}:
                continue

            payload_raw = item.get("payload")
            payload = dict(payload_raw) if isinstance(payload_raw, dict) else {}
            outbound_tags = _normalize_tag_list(payload.get("outbounds"))
            if not outbound_tags:
                continue

            include_all_nodes = _parse_bool(
                payload.get("includeAllNodes"),
                _parse_bool(payload.get("include_all_nodes"), False),
            )
            has_node_refs = any(tag not in aggregate_tag_set for tag in outbound_tags)
            if not has_node_refs:
                continue

            keep_refs = [tag for tag in outbound_tags if tag in aggregate_tag_set and tag != str(item.get("tag") or "")]

            payload["outbounds"] = keep_refs
            payload["includeAllNodes"] = True
            payload.pop("include_all_nodes", None)
            if include_all_nodes and payload.get("default") and payload["default"] not in keep_refs:
                payload["default"] = keep_refs[0] if keep_refs else ""
            if not include_all_nodes and payload.get("default") and keep_refs and payload["default"] not in keep_refs:
                payload["default"] = keep_refs[0]

            item["payload"] = payload
            item["updated_at"] = now
            changed_rows += 1

        return changed_rows

    return update_state(mutator)


def upsert_outbound_by_tag(
    *,
    tag: str,
    outbound_type: str,
    payload: dict[str, Any],
    enabled: bool = True,
    note: str = "",
) -> tuple[dict[str, Any], bool]:
    now = utc_now()
    normalized_type = _validate_aggregate_outbound_type(outbound_type)
    normalized_tag = tag.strip()
    if not normalized_tag:
        raise ValueError("outbound tag is required")

    def mutator(state: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        section = _outbounds_section(state)
        found = _find_outbound_by_tag(section["items"], normalized_tag)

        if found:
            index, existing = found
            updated = {
                "id": existing["id"],
                "tag": normalized_tag,
                "type": normalized_type,
                "payload": dict(payload),
                "enabled": bool(enabled),
                "note": note,
                "created_at": existing.get("created_at") or now,
                "updated_at": now,
            }
            section["items"][index] = updated
            return _normalize_outbound(updated), False

        next_id = int(section.get("next_id") or 1)
        item = {
            "id": next_id,
            "tag": normalized_tag,
            "type": normalized_type,
            "payload": dict(payload),
            "enabled": bool(enabled),
            "note": note,
            "created_at": now,
            "updated_at": now,
        }
        section["items"].append(item)
        section["next_id"] = next_id + 1
        return _normalize_outbound(item), True

    return update_state(mutator)
