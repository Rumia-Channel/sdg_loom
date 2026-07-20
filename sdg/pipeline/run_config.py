"""sdg/pipeline/run_config.py - 実行パラメータオブジェクト

25 以上の関数引数を型安全な Pydantic モデルに集約する。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ProviderConfig(BaseModel):
    """プロバイダー / リージョン設定

    CLI フラグや環境変数から PipelineEngine が解決した値をここに格納する。
    解決前の状態 (None) では Provider 既定値が使われる。
    """

    model_config = {"populate_by_name": True}

    name: Optional[str] = None  # CLI / 環境変数 / YAML で上書きされ得る
    region: Optional[str] = None  # 解決後のリージョン (cn / global)


class ConcurrencyConfig(BaseModel):
    """並行性制御設定

    Provider ごとに既定値が異なるフィールドは default=None とし、
    RunConfig.apply_provider_defaults() で Provider 既定を適用する。
    """

    model_config = {"populate_by_name": True}

    # Provider 駆動のフィールド (None = 未確定 → apply_provider_defaults() で埋める)
    max_concurrent: Optional[int] = None
    min_concurrent: Optional[int] = None
    max_concurrent_limit: Optional[int] = None
    target_latency_ms: Optional[int] = None
    target_queue_depth: Optional[int] = None
    max_batch_size: Optional[int] = None

    # Provider 非依存のフィールド
    adaptive: bool = False
    metrics_type: str = "none"
    adaptive_reprobe_enabled: bool = True
    adaptive_reprobe_rows: int = 64
    adaptive_reprobe_seconds: float = 120.0
    enable_request_batching: bool = False
    max_wait_ms: int = 50

    @model_validator(mode="before")
    @classmethod
    def _legacy_compat(cls, data):
        """後方互換: 旧来の default_factory 形式の呼び出しを許容する。

        pydantic 経由で dict / keyword 構築する想定。None フィールドは
        RunConfig.apply_provider_defaults() が埋める。
        """
        if isinstance(data, dict):
            # 全フィールドが None なら default_factory の戻り値に揃えておく
            # (直接 ConcurrencyConfig() を生成したケース)
            if all(data.get(k) is None for k in (
                "max_concurrent", "min_concurrent", "max_concurrent_limit",
                "target_latency_ms", "target_queue_depth", "max_batch_size",
            )):
                from ._provider_defaults import (
                    provider_max_concurrent_default,
                    provider_min_concurrent_default,
                    provider_max_concurrent_limit_default,
                    provider_target_latency_ms_default,
                    provider_target_queue_depth_default,
                    provider_max_batch_size_default,
                )
                data.setdefault("max_concurrent", provider_max_concurrent_default())
                data.setdefault("min_concurrent", provider_min_concurrent_default())
                data.setdefault("max_concurrent_limit", provider_max_concurrent_limit_default())
                data.setdefault("target_latency_ms", provider_target_latency_ms_default())
                data.setdefault("target_queue_depth", provider_target_queue_depth_default())
                data.setdefault("max_batch_size", provider_max_batch_size_default())
        return data


class IOConfig(BaseModel):
    """入出力バッファ設定"""

    model_config = {"populate_by_name": True}

    buffer_size: int = 1
    flush_interval: float = 1.0


class ResumeConfig(BaseModel):
    """再開・スキップ設定"""

    model_config = {"populate_by_name": True}

    resume: bool = False
    skip_lines: int = 0
    max_inputs: Optional[int] = None


class MemoryConfig(BaseModel):
    """メモリ管理設定"""

    model_config = {"populate_by_name": True}

    enable_scheduling: bool = False
    max_pending_tasks: int = 1000
    chunk_size: int = 100
    enable_memory_optimization: bool = False
    max_cache_size: int = 500
    enable_memory_monitoring: bool = False
    gc_interval: int = 100
    memory_threshold_mb: int = 1024


class ProfileConfig(BaseModel):
    """プロファイル収集設定"""

    model_config = {"populate_by_name": True}

    enable: bool = False
    output_path: Optional[str] = None
    output_fields: Optional[List[str]] = None


class TransportConfig(BaseModel):
    """HTTP トランスポート設定"""

    model_config = {"populate_by_name": True}

    use_shared_transport: bool = True
    http2: bool = True
    retry_on_empty: bool = True


class DataSourceConfig(BaseModel):
    """データソース設定"""

    model_config = {"populate_by_name": True}

    input_path: Optional[str] = None
    dataset_name: Optional[str] = None
    subset: Optional[str] = None
    split: str = "train"
    mapping: Optional[Dict[str, str]] = None


class RunConfig(BaseModel):
    """パイプライン実行設定（全パラメータを集約）"""

    model_config = {"populate_by_name": True}

    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    io: IOConfig = Field(default_factory=IOConfig)
    resume: ResumeConfig = Field(default_factory=ResumeConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    profile: ProfileConfig = Field(default_factory=ProfileConfig)
    transport: TransportConfig = Field(default_factory=TransportConfig)
    data_source: DataSourceConfig = Field(default_factory=DataSourceConfig)
    save_intermediate: bool = False
    show_progress: bool = True
    verbose: bool = False
    # キャラクターカード (--character) のパス。指定時は YAML の character: キーより優先される。
    character_path: Optional[str] = None
    # Heartbeat ファイル (VPS 無人運用向け)。
    # 進捗・PID・ステータスを JSON でアトミック書き出しし、
    # 外部監視（cron, systemd, Zabbix 等）から生死と進捗を確認できる。
    heartbeat_path: Optional[str] = None
    heartbeat_interval: float = 10.0

    def apply_provider_defaults(self, provider) -> None:
        """ConcurrencyConfig の None フィールドに Provider 既定値を適用する。

        ユーザー指定済みのフィールド (None 以外) は上書きしない。
        """
        if self.concurrency.max_concurrent is None:
            self.concurrency.max_concurrent = provider.max_concurrent_default
        if self.concurrency.min_concurrent is None:
            self.concurrency.min_concurrent = provider.min_concurrent_default
        if self.concurrency.max_concurrent_limit is None:
            self.concurrency.max_concurrent_limit = provider.max_concurrent_limit_default
        if self.concurrency.target_latency_ms is None:
            self.concurrency.target_latency_ms = provider.target_latency_ms_default
        if self.concurrency.target_queue_depth is None:
            self.concurrency.target_queue_depth = provider.target_queue_depth_default
        if self.concurrency.max_batch_size is None:
            self.concurrency.max_batch_size = provider.max_batch_size_default


__all__ = [
    "ConcurrencyConfig",
    "IOConfig",
    "ResumeConfig",
    "MemoryConfig",
    "ProfileConfig",
    "TransportConfig",
    "DataSourceConfig",
    "ProviderConfig",
    "RunConfig",
]
