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

from jingwei_common.logging import logger

# ── 提示词常量（FR-COMP-04 AI 生成标识 / FR-QA-05 标准拒答）──────────
# AI 生成内容标识（每条回答末尾强制拼接）
AI_DISCLAIMER = (
    "【AI 生成内容】本回答由人工智能基于知识库资料自动生成，"
    "可能存在不准确或时效性偏差，不构成任何投资建议，仅供参考。"
)

# 检索不足时的标准拒答话术（FR-QA-05，替代"转为通用助手回答"）
# G-06：强化合规边界——明确"不提供具体产品推荐/收益承诺"，并提示以官方渠道为准。
NO_CONTEXT_REPLY = (
    "当前知识库中未检索到足够信息来回答您的问题。"
    "为避免提供不准确内容，我无法基于现有资料作答。"
    "请注意：本助手不提供具体产品推荐或收益承诺，相关产品要素、风险与办理规则"
    "请以官方披露文件及持牌机构口径为准。"
    "您可以尝试换一种表述，或请管理员补充相关资料。"
)

# G-05：检索到候选但重排分数全部偏低（低于阈值），视为不相关。
# 与 NO_CONTEXT_REPLY 区分：前者是"没资料"，此处是"资料相关度不足"。
LOW_SCORE_REPLY = (
    "已检索到相关资料，但匹配度较低，不足以给出可靠回答。"
    "为避免误导，我无法基于当前资料作答。"
    "请注意：本助手不提供具体产品推荐或收益承诺，相关产品要素与风险"
    "请以官方披露文件及持牌机构口径为准。"
    "您可以尝试调整关键词、补充更多背景，或请管理员完善相关资料。"
)

# G-06：通用合规风险提示（FR-COMP-02），在非拒答场景下也可作为兜底风险提示语。
# 与 apply_compliance 内联的风险提示互为补充，集中常量便于统一口径。
RISK_DISCLAIMER = (
    "风险提示：金融产品存在风险，历史业绩不代表未来表现，投资需谨慎；"
    "具体产品要素与风险以官方披露文件及持牌机构口径为准。"
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

# 知识库无答案时调用外部通用大模型的来源标注（兜底分支）。
# 与基于知识库的回答区分，明确告知用户该回答未经内部资料校验。
EXTERNAL_FALLBACK_NOTE = (
    "（注：以上回答由通用大模型直接生成，未基于本知识库已导入资料，"
    "内容未经内部资料校验，仅供参考，不构成投资建议；"
    "具体产品要素与风险请以官方披露文件及持牌机构口径为准。）"
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

# FR-COMP-01 豁免：否定/禁止语境标记。
# 当违规词仅出现在「明确否定句中」（如"基金不得承诺收益""本办法禁止保本保收益"），
# 视为客观陈述监管规定，不作为正向收益承诺拦截，避免误伤政策/法规类问答。
# 注意：仅收录真正的否定词，不收录"根据/按照/《/管理办法"等引用标记——
# 引用监管文件后紧跟违规承诺仍属真违规，必须拦截。
_NEGATION_MARKERS: list[re.Pattern] = [
    re.compile(r"(不得|禁止|不可|不允许|不应|不会|无法|没有|不提供|不保证|不予|不支持)", re.IGNORECASE),
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


def _split_sentences(text: str) -> list[str]:
    """按中英文句末标点与换行切句，用于语境级合规判断。"""
    return re.split(r"[。！？!?\n；;]", text)


def _in_negation_context(sentence: str) -> bool:
    """句子是否处于明确的否定/禁止语境（如'不得''禁止''不保证'）。

    命中此类语境时，即便句子中出现'保本''收益'等词，也视为客观陈述监管规定，
    而非正向收益承诺，从而豁免整段拦截（合规底线不放松，仅放过客观引用）。
    """
    return _match_any(_NEGATION_MARKERS, sentence)


def check_output_compliance(text: str) -> ComplianceResult:
    """对最终输出做合规校验。

    - 命中收益承诺/保本 → passed=False（必须拦截）
    - 但若违规词仅出现在「明确否定/禁止语境」（如'基金不得承诺收益'），
      视为客观陈述监管规定，豁免整段拦截，仅保留风险提示（避免误伤政策类问答）
    - 命中荐股/买卖建议 → 标记 needs_risk_tip（仍放行，但需风险提示）
    - 涉及收益论述 → 标记 needs_risk_tip
    """
    if not text:
        return ComplianceResult(passed=True)

    violations: list[str] = []
    # 逐句判断：仅当某句含违规词且**无否定语境**时，才判定为违规承诺。
    for sent in _split_sentences(text):
        if not sent.strip():
            continue
        if _match_any(_BANNED_PATTERNS, sent) and not _in_negation_context(sent):
            violations.append("收益承诺/保本保收益话术")
            break

    needs_risk_tip = bool(violations) or _match_any(_ADVICE_PATTERNS, text) or _match_any(_RISK_KEYWORDS, text)

    passed = len(violations) == 0
    return ComplianceResult(passed=passed, violations=violations, needs_risk_tip=needs_risk_tip)


def ensure_disclaimer(text: str) -> str:
    """合规后处理占位：按需求不再为回答追加 AI 免责声明（FR-COMP-04 已停用）。

    保留函数接口以保证调用方兼容；当前直接原样返回文本。
    """
    return text


def apply_compliance(text: str) -> str:
    """对输出做合规后处理：违规拦截 + 风险提示（不再追加 AI 免责声明）。

    返回处理后可下发的文本（FR-COMP-01~04，FR-COMP-04 的 AI 标识已停用）。
    """
    if not text:
        return text
    result = check_output_compliance(text)
    if result.blocked:
        # 拦截违规内容，返回合规统一回复
        logger.debug(f"合规拦截命中：{result.violations}（已替换为标准合规回复）")
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
    "LOW_SCORE_REPLY",
    "RISK_DISCLAIMER",
    "COMPLIANCE_BLOCK_REPLY",
    "EXTERNAL_FALLBACK_NOTE",
]
