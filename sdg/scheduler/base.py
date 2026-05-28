"""sdg/scheduler/base.py - スケジューラー共通データ型"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RowTask:
    """スケジュールされた行タスク（インデックス + データ）"""

    row_index: int
    data: dict[str, Any]


@dataclass
class SchedulerConfig:
    """スケジューラーの全設定を一つのオブジェクトに集約。

    PipelineEngine が RunConfig から生成して Scheduler に渡す。
    スケジューラーはこの 1 オブジェクトを受け取るだけでよい。
    DeepSeek API の高並列（Flash=2500, Pro=500）に対応済み。
    """

    # ── 並行数制御 ──────────────────────────────────
    max_concurrent: int = 128          # DeepSeek の並列性能を活かす
    min_concurrent: int = 8            # ウォームアップ不要、高めから開始
    adaptive: bool = False
    max_concurrent_limit: int = 500    # V4 Pro 上限（Flash は 2500）
    target_latency_ms: int = 3000
    target_queue_depth: int = 64       # DeepSeek は深いキューを効率的に処理
    metrics_type: str = "none"
    adaptive_reprobe_enabled: bool = True
    adaptive_reprobe_rows: int = 64    # 並列数増に合わせて再試行間隔も拡大
    adaptive_reprobe_seconds: float = 120.0

    # ── リクエストバッチング ────────────────────────
    enable_request_batching: bool = False
    max_batch_size: int = 32
    max_wait_ms: int = 50

    # ── 階層スケジューリング / メモリ最適化 ────────
    enable_scheduling: bool = False
    max_pending_tasks: int = 1000
    chunk_size: int = 100
    enable_memory_optimization: bool = False
    max_cache_size: int = 500
    enable_memory_monitoring: bool = False
    gc_interval: int = 100
    memory_threshold_mb: int = 1024


__all__ = ["RowTask", "SchedulerConfig"]
