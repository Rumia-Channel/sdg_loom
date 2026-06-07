"""sdg/providers/deepseek.py - DeepSeek プロバイダー

既存の DeepSeek 最適化を維持しつつ、Provider 抽象に移植。
- KV キャッシュ分離 (user_id)
- thinking モード (extra_body.thinking)
- 高並列チューニング (V4 Pro=500, Flash=2500 対応)
"""
from __future__ import annotations

from .base import REGION_GLOBAL, Provider


DEEPSEEK_PROVIDER = Provider(
    name="deepseek",
    display_name="DeepSeek",
    default_region=REGION_GLOBAL,
    regions=(REGION_GLOBAL,),
    base_urls={REGION_GLOBAL: "https://api.deepseek.com"},
    default_model="deepseek-v4-flash",
    api_key_env="DEEPSEEK_API_KEY",
    api_key_fallbacks=("SDG_API_KEY",),
    supports_user_id=True,
    supports_thinking=True,
    thinking_mode_kind="deepseek_extra_body",
    extra_thinking_kwargs={"reasoning_effort": "high"},
    # DeepSeek V4 Pro 上限 500、Flash 上限 2500 に対応
    max_concurrent_default=128,
    max_concurrent_limit_default=500,
    min_concurrent_default=8,
    target_latency_ms_default=3000,
    target_queue_depth_default=64,
    max_batch_size_default=64,
    max_connections=600,
    max_keepalive=300,
    keepalive_expiry=90.0,
    # DeepSeek 向け: 積極的增加 / 低いエラー閾値 / 高い縮退下限
    adaptive_increase_step=10,
    adaptive_decrease_factor=0.5,
    adaptive_recovery_floor=8,
    adaptive_error_rate_threshold=0.25,
    adaptive_mild_decrease_factor=0.98,
    legacy_env_aliases={
        "SDG_API_KEY": "DEEPSEEK_API_KEY",
    },
)


__all__ = ["DEEPSEEK_PROVIDER"]
