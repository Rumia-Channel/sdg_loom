"""sdg/providers/minimax.py - MiniMax プロバイダー

MiniMax API (中国本土版 / グローバル版) 向け。
- 中国本土 (cn): api.minimaxi.com
- グローバル (global): api.minimax.io
- デフォルトモデル: MiniMax-M3
- レート制限/レイテンシ特性が DeepSeek と異なる可能性が高いため、
  やや保守的な並列既定値を採用。
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
    api_key_fallbacks=(),
    # MiniMax の user_id による KV 分離は未確認のため既定では無効。
    # 動作確認後に Provider 定義を更新するだけで切替可能。
    supports_user_id=False,
    # thinking モードの正式サポートは MiniMax API 仕様に依存するため既定 False。
    # 使う場合は Provider 定義の supports_thinking=True と
    # thinking_mode_kind を切り替えるだけで対応できる。
    supports_thinking=False,
    thinking_mode_kind=None,
    extra_thinking_kwargs={},
    # 保守的な並列既定値 (実際のレート制限は運用後に調整)
    max_concurrent_default=64,
    max_concurrent_limit_default=200,
    min_concurrent_default=4,
    target_latency_ms_default=4000,
    target_queue_depth_default=32,
    max_batch_size_default=32,
    # HTTP 接続プール
    max_connections=300,
    max_keepalive=150,
    keepalive_expiry=60.0,
    # MiniMax 向け: 保守的プロファイル
    # - 増加ステップ小さめ (急激な負荷上昇を避ける)
    # - 縮退はやや強め (1 回のエラーバーストで大きく下げない)
    # - 縮退下限も低めに (MiniMax 側で余裕がある前提で評価中)
    adaptive_increase_step=4,
    adaptive_decrease_factor=0.6,
    adaptive_recovery_floor=4,
    adaptive_error_rate_threshold=0.15,
    adaptive_mild_decrease_factor=0.95,
)


__all__ = ["MINIMAX_PROVIDER"]
