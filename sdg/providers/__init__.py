"""sdg/providers/__init__.py - プロバイダーレジストリ

利用可能なプロバイダーの一覧と、Provider 名とリージョンから
Provider インスタンスを解決するヘルパーを提供する。
"""
from __future__ import annotations

import os
from typing import Optional

from .base import (
    ALL_REGIONS,
    REGION_CN,
    REGION_GLOBAL,
    Provider,
)
from .deepseek import DEEPSEEK_PROVIDER
from .minimax import MINIMAX_PROVIDER


# プロバイダーレジストリ (新しい Provider を追加したらここにも登録する)
PROVIDERS: dict[str, Provider] = {
    DEEPSEEK_PROVIDER.name: DEEPSEEK_PROVIDER,
    MINIMAX_PROVIDER.name: MINIMAX_PROVIDER,
}


# 互換性のための既定 Provider (明示指定が無い場合は DeepSeek)
DEFAULT_PROVIDER_NAME = DEEPSEEK_PROVIDER.name


def list_providers() -> list[str]:
    """利用可能なプロバイダー名一覧"""
    return list(PROVIDERS.keys())


def get_provider(name: Optional[str] = None) -> Provider:
    """プロバイダー名から Provider を取得。未知の名前なら ValueError。"""
    name = (name or DEFAULT_PROVIDER_NAME).lower()
    if name not in PROVIDERS:
        raise ValueError(
            f"Unknown provider '{name}'. "
            f"Available providers: {', '.join(list_providers())}"
        )
    return PROVIDERS[name]


def resolve_region(
    provider: Provider,
    *,
    cli_value: Optional[str] = None,
    env_var: str = "SDG_REGION",
    yaml_value: Optional[str] = None,
) -> str:
    """リージョンを優先順位に従って解決する。

    優先順位:
        1. cli_value  (--region フラグ)
        2. 環境変数    (SDG_REGION 既定)
        3. yaml_value (YAML の region:)
        4. provider.default_region

    Args:
        provider: 解決先プロバイダー
        cli_value: CLI から渡された値
        env_var: 参照する環境変数名
        yaml_value: YAML に書かれた値

    Returns:
        解決されたリージョン文字列
    """
    for candidate in (cli_value, os.environ.get(env_var), yaml_value):
        if candidate:
            region = str(candidate).strip().lower()
            if region not in provider.regions:
                raise ValueError(
                    f"Region '{region}' is not supported by provider "
                    f"'{provider.name}'. Supported: {', '.join(provider.regions)}"
                )
            return region
    return provider.default_region


def resolve_provider_name(
    *,
    cli_value: Optional[str] = None,
    env_var: str = "SDG_PROVIDER",
    yaml_value: Optional[str] = None,
) -> str:
    """プロバイダー名を優先順位に従って解決する。

    優先順位:
        1. cli_value   (--provider フラグ)
        2. 環境変数     (SDG_PROVIDER 既定)
        3. yaml_value  (YAML の provider:)
        4. DEFAULT_PROVIDER_NAME
    """
    for candidate in (cli_value, os.environ.get(env_var), yaml_value):
        if candidate:
            name = str(candidate).strip().lower()
            if name not in PROVIDERS:
                raise ValueError(
                    f"Unknown provider '{name}'. "
                    f"Available: {', '.join(list_providers())}"
                )
            return name
    return DEFAULT_PROVIDER_NAME


__all__ = [
    "ALL_REGIONS",
    "DEFAULT_PROVIDER_NAME",
    "MINIMAX_PROVIDER",
    "DEEPSEEK_PROVIDER",
    "PROVIDERS",
    "Provider",
    "REGION_CN",
    "REGION_GLOBAL",
    "get_provider",
    "list_providers",
    "resolve_provider_name",
    "resolve_region",
]
