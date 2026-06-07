"""sdg/pipeline/_provider_defaults.py - 既定値の遅延解決

RunConfig の各 field default_factory から呼ばれるヘルパー群。
Pydantic の default_factory は呼び出し時点で「現在の Provider 」
を知ることができないため、環境変数 `SDG_PROVIDER` を見て既定値を
返す。CLI / YAML で上書きされた場合は RunConfig 構築時に明示的に
値が渡されるため factory は使われない。
"""
from __future__ import annotations

import os

from ..providers import (
    DEFAULT_PROVIDER_NAME,
    PROVIDERS,
)


def _resolve_provider_from_env() -> str:
    """SDG_PROVIDER 環境変数を読み取り、未知の値なら既定値."""
    name = os.environ.get("SDG_PROVIDER", "").strip().lower()
    if name and name in PROVIDERS:
        return name
    return DEFAULT_PROVIDER_NAME


def _provider():
    return PROVIDERS[_resolve_provider_from_env()]


def provider_max_concurrent_default() -> int:
    return _provider().max_concurrent_default


def provider_max_concurrent_limit_default() -> int:
    return _provider().max_concurrent_limit_default


def provider_min_concurrent_default() -> int:
    return _provider().min_concurrent_default


def provider_target_latency_ms_default() -> int:
    return _provider().target_latency_ms_default


def provider_target_queue_depth_default() -> int:
    return _provider().target_queue_depth_default


def provider_max_batch_size_default() -> int:
    return _provider().max_batch_size_default


def provider_max_connections() -> int:
    return _provider().max_connections


def provider_max_keepalive() -> int:
    return _provider().max_keepalive


def provider_keepalive_expiry() -> float:
    return _provider().keepalive_expiry


__all__ = [
    "provider_max_concurrent_default",
    "provider_max_concurrent_limit_default",
    "provider_min_concurrent_default",
    "provider_target_latency_ms_default",
    "provider_target_queue_depth_default",
    "provider_max_batch_size_default",
    "provider_max_connections",
    "provider_max_keepalive",
    "provider_keepalive_expiry",
]
