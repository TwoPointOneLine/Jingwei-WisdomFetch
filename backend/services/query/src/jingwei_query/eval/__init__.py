"""RAG 问答质量评估模块（标准问答对回归评测）。

对应需求文档 §十「质量验证建议」：建立基于知识库"标准问答对"的回归测试集，
定期评测真实性、可追溯性与合规命中率。

入口：
  - 命令行：python -m jingwei_query.eval.cli --dataset eval_dataset.sample.json
  - 编程调用：from jingwei_query.eval.runner import run_dataset
"""
from .dataset import EvalCase, EvalDataset, load_dataset
from .metrics import compliance, groundedness, groundedness_llm, traceability
from .runner import CaseResult, EvalReport, run_case, run_dataset

__all__ = [
    "EvalCase",
    "EvalDataset",
    "load_dataset",
    "compliance",
    "groundedness",
    "groundedness_llm",
    "traceability",
    "CaseResult",
    "EvalReport",
    "run_case",
    "run_dataset",
]
