"""合规护栏（精卫守正）。

对问答输出做**硬性**合规校验，作为 LLM prompt 软约束之外的兜底拦截，
覆盖 PRD 的 FR-COMP-01~04：禁用收益承诺、风险提示、不荐股、AI 生成标识。

设计原则：
- 不依赖模型是否"听话"，对最终输出文本做规则校验；
- 命中违规时返回结构化结果，由调用方决定替换/拦截；
- 提示词常量（AI 生成标识、标准拒答话术）集中在此，供问答链路复用。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ── 提示词常量（FR-COMP-04 AI 生成标识 / FR-QA-05 标准拒答）──────────
# AI 生成内容标识（每条回答末尾强制拼接）
AI_DISCLAIMER = (
    "【AI 生成内容】本回答由人工智能基于知识库资料自动生成，"
    "可能存在不准确或时效性偏差，不构成任何投资建议，仅供参考。"
)

# 检索不足时的标准拒答话术（FR-QA-05，替代"转为通用助手回答"）
NO_CONTEXT_REPLY = (
    "当前知识库中未检索到足够信息来回答您的问题。"
    "为避免提供不准确内容，我无法基于现有资料作答。"
    "您可以尝试换一种表述，或请管理员补充相关资料。"
)

# 命中合规违规时的统一回复（FR-COMP-01~03）
COMPLIANCE_BLOCK_REPLY = (
    "为确保合规，我无法就收益承诺、保本保收益或具体投资标的买卖给出回应。"
    "金融产品存在风险，投资需谨慎，请以官方披露文件与持牌顾问意见为准。"
)

# 当回答参考了外网（非内部资料）来源时，附带的「以官方渠道为准」提示（FR-QA-06）。
# 仅当 WEB_SEARCH_ENABLED=true 且重排结果中包含 external=True 来源时才追加。
EXTERNAL_SOURCE_NOTE = (
    "（注：以上回答部分参考了公开网络信息，仅供初步参考，不构成投资建议；"
    "具体产品要素与风险以官方披露文件及持牌机构口径为准。）"
)

# ── 规则库 ────────────────────────────────────────────────────────
# FR-COMP-01 收益承诺 / 保本话术（高敏感，必须拦截）
_BANNED_PATTERNS: list[re.Pattern] = [
    re.compile(r"保证\s*(赚|收益|回本|不亏|盈利)", re.IGNORECASE),
    re.compile(r"(稳赚|稳赢|包赚|必赚|一定赚|百分百赚)", re.IGNORECASE),
    re.compile(r"(保本|保收益|保底收益|无风险收益)", re.IGNORECASE),
    re.compile(r"(稳赚不赔|稳挣不赔|只涨不跌|零风险)", re.IGNORECASE),
    re.compile(r"(年化.*?%?.*?(确定|稳)|确定.*?收益)", re.IGNORECASE),
    re.compile(r"(闭眼买|闭眼入|躺赚|轻松赚)", re.IGNORECASE),
]

# FR-COMP-03 荐股 / 买卖建议（需谨慎处理，给出边界提示而非直接推荐）
_ADVICE_PATTERNS: list[re.Pattern] = [
    re.compile(r"(推荐(买|入|购|持有|建仓)|建议(买|入|购|持有|建仓)|可以(买|入|购|持有))", re.IGNORECASE),
    re.compile(r"(该(买|卖|入手|建仓|加仓|减仓)吗|能不能(买|卖|入)|值不值得(买|入|持有))", re.IGNORECASE),
    re.compile(r"(买入(信号|时机)|卖出(信号|时机)|抄底|追涨)", re.IGNORECASE),
]

# FR-COMP-02 风险提示关键词（回答中含收益/回报论述时，应附带风险提示）
_RISK_KEYWORDS: list[re.Pattern] = [
    re.compile(r"(收益|回报|年化|盈利|上涨|看涨|潜力|翻倍|获利)", re.IGNORECASE),
]


@dataclass
class ComplianceResult:
    """合规校验结果。"""

    passed: bool
    violations: list[str] = field(default_factory=list)
    # 是否涉及收益/荐股论述（用于决定是否强制拼接风险提示）
    needs_risk_tip: bool = False

    @property
    def blocked(self) -> bool:
        """命中必须拦截的违规（收益承诺/保本）。"""
        return not self.passed


def _match_any(patterns: list[re.Pattern], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def check_output_compliance(text: str) -> ComplianceResult:
    """对最终输出做合规校验。

    - 命中收益承诺/保本 → passed=False（必须拦截）
    - 命中荐股/买卖建议 → 标记 needs_risk_tip（仍放行，但需风险提示）
    - 涉及收益论述 → 标记 needs_risk_tip
    """
    if not text:
        return ComplianceResult(passed=True)

    violations: list[str] = []
    if _match_any(_BANNED_PATTERNS, text):
        violations.append("收益承诺/保本保收益话术")

    needs_risk_tip = bool(violations) or _match_any(_ADVICE_PATTERNS, text) or _match_any(_RISK_KEYWORDS, text)

    passed = len(violations) == 0
    return ComplianceResult(passed=passed, violations=violations, needs_risk_tip=needs_risk_tip)


def ensure_disclaimer(text: str) -> str:
    """确保回答末尾带有 AI 生成标识（FR-COMP-04）。"""
    if not text:
        return text
    if AI_DISCLAIMER in text:
        return text
    return f"{text.strip()}\n\n{AI_DISCLAIMER}"


def apply_compliance(text: str) -> str:
    """对输出做合规后处理：违规拦截 + 风险提示 + AI 标识拼接。

    返回处理后可下发的文本（FR-COMP-01~04 全覆盖）。
    """
    if not text:
        return text
    result = check_output_compliance(text)
    if result.blocked:
        # 拦截违规内容，返回合规统一回复（仍带 AI 标识）
        return ensure_disclaimer(COMPLIANCE_BLOCK_REPLY)
    out = text
    if result.needs_risk_tip and "风险" not in out:
        out = f"{out.strip()}\n\n风险提示：金融产品存在风险，历史业绩不代表未来表现，投资需谨慎。"
    return ensure_disclaimer(out)


__all__ = [
    "ComplianceResult",
    "check_output_compliance",
    "ensure_disclaimer",
    "apply_compliance",
    "AI_DISCLAIMER",
    "NO_CONTEXT_REPLY",
    "COMPLIANCE_BLOCK_REPLY",
]
