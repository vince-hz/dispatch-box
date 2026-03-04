from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import DOWNLOAD_TOKEN
from .schemas import (
    ConfigPreview,
    OutboundCreate,
    OutboundOut,
    OutboundUpdate,
    SingboxCheckResult,
    StaticLadderCreate,
    StaticLadderOut,
    StaticLadderUpdate,
    SubscriptionCreate,
    SubscriptionFilterOut,
    SubscriptionFilterUpdate,
    SubscriptionOut,
    SubscriptionRefreshBatchResult,
    SubscriptionRefreshResult,
    SubscriptionReplaceMapOut,
    SubscriptionReplaceMapUpdate,
    SubscriptionUpdate,
)
from .services.outbounds import (
    create_outbound,
    delete_outbound,
    list_outbounds,
    migrate_include_all_nodes_markers,
    purge_non_aggregate_outbounds,
    update_outbound,
)
from .services.singbox import (
    build_clash_subscription_bundle,
    build_full_config,
    ensure_clash_template_file,
    build_shadowrocket_subscription_bundle,
    build_subscription_bundle,
    check_singbox_config,
    ensure_base_config_file,
)
from .services.static_ladders import (
    create_static_ladder,
    delete_static_ladder,
    list_static_ladder_outbounds,
    list_static_ladders,
    migrate_legacy_static_ladders_to_provider,
    update_static_ladder,
)
from .services.subscription_sync import (
    SubscriptionSyncError,
    fetch_and_build_subscription_outbounds,
)
from .services.storage import (
    create_subscription,
    delete_subscription,
    get_subscription,
    get_subscription_global_filter,
    get_subscription_replace_map,
    list_subscriptions,
    list_subscription_cached_outbounds,
    save_subscription_sync_result,
    update_subscription,
    update_subscription_global_filter,
    update_subscription_replace_map,
)

BASE_DIR = Path(__file__).resolve().parent.parent
WEB_DIR = BASE_DIR / "web"

app = FastAPI(title="dispatch-box", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    ensure_base_config_file()
    ensure_clash_template_file()
    migrate_legacy_static_ladders_to_provider()
    purge_non_aggregate_outbounds()
    migrate_include_all_nodes_markers()


app.mount("/assets", StaticFiles(directory=WEB_DIR), name="assets")


def _assert_download_token(token: str | None) -> None:
    if DOWNLOAD_TOKEN and token != DOWNLOAD_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")


def _json_attachment_response(payload: object, filename: str) -> Response:
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    body = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    return Response(content=body, headers=headers, media_type="application/json")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/subscriptions", response_model=list[SubscriptionOut])
def api_list_subscriptions() -> list[SubscriptionOut]:
    return list_subscriptions()


@app.post("/api/subscriptions", response_model=SubscriptionOut)
def api_create_subscription(payload: SubscriptionCreate) -> SubscriptionOut:
    return create_subscription(payload)


@app.get("/api/subscriptions/rename-map", response_model=SubscriptionReplaceMapOut)
def api_get_subscription_replace_map() -> SubscriptionReplaceMapOut:
    return SubscriptionReplaceMapOut(replace_map=get_subscription_replace_map())


@app.put("/api/subscriptions/rename-map", response_model=SubscriptionReplaceMapOut)
def api_update_subscription_replace_map(payload: SubscriptionReplaceMapUpdate) -> SubscriptionReplaceMapOut:
    replace_map = update_subscription_replace_map(payload.replace_map)
    return SubscriptionReplaceMapOut(replace_map=replace_map)


@app.get("/api/subscriptions/filter", response_model=SubscriptionFilterOut)
def api_get_subscription_filter() -> SubscriptionFilterOut:
    result = get_subscription_global_filter()
    return SubscriptionFilterOut(
        available_flags=list(result.get("available_flags") or []),
        exclude_flags=list(result.get("exclude_flags") or []),
    )


@app.put("/api/subscriptions/filter", response_model=SubscriptionFilterOut)
def api_update_subscription_filter(payload: SubscriptionFilterUpdate) -> SubscriptionFilterOut:
    result = update_subscription_global_filter(
        {
            "available_flags": payload.available_flags,
            "exclude_flags": payload.exclude_flags,
        }
    )
    return SubscriptionFilterOut(
        available_flags=list(result.get("available_flags") or []),
        exclude_flags=list(result.get("exclude_flags") or []),
    )


@app.put("/api/subscriptions/{subscription_id}", response_model=SubscriptionOut)
def api_update_subscription(
    subscription_id: int, payload: SubscriptionUpdate
) -> SubscriptionOut:
    updated = update_subscription(subscription_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return updated


@app.delete("/api/subscriptions/{subscription_id}")
def api_delete_subscription(subscription_id: int) -> dict[str, bool]:
    ok = delete_subscription(subscription_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"ok": True}



def _sync_subscription(subscription_id: int) -> SubscriptionRefreshResult:
    subscription = get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    replace_map = get_subscription_replace_map()
    filter_config = get_subscription_global_filter()

    try:
        result = fetch_and_build_subscription_outbounds(
            subscription,
            replace_map=replace_map,
            filter_config=filter_config,
        )
    except SubscriptionSyncError as exc:
        save_subscription_sync_result(
            subscription_id,
            outbounds=list(subscription.get("cached_outbounds") or []),
            sync_error=str(exc),
        )
        return SubscriptionRefreshResult(
            id=subscription_id,
            name=str(subscription.get("name") or f"sub-{subscription_id}"),
            ok=False,
            error=str(exc),
            fetched_nodes=0,
            filtered_nodes=0,
            skipped_nodes=0,
            warnings=[],
        )
    except Exception as exc:  # pragma: no cover - unexpected runtime errors
        message = f"拉取订阅失败（已回退缓存）: {exc}"
        save_subscription_sync_result(
            subscription_id,
            outbounds=list(subscription.get("cached_outbounds") or []),
            sync_error=message,
        )
        return SubscriptionRefreshResult(
            id=subscription_id,
            name=str(subscription.get("name") or f"sub-{subscription_id}"),
            ok=False,
            error=message,
            fetched_nodes=0,
            filtered_nodes=0,
            skipped_nodes=0,
            warnings=[],
        )

    save_subscription_sync_result(
        subscription_id,
        outbounds=list(result.get("outbounds") or []),
        sync_error="",
    )

    return SubscriptionRefreshResult(
        id=subscription_id,
        name=str(subscription.get("name") or f"sub-{subscription_id}"),
        ok=True,
        fetched_nodes=int(result.get("fetched_nodes") or 0),
        filtered_nodes=int(result.get("filtered_nodes") or 0),
        skipped_nodes=int(result.get("skipped_nodes") or 0),
        warnings=list(result.get("warnings") or []),
    )


@app.post("/api/subscriptions/{subscription_id}/refresh", response_model=SubscriptionRefreshResult)
def api_refresh_subscription(subscription_id: int) -> SubscriptionRefreshResult:
    return _sync_subscription(subscription_id)


@app.post("/api/subscriptions/refresh", response_model=SubscriptionRefreshBatchResult)
def api_refresh_subscriptions(enabled_only: bool = True) -> SubscriptionRefreshBatchResult:
    subscriptions = list_subscriptions()
    target_rows = [item for item in subscriptions if item.get("enabled")] if enabled_only else subscriptions

    results: list[SubscriptionRefreshResult] = []
    for row in target_rows:
        subscription_id = int(row["id"])
        results.append(_sync_subscription(subscription_id))

    failed = len([item for item in results if not item.ok])
    return SubscriptionRefreshBatchResult(
        total=len(target_rows),
        refreshed=len(results) - failed,
        failed=failed,
        results=results,
    )


@app.get("/api/outbounds", response_model=list[OutboundOut])
def api_list_outbounds() -> list[OutboundOut]:
    return list_outbounds()


@app.post("/api/outbounds", response_model=OutboundOut)
def api_create_outbound(payload: OutboundCreate) -> OutboundOut:
    try:
        return create_outbound(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Create outbound failed: {exc}") from exc


@app.put("/api/outbounds/{outbound_id}", response_model=OutboundOut)
def api_update_outbound(outbound_id: int, payload: OutboundUpdate) -> OutboundOut:
    try:
        updated = update_outbound(outbound_id, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Update outbound failed: {exc}") from exc

    if not updated:
        raise HTTPException(status_code=404, detail="Outbound not found")
    return updated


@app.delete("/api/outbounds/{outbound_id}")
def api_delete_outbound(outbound_id: int) -> dict[str, bool]:
    ok = delete_outbound(outbound_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Outbound not found")
    return {"ok": True}


@app.get("/api/static-ladders", response_model=list[StaticLadderOut])
def api_list_static_ladders() -> list[StaticLadderOut]:
    return list_static_ladders()


@app.post("/api/static-ladders", response_model=StaticLadderOut)
def api_create_static_ladder(payload: StaticLadderCreate) -> StaticLadderOut:
    try:
        return create_static_ladder(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Create static ladder failed: {exc}") from exc


@app.put("/api/static-ladders/{ladder_id}", response_model=StaticLadderOut)
def api_update_static_ladder(ladder_id: int, payload: StaticLadderUpdate) -> StaticLadderOut:
    try:
        updated = update_static_ladder(ladder_id, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Update static ladder failed: {exc}") from exc

    if not updated:
        raise HTTPException(status_code=404, detail="Static ladder not found")
    return updated


@app.delete("/api/static-ladders/{ladder_id}")
def api_delete_static_ladder(ladder_id: int) -> dict[str, bool]:
    ok = delete_static_ladder(ladder_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Static ladder not found")
    return {"ok": True}


@app.get("/api/config/preview", response_model=ConfigPreview)
def api_config_preview() -> ConfigPreview:
    subscriptions = list_subscriptions()
    outbounds = list_outbounds()
    static_ladders = list_static_ladders()
    overlay = build_full_config(
        outbounds=outbounds,
        subscription_outbounds=list_subscription_cached_outbounds(enabled_only=True),
        static_outbounds=list_static_ladder_outbounds(enabled_only=True),
    )

    return {
        "generated_at": datetime.now(timezone.utc),
        "subscriptions": subscriptions,
        "outbounds": outbounds,
        "static_ladders": static_ladders,
        "overlay": overlay,
    }


@app.post("/api/singbox/check", response_model=SingboxCheckResult)
def api_singbox_check() -> SingboxCheckResult:
    config = build_full_config(
        outbounds=list_outbounds(),
        subscription_outbounds=list_subscription_cached_outbounds(enabled_only=True),
        static_outbounds=list_static_ladder_outbounds(enabled_only=True),
    )
    return check_singbox_config(config)


@app.get("/api/download-links")
def api_download_links() -> dict[str, str]:
    query = f"?{urlencode({'token': DOWNLOAD_TOKEN})}" if DOWNLOAD_TOKEN else ""
    return {
        "subscriptions": f"/downloads/subscriptions.txt{query}",
        "subscription_outbounds": f"/downloads/subscription-outbounds.json{query}",
        "overlay": f"/downloads/singbox-overlay.json{query}",
        "shadowrocket_subscription": f"/downloads/shadowrocket-sub.txt{query}",
        "clash_subscription": f"/downloads/clash.yaml{query}",
    }


@app.get("/downloads/subscriptions.txt")
def download_subscriptions(token: str | None = Query(default=None)) -> PlainTextResponse:
    _assert_download_token(token)
    body = build_subscription_bundle(list_subscriptions())
    headers = {
        "Content-Disposition": "attachment; filename=subscriptions.txt",
    }
    return PlainTextResponse(content=body, headers=headers)


@app.get("/downloads/subscription-outbounds.json")
def download_subscription_outbounds(token: str | None = Query(default=None)) -> Response:
    _assert_download_token(token)
    outbounds = list_subscription_cached_outbounds(enabled_only=True)
    return _json_attachment_response({"outbounds": outbounds}, "subscription-outbounds.json")


@app.get("/downloads/shadowrocket-sub.txt")
def download_shadowrocket_subscription(token: str | None = Query(default=None)) -> PlainTextResponse:
    _assert_download_token(token)
    body = build_shadowrocket_subscription_bundle(list_subscription_cached_outbounds(enabled_only=True))
    headers = {
        "Content-Disposition": "attachment; filename=shadowrocket-sub.txt",
    }
    return PlainTextResponse(content=body, headers=headers)


@app.get("/downloads/clash.yaml")
def download_clash_subscription(token: str | None = Query(default=None)) -> PlainTextResponse:
    _assert_download_token(token)
    outbounds = list_subscription_cached_outbounds(enabled_only=True) + list_static_ladder_outbounds(enabled_only=True)
    body = build_clash_subscription_bundle(outbounds)
    headers = {
        "Content-Disposition": "attachment; filename=clash.yaml",
    }
    return PlainTextResponse(content=body, headers=headers, media_type="application/yaml")


@app.get("/downloads/singbox-overlay.json")
def download_overlay(token: str | None = Query(default=None)) -> Response:
    _assert_download_token(token)
    overlay = build_full_config(
        outbounds=list_outbounds(),
        subscription_outbounds=list_subscription_cached_outbounds(enabled_only=True),
        static_outbounds=list_static_ladder_outbounds(enabled_only=True),
    )
    return _json_attachment_response(overlay, "singbox-overlay.json")
