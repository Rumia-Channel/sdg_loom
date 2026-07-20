# SDG-LOOM

> **LLMファインチューニング用のスケーラブルな合成データ生成フレームワーク。** DeepSeek API と MiniMax API を統一プロバイダー抽象化でサポートし、適応型並行制御と宣言的 MABEL v2.0 エージェントプログラムを提供します。

<img width="1024" alt="SDG-LOOM Logo" src="assets/logo.png" />

## 概要

**SDG-LOOM（Scalable Data Generator LOOM）** は、ファインチューニング用データを大規模に生成するための高スループットなバッチ合成データセット生成フレームワークです。**MABEL v2.0**（Model And Blocks Expansion Language）による宣言的エージェントプログラムと、統一プロバイダー抽象化レイヤーを通じて複数のLLMプロバイダーをサポートします。

- **DeepSeek API** — KVコンテキストキャッシング（ディスクベース）、thinking mode（思考連鎖）、HTTP/2接続プーリング
- **MiniMax API** — マルチリージョン対応（中国本土 / グローバル）、100万トークンコンテキストの MiniMax-M3

TCP輻輳制御（Vegas/Reno/BBR）に着想を得た適応型並行制御とEMA平滑化により、レート制限やレイテンシの変動に自動的に対応し、大規模バッチ生成でも安全に運用できます。

---

## 特徴

* **DeepSeek API 最適化**
  * 自動KVコンテキストキャッシング（ディスクベースプレフィックスキャッシュ）活用
  * Thinking mode（思考連鎖推論）対応
  * キャッシュヒット/ミスの追跡とコスト分析
  * DeepSeekエンドポイント向けHTTP/2接続プーリング最適化
  * MiniMax API（中国本土/グローバル）対応、MiniMax-M3 モデル
* **MABEL v2.0 サポート**

  * チューリング完全な式言語（MEX）
  * 高度な制御構造（`while`, `recurse`, `reduce`, `call`, `let`）
  * インラインPython関数
  * グローバル変数サポート
* **MABEL v1.x 後方互換**

  * 自動バージョン検出機能搭載
* **高度な並行処理**

  * TCP輻輳制御（Vegas/Reno/BBR）にインスパイアされた適応型並行制御
    * Slow Start（指数増加）とCongestion Avoidance（線形増加）の2フェーズ制御
    * EMA（指数移動平均）によるノイズ除去とトレンド検出
    * Vegas-styleプロアクティブ輻輳検出
    * 段階的減少ロジック（軽度の輻輳は無視、深刻な輻輳には即座に対応）
  * vLLM/SGLangバックエンドからのリアルタイムメトリクス収集
  * 最適なスループットのための動的リクエストバッチング
  * レイテンシベースの自動最適化
* **マルチモデル対応**

  * 同時に複数のLLMモデルを定義・運用可能
* **柔軟なI/Oサポート**

  * ストリーミング・バッチモードでのJSONL・CSVフォーマット対応
  * Hugging Face Datasetsの直接読み込み対応
  * キーマッピング機能によるデータセット互換性の向上
* **堅牢なエラーハンドリング**

  * リトライ機構付きで柔軟なエラー処理設定が可能
* **パフォーマンス最適化**

  * 共有HTTPトランスポートによるコネクションプーリング
  * HTTP/2サポートによるスループット向上
  * 非同期バッファI/Oによる効率的なファイル操作
  * Phase 2: 階層的タスクスケジューリングとメモリ最適化（[Phase 2最適化ガイド](docs/phase2_optimization.md)参照）
* **生成後プロファイリング**

  * 言語分布分析
  * 出力長分布統計
  * 重複検出と重複率
  * パース/検証失敗率の追跡
  * モデル別LLMトークン使用量統計

---

## 必要要件

* Python `>= 3.10`
* PyYAML `>= 6.0.1`
* openai `>= 1.40.0`
* tqdm `>= 4.66.0`

---

## インストール方法

複数の環境管理方法を用いたインストール例を紹介します。

### 通常のpipでインストール

```bash
pip install -e .
```

### pyenvを使用したインストール方法

```bash
# Pythonのバージョン管理
pyenv install 3.12.0
pyenv local 3.12.0

# venvを設定
python -m venv venv
source venv/bin/activate

# 依存関係のインストール
pip install -e .
```

### condaを使用したインストール方法

```bash
# 環境作成と有効化
conda create -n sdg python=3.12
conda activate sdg

# インストール
pip install -e .
```

### uvを使用した高速インストール方法（推奨）

[uv](https://github.com/astral-sh/uv) はPythonの高速パッケージマネージャーです。

```bash
# uvのインストール (まだの場合)
pip install uv

# 仮想環境作成と依存関係インストール
uv venv
source .venv/bin/activate

uv pip install -e .
```

---

## クイックスタート

プロバイダー別の最小設定例：

<table>
<tr>
<th width="50%">DeepSeek</th>
<th width="50%">MiniMax</th>
</tr>
<tr>
<td>

```yaml
mabel:
  version: "2.0"

models:
  - name: deepseek
    api_model: deepseek-v4-flash
    api_key: ${ENV.DEEPSEEK_API_KEY}

blocks:
  - type: ai
    exec: 1
    model: deepseek
    prompts:
      - "要約: {UserInput}"
    outputs:
      - name: Summary
        select: full

  - type: end
    exec: 2
    final:
      - name: answer
        value: "{Summary}"
```

</td>
<td>

```yaml
provider: minimax
region: cn

mabel:
  version: "2.0"

models:
  - name: minimax
    api_model: MiniMax-M3
    api_key: "${ENV.MINIMAX_API_KEY}"

blocks:
  - type: ai
    exec: 1
    model: minimax
    prompts:
      - "次の入力を要約してください: {UserInput}"
    outputs:
      - name: Summary
        select: full

  - type: end
    exec: 2
    final:
      - name: answer
        value: "{Summary}"
```

</td>
</tr>
</table>

詳細な仕様は以下を参照してください：

* **[MABEL v2 仕様書](docs/mabel/mabel_v2.md)** - 詳細な機能説明、サンプル、仕様

---

## 使用方法

### コマンドライン(CLI)での実行

プロバイダーとリージョンの指定:

```bash
# MiniMax（中国本土リージョン）
sdg run --yaml pipeline.yaml --input data.jsonl --output result.jsonl \
  --provider minimax --region cn

# DeepSeek（デフォルト — --provider 不要）
sdg run --yaml pipeline.yaml --input data.jsonl --output result.jsonl
```

基本的なJSONL処理:

```bash
sdg run \
  --yaml examples/sdg_demo_v2.yaml \
  --input examples/data/input.jsonl \
  --output output/result.jsonl
```

1件のデータで素早くテスト:

```bash
sdg test-run \
  --yaml examples/sdg_demo_v2.yaml \
  --input examples/data/input.jsonl
```

詳細ログを有効化して実行:

```bash
sdg run \
  --yaml examples/sdg_demo_v2.yaml \
  --input data.jsonl \
  --output result.jsonl \
  --verbose
```

日本語UIで実行（デフォルトは英語）:

```bash
sdg run \
  --yaml examples/sdg_demo_v2.yaml \
  --input data.jsonl \
  --output result.jsonl \
  --ui-locale ja
```

レガシーログ形式で実行（richフォーマット無効化）:

```bash
sdg run \
  --yaml examples/sdg_demo_v2.yaml \
  --input data.jsonl \
  --output result.jsonl \
  --legacy-logs
```

カスタムバッチ設定による実行:

```bash
sdg run \
  --yaml examples/sdg_demo_v2.yaml \
  --input data.jsonl \
  --output result.jsonl \
  --max-batch 16 \
  --min-batch 2 \
  --target-latency 2000
```

### Python APIによる利用

**シンプルなストリーミング実行（推奨）:**

```python
from sdg.runner import run_streaming

run_streaming(
    yaml_path="pipeline.yaml",
    input_path="data/input.jsonl",
    output_path="output/result.jsonl",
    max_concurrent=8,
)
```

**`PipelineEngine` を使った詳細制御:**

```python
from sdg.config import load_config
from sdg.runner import PipelineEngine, RunConfig, ConcurrencyConfig

cfg = load_config("pipeline.yaml")
run_config = RunConfig(
    concurrency=ConcurrencyConfig(max_concurrent=8),
)
engine = PipelineEngine(cfg, run_config)
engine.run("output/result.jsonl")
```

---

## プロバイダーとリージョン 🌍

SDG-LOOM は統一された抽象化レイヤーを通じて複数のLLMプロバイダーをサポートします。各プロバイダーは独自のベースURL、デフォルトモデル、APIキー環境変数、推奨並列設定を定義します。

### 対応プロバイダー

| プロバイダー | デフォルトモデル | デフォルトベースURL | APIキー環境変数 | 備考 |
|-------------|-----------------|---------------------|----------------|------|
| `deepseek` | `deepseek-v4-flash` | `https://api.deepseek.com` | `DEEPSEEK_API_KEY` | KVキャッシュ分離（user_id）、thinking mode |
| `minimax` | `MiniMax-M3` | `https://api.minimax.io` (global) / `https://api.minimaxi.com` (cn) | `MINIMAX_API_KEY` | マルチリージョン（cn/global） |

### リージョン選択（MiniMax）

`minimax` は2つのリージョンをサポートします。以下のいずれかで指定してください（優先順位: **CLI > 環境変数 > YAML > デフォルト**）:

| 指定方法 | 例 |
|---------|-----|
| CLIフラグ | `--provider minimax --region cn` |
| 環境変数 | `SDG_PROVIDER=minimax SDG_REGION=cn` |
| YAML | `provider: minimax`<br>`region: cn` |

### プロバイダー別並列処理のデフォルト値

`--max-concurrent` を省略した場合、フレームワークはプロバイダーに応じた既定値を使用します。

| 項目 | DeepSeek | MiniMax |
|------|---------:|--------:|
| `max_concurrent`（固定モード） | 128 | 64 |
| `max_concurrent_limit`（適応モード上限） | 500 | 200 |
| `min_concurrent`（適応モード下限） | 8 | 4 |
| `target_latency_ms` | 3000 | 4000 |
| `target_queue_depth` | 64 | 32 |
| `max_batch_size` | 64 | 32 |
| `SharedHttpTransport` max_connections | 600 | 300 |

---

## 詳細ドキュメント 📖

* **[使用ガイド](docs/usage.ja.md)** - CLI・Python APIの詳細な使用方法
* **[MABEL v2 完全仕様](docs/mabel/mabel_v2.md)** - MABELの文法・機能詳細

---

## MABEL エディター 🎨

MABELファイルのビジュアル編集用に、専用のGUIツールを提供しています：

* **[SDG UI](https://github.com/foxn2000/sdg_ui)** - MABEL設定ファイルを作成・編集するためのグラフィカルユーザーインターフェース

このツールを使用すると、YAMLファイルを手動で編集することなく、直感的にMABELパイプラインを設計・管理できます。

---

## データセット生成サンプル 🧮

### 日本語 算数・数学 文章題 CoT（僕っ娘キャラクター版）

14レベルの算数・数学カリキュラムに沿って「自信家な僕っ娘」キャラクターの解答データセットを生成します。

**MiniMax で実行:**
```bash
export MINIMAX_API_KEY="sk-..."
uv run sdg run \
  --yaml examples/cot_japanese_math_boku.yaml \
  --input examples/data/cot_japanese_math_scaled_seeds.jsonl \
  --output output/japanese_math_cot_boku.jsonl \
  --provider minimax --region cn \
  --adaptive --max-batch 32 --resume
```

**DeepSeek で実行:**
```bash
export DEEPSEEK_API_KEY="sk-..."
uv run sdg run \
  --yaml examples/cot_japanese_math_boku.yaml \
  --input examples/data/cot_japanese_math_scaled_seeds.jsonl \
  --output output/japanese_math_cot_boku.jsonl \
  --adaptive --max-batch 64 --resume
```

**大規模生成（1レベルあたり1000件以上）:**
```bash
# 環境変数でプロバイダー指定
export MINIMAX_API_KEY="sk-..."
export SDG_PROVIDER=minimax
export SDG_REGION=cn

# 14レベル × 5000 = 70,000問
uv run python examples/scripts/generate_cot_boku_1k.py --items-per-level 5000 --resume
```

### 日本語 算数・数学 文章題 CoT（標準版・キャラクターなし）:
```bash
uv run sdg run \
  --yaml examples/cot_japanese_math.yaml \
  --input examples/data/cot_japanese_math_scaled_seeds.jsonl \
  --output output/japanese_math_cot.jsonl \
  --provider minimax --region cn --adaptive --resume
```

---

## サンプル集

`examples/` ディレクトリに各種パイプラインとデータを提供しています。

| ファイル | 説明 |
|---------|------|
| `cot_japanese_math_boku.yaml` | 日本語算数・数学 CoT（僕っ娘キャラクター版・14レベル） |
| `cot_japanese_math.yaml` | 日本語算数・数学 CoT（標準版） |
| `cot_math_generator.yaml` | 英語 数学 CoT 生成器 |
| `minimax_demo.yaml` | MiniMax プロバイダーデモ（日本語要約） |
| `sdg_demo_v2.yaml` | MABEL v2.0 高度な機能サンプル |
| `sdg_demo.yaml` | 基本的な使用例 |
| `data/` | サンプル入出力データセット |

大規模シード生成用スクリプト:
```bash
examples/scripts/generate_cot_boku_1k.py              # 僕っ娘 レベルあたり1k件生成
examples/scripts/generate_cot_japanese_math_scaled_seeds.py  # シード拡張ユーティリティ
```

---

## ライセンス 📝

本プロジェクトは **MITライセンス** のもとで提供されます。
詳しくは [LICENSE](LICENSE) ファイルをご覧ください。

---

## コントリビューション 🤝

SDG-LOOMへの貢献を歓迎しています！
プルリクエスト提出時は以下を確認してください：

* MABEL v1互換性を維持していること
* MABEL v2機能が最新仕様に準拠していること
* すべての既存サンプルでテストがパスすること
* 適切なドキュメンテーションがされていること

---

## サポート 🛠️

問題報告や機能リクエストは [GitHub Issues](https://github.com/your-repository/issues) をご利用ください。

---
