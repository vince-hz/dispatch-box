from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class SubscriptionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    url: HttpUrl
    enabled: bool = True
    user_agent: str = Field(default="", max_length=500)
    rename_prefix: str = Field(default="", max_length=128)
    remove_flag: bool = False
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    note: str = Field(default="", max_length=500)


class SubscriptionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    url: HttpUrl | None = None
    enabled: bool | None = None
    user_agent: str | None = Field(default=None, max_length=500)
    rename_prefix: str | None = Field(default=None, max_length=128)
    remove_flag: bool | None = None
    include_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    note: str | None = Field(default=None, max_length=500)


class SubscriptionOut(BaseModel):
    id: int
    name: str
    url: str
    enabled: bool
    user_agent: str
    rename_prefix: str
    remove_flag: bool
    include_keywords: list[str]
    exclude_keywords: list[str]
    node_count: int
    last_synced_at: datetime | None = None
    last_sync_error: str
    note: str
    created_at: datetime
    updated_at: datetime


class SubscriptionRefreshResult(BaseModel):
    id: int
    name: str
    ok: bool
    fetched_nodes: int = 0
    filtered_nodes: int = 0
    skipped_nodes: int = 0
    error: str = ""
    warnings: list[str] = Field(default_factory=list)


class SubscriptionRefreshBatchResult(BaseModel):
    total: int
    refreshed: int
    failed: int
    results: list[SubscriptionRefreshResult] = Field(default_factory=list)


class SubscriptionReplaceMapOut(BaseModel):
    replace_map: dict[str, str] = Field(default_factory=dict)


class SubscriptionReplaceMapUpdate(BaseModel):
    replace_map: dict[str, str] = Field(default_factory=dict)


class SubscriptionFilterOut(BaseModel):
    available_flags: list[str] = Field(default_factory=list)
    exclude_flags: list[str] = Field(default_factory=list)


class SubscriptionFilterUpdate(BaseModel):
    available_flags: list[str] = Field(default_factory=list)
    exclude_flags: list[str] = Field(default_factory=list)


class OutboundCreate(BaseModel):
    tag: str = Field(min_length=1, max_length=128)
    type: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    note: str = Field(default="", max_length=500)


class OutboundUpdate(BaseModel):
    tag: str | None = Field(default=None, min_length=1, max_length=128)
    type: str | None = Field(default=None, min_length=1, max_length=64)
    payload: dict[str, Any] | None = None
    enabled: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class OutboundOut(BaseModel):
    id: int
    tag: str
    type: str
    payload: dict[str, Any]
    enabled: bool
    note: str
    created_at: datetime
    updated_at: datetime


class StaticLadderCreate(BaseModel):
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    note: str = Field(default="", max_length=500)


class StaticLadderUpdate(BaseModel):
    config: dict[str, Any] | None = None
    enabled: bool | None = None
    note: str | None = Field(default=None, max_length=500)


class StaticLadderOut(BaseModel):
    id: int
    tag: str
    type: str
    config: dict[str, Any]
    enabled: bool
    note: str
    created_at: datetime
    updated_at: datetime


class ConfigPreview(BaseModel):
    generated_at: datetime
    subscriptions: list[SubscriptionOut]
    outbounds: list[OutboundOut]
    static_ladders: list[StaticLadderOut] = Field(default_factory=list)
    overlay: dict[str, Any]


class SingboxCheckResult(BaseModel):
    ok: bool
    message: str
    command: str
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    checked_at: datetime
