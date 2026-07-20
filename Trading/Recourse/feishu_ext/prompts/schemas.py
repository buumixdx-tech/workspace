"""Pydantic models — single source of truth for LLMInput / LLMOutput schema.

Phase 0.6 schema change: from keep/drop/rewrite to 10-class classification +
multi-field extraction. Each input message gets exactly one TaskResult with:
  - task_id (matches input idx, 1-based)
  - info_type_code (1-10 integer, see INFO_TYPE_CODES mapping)
  - category (industry / sub-sector)
  - involved_stocks (list, typo-corrected)
  - core_tech_terms (list)
  - summary (≤30 Chinese chars)

INFO_TYPE_CODES 顺序与定义见 prompts/historical.md (1=个股点评 ... 10=其他).
单源真相: 中文 label 只用于人读 / web_ui / POST 文档 (build_post_text);
LLM 输出、db 存储、SKIP 过滤一律用 code.
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------- #
# input: 50 (or fewer) items sent to the LLM                              #
# ---------------------------------------------------------------------- #


class InputItem(BaseModel):
    """One row from messages.db, full text (no truncation by default)."""

    idx: int = Field(ge=1, description="1-based position; matches output task_id")
    ts: int = Field(description="unix ms; stable identifier for cross-ref")
    text: str = Field(description="full text content; no truncation")
    orig_len: int = Field(ge=0, description="character count of the original text")


class LLMInput(BaseModel):
    """The full batch handed to the LLM as the user message body."""

    count: int = Field(ge=1, description="must equal len(items)")
    items: list[InputItem]


# ---------------------------------------------------------------------- #
# 10 类信息分类,顺序与定义见 prompts/historical.md                         #
# 中文 label 顺序与 INFO_TYPE_CODES 严格对应. 顺序不能改.                  #
# ---------------------------------------------------------------------- #

INFO_TYPE_LABELS: tuple[str, ...] = (
    "个股点评",            # 1
    "行业板块点评",         # 2
    "产业点评",            # 3
    "盘前消息汇总",         # 4
    "盘后总结",            # 5
    "周报或其他周期性总结",  # 6
    "盘中提示",            # 7
    "时政新闻",            # 8
    "段子",               # 9
    "其他",               # 10
)

# 中文 label -> code (反向查代码, 用于反查 / backfill / 防御性 mapping)
INFO_TYPE_CODES: dict[str, int] = {
    label: i + 1 for i, label in enumerate(INFO_TYPE_LABELS)
}

# code -> 中文 label (用于 POST 文档 / web_ui / build_post_text)
CODE_TO_LABELS: dict[int, str] = {
    i + 1: label for i, label in enumerate(INFO_TYPE_LABELS)
}

# SKIP 类型 code 集合 (盘前/盘后/盘中提示/时政/段子/其他)
SKIP_TYPE_CODES: frozenset[int] = frozenset({4, 5, 7, 8, 9, 10})


# ---------------------------------------------------------------------- #
# output: classification + extraction per input item                      #
# ---------------------------------------------------------------------- #

# LLM 输出的 info_type 改为整数 code (1-10). Pydantic 用 Literal 限制范围.
InfoType = Literal[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]


class TaskResult(BaseModel):
    """LLM's classification + extraction for one input item."""

    task_id: int = Field(ge=1, description="must equal input idx")
    info_type: InfoType  # 1-10 整数 code (详见 INFO_TYPE_CODES 映射)
    category: str = Field(
        default="",
        description="1-2 core industries / sub-sectors, e.g. '先进封装/CoWoS'; '' if no clear industry",
    )
    involved_stocks: list[str] = Field(
        default_factory=list,
        description="standardized Chinese stock short names, typo/homophone-corrected; [] if none",
    )
    core_tech_terms: list[str] = Field(
        default_factory=list,
        description="high-density concepts / materials / processes / drivers; [] if none",
    )
    summary: str = Field(
        default="",
        description=(
            "Target ≤30 Chinese characters, but allow up to ~50 if needed to keep "
            "the sentence complete — never let the validator truncate a finished "
            "sentence. Concise investment-view summary."
        ),
    )

    @property
    def info_type_code(self) -> int:
        """Convenience alias — TaskResult.info_type IS the code."""
        return int(self.info_type)

    @property
    def info_type_label(self) -> str:
        """中文 label for human-readable output (build_post_text / web_ui)."""
        return CODE_TO_LABELS[int(self.info_type)]

    @field_validator("info_type", mode="before")
    @classmethod
    def _coerce_info_type(cls, v):
        """防御: 中文 label -> code 反查 (老 caller / 老 LLM 输出 fallback).
        查不到 fallback 10 (其他). 数字原样接受.
        """
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            stripped = v.strip()
            if stripped in INFO_TYPE_CODES:
                return INFO_TYPE_CODES[stripped]
            print(f"[schemas.TaskResult] info_type='{stripped}' 不在映射表, fallback 10 (其他)")
            return 10
        return v

    @field_validator("summary")
    @classmethod
    def _check_summary(cls, v: str) -> str:
        """2026-06-30 修订: 去掉防御性 v[:30] 截断.

        原设计: LLM 偶尔超过 30 字硬约束, 截到 30 字省得整批失败.
        副作用: 把"晶升股份作为长晶炉龙头…坚定看"这种 30 字断头残句直接进 db,
        下游做日报时信息量严重不足, 关键目标价/驱动逻辑被砍光.
        新规则: 保持原样, 仅在超过软上限 30 时打印一行 warn 提醒 caller.
        完整句优先于硬截断 -- 真超 30 字 caller 也不会因为这一行废掉整批.
        """
        if len(v) > 30:
            print(
                f"[schemas.TaskResult] summary len={len(v)} > 30 软上限, "
                f"保留完整句. 内容前 60 字: [{v[:60]}…]"
            )
        return v


class LLMOutput(BaseModel):
    """The full LLM response, validated by Pydantic."""

    results: list[TaskResult]


# ---------------------------------------------------------------------- #
# truncation helper (used by pipeline / demo before constructing LLMInput) #
# ---------------------------------------------------------------------- #


def truncate_text(
    text: str,
    *,
    max_chars: int = 800,
    keep_head: int = 500,
    keep_tail: int = 100,
) -> tuple[str, bool]:
    """If text > max_chars, return (head + marker + tail, True) else (text, False).

    Marker format: '...[+N 字符已省略]...'
    The returned bool is `was_truncated`, recorded as orig_len by the caller.
    """
    if len(text) <= max_chars:
        return text, False
    omitted = len(text) - keep_head - keep_tail
    return f"{text[:keep_head]}\n...[+{omitted} 字符已省略]...\n{text[-keep_tail:]}", True
