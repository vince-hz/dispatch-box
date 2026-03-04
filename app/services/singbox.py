from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from ..config import DATA_DIR

BASE_CONFIG_PATH = Path(DATA_DIR) / "base_config.json"
CLASH_TEMPLATE_PATH = Path(DATA_DIR) / "clash_template.json"
DEFAULT_BASE_CONFIG: dict[str, Any] = {
    "route": {
        "rules": [],
        "rule_set": [],
    }
}
DEFAULT_CLASH_TEMPLATE: dict[str, Any] = {
    "mixed-port": 7890,
    "allow-lan": False,
    "mode": "rule",
    "log-level": "info",
    "proxies": [],
    "proxy-groups": [
        {
            "name": "Proxy",
            "type": "select",
            "proxies": ["DIRECT"],
            "includeAllProxies": True,
        },
        {
            "name": "Auto",
            "type": "url-test",
            "url": "https://www.gstatic.com/generate_204",
            "interval": 300,
            "tolerance": 50,
            "includeAllProxies": True,
        },
    ],
    "rules": ["MATCH,Proxy"],
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


def ensure_clash_template_file() -> None:
    if CLASH_TEMPLATE_PATH.exists():
        return
    CLASH_TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CLASH_TEMPLATE_PATH.write_text(
        json.dumps(DEFAULT_CLASH_TEMPLATE, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_clash_template() -> dict[str, Any]:
    ensure_clash_template_file()
    try:
        raw = json.loads(CLASH_TEMPLATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return deepcopy(DEFAULT_CLASH_TEMPLATE)
    if not isinstance(raw, dict):
        return deepcopy(DEFAULT_CLASH_TEMPLATE)
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
        _normalize_shadowsocks_plugin_fields(cleaned)
        result.append(cleaned)

    return result


def _normalize_plugin_opts_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw.strip()
    if not isinstance(raw, dict):
        return ""

    parts: list[str] = []
    for key in sorted(raw.keys()):
        k = str(key or "").strip()
        if not k:
            continue
        v = str(raw.get(key) or "").strip()
        if not v:
            continue
        parts.append(f"{k}={v}")
    return ";".join(parts)


def _parse_plugin_opts_map(raw: Any) -> dict[str, str]:
    if isinstance(raw, dict):
        result: dict[str, str] = {}
        for key in sorted(raw.keys()):
            k = str(key or "").strip()
            if not k:
                continue
            v = str(raw.get(key) or "").strip()
            if not v:
                continue
            result[k] = v
        return result

    if not isinstance(raw, str):
        return {}

    result: dict[str, str] = {}
    segments = [part.strip() for part in raw.split(";") if part.strip()]
    for segment in segments:
        if "=" not in segment:
            continue
        key, value = segment.split("=", 1)
        k = key.strip()
        v = value.strip()
        if not k or not v:
            continue
        result[k] = v
    return result


def _normalize_shadowsocks_plugin_fields(outbound: dict[str, Any]) -> None:
    if str(outbound.get("type") or "").strip().lower() != "shadowsocks":
        return

    plugin = str(outbound.get("plugin") or "").strip().lower()
    plugin_opts_raw = outbound.get("plugin_opts")

    # sing-box expects plugin name `obfs-local` and string `plugin_opts`.
    if plugin in {"obfs", "simple-obfs", "simpleobfs"}:
        outbound["plugin"] = "obfs-local"

        if isinstance(plugin_opts_raw, dict):
            mode = str(plugin_opts_raw.get("mode") or plugin_opts_raw.get("obfs") or "").strip()
            host = str(plugin_opts_raw.get("host") or plugin_opts_raw.get("obfs-host") or "").strip()
            parts: list[str] = []
            if mode:
                parts.append(f"obfs={mode}")
            if host:
                parts.append(f"obfs-host={host}")
            outbound["plugin_opts"] = ";".join(parts)
            return

    if plugin_opts_raw is None:
        return
    outbound["plugin_opts"] = _normalize_plugin_opts_text(plugin_opts_raw)


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


def _format_uri_host(host: str) -> str:
    value = str(host or "").strip()
    if not value:
        return ""
    if ":" in value and not (value.startswith("[") and value.endswith("]")):
        return f"[{value}]"
    return value


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _string(value: Any) -> str:
    return str(value or "").strip()


def _build_query(params: dict[str, Any]) -> str:
    filtered: dict[str, str] = {}
    for key, value in params.items():
        text = _string(value)
        if text:
            filtered[key] = text
    if not filtered:
        return ""
    return "?" + urlencode(filtered, quote_via=quote)


def _share_ss(outbound: dict[str, Any]) -> str | None:
    method = _string(outbound.get("method"))
    password = _string(outbound.get("password"))
    server = _format_uri_host(_string(outbound.get("server")))
    port = _safe_int(outbound.get("server_port"), 0)
    tag = _string(outbound.get("tag")) or f"{server}:{port}"
    if not method or not password or not server or port <= 0:
        return None

    userinfo = f"{method}:{password}@{server}:{port}"
    encoded_userinfo = base64.urlsafe_b64encode(userinfo.encode("utf-8")).decode("utf-8").rstrip("=")

    plugin = _string(outbound.get("plugin")).lower()
    plugin_opts = _parse_plugin_opts_map(outbound.get("plugin_opts"))
    query: dict[str, str] = {}
    if plugin:
        if plugin in {"obfs", "obfs-local", "simple-obfs", "simpleobfs"}:
            segments = ["obfs-local"]
            mode = _string(plugin_opts.get("mode") or plugin_opts.get("obfs"))
            host = _string(plugin_opts.get("host") or plugin_opts.get("obfs-host"))
            if mode:
                segments.append(f"obfs={mode}")
            if host:
                segments.append(f"obfs-host={host}")
            query["plugin"] = ";".join(segments)
        else:
            segments = [plugin]
            for key in sorted(plugin_opts.keys()):
                k = _string(key)
                if not k:
                    continue
                v = _string(plugin_opts.get(key))
                if not v:
                    continue
                segments.append(f"{k}={v}")
            query["plugin"] = ";".join(segments)

    return f"ss://{encoded_userinfo}{_build_query(query)}#{quote(tag, safe='')}"


def _share_trojan(outbound: dict[str, Any]) -> str | None:
    password = _string(outbound.get("password"))
    server = _format_uri_host(_string(outbound.get("server")))
    port = _safe_int(outbound.get("server_port"), 0)
    tag = _string(outbound.get("tag")) or f"{server}:{port}"
    if not password or not server or port <= 0:
        return None

    query: dict[str, Any] = {}
    tls_raw = outbound.get("tls")
    tls = tls_raw if isinstance(tls_raw, dict) else {}
    if tls.get("enabled"):
        query["security"] = "tls"
    if tls.get("insecure"):
        query["allowInsecure"] = "1"
    if tls.get("server_name"):
        query["sni"] = tls.get("server_name")
    if isinstance(tls.get("alpn"), list):
        alpn = [str(item).strip() for item in tls.get("alpn") if str(item).strip()]
        if alpn:
            query["alpn"] = ",".join(alpn)

    transport_raw = outbound.get("transport")
    transport = transport_raw if isinstance(transport_raw, dict) else {}
    transport_type = _string(transport.get("type")).lower()
    if transport_type == "ws":
        query["type"] = "ws"
        query["path"] = _string(transport.get("path")) or "/"
        headers = transport.get("headers")
        if isinstance(headers, dict):
            host = _string(headers.get("Host"))
            if host:
                query["host"] = host
    elif transport_type == "grpc":
        query["type"] = "grpc"
        query["serviceName"] = _string(transport.get("service_name"))

    return (
        f"trojan://{quote(password, safe='')}@{server}:{port}"
        f"{_build_query(query)}"
        f"#{quote(tag, safe='')}"
    )


def _share_vmess(outbound: dict[str, Any]) -> str | None:
    server = _string(outbound.get("server"))
    port = _safe_int(outbound.get("server_port"), 0)
    uuid = _string(outbound.get("uuid"))
    tag = _string(outbound.get("tag")) or f"{server}:{port}"
    if not server or port <= 0 or not uuid:
        return None

    vmess: dict[str, str] = {
        "v": "2",
        "ps": tag,
        "add": server,
        "port": str(port),
        "id": uuid,
        "aid": str(_safe_int(outbound.get("alter_id"), 0)),
        "scy": _string(outbound.get("security")) or "auto",
        "net": "tcp",
        "type": "none",
        "host": "",
        "path": "",
        "tls": "",
    }

    tls_raw = outbound.get("tls")
    tls = tls_raw if isinstance(tls_raw, dict) else {}
    if tls.get("enabled"):
        vmess["tls"] = "tls"
    server_name = _string(tls.get("server_name"))
    if server_name:
        vmess["sni"] = server_name

    transport_raw = outbound.get("transport")
    transport = transport_raw if isinstance(transport_raw, dict) else {}
    transport_type = _string(transport.get("type")).lower()
    if transport_type == "ws":
        vmess["net"] = "ws"
        vmess["path"] = _string(transport.get("path")) or "/"
        headers = transport.get("headers")
        if isinstance(headers, dict):
            vmess["host"] = _string(headers.get("Host"))
    elif transport_type == "grpc":
        vmess["net"] = "grpc"
        vmess["path"] = _string(transport.get("service_name"))

    payload = json.dumps(vmess, ensure_ascii=False, separators=(",", ":"))
    encoded = base64.b64encode(payload.encode("utf-8")).decode("utf-8")
    return f"vmess://{encoded}"


def _share_vless(outbound: dict[str, Any]) -> str | None:
    server = _format_uri_host(_string(outbound.get("server")))
    port = _safe_int(outbound.get("server_port"), 0)
    uuid = _string(outbound.get("uuid"))
    tag = _string(outbound.get("tag")) or f"{server}:{port}"
    if not server or port <= 0 or not uuid:
        return None

    query: dict[str, Any] = {"encryption": "none"}
    tls_raw = outbound.get("tls")
    tls = tls_raw if isinstance(tls_raw, dict) else {}
    if tls.get("enabled"):
        utls_raw = tls.get("utls")
        utls = utls_raw if isinstance(utls_raw, dict) else {}
        query["security"] = "reality" if utls.get("enabled") else "tls"
    if tls.get("server_name"):
        query["sni"] = tls.get("server_name")
    if isinstance(tls.get("alpn"), list):
        alpn = [str(item).strip() for item in tls.get("alpn") if str(item).strip()]
        if alpn:
            query["alpn"] = ",".join(alpn)
    if tls.get("insecure"):
        query["allowInsecure"] = "1"
    flow = _string(outbound.get("flow"))
    if flow:
        query["flow"] = flow

    transport_raw = outbound.get("transport")
    transport = transport_raw if isinstance(transport_raw, dict) else {}
    transport_type = _string(transport.get("type")).lower()
    if transport_type == "ws":
        query["type"] = "ws"
        query["path"] = _string(transport.get("path")) or "/"
        headers = transport.get("headers")
        if isinstance(headers, dict):
            host = _string(headers.get("Host"))
            if host:
                query["host"] = host
    elif transport_type == "grpc":
        query["type"] = "grpc"
        query["serviceName"] = _string(transport.get("service_name"))

    return (
        f"vless://{quote(uuid, safe='')}@{server}:{port}"
        f"{_build_query(query)}"
        f"#{quote(tag, safe='')}"
    )


def _share_hysteria2(outbound: dict[str, Any]) -> str | None:
    server = _format_uri_host(_string(outbound.get("server")))
    port = _safe_int(outbound.get("server_port"), 0)
    password = _string(outbound.get("password"))
    tag = _string(outbound.get("tag")) or f"{server}:{port}"
    if not server or port <= 0:
        return None

    query: dict[str, Any] = {}
    tls_raw = outbound.get("tls")
    tls = tls_raw if isinstance(tls_raw, dict) else {}
    if tls.get("server_name"):
        query["sni"] = tls.get("server_name")
    if tls.get("insecure"):
        query["insecure"] = "1"

    obfs_raw = outbound.get("obfs")
    obfs = obfs_raw if isinstance(obfs_raw, dict) else {}
    obfs_type = _string(obfs.get("type"))
    if obfs_type:
        query["obfs"] = obfs_type
    obfs_password = _string(obfs.get("password"))
    if obfs_password:
        query["obfs-password"] = obfs_password

    if password:
        return (
            f"hy2://{quote(password, safe='')}@{server}:{port}"
            f"{_build_query(query)}"
            f"#{quote(tag, safe='')}"
        )
    return f"hy2://{server}:{port}{_build_query(query)}#{quote(tag, safe='')}"


def singbox_outbound_to_share_link(outbound: dict[str, Any]) -> str | None:
    outbound_type = _string(outbound.get("type")).lower()
    if outbound_type == "shadowsocks":
        return _share_ss(outbound)
    if outbound_type == "trojan":
        return _share_trojan(outbound)
    if outbound_type == "vmess":
        return _share_vmess(outbound)
    if outbound_type == "vless":
        return _share_vless(outbound)
    if outbound_type == "hysteria2":
        return _share_hysteria2(outbound)
    return None


def build_shadowrocket_subscription_bundle(outbounds: list[dict[str, Any]]) -> str:
    links: list[str] = []
    for outbound in outbounds:
        if not isinstance(outbound, dict):
            continue
        link = singbox_outbound_to_share_link(outbound)
        if link:
            links.append(link)

    if not links:
        return ""

    raw_text = "\n".join(links)
    encoded = base64.b64encode(raw_text.encode("utf-8")).decode("utf-8")
    return encoded + "\n"


def _clash_ws_opts(transport: dict[str, Any]) -> dict[str, Any]:
    ws_opts: dict[str, Any] = {
        "path": _string(transport.get("path")) or "/",
    }
    headers = transport.get("headers")
    if isinstance(headers, dict):
        host = _string(headers.get("Host"))
        if host:
            ws_opts["headers"] = {"Host": host}
    return ws_opts


def _clash_grpc_opts(transport: dict[str, Any]) -> dict[str, Any]:
    service_name = _string(transport.get("service_name"))
    if not service_name:
        return {}
    return {
        "grpc-service-name": service_name,
    }


def singbox_outbound_to_clash_proxy(outbound: dict[str, Any]) -> dict[str, Any] | None:
    outbound_type = _string(outbound.get("type")).lower()
    name = _string(outbound.get("tag"))
    server = _string(outbound.get("server"))
    port = _safe_int(outbound.get("server_port"), 0)
    if not name or not server or port <= 0:
        return None

    tls_raw = outbound.get("tls")
    tls = tls_raw if isinstance(tls_raw, dict) else {}
    transport_raw = outbound.get("transport")
    transport = transport_raw if isinstance(transport_raw, dict) else {}
    transport_type = _string(transport.get("type")).lower()

    if outbound_type == "shadowsocks":
        cipher = _string(outbound.get("method"))
        password = _string(outbound.get("password"))
        if not cipher or not password:
            return None
        proxy: dict[str, Any] = {
            "name": name,
            "type": "ss",
            "server": server,
            "port": port,
            "cipher": cipher,
            "password": password,
            "udp": True,
        }

        plugin = _string(outbound.get("plugin")).lower()
        plugin_opts = _parse_plugin_opts_map(outbound.get("plugin_opts"))
        if plugin in {"obfs", "obfs-local", "simple-obfs", "simpleobfs"}:
            proxy["plugin"] = "obfs"
            plugin_opts_item: dict[str, Any] = {}
            mode = _string(plugin_opts.get("mode") or plugin_opts.get("obfs"))
            host = _string(plugin_opts.get("host") or plugin_opts.get("obfs-host"))
            if mode:
                plugin_opts_item["mode"] = mode
            if host:
                plugin_opts_item["host"] = host
            if plugin_opts_item:
                proxy["plugin-opts"] = plugin_opts_item
        elif plugin:
            proxy["plugin"] = plugin
            if plugin_opts:
                proxy["plugin-opts"] = plugin_opts

        return proxy

    if outbound_type == "trojan":
        password = _string(outbound.get("password"))
        if not password:
            return None
        proxy = {
            "name": name,
            "type": "trojan",
            "server": server,
            "port": port,
            "password": password,
            "udp": True,
        }
        server_name = _string(tls.get("server_name"))
        if server_name:
            proxy["sni"] = server_name
        if tls.get("insecure"):
            proxy["skip-cert-verify"] = True

        if transport_type == "ws":
            proxy["network"] = "ws"
            proxy["ws-opts"] = _clash_ws_opts(transport)
        elif transport_type == "grpc":
            proxy["network"] = "grpc"
            grpc_opts = _clash_grpc_opts(transport)
            if grpc_opts:
                proxy["grpc-opts"] = grpc_opts

        return proxy

    if outbound_type == "vmess":
        uuid = _string(outbound.get("uuid"))
        if not uuid:
            return None
        proxy = {
            "name": name,
            "type": "vmess",
            "server": server,
            "port": port,
            "uuid": uuid,
            "alterId": _safe_int(outbound.get("alter_id"), 0),
            "cipher": _string(outbound.get("security")) or "auto",
            "udp": True,
        }

        if tls.get("enabled"):
            proxy["tls"] = True
            server_name = _string(tls.get("server_name"))
            if server_name:
                proxy["servername"] = server_name
            if tls.get("insecure"):
                proxy["skip-cert-verify"] = True

        if transport_type == "ws":
            proxy["network"] = "ws"
            proxy["ws-opts"] = _clash_ws_opts(transport)
        elif transport_type == "grpc":
            proxy["network"] = "grpc"
            grpc_opts = _clash_grpc_opts(transport)
            if grpc_opts:
                proxy["grpc-opts"] = grpc_opts

        return proxy

    if outbound_type == "vless":
        uuid = _string(outbound.get("uuid"))
        if not uuid:
            return None
        proxy = {
            "name": name,
            "type": "vless",
            "server": server,
            "port": port,
            "uuid": uuid,
            "udp": True,
        }

        flow = _string(outbound.get("flow"))
        if flow:
            proxy["flow"] = flow

        if tls.get("enabled"):
            proxy["tls"] = True
            server_name = _string(tls.get("server_name"))
            if server_name:
                proxy["servername"] = server_name
            if tls.get("insecure"):
                proxy["skip-cert-verify"] = True

        if transport_type == "ws":
            proxy["network"] = "ws"
            proxy["ws-opts"] = _clash_ws_opts(transport)
        elif transport_type == "grpc":
            proxy["network"] = "grpc"
            grpc_opts = _clash_grpc_opts(transport)
            if grpc_opts:
                proxy["grpc-opts"] = grpc_opts

        return proxy

    if outbound_type == "hysteria2":
        proxy = {
            "name": name,
            "type": "hysteria2",
            "server": server,
            "port": port,
            "udp": True,
        }
        password = _string(outbound.get("password"))
        if password:
            proxy["password"] = password
        server_name = _string(tls.get("server_name"))
        if server_name:
            proxy["sni"] = server_name
        if tls.get("insecure"):
            proxy["skip-cert-verify"] = True

        obfs_raw = outbound.get("obfs")
        obfs = obfs_raw if isinstance(obfs_raw, dict) else {}
        obfs_type = _string(obfs.get("type"))
        if obfs_type:
            proxy["obfs"] = obfs_type
        obfs_password = _string(obfs.get("password"))
        if obfs_password:
            proxy["obfs-password"] = obfs_password

        return proxy

    return None


def _ensure_unique_clash_proxy_names(proxies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    used: set[str] = set()
    result: list[dict[str, Any]] = []

    for row in proxies:
        if not isinstance(row, dict):
            continue
        base = _string(row.get("name")) or "node"
        name = base
        suffix = 2
        while name in used:
            name = f"{base}-{suffix}"
            suffix += 1
        used.add(name)

        updated = dict(row)
        updated["name"] = name
        result.append(updated)

    return result


def _normalize_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in raw:
        value = _string(item)
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _normalize_clash_proxy_groups(raw: Any, proxy_names: list[str]) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    groups: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        group = dict(item)
        name = _string(group.get("name"))
        group_type = _string(group.get("type")).lower()
        if group_type == "urltest":
            group_type = "url-test"
        if not name or not group_type:
            continue

        include_all = _parse_bool(group.pop("includeAllProxies", False), False)
        if "include_all_proxies" in group:
            include_all = _parse_bool(group.pop("include_all_proxies"), include_all)

        proxies = _normalize_string_list(group.get("proxies"))
        if include_all:
            proxies = _merge_outbound_tags(proxies, proxy_names)
        if group_type in {"select", "url-test", "fallback", "load-balance", "relay"}:
            if not proxies:
                proxies = list(proxy_names) if proxy_names else ["DIRECT"]
            if group_type == "select" and "DIRECT" not in proxies:
                proxies.append("DIRECT")
            proxies = _merge_outbound_tags([], proxies)
            group["proxies"] = proxies

        group["name"] = name
        group["type"] = group_type
        groups.append(group)

    return groups


def _normalize_clash_rules(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    result: list[str] = []
    for item in raw:
        line = _string(item)
        if not line:
            continue
        result.append(line)
    return result


def _yaml_key(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _to_yaml(value: Any, indent: int = 0) -> str:
    prefix = " " * indent

    if isinstance(value, dict):
        if not value:
            return prefix + "{}"
        lines: list[str] = []
        for key, item in value.items():
            key_text = _yaml_key(str(key))
            if isinstance(item, dict) and not item:
                lines.append(f"{prefix}{key_text}: {{}}")
                continue
            if isinstance(item, list) and not item:
                lines.append(f"{prefix}{key_text}: []")
                continue
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key_text}:")
                lines.append(_to_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}{key_text}: {_yaml_scalar(item)}")
        return "\n".join(lines)

    if isinstance(value, list):
        if not value:
            return prefix + "[]"
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(_to_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {_yaml_scalar(item)}")
        return "\n".join(lines)

    return prefix + _yaml_scalar(value)


def build_clash_subscription_config(outbounds: list[dict[str, Any]]) -> dict[str, Any]:
    template = load_clash_template()
    result = deepcopy(template if isinstance(template, dict) else {})

    proxies: list[dict[str, Any]] = []
    for outbound in outbounds:
        if not isinstance(outbound, dict):
            continue
        proxy = singbox_outbound_to_clash_proxy(outbound)
        if proxy:
            proxies.append(proxy)

    proxies = _ensure_unique_clash_proxy_names(proxies)
    proxy_names = [str(item["name"]) for item in proxies if str(item.get("name") or "").strip()]
    result["proxies"] = proxies

    proxy_groups = _normalize_clash_proxy_groups(result.get("proxy-groups"), proxy_names)
    if not proxy_groups:
        proxy_groups = _normalize_clash_proxy_groups(DEFAULT_CLASH_TEMPLATE.get("proxy-groups"), proxy_names)
    result["proxy-groups"] = proxy_groups

    rules = _normalize_clash_rules(result.get("rules"))
    if not rules:
        rules = ["MATCH,Proxy"]
    result["rules"] = rules

    return result


def build_clash_subscription_bundle(outbounds: list[dict[str, Any]]) -> str:
    config = build_clash_subscription_config(outbounds)
    return _to_yaml(config) + "\n"


def check_singbox_config(config: dict[str, Any]) -> dict[str, Any]:
    checked_at = datetime.now(timezone.utc)

    configured_bin = str(os.getenv("SINGBOX_BIN", "sing-box")).strip() or "sing-box"
    resolved_bin = shutil.which(configured_bin)
    command = f"{configured_bin} check -c <temp-config>"

    if not resolved_bin:
        return {
            "ok": False,
            "message": f"未找到 sing-box 可执行文件：{configured_bin}",
            "command": command,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "checked_at": checked_at,
        }

    command = f"{resolved_bin} check -c <temp-config>"
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as temp_file:
            json.dump(config, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
            temp_path = temp_file.name

        command = f"{resolved_bin} check -c {temp_path}"
        completed = subprocess.run(
            [resolved_bin, "check", "-c", temp_path],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "message": "sing-box 静态检测超时（30s）",
            "command": command,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "checked_at": checked_at,
        }
    except Exception as exc:
        return {
            "ok": False,
            "message": f"执行 sing-box 检测失败：{exc}",
            "command": command,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "checked_at": checked_at,
        }
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass

    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    ok = completed.returncode == 0
    message = "sing-box 静态检测通过" if ok else (stderr or stdout or f"sing-box 检测失败（exit code: {completed.returncode}）")

    return {
        "ok": ok,
        "message": message,
        "command": command,
        "exit_code": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "checked_at": checked_at,
    }
