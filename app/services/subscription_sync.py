from __future__ import annotations

import base64
import json
import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx

from .state_store import DEFAULT_SUBSCRIPTION_REPLACE_MAP

DEFAULT_SUBSCRIPTION_UA = "Mozilla/5.0 (compatible; dispatch-box/1.0)"

_SUPPORTED_SCHEMES = ("ss://", "trojan://", "vmess://", "vless://", "hysteria2://", "hy2://")

# Follows the rename intent from vince-rule-store/scripts/provider-rename.js
_REPLACE_MAP_DEFAULT: dict[str, str] = dict(DEFAULT_SUBSCRIPTION_REPLACE_MAP)


class SubscriptionSyncError(RuntimeError):
    pass


def _contains_supported_scheme(text: str) -> bool:
    lowered = text.lower()
    return any(scheme in lowered for scheme in _SUPPORTED_SCHEMES)


def _decode_base64(text: str) -> str:
    normalized = re.sub(r"\s+", "", text).replace("-", "+").replace("_", "/")
    padding = (-len(normalized)) % 4
    if padding:
        normalized += "=" * padding
    return base64.b64decode(normalized).decode("utf-8", "ignore")


def _normalize_subscription_text(raw: str) -> str:
    trimmed = (raw or "").strip()
    if not trimmed:
        return ""

    if _contains_supported_scheme(trimmed):
        return trimmed

    try:
        decoded = _decode_base64(trimmed).strip()
    except Exception:
        return trimmed

    if _contains_supported_scheme(decoded):
        return decoded
    return trimmed


def _name_from_fragment(fragment: str, fallback: str) -> str:
    value = unquote((fragment or "").strip())
    return value or fallback


def _parse_host_port(value: str) -> tuple[str, int]:
    # Some subscription providers emit ss URIs like `host:port/?plugin=...`.
    # Strip the trailing slash so `port` remains parseable.
    host_port = value.strip().rstrip("/")
    if not host_port:
        raise ValueError("missing host:port")

    host = ""
    port_str = ""

    if host_port.startswith("["):
        closing = host_port.find("]")
        if closing <= 0:
            raise ValueError("invalid ipv6 host")
        host = host_port[1:closing]
        suffix = host_port[closing + 1 :]
        if not suffix.startswith(":"):
            raise ValueError("invalid port separator")
        port_str = suffix[1:]
    else:
        if ":" not in host_port:
            raise ValueError("missing port")
        host, port_str = host_port.rsplit(":", 1)

    port = int(port_str)
    if not host or port <= 0:
        raise ValueError("invalid host/port")
    return host, port


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if not value:
        return default
    return value in {"1", "true", "yes", "on"}


def _parse_plugin(raw: str | None) -> tuple[str | None, dict[str, Any]]:
    if not raw:
        return None, {}

    decoded = unquote(raw)
    segments = [part for part in decoded.split(";") if part]
    if not segments:
        return None, {}

    plugin_name = segments[0]
    options: dict[str, str] = {}
    for segment in segments[1:]:
        if "=" not in segment:
            continue
        key, value = segment.split("=", 1)
        key = key.strip()
        if not key:
            continue
        options[key] = value.strip()

    if "obfs" in plugin_name:
        mode = options.get("obfs") or options.get("mode")
        host = options.get("obfs-host") or options.get("host")
        plugin_opts: dict[str, Any] = {}
        if mode:
            plugin_opts["mode"] = mode
        if host:
            plugin_opts["host"] = host
        return "obfs", plugin_opts

    return plugin_name, options


def _clean_node_name(name: str, replace_map: dict[str, str] | None = None) -> str:
    cleaned = name
    normalized_map = replace_map if isinstance(replace_map, dict) else _REPLACE_MAP_DEFAULT

    for old, new in normalized_map.items():
        if old == "":
            continue
        replacement = str(new or "")
        try:
            cleaned = re.sub(old, replacement, cleaned)
        except re.error:
            cleaned = cleaned.replace(old, replacement)

    return cleaned.strip()


def _apply_rename(name: str, rename_prefix: str, replace_map: dict[str, str] | None = None) -> str:
    base = _clean_node_name(name, replace_map=replace_map) or name.strip() or "node"
    if not rename_prefix:
        return base
    prefix = rename_prefix.strip()
    if not prefix:
        return base
    return f"{prefix}-{base}" if not prefix.endswith("-") else f"{prefix}{base}"


def _parse_ss_url(line: str) -> dict[str, Any]:
    rest = line[len("ss://") :]

    hash_index = rest.find("#")
    node_name = ""
    if hash_index >= 0:
        node_name = unquote(rest[hash_index + 1 :])
        rest = rest[:hash_index]

    query = ""
    query_index = rest.find("?")
    if query_index >= 0:
        query = rest[query_index + 1 :]
        rest = rest[:query_index]

    user_info_host = rest
    if "@" not in rest:
        user_info_host = _decode_base64(rest)

    if "@" not in user_info_host:
        raise ValueError("invalid ss node")

    user_info, host_port = user_info_host.rsplit("@", 1)
    if ":" not in user_info:
        user_info = _decode_base64(user_info)

    if ":" not in user_info:
        raise ValueError("invalid ss auth")

    method, password = user_info.split(":", 1)
    host, port = _parse_host_port(host_port)

    params = parse_qs(query, keep_blank_values=True)
    plugin, plugin_opts = _parse_plugin((params.get("plugin") or [None])[0])

    result: dict[str, Any] = {
        "type": "shadowsocks",
        "tag": node_name or f"{host}:{port}",
        "server": host,
        "server_port": port,
        "method": method,
        "password": password,
    }

    if plugin:
        result["plugin"] = plugin
        if plugin_opts:
            result["plugin_opts"] = plugin_opts

    return result


def _parse_trojan_url(line: str) -> dict[str, Any]:
    parsed = urlparse(line)
    if parsed.scheme != "trojan":
        raise ValueError("invalid trojan uri")

    host = parsed.hostname or ""
    port = int(parsed.port or 0)
    username = unquote(parsed.username or "")
    password_suffix = f":{unquote(parsed.password)}" if parsed.password else ""
    password = f"{username}{password_suffix}".strip()
    if not host or not port or not password:
        raise ValueError("invalid trojan auth/target")

    node_name = _name_from_fragment(parsed.fragment, f"{host}:{port}")
    params = parse_qs(parsed.query, keep_blank_values=True)

    result: dict[str, Any] = {
        "type": "trojan",
        "tag": node_name,
        "server": host,
        "server_port": port,
        "password": password,
    }

    tls: dict[str, Any] = {"enabled": True}
    if _parse_bool((params.get("allowInsecure") or [""])[0], False):
        tls["insecure"] = True

    sni = (params.get("sni") or params.get("peer") or [""])[0].strip()
    if sni:
        tls["server_name"] = sni

    alpn_raw = (params.get("alpn") or [""])[0]
    if alpn_raw:
        alpn = [part.strip() for part in alpn_raw.split(",") if part.strip()]
        if alpn:
            tls["alpn"] = alpn

    result["tls"] = tls

    network = (params.get("type") or [""])[0].strip().lower()
    if network == "ws":
        transport: dict[str, Any] = {
            "type": "ws",
            "path": (params.get("path") or ["/"])[0] or "/",
        }
        ws_host = (params.get("host") or [""])[0].strip()
        if ws_host:
            transport["headers"] = {"Host": ws_host}
        result["transport"] = transport

    return result


def _parse_vmess_url(line: str) -> dict[str, Any]:
    payload = line[len("vmess://") :].strip()
    info = json.loads(_decode_base64(payload))

    host = str(info.get("add") or "").strip()
    port = int(str(info.get("port") or "0").strip() or 0)
    uuid = str(info.get("id") or "").strip()
    if not host or not port or not uuid:
        raise ValueError("invalid vmess payload")

    node_name = str(info.get("ps") or f"{host}:{port}").strip()
    result: dict[str, Any] = {
        "type": "vmess",
        "tag": node_name,
        "server": host,
        "server_port": port,
        "uuid": uuid,
    }

    security = str(info.get("scy") or info.get("security") or "auto").strip()
    if security:
        result["security"] = security

    try:
        alter_id = int(str(info.get("aid") or "0"))
    except Exception:
        alter_id = 0
    if alter_id > 0:
        result["alter_id"] = alter_id

    tls_flag = str(info.get("tls") or "").strip().lower() in {"tls", "1", "true"}
    if tls_flag:
        tls: dict[str, Any] = {"enabled": True}
        sni = str(info.get("sni") or info.get("host") or "").strip()
        if sni:
            tls["server_name"] = sni
        result["tls"] = tls

    net = str(info.get("net") or "").strip().lower()
    if net == "ws":
        path = str(info.get("path") or "/").strip() or "/"
        host_header = str(info.get("host") or "").strip()
        transport: dict[str, Any] = {"type": "ws", "path": path}
        if host_header:
            transport["headers"] = {"Host": host_header}
        result["transport"] = transport
    elif net == "grpc":
        service = str(info.get("path") or "").strip()
        transport = {"type": "grpc"}
        if service:
            transport["service_name"] = service
        result["transport"] = transport

    return result


def _parse_vless_url(line: str) -> dict[str, Any]:
    parsed = urlparse(line)
    if parsed.scheme != "vless":
        raise ValueError("invalid vless uri")

    host = parsed.hostname or ""
    port = int(parsed.port or 0)
    uuid = unquote(parsed.username or "").strip()
    if not host or not port or not uuid:
        raise ValueError("invalid vless auth/target")

    node_name = _name_from_fragment(parsed.fragment, f"{host}:{port}")
    params = parse_qs(parsed.query, keep_blank_values=True)

    result: dict[str, Any] = {
        "type": "vless",
        "tag": node_name,
        "server": host,
        "server_port": port,
        "uuid": uuid,
    }

    flow = (params.get("flow") or [""])[0].strip()
    if flow:
        result["flow"] = flow

    security = (params.get("security") or [""])[0].strip().lower()
    if security in {"tls", "reality"}:
        tls: dict[str, Any] = {"enabled": True}
        if security == "reality":
            tls["utls"] = {"enabled": True}
        sni = (params.get("sni") or [""])[0].strip()
        if sni:
            tls["server_name"] = sni
        alpn_raw = (params.get("alpn") or [""])[0]
        if alpn_raw:
            alpn = [part.strip() for part in alpn_raw.split(",") if part.strip()]
            if alpn:
                tls["alpn"] = alpn
        if _parse_bool((params.get("allowInsecure") or [""])[0], False):
            tls["insecure"] = True
        result["tls"] = tls

    network = (params.get("type") or [""])[0].strip().lower()
    if network == "ws":
        transport: dict[str, Any] = {
            "type": "ws",
            "path": (params.get("path") or ["/"])[0] or "/",
        }
        ws_host = (params.get("host") or [""])[0].strip()
        if ws_host:
            transport["headers"] = {"Host": ws_host}
        result["transport"] = transport
    elif network == "grpc":
        service_name = (params.get("serviceName") or params.get("service_name") or [""])[0].strip()
        transport = {"type": "grpc"}
        if service_name:
            transport["service_name"] = service_name
        result["transport"] = transport

    return result


def _parse_hysteria2_url(line: str) -> dict[str, Any]:
    parsed = urlparse(line.replace("hy2://", "hysteria2://", 1))
    host = parsed.hostname or ""
    port = int(parsed.port or 0)
    password = unquote(parsed.username or "").strip()
    if not host or not port:
        raise ValueError("invalid hysteria2 target")

    node_name = _name_from_fragment(parsed.fragment, f"{host}:{port}")
    params = parse_qs(parsed.query, keep_blank_values=True)

    result: dict[str, Any] = {
        "type": "hysteria2",
        "tag": node_name,
        "server": host,
        "server_port": port,
    }
    if password:
        result["password"] = password

    tls: dict[str, Any] = {"enabled": True}
    sni = (params.get("sni") or [""])[0].strip()
    if sni:
        tls["server_name"] = sni
    if _parse_bool((params.get("insecure") or [""])[0], False):
        tls["insecure"] = True
    result["tls"] = tls

    obfs = (params.get("obfs") or [""])[0].strip()
    obfs_password = (params.get("obfs-password") or [""])[0].strip()
    if obfs:
        result["obfs"] = {
            "type": obfs,
            "password": obfs_password,
        }

    return result


def _parse_line(line: str) -> dict[str, Any]:
    lowered = line.lower()
    if lowered.startswith("ss://"):
        return _parse_ss_url(line)
    if lowered.startswith("trojan://"):
        return _parse_trojan_url(line)
    if lowered.startswith("vmess://"):
        return _parse_vmess_url(line)
    if lowered.startswith("vless://"):
        return _parse_vless_url(line)
    if lowered.startswith("hysteria2://") or lowered.startswith("hy2://"):
        return _parse_hysteria2_url(line)
    raise ValueError("unsupported node type")


def _ensure_unique_tags(outbounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    used: set[str] = set()
    result: list[dict[str, Any]] = []

    for row in outbounds:
        base = str(row.get("tag") or "node").strip() or "node"
        tag = base
        suffix = 2
        while tag in used:
            tag = f"{base}-{suffix}"
            suffix += 1
        used.add(tag)

        updated = dict(row)
        updated["tag"] = tag
        result.append(updated)

    return result


def _normalize_filter_tokens(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []

    result: list[str] = []
    seen: set[str] = set()
    for raw_item in values:
        token = str(raw_item or "").strip().lower()
        if not token:
            continue
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result


def _passes_global_filter(name: str, available_flags: list[str], exclude_flags: list[str]) -> bool:
    lowered_name = name.lower()

    if available_flags and not any(flag in lowered_name for flag in available_flags):
        return False

    if exclude_flags and any(flag in lowered_name for flag in exclude_flags):
        return False

    return True


def fetch_subscription_content(url: str, user_agent: str = "", timeout: float = 20.0) -> str:
    headers = {"User-Agent": user_agent.strip() or DEFAULT_SUBSCRIPTION_UA}
    response = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
    response.raise_for_status()
    return response.text


def fetch_and_build_subscription_outbounds(
    subscription: dict[str, Any],
    timeout: float = 20.0,
    replace_map: dict[str, str] | None = None,
    filter_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = str(subscription.get("url") or "").strip()
    if not url:
        raise SubscriptionSyncError("订阅 URL 为空")

    user_agent = str(subscription.get("user_agent") or "").strip()
    rename_prefix = str(subscription.get("rename_prefix") or "").strip()

    effective_replace_map = replace_map if isinstance(replace_map, dict) else _REPLACE_MAP_DEFAULT
    normalized_filter = filter_config if isinstance(filter_config, dict) else {}
    available_flags = _normalize_filter_tokens(normalized_filter.get("available_flags"))
    exclude_flags = _normalize_filter_tokens(normalized_filter.get("exclude_flags"))

    try:
        raw_text = fetch_subscription_content(url=url, user_agent=user_agent, timeout=timeout)
    except Exception as exc:  # pragma: no cover - network failures are runtime dependent
        raise SubscriptionSyncError(f"拉取订阅失败: {exc}") from exc

    normalized = _normalize_subscription_text(raw_text)
    lines = [line.strip() for line in normalized.splitlines() if line.strip() and not line.strip().startswith("#")]

    parsed_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped_nodes = 0

    for index, line in enumerate(lines):
        try:
            row = _parse_line(line)
            parsed_rows.append(row)
        except Exception as exc:
            skipped_nodes += 1
            warnings.append(f"line {index + 1}: {exc}")

    if not parsed_rows:
        raise SubscriptionSyncError(
            "未解析到可用节点（当前支持 ss/trojan/vmess/vless/hysteria2）"
        )

    filtered_nodes = 0
    outbounds: list[dict[str, Any]] = []

    for row in parsed_rows:
        original_name = str(row.get("tag") or "node")
        if not _passes_global_filter(original_name, available_flags, exclude_flags):
            filtered_nodes += 1
            continue

        renamed = _apply_rename(original_name, rename_prefix=rename_prefix, replace_map=effective_replace_map)
        updated = dict(row)
        updated["tag"] = renamed
        outbounds.append(updated)

    outbounds = _ensure_unique_tags(outbounds)

    return {
        "outbounds": outbounds,
        "fetched_nodes": len(parsed_rows),
        "filtered_nodes": filtered_nodes,
        "skipped_nodes": skipped_nodes,
        "warnings": warnings,
    }
