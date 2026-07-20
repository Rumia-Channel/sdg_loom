"""sdg/character.py - キャラクターカード: タスク非依存の人格定義

タスク定義（MABEL YAML）とキャラクター性を分離するためのモジュール。

キャラクターカード（YAML）を読み込み、以下を提供する:

1. プロンプト部品の自動生成
   カードから `{char.profile}` / `{char.solve_system}` / `{char.rewrite_system}`
   などのテンプレート変数を生成し、globals 経由で全ブロックから参照可能にする。
   タスク YAML はキャラクターの中身を一切知らずに済む。

2. 弱いモデル向けの2段構成サポート
   - solve_system:   タスクをキャラクターの声で直接解く（1段構成・強いモデル向け）
   - rewrite_system: 無人格な下書きを事実を変えずに文体変換する（2段構成・弱いモデル向け）
   文体変換は「事実の固定 + 機械的な変換ルール + few-shot」だけで完結するため、
   推論力の低いモデルでもキャラクター性を再現できる。

3. 機械的な口調検証 (score_voice)
   カードの validation マーカー群に基づき、生成文のキャラクター性を
   LLM なしでスコアリングする。python ブロックから
   `from sdg.character import score_voice` で利用できる。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# カードスキーマ
# ---------------------------------------------------------------------------


class SpeechConfig(BaseModel):
    """話し方の定義"""

    model_config = {"populate_by_name": True}

    first_person: str = "私"
    second_person: List[str] = Field(default_factory=list)
    politeness: str = ""  # 例: "常体。です・ます調は使わない"
    endings: List[str] = Field(default_factory=list)  # 基本語尾
    sample_phrases: List[str] = Field(default_factory=list)  # 使ってよい言い回し
    forbidden_phrases: List[str] = Field(default_factory=list)  # 禁止表現


class BehaviorConfig(BaseModel):
    """性格・判断様式の定義"""

    model_config = {"populate_by_name": True}

    traits: List[str] = Field(default_factory=list)  # 性格特徴
    principles: List[str] = Field(default_factory=list)  # キャラの出し方の原則
    avoid: List[str] = Field(default_factory=list)  # 避ける振る舞い


class FewShotExample(BaseModel):
    """文体変換の few-shot 例（タスク非依存）

    neutral → styled の対にすることで、弱いモデルにも
    「何をどう変えるか」を模倣だけで伝えられる。
    """

    model_config = {"populate_by_name": True}

    neutral: str  # 無人格な文
    styled: str  # キャラクターの声の文
    note: str = ""  # 変換の要点（省略可）


class IntensityConfig(BaseModel):
    """キャラクター濃度 (style_intensity) の定義"""

    model_config = {"populate_by_name": True}

    default: int = 2
    levels: Dict[str, str] = Field(default_factory=dict)  # "1"〜"4" → 説明


class ValidationConfig(BaseModel):
    """機械検証用マーカー定義

    voice_groups: 軸ごとのマーカー群。1軸でも命中すれば1点。
    「語尾だけキャラ」を弾くため、tone 系以外の軸（一人称・判断・確認など）を
    substantive として扱う。
    """

    model_config = {"populate_by_name": True}

    voice_groups: Dict[str, List[str]] = Field(default_factory=dict)
    # 語尾など「表層だけ」のマーカー軸名（voice_groups のキーを指す）
    tone_groups: List[str] = Field(default_factory=list)
    # 無人格化の兆候（出現数が多いと警告）
    neutral_penalties: List[str] = Field(
        default_factory=lambda: ["です", "ます", "である"]
    )
    neutral_penalty_max: int = 2
    # style_intensity → 必要スコア
    required_score: Dict[str, int] = Field(
        default_factory=lambda: {"1": 1, "2": 2, "3": 3, "4": 3}
    )


class CharacterCard(BaseModel):
    """キャラクターカード本体"""

    model_config = {"populate_by_name": True}

    name: str
    label: str = ""  # 短い呼称（例: "自信家な僕っ娘"）
    persona: str = ""  # 人物像の自由記述
    speech: SpeechConfig = Field(default_factory=SpeechConfig)
    behavior: BehaviorConfig = Field(default_factory=BehaviorConfig)
    style_intensity: IntensityConfig = Field(default_factory=IntensityConfig)
    few_shot: List[FewShotExample] = Field(default_factory=list)
    validation: ValidationConfig = Field(default_factory=ValidationConfig)
    # カード側で自由に追加できるテンプレ変数（{char.<key>} で参照）
    extra: Dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 読み込み
# ---------------------------------------------------------------------------


def load_character(path: str) -> CharacterCard:
    """キャラクターカード YAML を読み込む。

    トップレベルが `character:` キーでも、カード直書きでも受け付ける。
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if "character" in data and isinstance(data["character"], dict):
        data = data["character"]
    return CharacterCard(**data)


# ---------------------------------------------------------------------------
# プロンプト部品の生成
# ---------------------------------------------------------------------------


def _bullets(items: List[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _render_profile(card: CharacterCard) -> str:
    """キャラクター設定シート（プロンプト埋め込み用）"""
    sections: List[str] = [f"# キャラクター設定: {card.name}"]
    if card.label:
        sections.append(f"呼称: {card.label}")
    if card.persona:
        sections.append(f"## 人物像\n{card.persona.strip()}")

    speech_lines: List[str] = [f"- 一人称は必ず「{card.speech.first_person}」。"]
    if card.speech.second_person:
        speech_lines.append(
            "- 二人称は「" + "」「".join(card.speech.second_person) + "」を使う。"
        )
    if card.speech.politeness:
        speech_lines.append(f"- {card.speech.politeness}")
    if card.speech.endings:
        speech_lines.append(
            "- 基本語尾: " + " / ".join(f"「{e}」" for e in card.speech.endings)
        )
    sections.append("## 話し方\n" + "\n".join(speech_lines))

    if card.speech.sample_phrases:
        sections.append(
            "## 使ってよい言い回し（連発しないこと）\n"
            + _bullets(card.speech.sample_phrases)
        )
    if card.behavior.traits:
        sections.append("## 性格\n" + _bullets(card.behavior.traits))
    if card.behavior.principles:
        sections.append("## キャラの出し方の原則\n" + _bullets(card.behavior.principles))
    if card.behavior.avoid:
        sections.append("## 避ける振る舞い\n" + _bullets(card.behavior.avoid))
    if card.speech.forbidden_phrases:
        sections.append(
            "## 禁止表現（絶対に使わない）\n" + _bullets(card.speech.forbidden_phrases)
        )
    return "\n\n".join(sections)


def _render_intensity_guide(card: CharacterCard) -> str:
    """style_intensity の説明ブロック"""
    if not card.style_intensity.levels:
        return ""
    lines = ["# style_intensity（キャラクター濃度）の指針"]
    for key in sorted(card.style_intensity.levels.keys()):
        desc = card.style_intensity.levels[key].strip()
        lines.append(f"- style_intensity = {key}: {desc}")
    return "\n".join(lines)


def _render_examples(card: CharacterCard) -> str:
    """few-shot 例（無人格 → キャラの声）のレンダリング"""
    if not card.few_shot:
        return ""
    parts = ["# 文体の例（無人格な文 → このキャラクターの声）"]
    for i, ex in enumerate(card.few_shot, 1):
        block = [f"例{i}:", f"変換前: {ex.neutral.strip()}", f"変換後: {ex.styled.strip()}"]
        if ex.note:
            block.append(f"要点: {ex.note.strip()}")
        parts.append("\n".join(block))
    return "\n\n".join(parts)


def _render_solve_system(card: CharacterCard) -> str:
    """1段構成用: タスクをキャラクターの声で直接解くシステムプロンプト。

    タスク固有の指示はタスク YAML 側の system_prompt / prompts に書き、
    このブロックはキャラクター性の指示だけを担う。
    """
    parts = [
        f"あなたは「{card.name}」というキャラクターとして応答します。",
        "タスクの指示・出力形式には正確に従いつつ、文章はすべて"
        "このキャラクターの声で書いてください。",
        _render_profile(card),
    ]
    guide = _render_intensity_guide(card)
    if guide:
        parts.append(guide)
    examples = _render_examples(card)
    if examples:
        parts.append(examples)
    parts.append(
        "# 重要\n"
        "- キャラクター性は語尾だけでなく、判断の仕方・確認の仕方に出すこと。\n"
        "- タスクの正確さを最優先し、キャラクター表現がそれを壊さないこと。\n"
        "- 出力形式の指定（タグ・JSON など）にはキャラ表現を持ち込まないこと。"
    )
    return "\n\n".join(parts)


def _render_rewrite_system(card: CharacterCard) -> str:
    """2段構成用: 無人格な下書きをキャラクターの声に変換するシステムプロンプト。

    弱いモデルでも成立するよう、次の設計にしている:
    - 事実の変更を明確に禁止（数値・式・結論・固有名詞は固定）
    - 変換手順を機械的なチェックリストとして提示
    - few-shot 例で模倣させる
    - 迷った場合のフォールバック（元の文を残す）を明示
    - 出力を <styled> タグで囲ませ、抽出を安定させる
    """
    steps = [
        f"1. 一人称をすべて「{card.speech.first_person}」に置き換える。",
    ]
    if card.speech.second_person:
        steps.append(
            "2. 読み手への呼びかけが必要な場合は「"
            + "」「".join(card.speech.second_person)
            + "」を使う。"
        )
    n = len(steps) + 1
    if card.speech.endings:
        steps.append(
            f"{n}. 各文の語尾を、下の基本語尾のどれかに自然に置き換える。"
            "全文を同じ語尾にせず、混ぜて使う。"
        )
        n += 1
    steps.append(
        f"{n}. 下の「使ってよい言い回し」を、文脈に合う場所に1〜3個だけ自然に差し込む。"
    )
    n += 1
    steps.append(f"{n}. 禁止表現が1つも入っていないことを確認する。")
    n += 1
    steps.append(
        f"{n}. 数値・計算式・記号・結論・固有名詞が変換前と完全に一致していることを確認する。"
    )

    parts = [
        "あなたは文体変換の専門家です。"
        f"与えられた文章を、意味を一切変えずに「{card.name}」"
        f"{'（' + card.label + '）' if card.label else ''}の声に書き換えてください。",
        "# 絶対に守ること\n"
        "- 数値・計算式・数学記号・LaTeX・固有名詞・結論は一文字も変えない。\n"
        "- 情報を追加しない。削らない。文の順序も変えない。\n"
        "- 変えてよいのは、言い回し・語尾・一人称・接続表現だけ。\n"
        "- どう変換すべきか迷った文は、無理に変えず元のまま残す。",
        "# 変換手順（この順に機械的に行う）\n" + "\n".join(steps),
        _render_profile(card),
    ]
    examples = _render_examples(card)
    if examples:
        parts.append(examples)
    parts.append(
        "# 出力形式（厳守）\n"
        "変換後の文章だけを次の形式で出力する。前置きや説明は書かない。\n"
        "<styled>\n[変換後の文章]\n</styled>"
    )
    return "\n\n".join(parts)


def build_template_vars(
    card: CharacterCard, *, card_path: str = ""
) -> Dict[str, str]:
    """カードから `{char.*}` テンプレート変数の dict を生成する。

    返り値を globals の const に `char` として注入すると、
    タスク YAML から以下が参照できる:

    - {char.name} / {char.label} / {char.first_person} / {char.persona}
    - {char.card_path}       カードファイルの絶対パス（python ブロックでの再読込用）
    - {char.intensity}       既定の style_intensity
    - {char.profile}         キャラクター設定シート全体
    - {char.speech_rules}    話し方ルールのみ
    - {char.forbidden}       禁止表現リスト
    - {char.examples}        few-shot（無人格→キャラ声）
    - {char.intensity_guide} style_intensity の説明
    - {char.solve_system}    1段構成用システムプロンプト（キャラ声で直接解く）
    - {char.rewrite_system}  2段構成用システムプロンプト（文体変換専任）
    - {char.<extra キー>}    カードの extra で定義した任意変数
    """
    speech_rules_lines = [f"- 一人称は必ず「{card.speech.first_person}」。"]
    if card.speech.politeness:
        speech_rules_lines.append(f"- {card.speech.politeness}")
    if card.speech.endings:
        speech_rules_lines.append(
            "- 基本語尾: " + " / ".join(f"「{e}」" for e in card.speech.endings)
        )

    tvars: Dict[str, str] = {
        "name": card.name,
        "label": card.label,
        "card_path": card_path,
        "first_person": card.speech.first_person,
        "persona": card.persona.strip(),
        "intensity": str(card.style_intensity.default),
        "profile": _render_profile(card),
        "speech_rules": "\n".join(speech_rules_lines),
        "forbidden": _bullets(card.speech.forbidden_phrases),
        "examples": _render_examples(card),
        "intensity_guide": _render_intensity_guide(card),
        "solve_system": _render_solve_system(card),
        "rewrite_system": _render_rewrite_system(card),
    }
    # extra はビルトイン変数を上書きしない
    for k, v in card.extra.items():
        tvars.setdefault(k, v)
    return tvars


# ---------------------------------------------------------------------------
# 機械的な口調検証
# ---------------------------------------------------------------------------


def score_voice(
    text: str,
    card: CharacterCard,
    intensity: Optional[int] = None,
) -> Dict[str, Any]:
    """生成文のキャラクター性を LLM なしでスコアリングする。

    voice_groups の各軸について、マーカーが1つでも含まれれば1点。
    合計スコアが required_score[intensity] 以上なら passed。

    「語尾だけキャラ」検出:
    tone_groups に挙げた軸だけが命中し、実質軸（それ以外）が
    全滅している場合は tone_only=True として警告する。

    Returns:
        {
          "score": int,             # 命中した軸数
          "required": int,          # 必要軸数
          "passed": bool,
          "tone_only": bool,        # 語尾だけキャラか
          "group_hits": {軸: [命中マーカー]},
          "forbidden_hits": [...],  # 禁止表現の命中
          "neutral_count": int,     # です/ます等の出現数
          "warnings": [...],        # 人間可読の警告文
        }
    """
    text = text or ""
    v = card.validation
    if intensity is None:
        intensity = card.style_intensity.default

    group_hits: Dict[str, List[str]] = {
        group: [m for m in markers if m in text]
        for group, markers in v.voice_groups.items()
    }
    score = sum(1 for hits in group_hits.values() if hits)
    required = v.required_score.get(
        str(intensity), max(v.required_score.values() or [1])
    )

    substantive_groups = [g for g in v.voice_groups if g not in v.tone_groups]
    has_substantive = any(group_hits.get(g) for g in substantive_groups)
    has_tone = any(group_hits.get(g) for g in v.tone_groups)
    tone_only = bool(has_tone and substantive_groups and not has_substantive)

    forbidden_hits = [p for p in card.speech.forbidden_phrases if p in text]
    neutral_count = sum(text.count(p) for p in v.neutral_penalties)

    warnings: List[str] = []
    if score < required:
        missing = [g for g, hits in group_hits.items() if not hits]
        warnings.append(
            f"キャラクター性が不足しています (score: {score}, required: {required}, "
            f"未検出の軸: {', '.join(missing)})"
        )
    if tone_only:
        warnings.append(
            "語尾だけのキャラクター表現になっています。"
            "判断主体・条件確認などの実質的な要素を追加してください"
        )
    if forbidden_hits:
        warnings.append("禁止表現が含まれています: " + ", ".join(forbidden_hits))
    if neutral_count > v.neutral_penalty_max:
        warnings.append(
            f"無人格な文体（{'/'.join(v.neutral_penalties)}）に寄りすぎています "
            f"(count: {neutral_count})"
        )

    passed = score >= required and not tone_only and not forbidden_hits

    return {
        "score": score,
        "required": required,
        "passed": passed,
        "tone_only": tone_only,
        "group_hits": group_hits,
        "forbidden_hits": forbidden_hits,
        "neutral_count": neutral_count,
        "warnings": warnings,
    }


__all__ = [
    "SpeechConfig",
    "BehaviorConfig",
    "FewShotExample",
    "IntensityConfig",
    "ValidationConfig",
    "CharacterCard",
    "load_character",
    "build_template_vars",
    "score_voice",
]
