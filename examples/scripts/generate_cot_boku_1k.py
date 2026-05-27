#!/usr/bin/env python3
"""
cot_japanese_math_boku.yaml を使った大規模生成サンプル

1レベルあたり1000問（既定）のシードを生成し、SDGパイプラインを実行する。
14レベル × 1000問 = 14000件が既定の生成総数。

シード生成は generate_cot_japanese_math_scaled_seeds.py のロジックを再利用し、
パイプライン実行は sdg.runner.run_streaming_adaptive() を使う。

使用方法:
    # テスト実行（1件）
    python examples/scripts/generate_cot_boku_1k.py --test

    # シード生成のみ（dry-run）
    python examples/scripts/generate_cot_boku_1k.py --gen-seeds --dry-run

    # シード生成のみ（実ファイル出力）
    python examples/scripts/generate_cot_boku_1k.py --gen-seeds

    # シード生成 + パイプライン実行（1レベルあたり1000問）
    python examples/scripts/generate_cot_boku_1k.py

    # 1レベルあたり2000問
    python examples/scripts/generate_cot_boku_1k.py --items-per-level 2000

    # 少量で動作確認（5件だけ）
    python examples/scripts/generate_cot_boku_1k.py --max-inputs 5

    # 再開実行
    python examples/scripts/generate_cot_boku_1k.py --resume

環境変数:
    SDG_API_MODEL : モデル名（例: qwen3, gpt-4o）
    SDG_API_KEY   : APIキー
    SDG_BASE_URL  : プロバイダURL（例: http://localhost:8000/v1）
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_project_root))

from examples.scripts.generate_cot_japanese_math_scaled_seeds import (
    DEFAULT_SCENARIO_WEIGHTS,
    SCENARIOS,
    build_weighted_schedule,
    build_record,
    expand_rows,
    parse_scenarios,
    parse_weights,
    print_summary,
    read_jsonl,
    write_jsonl,
)

YAML_PATH = _project_root / "examples" / "cot_japanese_math_boku.yaml"
SOURCE_SEEDS = _project_root / "examples" / "data" / "cot_japanese_math_seeds.jsonl"
SCALED_SEEDS = _project_root / "examples" / "data" / "cot_japanese_math_scaled_seeds.jsonl"
DEFAULT_OUTPUT = _project_root / "output" / "japanese_math_cot_boku_1k.jsonl"


def generate_seeds(
    items_per_level: int = 1000,
    scenarios: list[dict] | None = None,
    weights: dict[str, int] | None = None,
    output_path: Path = SCALED_SEEDS,
    style_intensity: int = 2,
) -> list[dict]:
    """生成シードを展開して JSONL に書き込む。"""
    if scenarios is None:
        scenarios = list(SCENARIOS)
    if weights is None:
        weights = {s["type"]: DEFAULT_SCENARIO_WEIGHTS.get(s["type"], 1) for s in scenarios}

    base_rows = read_jsonl(SOURCE_SEEDS)
    expanded = expand_rows(
        base_rows,
        items_per_level=items_per_level,
        scenarios=scenarios,
        scenario_weights=weights,
        per_scenario=False,
        style_intensity=style_intensity,
    )
    write_jsonl(output_path, expanded)
    print(f"\nシード生成完了: {output_path}")
    print_summary(expanded)
    return expanded


def run_pipeline(
    output_path: Path,
    max_concurrent: int = 64,
    min_concurrent: int = 1,
    target_latency_ms: int = 3000,
    use_shared_transport: bool = True,
    http2: bool = True,
    resume: bool = False,
    max_inputs: int | None = None,
    enable_profile: bool = False,
) -> None:
    """SDG パイプラインを実行する。"""
    from sdg.runner import run_streaming_adaptive

    print(f"\nパイプライン実行開始")
    print(f"  YAML     : {YAML_PATH}")
    print(f"  入力     : {SCALED_SEEDS}")
    print(f"  出力     : {output_path}")
    print(f"  適応制御 : max={max_concurrent}, min={min_concurrent}, target_latency={target_latency_ms}ms")
    print(f"  共有通信 : {use_shared_transport}, HTTP/2={http2}")
    print(f"  再開     : {resume}")
    if max_inputs:
        print(f"  上限     : {max_inputs} 件")

    run_streaming_adaptive(
        yaml_path=str(YAML_PATH),
        input_path=str(SCALED_SEEDS),
        output_path=str(output_path),
        max_concurrent=max_concurrent,
        min_concurrent=min_concurrent,
        target_latency_ms=target_latency_ms,
        use_shared_transport=use_shared_transport,
        http2=http2,
        retry_on_empty=True,
        resume=resume,
        max_inputs=max_inputs,
        enable_profile=enable_profile,
        profile_output_path=str(output_path.with_suffix(".profile.json")) if enable_profile else None,
        show_progress=True,
    )

    print(f"\n完了: {output_path}")


def test_run() -> None:
    """test-run で1件動作確認する。"""
    from sdg.runner import test_run as sdg_test_run
    sdg_test_run(str(YAML_PATH), str(SOURCE_SEEDS))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="cot_japanese_math_boku.yaml 1k生成サンプル",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--items-per-level", type=int, default=1000,
                        help="1レベルあたりの生成件数 (既定: 1000)")
    parser.add_argument("--gen-seeds", action="store_true",
                        help="シード生成のみ。パイプラインは実行しない")
    parser.add_argument("--dry-run", action="store_true",
                        help="シード生成のみ。ファイル出力しない")
    parser.add_argument("--test", action="store_true",
                        help="test-run で1件動作確認")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help=f"出力 JSONL のパス (既定: {DEFAULT_OUTPUT})")
    parser.add_argument("--max-concurrent", type=int, default=64,
                        help="適応制御の最大並行数 (既定: 64)")
    parser.add_argument("--min-concurrent", type=int, default=1,
                        help="適応制御の最小並行数 (既定: 1)")
    parser.add_argument("--target-latency-ms", type=int, default=3000,
                        help="目標レイテンシ ms (既定: 3000)")
    parser.add_argument("--no-shared-transport", action="store_true",
                        help="共有 HTTP トランスポートを使わない")
    parser.add_argument("--no-http2", action="store_true",
                        help="HTTP/2 を使わない")
    parser.add_argument("--resume", action="store_true",
                        help="既存出力から再開")
    parser.add_argument("--max-inputs", "-n", type=int, default=None,
                        help="処理する最大入力件数（動作確認用）")
    parser.add_argument("--profile", action="store_true",
                        help="プロファイリングを有効化")
    parser.add_argument("--style-intensity", type=int, default=2,
                        help="キャラクター濃度 1-4 (既定: 2)")

    args = parser.parse_args()

    # test-run モード
    if args.test:
        test_run()
        return

    # シード生成
    if args.dry_run:
        expanded = expand_rows(
            read_jsonl(SOURCE_SEEDS),
            items_per_level=args.items_per_level,
            scenarios=list(SCENARIOS),
            scenario_weights={
                s["type"]: DEFAULT_SCENARIO_WEIGHTS.get(s["type"], 1)
                for s in SCENARIOS
            },
            per_scenario=False,
            style_intensity=args.style_intensity,
        )
        print_summary(expanded)
        return

    generate_seeds(
        items_per_level=args.items_per_level,
        style_intensity=args.style_intensity,
    )

    if args.gen_seeds:
        return

    # パイプライン実行
    args.output.parent.mkdir(parents=True, exist_ok=True)
    run_pipeline(
        output_path=args.output,
        max_concurrent=args.max_concurrent,
        min_concurrent=args.min_concurrent,
        target_latency_ms=args.target_latency_ms,
        use_shared_transport=not args.no_shared_transport,
        http2=not args.no_http2,
        resume=args.resume,
        max_inputs=args.max_inputs,
        enable_profile=args.profile,
    )


if __name__ == "__main__":
    main()
