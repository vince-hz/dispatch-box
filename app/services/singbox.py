from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ..config import DATA_DIR

BASE_CONFIG_PATH = Path(DATA_DIR) / "base_config.json"
DEFAULT_BASE_CONFIG: dict[str, Any] = {
    "route": {
        "rules": [],
        "rule_set": [],
    }
}


def ensure_base_config_file() -> None:
    if BASE_CONFIG_PATH.exists():
        return
    BASE_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASE_CONFIG_PATH.write_text(
        json.dumps(DEFAULT_BASE_CONFIG, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_base_config() -> dict[str, Any]:
    ensure_base_config_file()
    try:
        raw = json.loads(BASE_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(DEFAULT_BASE_CONFIG)
    if not isinstance(raw, dict):
        return deepcopy(DEFAULT_BASE_CONFIG)
    return raw


def _normalize_outbound_type(outbound_type: str) -> str:
    lowered = outbound_type.strip().lower()
    if lowered in {"url-test", "url_test"}:
        return "urltest"
    return lowered


def _parse_bool(raw: Any, default: bool = False) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return raw != 0
    if isinstance(raw, str):
        lowered = raw.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _normalize_outbound_tag_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []

    tags: list[str] = []
    seen: set[str] = set()
    for item in raw:
        tag = str(item or "").strip()
        if not tag or tag in seen:
            continue
        tags.append(tag)
        seen.add(tag)
    return tags


def _merge_outbound_tags(base_tags: list[str], extra_tags: list[str]) -> list[str]:
    tags: list[str] = []
    seen: set[str] = set()
    for item in base_tags + extra_tags:
        tag = str(item or "").strip()
        if not tag or tag in seen:
            continue
        tags.append(tag)
        seen.add(tag)
    return tags


def _normalize_raw_outbound_list(raw_list: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    for item in raw_list or []:
        if not isinstance(item, dict):
            continue

        cleaned = dict(item)
        tag = str(cleaned.get("tag") or "").strip()
        outbound_type = str(cleaned.get("type") or "").strip()
        if not tag or not outbound_type:
            continue

        cleaned["tag"] = tag
        cleaned["type"] = outbound_type
        result.append(cleaned)

    return result


def outbound_to_singbox_outbound(
    outbound: dict[str, Any],
    *,
    available_node_tags: list[str] | None = None,
) -> dict[str, Any]:
    payload = dict(outbound.get("payload") or {})

    include_all_nodes = _parse_bool(payload.pop("includeAllNodes", False), False)
    if "include_all_nodes" in payload:
        include_all_nodes = _parse_bool(payload.pop("include_all_nodes"), include_all_nodes)

    tag = str(outbound.get("tag") or "").strip()
    outbound_type = _normalize_outbound_type(str(outbound.get("type") or ""))

    if include_all_nodes and outbound_type in {"selector", "urltest"}:
        merged = _merge_outbound_tags(
            _normalize_outbound_tag_list(payload.get("outbounds")),
            list(available_node_tags or []),
        )
        payload["outbounds"] = merged

        default_tag = str(payload.get("default") or "").strip()
        if not default_tag and merged:
            payload["default"] = merged[0]

    result: dict[str, Any] = {
        "tag": tag,
        "type": outbound_type,
    }
    result.update(payload)

    result["tag"] = tag
    result["type"] = outbound_type
    return result


def build_overlay(
    *,
    outbounds: list[dict[str, Any]],
    subscription_outbounds: list[dict[str, Any]] | None = None,
    static_outbounds: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    resolved_subscription_outbounds = _normalize_raw_outbound_list(subscription_outbounds)
    resolved_static_outbounds = _normalize_raw_outbound_list(static_outbounds)

    available_node_tags = [
        str(item.get("tag") or "").strip()
        for item in (resolved_subscription_outbounds + resolved_static_outbounds)
        if str(item.get("tag") or "").strip()
    ]

    enabled_outbounds = [
        outbound_to_singbox_outbound(item, available_node_tags=available_node_tags)
        for item in outbounds
        if item.get("enabled")
    ]

    merged_outbounds: dict[str, dict[str, Any]] = {}
    for item in resolved_subscription_outbounds + resolved_static_outbounds + enabled_outbounds:
        merged_outbounds[str(item["tag"])] = item

    return {
        "outbounds": list(merged_outbounds.values()),
    }


def merge_base_with_overlay(
    *,
    base_config: dict[str, Any],
    overlay: dict[str, Any],
) -> dict[str, Any]:
    merged = deepcopy(base_config if isinstance(base_config, dict) else {})

    overlay_outbounds = overlay.get("outbounds")
    if isinstance(overlay_outbounds, list):
        # outbounds 直接覆盖写入，不做合并。
        merged["outbounds"] = overlay_outbounds

    return merged


def build_full_config(
    *,
    outbounds: list[dict[str, Any]],
    subscription_outbounds: list[dict[str, Any]] | None = None,
    static_outbounds: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    base_config = load_base_config()
    overlay = build_overlay(
        outbounds=outbounds,
        subscription_outbounds=subscription_outbounds,
        static_outbounds=static_outbounds,
    )
    return merge_base_with_overlay(base_config=base_config, overlay=overlay)


def build_subscription_bundle(subscriptions: list[dict[str, Any]]) -> str:
    enabled = [sub for sub in subscriptions if sub["enabled"]]
    lines = [f"# {item['name']}\n{item['url']}" for item in enabled]
    return "\n\n".join(lines).strip() + ("\n" if lines else "")
