"""评测数据集模型与加载（标准问答对回归测试集）。

对应需求文档 §十「质量验证建议」：建立基于知识库"标准问答对"的回归测试集，
定期评测真实性、可追溯性与合规命中率。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ExpectationType = Literal["answerable", "no_context", "compliance_block"]
ComplianceExpectation = Literal["pass", "block"]


@dataclass
class EvalCase:
    """单条标准问答对。

    expectation 决定该用例的预期行为：
      - answerable：知识库应能回答，期望有引用命中 + 关键事实覆盖 + 输出合规；
      - no_context：知识库无资料，期望正确拒答（不编造）；
      - compliance_block：违规提问，期望被合规护栏拦截。
    """

    id: str
    query: str
    expectation: ExpectationType = "answerable"
    reference: str = ""  # 标准答案/参考资料，用于真实性弱校验
    key_facts: list[str] = field(default_factory=list)  # 期望回答覆盖的关键事实
    expected_sources: list[str] = field(default_factory=list)  # 期望命中的来源文档名
    expected_compliance: ComplianceExpectation = "pass"  # pass=输出合规 / block=应被拦截
    note: str = ""


@dataclass
class EvalDataset:
    name: str
    cases: list[EvalCase] = field(default_factory=list)


def load_dataset(path: str | Path) -> EvalDataset:
    """从 JSON 文件加载标准问答对评测集。"""
    path = Path(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    cases: list[EvalCase] = []
    for i, c in enumerate(raw.get("cases", [])):
        cases.append(
            EvalCase(
                id=c.get("id") or f"case-{i + 1:03d}",
                query=c["query"],
                expectation=c.get("expectation", "answerable"),
                reference=c.get("reference", ""),
                key_facts=c.get("key_facts", []),
                expected_sources=c.get("expected_sources", []),
                expected_compliance=c.get("expected_compliance", "pass"),
                note=c.get("note", ""),
            )
        )
    return EvalDataset(name=raw.get("name", path.stem), cases=cases)
