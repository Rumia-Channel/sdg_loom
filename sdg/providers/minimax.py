"""sdg/providers/minimax.py - MiniMax プロバイダー

MiniMax API (中国本土版 / グローバル版) 向け。
- 中国本土 (cn): api.minimaxi.com
- グローバル (global): api.minimax.io
- デフォルトモデル: MiniMax-M3
- MiniMax M3 は自動コンテキストキャッシュに対応。入力 512K tokens 超で料金 2 倍に注意。
- 並列既定値は M3 の特性に合わせて調整済み。
"""
from __future__ import annotations

from .base import REGION_CN, REGION_GLOBAL, Provider


MINIMAX_PROVIDER = Provider(
    name="minimax",
    display_name="MiniMax",
    default_region=REGION_GLOBAL,
    regions=(REGION_CN, REGION_GLOBAL),
    base_urls={
        REGION_CN: "https://api.minimaxi.com",
        REGION_GLOBAL: "https://api.minimax.io",
    },
    default_model="MiniMax-M3",
    api_key_env="MINIMAX_API_KEY",
    api_key_fallbacks=("SDG_API_KEY",),
    # MiniMax の user_id による KV 分離は未確認のため既定では無効。
    # 動作確認後に Provider 定義を更新するだけで切替可能。
    supports_user_id=False,
    # MiniMax M3 は自動コンテキストキャッシュ対応（サーバー側で自動生效）。
    # prompt_cache_hit_tokens / prompt_cache_miss_tokens が返れば
    # LLMClient の汎用キャッシュ追跡で自動記録される。
    # thinking モードの正式サポートは MiniMax API 仕様に依存するため既定 False。
    # 使う場合は Provider 定義の supports_thinking=True と
    # thinking_mode_kind を切り替えるだけで対応できる。
    supports_thinking=False,
    thinking_mode_kind=None,
    extra_thinking_kwargs={},
    # MiniMax M3 向け並列既定値（入力 512K 超過で料金 2 倍。YAML の max_tokens に注意）
    max_concurrent_default=96,
    max_concurrent_limit_default=300,
    min_concurrent_default=4,
    target_latency_ms_default=5000,
    target_queue_depth_default=48,
    max_batch_size_default=48,
    # HTTP 接続プール
    max_connections=300,
    max_keepalive=150,
    keepalive_expiry=60.0,
    # MiniMax M3 向け適応制御プロファイル
    # M3 は安定したAPIのため、DeepSeek よりやや保守的だが実用的な値
    adaptive_increase_step=6,
    adaptive_decrease_factor=0.55,
    adaptive_recovery_floor=4,
    adaptive_error_rate_threshold=0.20,
    adaptive_mild_decrease_factor=0.95,
)


__all__ = ["MINIMAX_PROVIDER"]
