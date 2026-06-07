"""sdg/providers/base.py - プロバイダー抽象の基底

DeepSeek / MiniMax など複数の LLM プロバイダーに対して、
同じ抽象 (URL、デフォルトモデル、env 変数、特徴フラグ) で扱えるようにする。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


REGION_CN = "cn"
REGION_GLOBAL = "global"

ALL_REGIONS: Tuple[str, ...] = (REGION_CN, REGION_GLOBAL)


@dataclass(frozen=True)
class Provider:
    """LLM プロバイダーの設定一式.

    Attributes:
        name: プロバイダー識別子 ("deepseek" / "minimax" 等)
        display_name: 人間に見せる名前
        default_region: 既定のリージョン
        regions: サポートするリージョンのタプル
        base_urls: リージョン -> base URL
        default_model: 既定モデル名 (YAML で api_model 未指定時に使用)
        api_key_env: 既定の API キー用環境変数名
        api_key_fallbacks: 環境変数のフォールバック探索順
        supports_user_id: user_id ヘッダ/パラメータでセッション分離できるか (KV キャッシュ分離)
        supports_thinking: thinking / reasoning モードをサポートするか
        thinking_mode_kind: thinking モードの指定方法
            - "deepseek_extra_body": extra_body.thinking={type: "enabled"} (DeepSeek 互換)
            - "openai_reasoning_effort": reasoning_effort パラメータ (OpenAI o1 系)
            - None: サポートしない
        extra_thinking_kwargs: thinking モード時に追加する payload kwargs
        # 推奨チューニング既定値 (Provider ごとに異なるレート制限/レイテンシ特性に合わせる)
        max_concurrent_default: 固定モードの既定並列数
        max_concurrent_limit_default: 適応モードの上限
        min_concurrent_default: 適応モードの最小値
        target_latency_ms_default: 目標 P95 レイテンシ
        target_queue_depth_default: 目標バックエンドキュー深度
        max_batch_size_default: リクエストバッチの最大サイズ
        # HTTP 接続プール
        max_connections: 最大接続数
        max_keepalive: キープアライブ接続数
        keepalive_expiry: キープアライブ有効秒
        # 互換性用
        legacy_env_aliases: 旧 DeepSeek 環境変数名 → 対応する新環境変数名
    """

    name: str
    display_name: str
    default_region: str
    regions: Tuple[str, ...]
    base_urls: Dict[str, str]
    default_model: str
    api_key_env: str
    api_key_fallbacks: Tuple[str, ...] = ()
    supports_user_id: bool = False
    supports_thinking: bool = False
    thinking_mode_kind: Optional[str] = None
    extra_thinking_kwargs: Dict[str, object] = field(default_factory=dict)
    # 推奨チューニング
    max_concurrent_default: int = 64
    max_concurrent_limit_default: int = 500
    min_concurrent_default: int = 8
    target_latency_ms_default: int = 3000
    target_queue_depth_default: int = 32
    max_batch_size_default: int = 32
    # HTTP
    max_connections: int = 200
    max_keepalive: int = 100
    keepalive_expiry: float = 60.0
    # AdaptiveController 向けのチューニングプロファイル
    adaptive_increase_step: int = 2
    adaptive_decrease_factor: float = 0.5
    adaptive_recovery_floor: int = 8
    adaptive_error_rate_threshold: float = 0.25
    adaptive_mild_decrease_factor: float = 0.98
    # 互換性
    legacy_env_aliases: Dict[str, str] = field(default_factory=dict)

    def base_url_for(self, region: Optional[str] = None) -> str:
        """指定リージョン (未指定なら default_region) の base URL を返す。"""
        region = region or self.default_region
        if region not in self.base_urls:
            if region not in self.regions:
                raise ValueError(
                    f"Provider '{self.name}' does not support region '{region}'. "
                    f"Supported regions: {', '.join(self.regions)}"
                )
            return self.base_urls[self.default_region]
        return self.base_urls[region]

    def resolve_api_key_env(self) -> List[str]:
        """API キー探索順 (primary + fallbacks) を返す。"""
        return [self.api_key_env, *self.api_key_fallbacks]


__all__ = [
    "REGION_CN",
    "REGION_GLOBAL",
    "ALL_REGIONS",
    "Provider",
]
