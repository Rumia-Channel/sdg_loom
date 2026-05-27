#!/usr/bin/env python3
"""Generate scaled Japanese math seed JSONL.

This expands the compact hand-written seed file into many generation records.
Each output record is still only a seed: the actual problem, learner response,
solution trace, and final answer are produced by a YAML pipeline.
Use examples/cot_japanese_math.yaml for the neutral version and
examples/cot_japanese_math_boku.yaml for the character roleplay version.

Default output:
  14 levels * 100 records per level = 1400 records

Default scenario mix per level:
  - direct_solution: 70%
  - wrong_answer_correction: 10%
  - correct_answer_verification: 10%
  - prerequisite_bridge_teaching: 10%
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = ROOT / "examples" / "data" / "cot_japanese_math_seeds.jsonl"
DEFAULT_OUTPUT = ROOT / "examples" / "data" / "cot_japanese_math_scaled_seeds.jsonl"


SCENARIOS = [
    {
        "type": "direct_solution",
        "abbr": "solve",
        "label": "通常解答",
        "learner_profile": "問題をそのまま解く場面。学習者の発言はない。",
        "instruction": "問題をそのまま解き、条件確認・計算・検算を含む正しい解答を作る。",
    },
    {
        "type": "wrong_answer_correction",
        "abbr": "wrong",
        "label": "誤答訂正",
        "learner_profile": "問題に対してもっともらしいが間違った答えを出した学習者。",
        "instruction": "学習者の誤答を作り、それを明確に否定して、間違いの理由・正しい計算・条件違反・正答を教える。",
    },
    {
        "type": "correct_answer_verification",
        "abbr": "check",
        "label": "正答確認",
        "learner_profile": "問題に対して正しい答えを出したが、自信がなく確認してほしい学習者。",
        "instruction": "学習者の正答を作り、それが合っていることを条件・計算・検算で確認して確かめる。",
    },
    {
        "type": "prerequisite_bridge_teaching",
        "abbr": "bridge",
        "label": "下位概念からの橋渡し説明",
        "learner_profile": "一つ下の内部難易度までの概念しかまだ理解していない学習者。",
        "instruction": "前の範囲の考え方から新しい概念へ橋をかけるように、丁寧に説明して正答へ導く。",
    },
]


DEFAULT_SCENARIO_WEIGHTS = {
    "direct_solution": 70,
    "wrong_answer_correction": 10,
    "correct_answer_verification": 10,
    "prerequisite_bridge_teaching": 10,
}


VARIATION_HINTS = [
    "場面の対象物を変え、同じ演算でも問う量を少し変える",
    "答えが整数になるようにしつつ、条件を一つ増やす",
    "比較・差分・残りの量のいずれかを自然に含める",
    "途中で単位変換や個数条件を確認したくなる設定にする",
    "最大・最小・ちょうど・以上以下のいずれかを自然に含める",
    "既習事項を一つ使わないと解けない数値設定にする",
    "同じ公式を使うが、文脈と数値の桁を変える",
    "検算しやすいが、早とちりしやすい条件を一つ入れる",
]


PROBLEM_ARCHETYPES = [
    "合計・差・残りを直接問う標準問題",
    "条件を一つ追加し、途中で確認が必要になる問題",
    "最大・最小または制約内の最適値を問う問題",
    "未知量を置いて、条件から式を立てる問題",
    "二つの候補を比較し、どちらが条件に合うか判断する問題",
    "不足量・超過量・差分を使って答えを求める問題",
    "単位変換や割合の読み替えを自然に含む問題",
    "逆算で元の量や初期値を求める問題",
    "表・配列・規則性から量を求める問題",
    "整数条件や境界値を確認して答えを決める問題",
    "公式・定理・性質を使って値や範囲を確認する問題",
    "反例・隣接値・端点を確認して結論を出す問題",
]


SURFACE_THEMES = [
    "買い物・代金・予算",
    "学校・教室・配布物",
    "図書館・本・読書記録",
    "料理・材料・分量",
    "移動・時間・距離",
    "図形・面積・長さ",
    "実験・測定・記録",
    "ゲーム・得点・順位",
    "分け方・並べ方・班分け",
    "表・グラフ・データ",
    "関数・曲線・変化量",
    "写像・集合・構造",
]


CONSTRAINT_FOCI = [
    "等号条件",
    "不等号条件",
    "整数条件",
    "単位の一致",
    "境界値",
    "最大・最小",
    "存在条件",
    "符号",
    "定義域",
    "一意性",
    "検算",
    "条件の過不足",
]


WRONG_ANSWER_PATTERNS = [
    "足すべきところを引く、または引くべきところを足す",
    "単位をそろえずに計算する",
    "最大・最小で隣接値を確認しない",
    "整数条件を忘れて小数や分数のまま答える",
    "符号や不等号の向きを取り違える",
    "約分・通分・分母の扱いを誤る",
    "括弧・分配法則・移項を誤る",
    "条件を一つ読み落として計算する",
    "定数項・積分定数・範囲の端を忘れる",
    "定義域・端点・例外条件を確認しない",
]


NUMBER_POLICIES = [
    "小さめの自然数を使い、暗算でも追えるが条件確認が必要な数値にする",
    "計算結果がきれいになるようにし、解法の中心が概念理解になる数値にする",
    "一つ上・一つ下を試すと条件違反が分かりやすい数値にする",
    "途中計算で繰り上がり・繰り下がり・約分・因数分解などが自然に出る数値にする",
    "単位や割合を確認しないと誤答になりやすい数値にする",
    "答えが一意に定まるよう、条件不足や複数解を避ける数値にする",
]


KNOWLEDGE_PROGRESSION = [
    {
        "concept": "一桁の加減、数の大小比較",
        "methods": "一桁の足し算、一桁の引き算、数え上げ、数え戻し、数の大小比較",
    },
    {
        "concept": "二桁以上の加減、繰り上がり・繰り下がり、筆算の考え方",
        "methods": "二桁以上の足し算、二桁以上の引き算、繰り上がり、繰り下がり、位取り、筆算の考え方",
    },
    {
        "concept": "九九と乗法の意味",
        "methods": "同数累加としての乗法、九九、配列やまとまりの数え方",
    },
    {
        "concept": "割り算、等分除、包含除、余り",
        "methods": "整数の割り算、等分除、包含除、余り、必要な切り上げ・切り捨て",
    },
    {
        "concept": "小数の四則演算、位取り",
        "methods": "小数の加減乗除、小数の位取り、単位量あたりの簡単な計算",
    },
    {
        "concept": "分数の四則演算、通分・約分",
        "methods": "分数の加減乗除、通分、約分、割合の基礎",
    },
    {
        "concept": "文字式、一次方程式、正負の数",
        "methods": "正負の数、文字式、変数設定、一次方程式",
    },
    {
        "concept": "連立方程式、不等式",
        "methods": "連立方程式、一次不等式、範囲条件、整数条件",
    },
    {
        "concept": "二次方程式、因数分解、平方根",
        "methods": "二次方程式、因数分解、平方根、解の公式",
    },
    {
        "concept": "関数、一次関数、二次関数、三角比",
        "methods": "一次関数、二次関数、三角比、グラフ、関数の値域・定義域",
    },
    {
        "concept": "極限、微分係数、導関数、接線、増減表、極値",
        "methods": "極限、微分係数、導関数、接線、増減表、極値",
    },
    {
        "concept": "不定積分、定積分、面積、体積",
        "methods": "不定積分、定積分、面積計算、体積計算",
    },
    {
        "concept": "行列、行列式、固有値、偏微分、重積分",
        "methods": "行列、行列式、固有値、偏微分、重積分",
    },
    {
        "concept": "群論、複素解析、位相空間、関数解析",
        "methods": "群論、複素解析、位相空間、関数解析、および前段階までの既習事項",
    },
]


def cycle_choice(options: list[str], *indices: int) -> str:
    return options[sum(indices) % len(options)]


def problem_archetypes_for(level_num: int) -> list[str]:
    if level_num <= 3:
        return [
            "合計・差・残りを直接問う標準問題",
            "条件を一つ追加し、途中で確認が必要になる問題",
            "二つの候補を比較し、どちらが条件に合うか判断する問題",
            "不足量・超過量・差分を使って答えを求める問題",
            "表・配列・規則性から量を求める問題",
        ]
    if level_num <= 6:
        return [
            *PROBLEM_ARCHETYPES[:3],
            "不足量・超過量・差分を使って答えを求める問題",
            "単位変換や割合の読み替えを自然に含む問題",
            "逆算で元の量や初期値を求める問題",
            "整数条件や境界値を確認して答えを決める問題",
        ]
    if level_num <= 8:
        return [
            *PROBLEM_ARCHETYPES[:10],
        ]
    if level_num >= 13:
        return [
            "定義を確認して性質を示す問題",
            "条件を満たす対象をすべて求める問題",
            "公式・定理・性質を使って値や範囲を確認する問題",
            "反例・隣接値・端点を確認して結論を出す問題",
            "写像・集合・構造の条件を確認する問題",
            "存在条件や一意性を確認する問題",
            "極限・収束・連続性などの条件を確認する問題",
        ]
    return PROBLEM_ARCHETYPES


def surface_themes_for(level_num: int) -> list[str]:
    if level_num <= 8:
        return SURFACE_THEMES[:10]
    if level_num <= 12:
        return [
            "表・グラフ・データ",
            "関数・曲線・変化量",
            "図形・面積・長さ",
            "実験・測定・記録",
            "移動・時間・距離",
        ]
    return [
        "写像・集合・構造",
        "関数・曲線・変化量",
        "表・グラフ・データ",
        "図形・面積・長さ",
    ]


def constraint_foci_for(level_num: int) -> list[str]:
    if level_num <= 3:
        return [
            "等号条件",
            "大小比較",
            "単位の一致",
            "検算",
            "条件の過不足",
        ]
    if level_num <= 6:
        return [
            "等号条件",
            "不等号条件",
            "整数条件",
            "単位の一致",
            "境界値",
            "最大・最小",
            "検算",
            "条件の過不足",
        ]
    return CONSTRAINT_FOCI


def wrong_answer_patterns_for(level_num: int) -> list[str]:
    if level_num <= 3:
        return [
            "足すべきところを引く、または引くべきところを足す",
            "どちらが多いかを見て、差ではなく片方の数を答える",
            "同じものを二回数える、または一つ数え落とす",
            "問題で聞かれている量ではなく、途中の量を答える",
            "条件を一つ読み落として計算する",
        ]
    if level_num <= 5:
        return [
            *wrong_answer_patterns_for(3),
            "単位をそろえずに計算する",
            "最大・最小で隣接値を確認しない",
            "整数条件を忘れて小数や分数のまま答える",
        ]
    if level_num <= 6:
        return [
            *wrong_answer_patterns_for(5),
            "約分・通分・分母の扱いを誤る",
        ]
    if level_num <= 8:
        return [
            *wrong_answer_patterns_for(6),
            "符号や不等号の向きを取り違える",
            "括弧・分配法則・移項を誤る",
        ]
    return WRONG_ANSWER_PATTERNS


def variation_hints_for(level_num: int) -> list[str]:
    if level_num <= 3:
        return [
            "場面の対象物を変え、同じ演算でも問う量を少し変える",
            "答えが整数になるようにしつつ、条件を一つ増やす",
            "比較・差分・残りの量のいずれかを自然に含める",
            "数え落としや早とちりが起きやすい条件を一つ入れる",
            "検算しやすいが、聞かれている量を取り違えやすい設定にする",
        ]
    if level_num <= 8:
        return VARIATION_HINTS[:]
    if level_num <= 12:
        return [
            "同じ公式を使うが、関数・図形・変化量の文脈を変える",
            "境界値、定義域、最大・最小のいずれかを自然に含める",
            "計算だけでなく、条件確認や検算が必要な設定にする",
            "既習事項を一つ使わないと解けない数値設定にする",
            "符号・単位・範囲の確認を怠ると誤答になりやすい設定にする",
        ]
    return [
        "定義・仮定・例外条件のいずれかを確認させる",
        "同じ概念を使うが、対象となる集合・関数・空間を変える",
        "反例、端点、特殊な元の確認が必要な設定にする",
        "計算よりも条件の読み替えや定理の適用条件が中心になる設定にする",
        "結論だけでなく、なぜ条件を満たすかを確認させる",
    ]


def number_policies_for(level_num: int) -> list[str]:
    if level_num <= 3:
        return [
            "小さめの自然数を使い、暗算でも追えるが条件確認が必要な数値にする",
            "答えが指定単元に合う範囲に収まる数値にする",
            "比較したときの差が分かりやすい数値にする",
            "検算で元の数に戻しやすい数値にする",
            "聞かれている量と途中の量が区別しやすい数値にする",
        ]
    if level_num <= 5:
        return [
            "繰り上がり・繰り下がり・余りが自然に出る数値にする",
            "計算結果がきれいになるようにし、解法の中心が概念理解になる数値にする",
            "一つ上・一つ下を試すと条件違反が分かりやすい数値にする",
            "単位や個数条件を確認しないと誤答になりやすい数値にする",
            "答えが一意に定まるよう、条件不足や複数解を避ける数値にする",
        ]
    if level_num <= 8:
        return [
            "整数・小数・分数の計算が自然に必要になる数値にする",
            "約分・通分・符号・移項の確認が自然に出る数値にする",
            "一つ上・一つ下を試すと条件違反が分かりやすい数値にする",
            "単位や割合を確認しないと誤答になりやすい数値にする",
            "答えが一意に定まるよう、条件不足や複数解を避ける数値にする",
        ]
    if level_num <= 12:
        return [
            "式変形が長くなりすぎず、方針と条件確認が中心になる数値にする",
            "因数分解・平方根・三角比・微積分の計算が自然に出る数値にする",
            "定義域・境界値・符号の確認が必要になる数値にする",
            "代入検算しやすく、誤答との差が分かりやすい数値にする",
            "答えが一意に定まるよう、条件不足や複数解を避ける数値にする",
        ]
    return [
        "計算量を抑え、定義・仮定・定理の適用条件が中心になる設定にする",
        "例外条件や端点を確認しやすい対象を選ぶ",
        "標準的な対象を少し変え、丸暗記ではなく条件確認が必要な設定にする",
        "結論が一意に決まるよう、必要な仮定を明示できる設定にする",
        "検算や反例確認によって結論の正しさを確かめやすい設定にする",
    ]


def derive_knowledge_policy(level_num: int) -> dict[str, str]:
    current = min(max(level_num, 1), len(KNOWLEDGE_PROGRESSION))
    introduced = KNOWLEDGE_PROGRESSION[:current]
    future = KNOWLEDGE_PROGRESSION[current:]
    allowed = "、".join(item["methods"] for item in introduced)
    forbidden = "、".join(item["concept"] for item in future)
    if not forbidden:
        forbidden = "問題で明示されていない高度な定理の無断使用、条件確認のない断定"
    return {"allowed": allowed, "forbidden": forbidden}


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            row["_source_seed_index"] = line_no
            rows.append(row)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")


def parse_scenarios(value: str) -> list[dict]:
    requested = [item.strip() for item in value.split(",") if item.strip()]
    by_type = {item["type"]: item for item in SCENARIOS}
    by_abbr = {item["abbr"]: item for item in SCENARIOS}
    selected: list[dict] = []
    for name in requested:
        scenario = by_type.get(name) or by_abbr.get(name)
        if not scenario:
            valid = ", ".join(item["type"] for item in SCENARIOS)
            raise SystemExit(f"Unknown scenario '{name}'. Valid scenarios: {valid}")
        selected.append(scenario)
    return selected


def parse_weights(value: str, scenarios: list[dict]) -> dict[str, int]:
    scenario_types = {scenario["type"] for scenario in scenarios}
    if not value.strip():
        return {
            scenario_type: DEFAULT_SCENARIO_WEIGHTS.get(scenario_type, 1)
            for scenario_type in scenario_types
        }

    by_type = {item["type"]: item["type"] for item in SCENARIOS}
    by_abbr = {item["abbr"]: item["type"] for item in SCENARIOS}
    weights: dict[str, int] = {}
    for raw_item in value.split(","):
        item = raw_item.strip()
        if not item:
            continue
        if "=" not in item:
            raise SystemExit(
                "--scenario-weights must use name=value pairs, "
                "for example direct_solution=70,wrong_answer_correction=10"
            )
        raw_name, raw_weight = item.split("=", 1)
        name = raw_name.strip()
        scenario_type = by_type.get(name) or by_abbr.get(name)
        if scenario_type not in scenario_types:
            valid = ", ".join(sorted(scenario_types))
            raise SystemExit(f"Unknown weighted scenario '{name}'. Active scenarios: {valid}")
        try:
            weight = int(raw_weight.strip())
        except ValueError as exc:
            raise SystemExit(f"Invalid weight for scenario '{name}': {raw_weight}") from exc
        if weight < 0:
            raise SystemExit(f"Scenario weight must be non-negative: {name}={weight}")
        weights[scenario_type] = weight

    for scenario_type in scenario_types:
        weights.setdefault(scenario_type, 0)
    if sum(weights.values()) <= 0:
        raise SystemExit("At least one scenario weight must be positive")
    return weights


def build_weighted_schedule(
    *,
    items_per_level: int,
    scenarios: list[dict],
    weights: dict[str, int],
) -> list[dict]:
    """Build a deterministic weighted scenario schedule.

    For the default 100 records per level and weights 70/10/10/10 this produces
    exactly 70 direct_solution records and 10 for each remaining scenario.
    """

    total_weight = sum(weights[scenario["type"]] for scenario in scenarios)
    raw_counts = [
        (
            scenario,
            items_per_level * weights[scenario["type"]] / total_weight,
        )
        for scenario in scenarios
    ]
    counts = {scenario["type"]: int(raw) for scenario, raw in raw_counts}
    remaining = items_per_level - sum(counts.values())
    remainders = sorted(
        (
            (raw - int(raw), index, scenario)
            for index, (scenario, raw) in enumerate(raw_counts)
        ),
        key=lambda item: (-item[0], item[1]),
    )
    for _, _, scenario in remainders[:remaining]:
        counts[scenario["type"]] += 1

    schedule: list[dict] = []
    for scenario in scenarios:
        schedule.extend([scenario] * counts[scenario["type"]])
    return schedule


def level_key(row: dict) -> int:
    try:
        return int(row["level"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit(f"Seed row has invalid level: {row!r}") from exc


def build_record(
    *,
    base: dict,
    level_num: int,
    level_item_index: int,
    variant_index: int,
    scenario: dict,
    style_intensity: int,
) -> dict:
    record = {
        key: value for key, value in base.items() if not key.startswith("_")
    }
    record["style_intensity"] = style_intensity
    record["sample_id"] = (
        f"jp-math-l{level_num:02d}-{level_item_index:03d}-{scenario['abbr']}"
    )
    record["source_seed_index"] = base["_source_seed_index"]
    record["level_item_index"] = level_item_index
    record["variant_index"] = variant_index
    record["interaction_type"] = scenario["type"]
    record["interaction_label"] = scenario["label"]
    record["interaction_instruction"] = scenario["instruction"]
    record["learner_profile"] = scenario["learner_profile"]
    record["variation_hint"] = cycle_choice(
        variation_hints_for(level_num), level_item_index - 1
    )
    record["number_policy"] = cycle_choice(
        number_policies_for(level_num), variant_index - 1
    )
    record["problem_archetype"] = cycle_choice(
        problem_archetypes_for(level_num), level_item_index - 1, variant_index - 1
    )
    record["surface_theme"] = cycle_choice(
        surface_themes_for(level_num), level_item_index - 1, level_num - 1
    )
    record["constraint_focus"] = cycle_choice(
        constraint_foci_for(level_num), level_item_index - 1, (variant_index - 1) * 2
    )
    record["wrong_answer_pattern"] = cycle_choice(
        wrong_answer_patterns_for(level_num),
        level_item_index - 1,
        level_num - 1,
        variant_index - 1,
    )
    knowledge_policy = derive_knowledge_policy(level_num)
    record["allowed_methods"] = knowledge_policy["allowed"]
    record["forbidden_methods"] = knowledge_policy["forbidden"]
    record["method_policy"] = (
        "解法は allowed_methods に含まれる知識だけで組み立てる。"
        "forbidden_methods に含まれる道具は、近道になっても使わない。"
        "導入済みの概念で直接扱える問題を、未導入の上位概念へ持ち上げて解かない。"
    )
    record["diversity_instruction"] = (
        "seed の場面は素材として使い、同じ問題文にしない。"
        "対象物・数値・問う量・条件焦点のうち少なくとも2つを変える。"
        "ただし、新規導入概念と指定トピックからは外れない。"
    )
    return record


def expand_rows(
    base_rows: list[dict],
    *,
    items_per_level: int,
    scenarios: list[dict],
    scenario_weights: dict[str, int],
    per_scenario: bool,
    style_intensity: int,
) -> list[dict]:
    by_level: dict[int, list[dict]] = defaultdict(list)
    for row in base_rows:
        by_level[level_key(row)].append(row)

    expanded: list[dict] = []
    for level_num in sorted(by_level):
        level_rows = by_level[level_num]
        if per_scenario:
            for scenario in scenarios:
                for item_index in range(1, items_per_level + 1):
                    base = level_rows[(item_index - 1) % len(level_rows)]
                    variant_index = ((item_index - 1) // len(level_rows)) + 1
                    expanded.append(
                        build_record(
                            base=base,
                            level_num=level_num,
                            level_item_index=item_index,
                            variant_index=variant_index,
                            scenario=scenario,
                            style_intensity=style_intensity,
                        )
                    )
        else:
            scenario_schedule = build_weighted_schedule(
                items_per_level=items_per_level,
                scenarios=scenarios,
                weights=scenario_weights,
            )
            for item_index in range(1, items_per_level + 1):
                base = level_rows[(item_index - 1) % len(level_rows)]
                variant_index = ((item_index - 1) // len(level_rows)) + 1
                scenario = scenario_schedule[item_index - 1]
                expanded.append(
                    build_record(
                        base=base,
                        level_num=level_num,
                        level_item_index=item_index,
                        variant_index=variant_index,
                        scenario=scenario,
                        style_intensity=style_intensity,
                    )
                )
    return expanded


def print_summary(rows: list[dict]) -> None:
    by_level = Counter(row["level"] for row in rows)
    by_scenario = Counter(row["interaction_type"] for row in rows)
    print(f"records: {len(rows)}")
    print(f"levels: {dict(sorted(by_level.items(), key=lambda kv: int(kv[0])))}")
    print(f"scenarios: {dict(by_scenario)}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate scaled Japanese math seed JSONL."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--items-per-level", type=int, default=100)
    parser.add_argument(
        "--scenarios",
        default=",".join(item["type"] for item in SCENARIOS),
        help="Comma-separated scenario types or abbreviations.",
    )
    parser.add_argument(
        "--scenario-weights",
        default="",
        help=(
            "Comma-separated name=weight pairs used when --per-scenario is not set. "
            "Default is direct_solution=70 and 10 for each auxiliary scenario."
        ),
    )
    parser.add_argument(
        "--per-scenario",
        action="store_true",
        help="Generate --items-per-level records for each scenario at each level.",
    )
    parser.add_argument("--style-intensity", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.items_per_level <= 0:
        raise SystemExit("--items-per-level must be positive")

    base_rows = read_jsonl(args.source)
    scenarios = parse_scenarios(args.scenarios)
    scenario_weights = parse_weights(args.scenario_weights, scenarios)
    expanded = expand_rows(
        base_rows,
        items_per_level=args.items_per_level,
        scenarios=scenarios,
        scenario_weights=scenario_weights,
        per_scenario=args.per_scenario,
        style_intensity=args.style_intensity,
    )

    print_summary(expanded)
    if args.dry_run:
        return
    write_jsonl(args.output, expanded)
    print(f"wrote: {args.output}")


if __name__ == "__main__":
    main()
