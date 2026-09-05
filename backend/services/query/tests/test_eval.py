"""评估模块单测：用注入的 mock 主图验证指标与聚合，不依赖真实检索/LLM。"""
from jingwei_common.compliance import (
    COMPLIANCE_BLOCK_REPLY,
    LOW_SCORE_REPLY,
    NO_CONTEXT_REPLY,
)

from jingwei_query.eval.dataset import EvalCase, EvalDataset, load_dataset
from jingwei_query.eval.metrics import compliance, groundedness, traceability
from jingwei_query.eval.runner import run_case, run_dataset


def _mock_graph(payload: dict):
    def _g(state):
        return payload

    return _g


def test_traceability_hit():
    cit = [{"source_file": "基金产品说明书.pdf", "title": "稳健一号"}]
    assert traceability(cit, ["基金产品说明书.pdf"])["hit"] is True
    assert traceability(cit, ["不存在.pdf"])["hit"] is False
    assert traceability([], [])["hit"] is False  # 无来源且无引用


def test_groundedness_coverage():
    g = groundedness("最低申购金额为1000元。", key_facts=["1000元", "申购金额"])
    assert g["ok"] is True and g["coverage"] == 1.0
    g2 = groundedness("与金额无关。", key_facts=["1000元", "申购金额"])
    assert g2["ok"] is False


def test_compliance_block_and_pass():
    assert compliance(COMPLIANCE_BLOCK_REPLY, "block")["ok"] is True
    assert compliance("该基金最小申购1000元。", "pass")["ok"] is True


def test_run_case_answerable():
    payload = {
        "llm_output": "稳健一号最低申购金额为1000元。",
        "rerank_documents": [
            {"doc_meta": {"source_file": "基金产品说明书.pdf"}, "content": "x", "source": "milvus"}
        ],
        "citations": [{"source_file": "基金产品说明书.pdf", "title": "稳健一号", "source": "milvus"}],
    }
    case = EvalCase(
        id="c1", query="q", expectation="answerable",
        key_facts=["1000元"], expected_sources=["基金产品说明书.pdf"],
    )
    res = run_case(case, graph_callable=_mock_graph(payload))
    assert res.passed is True
    assert res.metrics["traceability"]["hit"] is True


def test_run_case_compliance_block():
    payload = {"llm_output": COMPLIANCE_BLOCK_REPLY, "rerank_documents": [], "citations": []}
    case = EvalCase(id="c2", query="q", expectation="compliance_block", expected_compliance="block")
    res = run_case(case, graph_callable=_mock_graph(payload))
    assert res.passed is True


def test_run_case_no_context():
    payload = {"llm_output": NO_CONTEXT_REPLY, "rerank_documents": [], "citations": []}
    case = EvalCase(id="c3", query="q", expectation="no_context")
    res = run_case(case, graph_callable=_mock_graph(payload))
    assert res.passed is True


def test_run_dataset_aggregate():
    ds = EvalDataset(
        name="t",
        cases=[
            EvalCase(
                id="a", query="q", expectation="answerable",
                key_facts=["1000元"], expected_sources=["x.pdf"],
            ),
        ],
    )
    payload = {
        "llm_output": "最低申购1000元。",
        "rerank_documents": [],
        "citations": [{"source_file": "x.pdf"}],
    }
    report = run_dataset(ds, graph_callable=_mock_graph(payload))
    assert report.total == 1 and report.passed == 1
    assert report.aggregate["pass_rate"] == 1.0


def test_load_dataset(tmp_path):
    p = tmp_path / "ds.json"
    p.write_text('{"name":"d","cases":[{"id":"1","query":"q"}]}', encoding="utf-8")
    ds = load_dataset(p)
    assert ds.name == "d"
    assert len(ds.cases) == 1
    assert ds.cases[0].expectation == "answerable"
