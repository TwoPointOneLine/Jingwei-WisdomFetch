"""评测引擎：驱动完整问答链路并对每条标准问答对计算质量指标。

设计：
  - 复用生产问答主图 `kb_query_app`（检索→重排→生成→合规），端到端评测检索与生成质量；
  - graph 调用可注入（默认 kb_query_app.invoke），便于无环境时单测；
  - 指标计算与链路解耦，纯函数见 metrics.py；
  - `citations` 未声明进 QueryGraphState，故取 final_state['citations'] 失败时用
    rerank_documents 重建，保证可追溯性指标可靠。
"""
from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from jingwei_common.compliance import (
    LOW_SCORE_REPLY,
    NO_CONTEXT_REPLY,
)
from jingwei_common.config.rag_config import rag_config

from . import metrics
from .dataset import EvalCase, EvalDataset


def build_init_state(query: str, model: str | None = None) -> dict:
    """构造问答主图所需的初始 state（与 query_server.run_query_task 同源，去掉流式/SSE）。

    以 admin 身份全量检索：评测关注知识库内容质量（真实性/可追溯性/合规），
    而非权限隔离，故 user_role=admin 使检索不过滤 item_name。
    """
    return {
        "task_id": uuid.uuid4().hex,
        "session_id": "",  # 置空避免评测写入历史库
        "username": "eval",
        "user_role": "admin",
        "user_team_id": "",
        "query": query,
        "user_query": query,
        "item_name": "",
        "model": model or "",
        "rephrased_query": "",
        "history": [],
        "history_text": "",
        "history_turns": rag_config.history_turns,
        "keywords": [],
        "vector_documents": [],
        "hyde_documents": [],
        "web_documents": [],
        "rrf_documents": [],
        "rerank_documents": [],
        "llm_output": "",
        "citations": [],
        "delta_queue": None,
        "need_stream_output": False,
    }


@dataclass
class CaseResult:
    case_id: str
    query: str
    expectation: str
    answer: str
    citations: list = field(default_factory=list)
    passed: bool = False
    metrics: dict = field(default_factory=dict)
    latency_ms: float = 0.0
    error: str = ""


@dataclass
class EvalReport:
    dataset: str = ""
    total: int = 0
    passed: int = 0
    results: list = field(default_factory=list)
    aggregate: dict = field(default_factory=dict)

    def pass_rate(self) -> float:
        return self.passed / self.total if self.total else 0.0


def _rebuild_citations(state: dict) -> list:
    """citations 未声明进 state schema 时，由 rerank_documents 重建（与 answer_service 同口径）。"""
    reranked = state.get("rerank_documents") or []
    if not reranked:
        return state.get("citations") or []
    try:
        from jingwei_query.rag.query.answer_service import _build_citations

        return _build_citations(reranked)
    except Exception:
        return state.get("citations") or []


def _build_judge_context(state: dict) -> str:
    """拼接实际喂给 LLM 的检索上下文，作为 LLM-as-judge 的参考来源。

    优先用重排后的 rerank_documents；为空时回退到 RRF / HyDE / 向量召回结果，
    确保 judge 看到的证据与生成答案时一致（避免仅拿单条 case.reference 导致
    答案引用了其它召回片段却被误判为编造）。
    """
    docs = (
        state.get("rerank_documents")
        or state.get("rrf_documents")
        or state.get("hyde_documents")
        or state.get("vector_documents")
        or []
    )
    if not docs:
        return ""
    parts = []
    for d in docs[:8]:
        content = (d.get("content") or d.get("snippet") or "").strip()
        if content:
            parts.append(content[:1200])
    return "\n\n".join(parts)


def run_case(
    case: EvalCase,
    graph_callable: Callable | None = None,
    model: str | None = None,
    use_llm_judge: bool = False,
) -> CaseResult:
    """对单条用例跑完整问答链路并计算质量指标。

    use_llm_judge=True 时，真实性（groundedness）改用 LLM-as-judge，对改写/概括型
    回答更宽容；默认 False 走纯启发式，便于无 LLM 的 CI 环境。
    """
    # 延迟导入主图，避免无完整部署环境时 import 失败
    if graph_callable is None:
        from jingwei_query.process.query_chain.main_graph import kb_query_app

        graph = kb_query_app.invoke
    else:
        graph = graph_callable

    init_state = build_init_state(case.query, model)
    start = time.perf_counter()
    try:
        final_state = graph(init_state)
        latency = (time.perf_counter() - start) * 1000
        if not isinstance(final_state, dict):
            raise TypeError(f"主图返回非 dict: {type(final_state)}")
        answer = final_state.get("llm_output", "")
        citations = final_state.get("citations") or _rebuild_citations(final_state)
    except Exception as e:  # noqa: BLE001 — 记录为用例运行异常
        latency = (time.perf_counter() - start) * 1000
        return CaseResult(
            case.id, case.query, case.expectation, "", passed=False,
            latency_ms=latency, error=f"{type(e).__name__}: {e}",
        )

    m: dict = {}
    passed = True
    if case.expectation == "no_context":
        ok = (NO_CONTEXT_REPLY in answer) or (LOW_SCORE_REPLY in answer)
        m["no_context"] = {
            "ok": ok,
            "detail": "正确拒答（无资料不编造）" if ok else "期望拒答但未触发",
        }
        passed = ok
    elif case.expectation == "compliance_block":
        cm = metrics.compliance(answer, "block")
        m["compliance"] = cm
        passed = cm["ok"]
    else:  # answerable
        tr = metrics.traceability(citations, case.expected_sources)
        if use_llm_judge:
            # judge 以实际喂给 LLM 的检索上下文为参考，而非单条 case.reference
            judge_ctx = _build_judge_context(final_state) or case.reference
            gr = metrics.groundedness_llm(answer, judge_ctx, model)
        else:
            gr = metrics.groundedness(answer, case.key_facts or None, case.reference)
        cm = metrics.compliance(answer, case.expected_compliance)
        m["traceability"] = tr
        m["groundedness"] = gr
        m["compliance"] = cm
        passed = tr["hit"] and gr["ok"] and cm["ok"]

    return CaseResult(
        case.id, case.query, case.expectation, answer,
        citations=citations, passed=passed, metrics=m, latency_ms=latency,
    )


def run_dataset(
    dataset: EvalDataset,
    graph_callable: Callable | None = None,
    model: str | None = None,
    use_llm_judge: bool = False,
) -> EvalReport:
    """遍历数据集，运行全部用例并聚合指标。"""
    report = EvalReport(dataset=dataset.name, total=len(dataset.cases))
    for case in dataset.cases:
        res = run_case(case, graph_callable=graph_callable, model=model, use_llm_judge=use_llm_judge)
        report.results.append(res)
        if res.passed:
            report.passed += 1
    report.aggregate = _aggregate(report)
    return report


def _aggregate(report: EvalReport) -> dict:
    n = report.total
    if not n:
        return {}

    def _rate(key: str):
        vals = [r.metrics.get(key, {}).get("ok") for r in report.results if key in r.metrics]
        return sum(1 for v in vals if v) / len(vals) if vals else None

    cov = [
        r.metrics.get("groundedness", {}).get("coverage")
        for r in report.results
        if "groundedness" in r.metrics
    ]
    avg_cov = sum(cov) / len(cov) if cov else None
    return {
        "pass_rate": report.pass_rate(),
        "traceability_rate": _rate("traceability"),
        "groundedness_ok_rate": _rate("groundedness"),
        "avg_fact_coverage": avg_cov,
        "compliance_ok_rate": _rate("compliance"),
        "avg_latency_ms": sum(r.latency_ms for r in report.results) / n,
    }
