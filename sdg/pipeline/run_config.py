"""sdg/pipeline/run_config.py - 実行パラメータオブジェクト

25 以上の関数引数を型安全な Pydantic モデルに集約する。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ConcurrencyConfig(BaseModel):
    """並行性制御設定（DeepSeek API 向け最適化済み）"""

    model_config = {"populate_by_name": True}

    max_concurrent: int = 128           # DeepSeek V4 Pro=500, Flash=2500 に対応
    adaptive: bool = False
    min_concurrent: int = 8             # DeepSeek はウォームアップ不要、高めから開始
    max_concurrent_limit: int = 500     # V4 Pro の上限に合わせる（Flash は 2500）
    target_latency_ms: int = 3000
    target_queue_depth: int = 64        # DeepSeek は深いキューを効率的に処理
    metrics_type: str = "none"
    adaptive_reprobe_enabled: bool = True
    adaptive_reprobe_rows: int = 64     # 並列数が多いので reprobe 間隔も広げる
    adaptive_reprobe_seconds: float = 120.0
    enable_request_batching: bool = False
    max_batch_size: int = 64            # DeepSeek KVキャッシュ活用のため大きめのバッチ
    max_wait_ms: int = 50


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
    """HTTP トランスポート設定（DeepSeek API 向け最適化）"""

    model_config = {"populate_by_name": True}

    use_shared_transport: bool = True   # DeepSeek 高並列ではコネクションプーリング必須
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


__all__ = [
    "ConcurrencyConfig",
    "IOConfig",
    "ResumeConfig",
    "MemoryConfig",
    "ProfileConfig",
    "TransportConfig",
    "DataSourceConfig",
    "RunConfig",
]
