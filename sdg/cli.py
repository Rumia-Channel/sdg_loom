from __future__ import annotations
import argparse
import os
import sys
from .runner import (
    run,
    test_run,
)


# 日本語ヘルプメッセージ
HELP_JA = """使い方: sdg [--help.ja] {run,test-run} ...

SDG (Scalable Data Generator) CLI

オプション:
  -h, --help      このヘルプメッセージを表示して終了
  --help.ja       このヘルプメッセージを日本語で表示して終了

サブコマンド:
  {run,test-run}
    run           YAMLブループリントを入力データセットに対して実行
    test-run      YAMLブループリントを1件のデータに対してテスト実行

'sdg run --help.ja' でサブコマンドの詳細なヘルプを表示できます。
'sdg test-run --help.ja' でtest-runコマンドの詳細なヘルプを表示できます。

レガシーモード（後方互換性のため）:
  sdg --yaml <file> --input <file> --output <file> [オプション]
"""

RUN_HELP_JA = """使い方: sdg run --yaml YAML --input INPUT --output OUTPUT [オプション]

YAMLブループリントを入力データセットに対して実行

必須引数:
  --yaml YAML              YAMLブループリントパス
  --input INPUT            入力データセット (.jsonl または .csv)
  --output OUTPUT          出力JSONLファイル

オプション引数:
  -h, --help               このヘルプメッセージを表示して終了
  --help.ja                このヘルプメッセージを日本語で表示して終了
  --save-intermediate      中間出力を保存
  --character PATH         キャラクターカード YAML のパス（{char.*} 変数を注入。YAML の character: キーより優先）

データ制限オプション:
  --max-inputs MAX_INPUTS, -n MAX_INPUTS
                          処理する最大入力データ数（デフォルト: 全件処理）
  --skip SKIP, --skip-lines SKIP
                          先頭からスキップする行数（デフォルト: 0）
  --resume                既存の出力ファイルから処理済み行を検出して再開

Hugging Face データセットオプション:
  --dataset DATASET       Hugging Face データセット名
  --subset SUBSET         データセットのサブセット名
  --split SPLIT           データセットの分割 (デフォルト: train)
  --mapping MAPPING       'orig:new' 形式のキーマッピング (複数回使用可)

ストリーミングモードオプション（デフォルトモード）:
  --max-concurrent MAX_CONCURRENT
                          並行処理する最大行数 (デフォルト: 8)
  --no-progress           プログレス表示を無効化
  --verbose, -v           詳細ログを有効化（デバッグ出力）
  --legacy-logs           レガシーログ形式を使用（richフォーマット無効化）

適応的並行性制御オプション:
  --adaptive               適応的並行性制御を有効化（レイテンシに応じて動的に調整）
                          ※ --adaptive-concurrency でも可
  --min-batch MIN_BATCH   最小並行処理数（適応的制御時、デフォルト: 1）
  --max-batch MAX_BATCH   最大並行処理数（適応的制御時、デフォルト: 64）
  --target-latency-ms TARGET_LATENCY_MS
                          目標P95レイテンシ（ミリ秒、デフォルト: 3000）
  --target-queue-depth TARGET_QUEUE_DEPTH
                          目標バックエンドキュー深度（デフォルト: 32）
  --adaptive-reprobe-rows ADAPTIVE_REPROBE_ROWS
                          並行数低下後に最大並行数を再試行する処理済み行数（デフォルト: 32）
  --adaptive-reprobe-seconds ADAPTIVE_REPROBE_SECONDS
                          並行数低下後に最大並行数を再試行する秒数（デフォルト: 120）
  --no-adaptive-reprobe   並行数低下後の最大並行数再試行を無効化

バックエンドメトリクスオプション（適応的制御時）:
  --use-vllm-metrics      vLLMのPrometheusメトリクスを使用して並行性を最適化
  --use-sglang-metrics    SGLangのPrometheusメトリクスを使用して並行性を最適化

リクエストバッチングオプション（適応的制御時）:
  --enable-request-batching
                          リクエストバッチングを有効化（複数リクエストを集約して送信）
  --max-batch-size MAX_BATCH_SIZE
                          バッチあたりの最大リクエスト数（デフォルト: 32）
  --max-wait-ms MAX_WAIT_MS
                          バッチ形成の最大待機時間（ミリ秒、デフォルト: 50）

Phase 2 最適化オプション:
  --enable-scheduling     階層的タスクスケジューリングを有効化（大規模データセット用）
  --max-pending-tasks MAX_PENDING_TASKS
                          最大保留タスク数（スケジューリング有効時、デフォルト: 1000）
  --chunk-size CHUNK_SIZE データセット分割サイズ（スケジューリング有効時、デフォルト: 100）
  --enable-memory-optimization
                          メモリ最適化を有効化（LRUキャッシュによるコンテキスト管理）
  --max-cache-size MAX_CACHE_SIZE
                          コンテキストキャッシュの最大サイズ（デフォルト: 500）
  --enable-memory-monitoring
                          メモリ使用状況監視を有効化（psutilが必要）
  --gc-interval GC_INTERVAL
                          ガベージコレクション実行間隔（処理行数、デフォルト: 100）
  --memory-threshold-mb MEMORY_THRESHOLD_MB
                          メモリ使用量警告閾値（MB、デフォルト: 1024）

LLMリトライオプション:
  --no-retry-on-empty     空返答時のリトライを無効化（デフォルトは有効）

プロファイルオプション:
  --profile               生成後プロファイリングを有効化（言語分布、長さ分布、重複検出等）
  --profile-output PATH   プロファイルJSONの出力パス
  --profile-fields FIELDS 分析対象の出力フィールド名（カンマ区切り、デフォルト: 全フィールド）

最適化オプション:
  --use-shared-transport  共有HTTPトランスポートを使用（コネクションプール共有）
  --no-http2              HTTP/2を無効化（デフォルトは有効）

例:
  # ストリーミングモード（デフォルト・固定並行数）
  sdg run --yaml config.yaml --input data.jsonl --output result.jsonl --max-concurrent 16

  # 最大500件のみ処理
  sdg run --yaml config.yaml --input data.jsonl --output result.jsonl --max-inputs 500

  # 先頭100行をスキップして処理
  sdg run --yaml config.yaml --input data.jsonl --output result.jsonl --skip 100

  # 既存の出力ファイルから処理済み行を検出して再開
  sdg run --yaml config.yaml --input data.jsonl --output result.jsonl --resume

  # 適応的並行性制御を有効化（並行数が動的に調整される）
  sdg run --yaml config.yaml --input data.jsonl --output result.jsonl \\
    --adaptive --min-batch 1 --max-batch 32 --target-latency-ms 2000

  # vLLMメトリクスを使用した適応的並行性制御
  sdg run --yaml config.yaml --input data.jsonl --output result.jsonl \\
    --adaptive --use-vllm-metrics --min-batch 1 --max-batch 64

  # リクエストバッチングを有効化（高スループット向け）
  sdg run --yaml config.yaml --input data.jsonl --output result.jsonl \\
    --adaptive --use-vllm-metrics --enable-request-batching

  # 中間出力を保存
  sdg run --yaml config.yaml --input data.jsonl --output result.jsonl --save-intermediate

  # 生成後プロファイリングを有効化（ターミナル表示 + JSON出力）
  sdg run --yaml config.yaml --input data.jsonl --output result.jsonl \\
    --profile --profile-output profile.json

Heartbeat / 監視オプション（VPS 無人運用向け）:
  --heartbeat PATH        ハートビート JSON の出力パス（進捗・PID・ステータス）
                          外部監視（cron, systemd 等）からファイルの mtime や
                          status フィールドでプロセスの生死と進捗を確認できる
  --heartbeat-interval SEC
                          ハートビート書き込み間隔（秒、デフォルト: 10）
"""

# test-run command help message in Japanese
TEST_RUN_HELP_JA = """使い方: sdg test-run --yaml YAML [--input INPUT | --dataset DATASET] [オプション]

YAMLブループリントを1件のデータに対してテスト実行

このコマンドは、AIエージェントの動作確認を素早く行うためのものです。
入力データの1件目のみを処理し、詳細なログを出力します。

必須引数:
  --yaml YAML              YAMLブループリントパス

データソース（いずれか1つを指定）:
  --input INPUT            入力データセット (.jsonl または .csv)
  --dataset DATASET        Hugging Face データセット名

オプション引数:
  -h, --help               このヘルプメッセージを表示して終了
  --help.ja                このヘルプメッセージを日本語で表示して終了
  --character PATH         キャラクターカード YAML のパス（{char.*} 変数を注入。YAML の character: キーより優先）

Hugging Face データセットオプション:
  --subset SUBSET          データセットのサブセット名
  --split SPLIT            データセットの分割 (デフォルト: train)
  --mapping MAPPING        'orig:new' 形式のキーマッピング (複数回使用可)

データ選択オプション:
  --random-input           データの先頭から最大100件の中からランダムに1件を選択

UIオプション:
  --ui-locale {en,ja}      UIロケール (デフォルト: en)
  --verbose, -v            詳細ログを有効化（デフォルト: 有効）
  --no-verbose             詳細ログを無効化
  --meta                   最終結果にメタ情報を表示（実行時間、行インデックスなど）

例:
  # ローカルJSONLファイルでテスト実行
  sdg test-run --yaml config.yaml --input data.jsonl

  # ランダムに1件選択してテスト実行
  sdg test-run --yaml config.yaml --input data.jsonl --random-input

  # ローカルCSVファイルでテスト実行
  sdg test-run --yaml config.yaml --input data.csv

  # Hugging Faceデータセットでテスト実行
  sdg test-run --yaml config.yaml --dataset squad --split validation

  # 日本語UIでテスト実行
  sdg test-run --yaml config.yaml --input data.jsonl --ui-locale ja
"""

# Legacy mode help message in Japanese
LEGACY_HELP_JA = """使い方: sdg --yaml YAML --input INPUT --output OUTPUT [オプション]

SDG (Scalable Data Generator) CLI [レガシーモード: sdg --yaml ...]

オプション:
  -h, --help            このヘルプメッセージを表示して終了
  --help.ja             このヘルプメッセージを日本語で表示して終了
  --yaml YAML           YAMLブループリントパス
  --input INPUT         入力データセット (.jsonl または .csv)
  --output OUTPUT       出力JSONLファイル
  --save-intermediate   中間出力を保存
  --character PATH      キャラクターカード YAML のパス（{char.*} 変数を注入。YAML の character: キーより優先）
  --max-inputs MAX_INPUTS, -n MAX_INPUTS
                        処理する最大入力データ数（デフォルト: 全件処理）
  --dataset DATASET     Hugging Face データセット名
  --subset SUBSET       データセットのサブセット名
  --split SPLIT         データセットの分割 (デフォルト: train)
  --mapping MAPPING     'orig:new' 形式のキーマッピング (複数回使用可)
  --max-concurrent MAX_CONCURRENT
                        並行処理する最大行数 (デフォルト: 8)
  --no-progress         プログレス表示を無効化
  --verbose, -v         詳細ログを有効化（デバッグ出力）
  --legacy-logs         レガシーログ形式を使用（richフォーマット無効化）
  --adaptive            適応的並行性制御を有効化
  --min-batch MIN_BATCH
                        最小並行処理数（適応的制御時、デフォルト: 1）
  --max-batch MAX_BATCH
                        最大並行処理数（適応的制御時、デフォルト: 64）
  --target-latency-ms TARGET_LATENCY_MS
                        目標P95レイテンシ（ミリ秒、デフォルト: 3000）
  --target-queue-depth TARGET_QUEUE_DEPTH
                        目標バックエンドキュー深度（デフォルト: 32）
  --adaptive-reprobe-rows ADAPTIVE_REPROBE_ROWS
                        並行数低下後に最大並行数を再試行する処理済み行数（デフォルト: 32）
  --adaptive-reprobe-seconds ADAPTIVE_REPROBE_SECONDS
                        並行数低下後に最大並行数を再試行する秒数（デフォルト: 120）
  --no-adaptive-reprobe 並行数低下後の最大並行数再試行を無効化
  --use-vllm-metrics    vLLMのメトリクスを使用
  --use-sglang-metrics  SGLangのメトリクスを使用
  --enable-request-batching
                        リクエストバッチングを有効化
  --max-batch-size MAX_BATCH_SIZE
                        バッチあたりの最大リクエスト数（デフォルト: 32）
  --max-wait-ms MAX_WAIT_MS
                        バッチ形成の最大待機時間（ミリ秒、デフォルト: 50）
  --enable-scheduling   階層的タスクスケジューリングを有効化
  --max-pending-tasks MAX_PENDING_TASKS
                        最大保留タスク数（デフォルト: 1000）
  --chunk-size CHUNK_SIZE
                        データセット分割サイズ（デフォルト: 100）
  --enable-memory-optimization
                        メモリ最適化を有効化
  --max-cache-size MAX_CACHE_SIZE
                        コンテキストキャッシュの最大サイズ（デフォルト: 500）
  --enable-memory-monitoring
                        メモリ使用状況監視を有効化
  --gc-interval GC_INTERVAL
                        ガベージコレクション実行間隔（デフォルト: 100）
  --memory-threshold-mb MEMORY_THRESHOLD_MB
                        メモリ使用量警告閾値（MB、デフォルト: 1024）
  --no-retry-on-empty   空返答時のリトライを無効化（デフォルトは有効）
  --use-shared-transport
                        共有HTTPトランスポートを使用（コネクションプール共有）
  --no-http2            HTTP/2を無効化（デフォルトは有効）
"""


def build_run_parser(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
    p.add_argument("--yaml", required=True, help="YAML blueprint path")
    p.add_argument("--input", help="Input dataset (.jsonl or .csv)")
    p.add_argument("--output", required=True, help="Output JSONL file")
    p.add_argument(
        "--save-intermediate", action="store_true", help="Save intermediate outputs"
    )

    # Character card option (resolve by CLI > YAML 'character:' key)
    p.add_argument(
        "--character",
        default=None,
        help=(
            "Character card YAML path (injects {char.*} template variables). "
            "Takes precedence over the YAML 'character:' key."
        ),
    )

    # Provider options (resolve by CLI > env > YAML > default)
    from .providers import list_providers, ALL_REGIONS

    p.add_argument(
        "--provider",
        choices=list_providers(),
        default=None,
        help=(
            "LLM provider name. Available: "
            + ", ".join(list_providers())
            + ". Can also be set via SDG_PROVIDER env var or YAML 'provider:'"
        ),
    )
    p.add_argument(
        "--region",
        choices=list(ALL_REGIONS),
        default=None,
        help=(
            "Region for multi-region providers (e.g. minimax: cn|global). "
            "Can also be set via SDG_REGION env var or YAML 'region:'"
        ),
    )

    # Data limit options
    p.add_argument(
        "--max-inputs",
        "-n",
        type=int,
        default=None,
        help="Maximum number of input data to process (default: process all)",
    )
    p.add_argument(
        "--skip",
        "--skip-lines",
        type=int,
        default=0,
        dest="skip_lines",
        help="Number of input lines to skip from the beginning (default: 0)",
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="Resume from existing output file (skip already processed rows based on _row_index)",
    )

    # Hugging Face Dataset options
    p.add_argument("--dataset", help="Hugging Face dataset name")
    p.add_argument("--subset", help="Dataset subset name")
    p.add_argument("--split", default="train", help="Dataset split (default: train)")
    p.add_argument(
        "--mapping",
        action="append",
        help="Key mapping in format 'orig:new' (can be used multiple times)",
    )
    p.add_argument(
        "--help.ja", action="store_true", help="Show this help message in Japanese"
    )

    # UI locale option
    p.add_argument(
        "--ui-locale",
        choices=["en", "ja"],
        default="en",
        help="UI locale for log output (default: en)",
    )

    # Streaming mode options (default mode)
    p.add_argument(
        "--max-concurrent",
        type=int,
        default=None,
        help=(
            "Max concurrent rows to process. "
            "省略時は Provider 既定値 (DeepSeek=128, MiniMax=64)"
        ),
    )
    p.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress display",
    )
    p.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (detailed debug output)",
    )
    p.add_argument(
        "--legacy-logs",
        action="store_true",
        help="Use legacy log format (disable rich formatting)",
    )

    # Adaptive concurrency options
    p.add_argument(
        "--adaptive",
        action="store_true",
        help="Enable adaptive concurrency control (adjusts dynamically based on latency)",
    )
    p.add_argument(
        "--adaptive-concurrency",
        action="store_true",
        dest="adaptive",
        help=argparse.SUPPRESS,  # Hidden alias for --adaptive
    )
    p.add_argument(
        "--min-batch",
        type=int,
        default=None,
        help=(
            "Min concurrency (adaptive mode). "
            "省略時は Provider 既定値 (DeepSeek=8, MiniMax=4)"
        ),
    )
    p.add_argument(
        "--max-batch",
        type=int,
        default=None,
        help=(
            "Max concurrency (adaptive mode). "
            "省略時は Provider 既定値 (DeepSeek=500, MiniMax=200)"
        ),
    )
    p.add_argument(
        "--target-latency-ms",
        type=int,
        default=None,
        help=(
            "Target P95 latency in ms. "
            "省略時は Provider 既定値 (DeepSeek=3000, MiniMax=4000)"
        ),
    )
    p.add_argument(
        "--target-queue-depth",
        type=int,
        default=None,
        help=(
            "Target backend queue depth. "
            "省略時は Provider 既定値 (DeepSeek=64, MiniMax=32)"
        ),
    )
    p.add_argument(
        "--adaptive-reprobe-rows",
        type=int,
        default=64,
        help="Completed rows before adaptive mode retries --max-batch after backoff (default: 64)",
    )
    p.add_argument(
        "--adaptive-reprobe-seconds",
        type=float,
        default=120.0,
        help="Seconds before adaptive mode retries --max-batch after backoff (default: 120)",
    )
    p.add_argument(
        "--no-adaptive-reprobe",
        action="store_true",
        help="Disable periodic max-batch retry in adaptive mode",
    )

    # Backend metrics options (for adaptive mode)
    p.add_argument(
        "--use-vllm-metrics",
        action="store_true",
        help="Use vLLM Prometheus metrics for adaptive optimization",
    )
    p.add_argument(
        "--use-sglang-metrics",
        action="store_true",
        help="Use SGLang Prometheus metrics for adaptive optimization",
    )

    # Request batching options (for adaptive mode)
    p.add_argument(
        "--enable-request-batching",
        action="store_true",
        help="Enable request batching (groups multiple requests before sending)",
    )
    p.add_argument(
        "--max-batch-size",
        type=int,
        default=None,
        help=(
            "Max requests per batch. "
            "省略時は Provider 既定値 (DeepSeek=64, MiniMax=32)"
        ),
    )
    p.add_argument(
        "--max-wait-ms",
        type=int,
        default=50,
        help="Max wait time for batch formation in ms (default: 50)",
    )

    # Phase 2: Hierarchical scheduling options
    p.add_argument(
        "--enable-scheduling",
        action="store_true",
        help="Enable hierarchical task scheduling (for large datasets)",
    )
    p.add_argument(
        "--max-pending-tasks",
        type=int,
        default=1000,
        help="Max pending tasks (scheduling mode, default: 1000)",
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=100,
        help="Dataset chunk size (scheduling mode, default: 100)",
    )

    # Phase 2: Memory optimization options
    p.add_argument(
        "--enable-memory-optimization",
        action="store_true",
        help="Enable memory optimization (LRU cache for context management)",
    )
    p.add_argument(
        "--max-cache-size",
        type=int,
        default=500,
        help="Max context cache size (default: 500)",
    )
    p.add_argument(
        "--enable-memory-monitoring",
        action="store_true",
        help="Enable memory usage monitoring (requires psutil)",
    )
    p.add_argument(
        "--gc-interval",
        type=int,
        default=100,
        help="Garbage collection interval in rows (default: 100)",
    )
    p.add_argument(
        "--memory-threshold-mb",
        type=int,
        default=1024,
        help="Memory usage warning threshold in MB (default: 1024)",
    )

    # LLM retry options
    p.add_argument(
        "--no-retry-on-empty",
        action="store_true",
        help="Disable retry on empty response (enabled by default)",
    )

    # Profile options
    p.add_argument(
        "--profile",
        action="store_true",
        help="Enable post-generation profiling (language dist, length dist, duplicates, etc.)",
    )
    p.add_argument(
        "--profile-output",
        type=str,
        default=None,
        help="Path to save profile JSON file",
    )
    p.add_argument(
        "--profile-fields",
        type=str,
        default=None,
        help="Comma-separated list of output field names to profile (default: all non-meta fields)",
    )

    # Heartbeat / monitoring options (VPS unattended operation)
    p.add_argument(
        "--heartbeat",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "Write heartbeat JSON to PATH (progress, PID, status). "
            "Useful for remote monitoring on VPS. "
            "The file is atomically updated every --heartbeat-interval seconds."
        ),
    )
    p.add_argument(
        "--heartbeat-interval",
        type=float,
        default=10.0,
        metavar="SEC",
        help="Heartbeat write interval in seconds (default: 10)",
    )

    # Optimization options
    p.add_argument(
        "--use-shared-transport",
        action="store_true",
        help="Use shared HTTP transport (connection pooling)",
    )
    p.add_argument(
        "--no-http2",
        action="store_true",
        help="Disable HTTP/2 (enabled by default)",
    )

    # Legacy options (hidden, for backward compatibility)
    p.add_argument(
        "--batch-mode",
        action="store_true",
        help=argparse.SUPPRESS,  # Hidden, use --adaptive instead
    )
    p.add_argument(
        "--streaming", action="store_true", help=argparse.SUPPRESS
    )  # Now default, kept for compatibility
    p.add_argument(
        "--max-concurrent-rows", type=int, default=None, help=argparse.SUPPRESS
    )  # Alias for --max-concurrent
    p.add_argument(
        "--min-concurrent", type=int, default=None, help=argparse.SUPPRESS
    )  # Alias for --min-batch
    return p


def build_test_run_parser(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Build argument parser for test-run command"""
    p.add_argument("--yaml", required=True, help="YAML blueprint path")
    p.add_argument("--input", help="Input dataset (.jsonl or .csv)")

    # Character card option (resolve by CLI > YAML 'character:' key)
    p.add_argument(
        "--character",
        default=None,
        help=(
            "Character card YAML path (injects {char.*} template variables). "
            "Takes precedence over the YAML 'character:' key."
        ),
    )

    # Hugging Face Dataset options
    p.add_argument("--dataset", help="Hugging Face dataset name")
    p.add_argument("--subset", help="Dataset subset name")
    p.add_argument("--split", default="train", help="Dataset split (default: train)")
    p.add_argument(
        "--mapping",
        action="append",
        help="Key mapping in format 'orig:new' (can be used multiple times)",
    )
    p.add_argument(
        "--help.ja", action="store_true", help="Show this help message in Japanese"
    )

    # UI locale option
    p.add_argument(
        "--ui-locale",
        choices=["en", "ja"],
        default="en",
        help="UI locale for log output (default: en)",
    )

    # Verbose option (default: True for test-run)
    p.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=True,
        help="Enable verbose logging (default: enabled for test-run)",
    )
    p.add_argument(
        "--no-verbose",
        action="store_true",
        help="Disable verbose logging",
    )

    # Meta information display option
    p.add_argument(
        "--meta",
        action="store_true",
        help="Show meta information in final result (e.g., elapsed time, row index)",
    )

    # Random input selection option
    p.add_argument(
        "--random-input",
        action="store_true",
        help="Randomly select one item from the first 100 data items",
    )

    return p


def _execute_test_run(args):
    """Execute the test-run command based on args"""
    from .logger import init_logger

    # Get locale from --ui-locale parameter
    locale = getattr(args, "ui_locale", "en")

    # Initialize logger for validation messages
    logger = init_logger(
        verbose=True,
        quiet=False,
        use_rich=True,
        locale=locale,
    )

    # Validation
    if not args.input and not args.dataset:
        logger.error("Either --input or --dataset must be provided.")
        sys.exit(1)
    if args.input and args.dataset:
        logger.error("Cannot specify both --input and --dataset.")
        sys.exit(1)

    # Parse mapping
    mapping = {}
    if args.mapping:
        for m in args.mapping:
            if ":" not in m:
                print(
                    f"Error: Invalid mapping format '{m}'. Expected 'orig:new'.",
                    file=sys.stderr,
                )
                sys.exit(1)
            k, v = m.split(":", 1)
            mapping[k] = v

    # Determine verbose setting
    verbose = args.verbose and not args.no_verbose

    # Execute test run
    try:
        result = test_run(
            yaml_path=args.yaml,
            input_path=args.input,
            dataset_name=args.dataset,
            subset=args.subset,
            split=args.split,
            mapping=mapping if mapping else None,
            verbose=verbose,
            locale=locale,
            show_meta=args.meta,
            random_input=args.random_input,
            character_path=(
                os.path.abspath(args.character)
                if getattr(args, "character", None)
                else None
            ),
        )
        # Result is already displayed by test_run using rich formatting

    except Exception as e:
        logger.error(f"Test run failed: {e}")
        sys.exit(1)


def _apply_yaml_provider_to_run_config(cfg, run_config) -> None:
    """YAML の provider / region を RunConfig.provider に反映する。

    RunConfig.concurrency には None を残し、PipelineEngine.run 内で
    Provider 解決後に RunConfig.apply_provider_defaults() で埋める。
    """
    from .providers import (
        resolve_provider_name,
        resolve_region,
        get_provider,
    )

    yaml_provider = getattr(cfg, "provider", None)
    yaml_region = getattr(cfg, "region", None)

    # 解決済み Provider (CLI > env > YAML > 既定)
    effective_name = resolve_provider_name(
        cli_value=run_config.provider.name,
        yaml_value=yaml_provider,
    )
    provider = get_provider(effective_name)
    effective_region = resolve_region(
        provider,
        cli_value=run_config.provider.region,
        yaml_value=yaml_region,
    )

    # RunConfig に書き戻し (PipelineEngine._resolve_provider() と重複するが無害)
    run_config.provider.name = provider.name
    run_config.provider.region = effective_region


def _build_run_config(args) -> "RunConfig":
    """argparse の Namespace から RunConfig を構築"""
    from .pipeline.run_config import (
        RunConfig,
        ConcurrencyConfig,
        IOConfig,
        ResumeConfig,
        MemoryConfig,
        ProfileConfig,
        ProviderConfig,
        TransportConfig,
        DataSourceConfig,
    )

    # mapping解析
    mapping = {}
    if getattr(args, "mapping", None):
        for m in args.mapping:
            if ":" in m:
                k, v = m.split(":", 1)
                mapping[k] = v

    # max_concurrent の解決 (レガシーオプション考慮)
    max_concurrent = (
        getattr(args, "max_concurrent_rows", None)
        or getattr(args, "max_concurrent", None)
    )
    min_concurrent = (
        getattr(args, "min_concurrent", None)
        or getattr(args, "min_batch", None)
    )

    # metrics_type の決定
    metrics_type = "none"
    if getattr(args, "use_vllm_metrics", False):
        metrics_type = "vllm"
    elif getattr(args, "use_sglang_metrics", False):
        metrics_type = "sglang"

    # ProviderConfig 構築 (CLI > env > YAML > 既定)
    provider_cfg = ProviderConfig(
        name=getattr(args, "provider", None),
        region=getattr(args, "region", None),
    )

    return RunConfig(
        provider=provider_cfg,
        concurrency=ConcurrencyConfig(
            # Provider 駆動のフィールドは None のまま残す
            # → PipelineEngine.run() で apply_provider_defaults() が埋める
            max_concurrent=max_concurrent,
            adaptive=getattr(args, "adaptive", False),
            min_concurrent=min_concurrent,
            max_concurrent_limit=getattr(args, "max_batch", None),
            target_latency_ms=getattr(args, "target_latency_ms", None),
            target_queue_depth=getattr(args, "target_queue_depth", None),
            metrics_type=metrics_type,
            adaptive_reprobe_enabled=not getattr(
                args, "no_adaptive_reprobe", False
            ),
            adaptive_reprobe_rows=getattr(args, "adaptive_reprobe_rows", 64),
            adaptive_reprobe_seconds=getattr(args, "adaptive_reprobe_seconds", 120.0),
            enable_request_batching=getattr(args, "enable_request_batching", False),
            max_batch_size=getattr(args, "max_batch_size", None),
            max_wait_ms=getattr(args, "max_wait_ms", 50),
        ),
        io=IOConfig(),
        resume=ResumeConfig(
            resume=getattr(args, "resume", False),
            skip_lines=getattr(args, "skip_lines", 0),
            max_inputs=getattr(args, "max_inputs", None),
        ),
        memory=MemoryConfig(
            enable_scheduling=getattr(args, "enable_scheduling", False),
            max_pending_tasks=getattr(args, "max_pending_tasks", 1000),
            chunk_size=getattr(args, "chunk_size", 100),
            enable_memory_optimization=getattr(
                args, "enable_memory_optimization", False
            ),
            max_cache_size=getattr(args, "max_cache_size", 500),
            enable_memory_monitoring=getattr(args, "enable_memory_monitoring", False),
            gc_interval=getattr(args, "gc_interval", 100),
            memory_threshold_mb=getattr(args, "memory_threshold_mb", 1024),
        ),
        profile=ProfileConfig(
            enable=getattr(args, "profile", False),
            output_path=getattr(args, "profile_output", None),
            output_fields=(
                args.profile_fields.split(",")
                if getattr(args, "profile_fields", None)
                else None
            ),
        ),
        transport=TransportConfig(
            use_shared_transport=getattr(args, "use_shared_transport", False),
            http2=not getattr(args, "no_http2", False),
            retry_on_empty=not getattr(args, "no_retry_on_empty", False),
        ),
        data_source=DataSourceConfig(
            input_path=getattr(args, "input", None),
            dataset_name=getattr(args, "dataset", None),
            subset=getattr(args, "subset", None),
            split=getattr(args, "split", "train"),
            mapping=mapping if mapping else None,
        ),
        save_intermediate=getattr(args, "save_intermediate", False),
        show_progress=not getattr(args, "no_progress", False),
        verbose=getattr(args, "verbose", False),
        character_path=(
            os.path.abspath(args.character)
            if getattr(args, "character", None)
            else None
        ),
        heartbeat_path=getattr(args, "heartbeat", None),
        heartbeat_interval=getattr(args, "heartbeat_interval", 10.0),
    )


def _execute_run(args):
    """Execute the run command based on args"""
    from .logger import init_logger
    from .config import load_config
    from .pipeline import PipelineEngine

    # Get locale from --ui-locale parameter
    locale = getattr(args, "ui_locale", "en")
    logger = init_logger(
        verbose=getattr(args, "verbose", False),
        quiet=args.no_progress,
        use_rich=not getattr(args, "legacy_logs", False),
        locale=locale,
    )

    # Validation
    if not args.input and not args.dataset:
        logger.error("Either --input or --dataset must be provided.")
        sys.exit(1)
    if args.input and args.dataset:
        logger.error("Cannot specify both --input and --dataset.")
        sys.exit(1)
    if args.max_inputs is not None and args.max_inputs <= 0:
        logger.error("--max-inputs must be a positive integer.")
        sys.exit(1)
    if args.skip_lines < 0:
        logger.error("--skip must be a non-negative integer.")
        sys.exit(1)
    if args.resume and args.skip_lines > 0:
        logger.error("Cannot use both --resume and --skip at the same time.")
        sys.exit(1)
    if getattr(args, "adaptive_reprobe_rows", 1) <= 0:
        logger.error("--adaptive-reprobe-rows must be a positive integer.")
        sys.exit(1)
    if getattr(args, "adaptive_reprobe_seconds", 0.0) < 0:
        logger.error("--adaptive-reprobe-seconds must be non-negative.")
        sys.exit(1)

    # Legacy batch mode (backward compatibility のため維持)
    if getattr(args, "batch_mode", False):
        mapping = {}
        if args.mapping:
            for m in args.mapping:
                if ":" in m:
                    k, v = m.split(":", 1)
                    mapping[k] = v
        run(
            args.yaml,
            args.input,
            args.output,
            max_batch=args.max_batch,
            min_batch=args.min_batch,
            target_latency_ms=args.target_latency_ms,
            save_intermediate=args.save_intermediate,
            max_inputs=args.max_inputs,
            dataset_name=args.dataset,
            subset=args.subset,
            split=args.split,
            mapping=mapping if mapping else None,
            character_path=(
                os.path.abspath(args.character)
                if getattr(args, "character", None)
                else None
            ),
        )
        return

    # RunConfig-based execution (新方式)
    try:
        cfg = load_config(args.yaml)
        run_config = _build_run_config(args)
        # YAML 側の provider / region を RunConfig に反映 (CLI 優先を維持)
        _apply_yaml_provider_to_run_config(cfg, run_config)
        engine = PipelineEngine(cfg, run_config)
        report = engine.run(args.output)
        if getattr(report, "interrupted", False):
            sys.exit(130)
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        sys.exit(1)


def main():
    argv = sys.argv[1:]

    # Check for --help.ja option (before argparse processes it)
    if "--help.ja" in argv:
        # Backward compatibility: detect legacy mode
        legacy_mode = (
            len(argv) > 0
            and not argv[0] in {"run", "test-run"}
            and argv[0].startswith("--")
        )

        # Determine if this is for 'run' subcommand, 'test-run' subcommand, legacy mode, or main help
        if len(argv) >= 2 and argv[0] == "run":
            # sdg run --help.ja
            print(RUN_HELP_JA)
            sys.exit(0)
        elif len(argv) >= 2 and argv[0] == "test-run":
            # sdg test-run --help.ja
            print(TEST_RUN_HELP_JA)
            sys.exit(0)
        elif legacy_mode:
            # sdg --yaml ... --help.ja (legacy mode)
            print(LEGACY_HELP_JA)
            sys.exit(0)
        else:
            # sdg --help.ja (main help)
            print(HELP_JA)
            sys.exit(0)

    # Backward compatibility: support legacy usage `sdg --yaml ...`
    legacy_mode = (
        len(argv) > 0
        and not argv[0] in {"run", "test-run"}
        and argv[0].startswith("--")
    )

    if legacy_mode:
        p = argparse.ArgumentParser(
            description="SDG (Scalable Data Generator) CLI [legacy mode: sdg --yaml ...]"
        )
        build_run_parser(p)
        args = p.parse_args(argv)
        _execute_run(args)
        return

    # Subcommand style: `sdg run --yaml ...` or `sdg test-run --yaml ...`
    p = argparse.ArgumentParser(description="SDG (Scalable Data Generator) CLI")
    sub = p.add_subparsers(dest="command")
    # Python 3.10 supports required for subparsers
    try:
        sub.required = True  # type: ignore[attr-defined]
    except Exception:
        pass

    # run subcommand
    run_p = sub.add_parser("run", help="Run a YAML blueprint over an input dataset")
    build_run_parser(run_p)

    # test-run subcommand
    test_run_p = sub.add_parser(
        "test-run",
        help="Test run a YAML blueprint with a single data item for verification",
    )
    build_test_run_parser(test_run_p)

    args = p.parse_args(argv)

    if args.command == "run":
        _execute_run(args)
    elif args.command == "test-run":
        _execute_test_run(args)
