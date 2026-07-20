# SDG-LOOM

> **Scalable synthetic data generator for LLM fine-tuning.** Supports DeepSeek API and MiniMax API with unified provider abstraction, adaptive concurrency control, and declarative MABEL v2.0 agent programs.

<img width="1024" alt="SDG-LOOM Logo" src="assets/logo.png" />

## Overview

**SDG-LOOM (Scalable Data Generator LOOM)** is a high-throughput batch synthetic-dataset generator framework purpose-built for producing fine-tuning data at scale. It uses **MABEL v2.0** (Model And Blocks Expansion Language) declarative agent programs and supports multiple LLM providers through a unified abstraction layer.

- **DeepSeek API** — KV context caching (disk-based), thinking mode (chain-of-thought), HTTP/2 connection pooling
- **MiniMax API** — Multi-region support (China / global), MiniMax-M3 with 1M context

Adaptive concurrency control (TCP Vegas/Reno/BBR-inspired) with EMA smoothing handles rate limits and latency spikes automatically, making it safe for large-scale batch generation.

---

## Features

* **DeepSeek API Optimized**
  * Automatic KV context caching (disk-based prefix cache) utilization
  * Thinking mode (chain-of-thought reasoning) support
  * Cache hit/miss tracking and cost analysis
  * Optimized HTTP/2 connection pooling for DeepSeek endpoints
* **MABEL v2.0 Support**
  * Turing-complete expression language (MEX)
  * Advanced control structures (`while`, `recurse`, `reduce`, `call`, `let`)
  * Inline Python functions
  * Global variable support
* **MABEL v1.x Backward Compatibility**
  * Automatic version detection
* **Advanced Concurrent Processing**
  * Adaptive concurrency control inspired by TCP congestion control (Vegas/Reno/BBR)
    * Two-phase control: Slow Start (exponential increase) and Congestion Avoidance (linear increase)
    * Noise reduction and trend detection using EMA (Exponential Moving Average)
    * Vegas-style proactive congestion detection
    * Graduated decrease logic (ignores mild congestion, responds immediately to severe congestion)
  * Real-time metrics collection from vLLM/SGLang backends
  * Dynamic request batching for optimal throughput
  * Automatic latency-based optimization
* **Multi-Model Support**
  * Define and operate multiple LLM models simultaneously
* **Flexible I/O Support**
  * JSONL and CSV format support in streaming and batch modes
  * Direct loading of Hugging Face Datasets
  * Key mapping feature for improved dataset compatibility
* **Robust Error Handling**
  * Flexible error handling with retry mechanisms
  * Failed rows are written to a separate `<output>.error.jsonl` file instead
    of polluting the main output, so a run with partial failures still
    produces a clean, directly-usable dataset
* **Performance Optimization**
  * Shared HTTP transport for connection pooling
  * HTTP/2 support for improved throughput
  * Asynchronous buffered I/O for efficient file operations
  * Phase 2: Hierarchical task scheduling and memory optimization (see [Phase 2 Optimization Guide](docs/phase2_optimization.md))
* **Post-Generation Profiling**
  * Language distribution analysis
  * Output length distribution statistics
  * Duplicate detection and deduplication rate
  * Parse/validation failure rate tracking
  * LLM token usage statistics per model

---

## Project Structure 🗂️

```
sdg/
├── cli.py                 # argparse CLI: sdg run / sdg test-run / legacy mode
├── config.py               # compat layer — re-exports sdg/schema/*, old AIBlock/LogicBlock/... aliases
├── character.py            # character cards: CharacterCard, load_character(), build_template_vars(), score_voice()
├── llm_client.py           # LLMClient (AsyncOpenAI wrapper), SharedHttpTransport, streaming TTFB latency
├── io.py                   # AsyncBufferedWriter, jsonl/csv/HF-dataset readers, resume support
├── mex.py                  # MEX: the MABEL v2 expression language (Turing-complete)
├── utils.py                # render_template ({a.b} placeholders), image data-URI handling, JSONL cleanup
├── profiler.py             # post-run profiling: language mix, length stats, dedup, token usage
├── logger.py                # rich-based logger (en/ja locale)
│
├── schema/                 # Pydantic config models
│   ├── config.py            # SDGConfig.from_yaml(), ModelConfig, GlobalsConfig, provider/character resolution
│   └── blocks.py             # AIBlockConfig / LogicBlockConfig / PythonBlockConfig / EndBlockConfig
│
├── pipeline/                # unified execution engine
│   ├── engine.py              # PipelineEngine — resume, provider defaults, character injection, run loop
│   ├── run_config.py          # RunConfig / ConcurrencyConfig / IOConfig / ProviderConfig (all Pydantic)
│   ├── _provider_defaults.py  # env-based lazy defaults for ConcurrencyConfig
│   └── result.py              # RowResult / RunReport
│
├── executors/               # per-block-type execution logic
│   ├── core.py                 # ExecutionContext (globals/loop/recursion budgets), template resolution
│   ├── ai.py                    # AI block execution, client construction, multimodal content, thinking mode
│   ├── logic.py                 # if/and/or/for/while/recurse/set/let/reduce/call/emit
│   ├── python.py                # inline/external Python function blocks, PythonContext (ctx.get/set/log)
│   ├── pipeline_core.py         # process_single_row() — runs one row through all blocks
│   ├── pipeline_legacy.py       # legacy batch-mode runner (backward compat only)
│   └── scheduling.py            # HierarchicalTaskScheduler, LRUCache, MemoryMonitor
│
├── scheduler/                # parallel execution strategies
│   ├── fixed.py                 # FixedScheduler — asyncio.Semaphore, fixed concurrency
│   └── adaptive.py              # AdaptiveScheduler — progressive launch, driven by AdaptiveController
│
├── adaptive/                  # adaptive concurrency control
│   ├── controller.py             # AdaptiveController (TCP Vegas/Reno/BBR-inspired AIMD), DynamicSemaphore
│   ├── batcher.py                 # RequestBatcher / AdaptiveRequestBatcher
│   └── metrics.py                 # MetricsCollector (vLLM / SGLang Prometheus scraping)
│
├── providers/                 # LLM provider abstraction
│   ├── base.py                    # Provider dataclass — base URLs, defaults, concurrency/adaptive tuning
│   ├── deepseek.py                 # DeepSeek profile (KV cache isolation, thinking mode, aggressive AIMD)
│   ├── minimax.py                  # MiniMax profile (cn / global regions, MiniMax-M3 1M context)
│   └── __init__.py                 # registry + resolve_provider_name() / resolve_region()
│
└── runners/                   # backward-compatible entry points
    ├── legacy.py                    # run() — legacy batch mode
    └── test.py                      # test_run() — single-row debug run

characters/                  # character cards (persona definitions, task-independent)
└── confident_bokukko.yaml     # reference card: "自信家な僕っ娘"

examples/                    # sample MABEL pipelines + input data + helper scripts
docs/                        # usage guides and the full MABEL v2 spec
```

New LLM providers are added by dropping a `Provider(...)` instance in `sdg/providers/`
and registering it in `sdg/providers/__init__.py`'s `PROVIDERS` dict — no changes
needed elsewhere, since concurrency tuning, base URLs, and thinking-mode behavior
all flow through that one dataclass.

---

## Requirements

* Python `>= 3.10`
* PyYAML `>= 6.0.1`
* openai `>= 1.40.0`
* tqdm `>= 4.66.0`

---

## Installation

Examples of installation using multiple environment management methods are provided.

### Standard pip Installation

```bash
pip install -e .
```

### Installation with pyenv

```bash
# Python version management
pyenv install 3.12.0
pyenv local 3.12.0

# Set up venv
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -e .
```

### Installation with conda

```bash
# Create and activate environment
conda create -n sdg python=3.12
conda activate sdg

# Install
pip install -e .
```

### Fast Installation with uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager.

```bash
# Install uv (if not already installed)
pip install uv

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate

uv pip install -e .
```

---

## Quick Start

Minimal configuration examples for both providers:

<table>
<tr>
<th>DeepSeek</th>
<th>MiniMax</th>
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
      - "Summarize: {UserInput}"
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
mabel:
  version: "2.0"

provider: minimax
region: cn

models:
  - name: m3
    api_model: MiniMax-M3
    api_key: "${ENV.MINIMAX_API_KEY}"

blocks:
  - type: ai
    exec: 1
    model: m3
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

For detailed specifications, please refer to:

* **[MABEL v2 Specification](docs/mabel/mabel_v2_en.md)** - Detailed feature descriptions, samples, and specifications

---

## Usage

### Command Line (CLI) Execution

Select your provider and region at the CLI:

```bash
# MiniMax (China region)
sdg run --yaml pipeline.yaml --input data.jsonl --output result.jsonl \
  --provider minimax --region cn

# DeepSeek (default — no --provider needed)
sdg run --yaml pipeline.yaml --input data.jsonl --output result.jsonl
```

Basic JSONL processing:

```bash
sdg run \
  --yaml examples/sdg_demo_v2.yaml \
  --input examples/data/input.jsonl \
  --output output/result.jsonl
```

Quick test with a single data item:

```bash
sdg test-run \
  --yaml examples/sdg_demo_v2.yaml \
  --input examples/data/input.jsonl
```

With verbose logging (detailed debug output):

```bash
sdg run \
  --yaml examples/sdg_demo_v2.yaml \
  --input data.jsonl \
  --output result.jsonl \
  --verbose
```

With Japanese UI (default is English):

```bash
sdg run \
  --yaml examples/sdg_demo_v2.yaml \
  --input data.jsonl \
  --output result.jsonl \
  --ui-locale ja
```

Execution with adaptive concurrency and custom batch settings:

```bash
sdg run \
  --yaml examples/sdg_demo_v2.yaml \
  --input data.jsonl \
  --output result.jsonl \
  --adaptive \
  --max-batch 16 \
  --min-batch 2 \
  --target-latency-ms 2000
```

### Using Python API

**Simple streaming execution (recommended):**

```python
from sdg.runner import run_streaming

run_streaming(
    yaml_path="pipeline.yaml",
    input_path="data/input.jsonl",
    output_path="output/result.jsonl",
    max_concurrent=8,
)
```

**Full control with `PipelineEngine`:**

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

## Providers & Regions 🌍

SDG-LOOM supports multiple LLM providers through a unified abstraction. Each
provider defines its own base URLs (per region), default model, API key
environment variable, KV-cache/user_id support, thinking-mode style, and
recommended concurrency tuning.

### Supported providers

| Provider | Default model | Default base URL | API key env | Notes |
|----------|---------------|------------------|-------------|-------|
| `deepseek` | `deepseek-v4-flash` | `https://api.deepseek.com` | `DEEPSEEK_API_KEY` | KV cache isolation via `user_id`, thinking mode (`extra_body.thinking`) |
| `minimax` | `MiniMax-M3`        | `https://api.minimax.io` (global) / `https://api.minimaxi.com` (cn) | `MINIMAX_API_KEY` | Multi-region (cn/global) |

### Region selection (MiniMax)

`minimax` supports two regions. Pick one with any of the three mechanisms
below (priority: **CLI > env > YAML > default**):

| Source | Example |
|--------|---------|
| CLI flag | `--provider minimax --region cn` |
| Env var | `SDG_PROVIDER=minimax SDG_REGION=cn` |
| YAML   | `provider: minimax`<br>`region: cn` |

If no region is specified, the provider's default is used (currently `global`).

### Provider resolution chain

Provider name is also resolved by **CLI > env > YAML > default (`deepseek`)**.
This means existing DeepSeek YAML files keep working without changes.

### Quick example (MiniMax, China region)

```yaml
provider: minimax
region: cn   # use api.minimaxi.com

models:
  - name: m3
    api_model: MiniMax-M3   # optional: provider default is also MiniMax-M3
    api_key: "${ENV.MINIMAX_API_KEY}"

blocks:
  - type: ai
    exec: 1
    model: m3
    prompts:
      - "次の入力を要約してください: {UserInput}"
    outputs:
      - name: Summary
        select: full
  - type: end
    exec: 10
    final:
      - name: result
        value: "{Summary}"
```

Run it:

```bash
# 1. CLI flag
sdg run --yaml examples/minimax_demo.yaml --input examples/data/minimax_input.jsonl \
  --output output/result.jsonl --provider minimax --region cn

# 2. env var
SDG_PROVIDER=minimax SDG_REGION=cn \
  sdg run --yaml examples/minimax_demo.yaml --input examples/data/minimax_input.jsonl \
  --output output/result.jsonl
```

### Per-provider concurrency defaults

The `ConcurrencyConfig` and `SharedHttpTransport` apply provider-specific
defaults. For example, `--max-concurrent` is omitted on the CLI, the framework
uses `128` for DeepSeek and `64` for MiniMax. Override any field explicitly
to take precedence over the provider default.

| Field | DeepSeek | MiniMax |
|-------|---------:|--------:|
| `max_concurrent` (固定モード) | 128 | 64 |
| `max_concurrent_limit` (適応モード上限) | 500 | 200 |
| `min_concurrent` (適応モード下限) | 8 | 4 |
| `target_latency_ms` | 3000 | 4000 |
| `target_queue_depth` | 64 | 32 |
| `max_batch_size` | 64 | 32 |
| `SharedHttpTransport` max_connections | 600 | 300 |

### Local / self-hosted models (llama.cpp, vLLM, etc.)

`LLMClient` is a plain `AsyncOpenAI` client, so **any OpenAI-compatible
server works with zero code changes** — just point `base_url` at it. This
includes `llama.cpp`'s built-in `llama-server` (`/v1/chat/completions`),
vLLM, SGLang, and LM Studio.

```bash
# start an OpenAI-compatible server, e.g.:
llama-server -m model.gguf -c 16384 --parallel 2 --host 127.0.0.1 --port 8080

# then just override the endpoint — no provider needed
export SDG_API_MODEL="local"                 # most local servers ignore this field
export SDG_API_KEY="sk-no-key-required"       # api_key must be a non-empty string
export SDG_BASE_URL="http://127.0.0.1:8080/v1"

sdg run --yaml examples/cot_japanese_math_boku.yaml \
  --input examples/data/cot_japanese_math_seeds.jsonl \
  --output output/local.jsonl \
  --max-concurrent 2   # match your server's --parallel slot count
```

Leaving `--provider` unset still applies the DeepSeek concurrency profile
(`max_concurrent=128` by default) even though requests go to your local
server — always pass `--max-concurrent` (or `--adaptive --max-batch`)
explicitly to match what a single local instance can actually handle.
Small local models also tend to struggle with prompts that mix strict task
correctness and character voice in one shot; see the **Character Cards**
section below for a two-stage design that works better with weaker models.

---

## Character Cards (Task / Persona Separation) 🎭

SDG-LOOM lets you separate **what to generate** (the task YAML) from **who is
speaking** (a character card). A character card is a standalone YAML file
(see `sdg/character.py`) that gets loaded and injected into `globals.const`
as a `char` variable, so any block can reference `{char.*}` without the task
YAML knowing anything about the persona.

### Usage

Point a task YAML at a card via the top-level `character:` key (path is
resolved relative to the YAML file's directory):

```yaml
character: ../characters/confident_bokukko.yaml
```

Or override it at run time with `--character` (takes precedence over the
YAML key), for both `sdg run` and `sdg test-run`:

```bash
sdg run --yaml examples/character_two_stage.yaml \
  --character characters/confident_bokukko.yaml \
  --input examples/data/cot_japanese_math_seeds.jsonl \
  --output output/result.jsonl
```

### Available `{char.*}` variables

| Variable | Description |
|----------|-------------|
| `{char.name}` / `{char.label}` / `{char.persona}` / `{char.first_person}` | Basic identity fields |
| `{char.profile}` | Full character sheet (prompt-ready) |
| `{char.speech_rules}` / `{char.forbidden}` / `{char.examples}` / `{char.intensity_guide}` | Individual prompt components |
| `{char.solve_system}` | System prompt for solving a task directly in-character (single-stage, strong models) |
| `{char.rewrite_system}` | System prompt for style-transferring a neutral draft (two-stage, weak models) |
| `{char.card_path}` | Absolute path to the card file (for reloading inside `python` blocks) |

### Two-stage generation for weaker models

`examples/character_two_stage.yaml` shows the recommended pattern when the
generating model isn't strong enough to satisfy task correctness *and*
character voice in a single call:

1. **solve** — an `ai` block solves the task with a neutral, in-character-agnostic
   system prompt (no persona knowledge required, so smaller models do fine).
2. **stylize** — a second `ai` block runs `{char.rewrite_system}`, which
   instructs the model to change *only* wording/tone (never facts, numbers,
   or formulas) and gives it few-shot examples from the card. This is a much
   easier task than solving-in-character, so it works even on small/cheap
   models.
3. **validate** — a `python` block calls `sdg.character.score_voice()` to
   score the result against the card's marker groups, with **no LLM call at
   all** — catching "tone-suffix-only" fake persona voice and flagging rows
   that need regeneration.

```bash
sdg run --yaml examples/character_two_stage.yaml \
  --character characters/confident_bokukko.yaml \
  --input examples/data/cot_japanese_math_seeds.jsonl \
  --output output/character_two_stage.jsonl \
  --max-concurrent 4
```

Each stage can use a different model — e.g. a strong model for `solver` and
a cheap/local one for `stylizer` — by giving them separate `models:` entries
in the task YAML and pointing each at whichever `base_url` fits.

---

## Detailed Documentation 📖

* **[Usage Guide](docs/usage.md)** - Detailed usage of CLI and Python API
* **[MABEL v2 Complete Specification](docs/mabel/mabel_v2_en.md)** - MABEL grammar and feature details

---

## MABEL Editor 🎨

For visual editing of MABEL files, we provide a dedicated GUI tool:

* **[SDG UI](https://github.com/foxn2000/sdg_ui)** - A graphical user interface for creating and editing MABEL configuration files

This tool provides an intuitive way to design and manage MABEL pipelines without manually editing YAML files.

---

## Dataset Generation Examples 🧮

### Japanese Math Chain-of-Thought (Boku-kko Persona)

Generate a 14-level Japanese math curriculum dataset with a "自信家な僕っ娘" (confident boy-style girl) character persona:

**MiniMax:**
```bash
export MINIMAX_API_KEY="sk-..."
uv run sdg run \
  --yaml examples/cot_japanese_math_boku.yaml \
  --input examples/data/cot_japanese_math_scaled_seeds.jsonl \
  --output output/japanese_math_cot_boku.jsonl \
  --provider minimax --region cn \
  --adaptive --max-batch 32 --resume
```

**DeepSeek:**
```bash
export DEEPSEEK_API_KEY="sk-..."
uv run sdg run \
  --yaml examples/cot_japanese_math_boku.yaml \
  --input examples/data/cot_japanese_math_scaled_seeds.jsonl \
  --output output/japanese_math_cot_boku.jsonl \
  --adaptive --max-batch 64 --resume
```

**Large-scale (1,000+ per level):**
```bash
# Set provider via environment
export MINIMAX_API_KEY="sk-..."
export SDG_PROVIDER=minimax
export SDG_REGION=cn

# 14 levels × 5000 = 70,000 questions
uv run python examples/scripts/generate_cot_boku_1k.py --items-per-level 5000 --resume
```

### Pure Math CoT (neutral tone):
```bash
uv run sdg run \
  --yaml examples/cot_japanese_math.yaml \
  --input examples/data/cot_japanese_math_scaled_seeds.jsonl \
  --output output/japanese_math_cot.jsonl \
  --provider minimax --region cn --adaptive --resume
```

---

## Examples

Sample pipelines and data are provided in `examples/`:

| File | Description |
|------|-------------|
| `cot_japanese_math_boku.yaml` | Japanese math CoT with bokukko persona, single-stage (14 levels) |
| `character_two_stage.yaml` | Persona-agnostic two-stage pipeline: neutral solve → character rewrite → voice validation |
| `cot_japanese_math.yaml` | Japanese math CoT (neutral tone) |
| `cot_math_generator.yaml` | English math CoT generator |
| `minimax_demo.yaml` | MiniMax provider demo (Japanese summarization) |
| `sdg_demo_v2.yaml` | MABEL v2.0 advanced features |
| `sdg_demo.yaml` | Basic usage example |
| `data/` | Sample input/output datasets |
| `../characters/` | Character cards (persona definitions), e.g. `confident_bokukko.yaml` |

Scripts for large-scale seed generation:
```bash
examples/scripts/generate_cot_boku_1k.py           # Bokukko 1k-per-level generator
examples/scripts/generate_cot_japanese_math_scaled_seeds.py  # Seed expansion utility
```

---

## License 📝

This project is provided under the **MIT License**.
See the [LICENSE](LICENSE) file for details.

---

## Contributing 🤝

Contributions to SDG-LOOM are welcome!
When submitting pull requests, please ensure:

* MABEL v1 compatibility is maintained
* MABEL v2 features comply with the latest specifications
* All existing samples pass tests
* Appropriate documentation is provided

---

## Support 🛠️

For bug reports and feature requests, please use [GitHub Issues](https://github.com/your-repository/issues).

---
