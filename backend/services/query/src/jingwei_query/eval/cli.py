"""评测命令行入口。

用法：
  python -m jingwei_query.eval.cli --dataset eval_dataset.sample.json
  python -m jingwei_query.eval.cli --dataset ds.json --json report.json --html report.html

说明：
  - 需在有完整部署（Milvus 已导入资料、embedding/LLM 可用）的环境下运行真实评测；
  - 联网检索是否启用取决于部署配置，纯内部知识库质量评测请在关闭联网时运行；
  - 无环境时可用注入 mock 主图的方式跑 tests/test_eval.py 验证指标逻辑。
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import UTC, datetime

from .dataset import load_dataset
from .runner import run_dataset

_EXPECT_LABEL = {
    "answerable": "可回答",
    "no_context": "无资料拒答",
    "compliance_block": "合规拦截",
}
_AGG_LABELS = {
    "pass_rate": "通过率",
    "traceability_rate": "可追溯率",
    "groundedness_ok_rate": "真实性合格率",
    "avg_fact_coverage": "平均事实覆盖率",
    "compliance_ok_rate": "合规合格率",
    "avg_latency_ms": "平均时延(ms)",
}


def _fmt_val(k: str, v) -> str:
    if not isinstance(v, float):
        return str(v)
    if "latency" in k:
        return f"{v:.1f}"
    return f"{v * 100:.1f}%"


def _print_report(report):
    agg = report.aggregate
    print("=" * 64)
    print(
        f"评测集：{report.dataset}    用例数：{report.total}    "
        f"通过：{report.passed}（{report.pass_rate() * 100:.1f}%）"
    )
    print("-" * 64)
    for r in report.results:
        status = "PASS" if r.passed else "FAIL"
        print(f"[{status}] {r.case_id}  ({r.expectation})  {r.query[:32]}")
        if r.error:
            print(f"        ⚠ 运行异常：{r.error}")
            continue
        for k, v in r.metrics.items():
            mark = "OK" if v.get("ok") else "X"
            extra = ""
            if k == "groundedness" and v.get("coverage") is not None:
                extra = f"  覆盖率={v['coverage']:.2f}"
            print(f"        · {k}: {mark}  {v.get('detail', '')}{extra}")
    print("-" * 64)
    print("聚合指标：")
    for k, v in agg.items():
        print(f"  {_AGG_LABELS.get(k, k)}: {_fmt_val(k, v)}")
    print("=" * 64)


def generate_html(report) -> str:
    """生成单文件 HTML 报告（内联样式，可直接浏览器打开）。"""
    agg = report.aggregate
    pass_rate = report.pass_rate() * 100
    cards = "".join(
        f'<div class="card"><div class="cval">{_fmt_val(k, v)}</div>'
        f'<div class="clabel">{_AGG_LABELS.get(k, k)}</div></div>'
        for k, v in agg.items()
    )
    rows = []
    for r in report.results:
        if r.error:
            detail = f'<span class="bad">运行异常：{html.escape(r.error)}</span>'
        else:
            parts = []
            for k, v in r.metrics.items():
                mark = "ok" if v.get("ok") else "bad"
                extra = ""
                if k == "groundedness" and v.get("coverage") is not None:
                    extra = f" 覆盖率={v['coverage']:.2f}"
                parts.append(
                    f'<div class="m {mark}"><b>{k}</b>: '
                    f'{"OK" if v.get("ok") else "X"} — '
                    f'{html.escape(v.get("detail", ""))}{extra}</div>'
                )
            detail = "".join(parts)
        badge = "pass" if r.passed else "fail"
        rows.append(
            f'<tr class="{badge}">'
            f'<td><span class="badge {badge}">{"PASS" if r.passed else "FAIL"}</span></td>'
            f"<td>{html.escape(r.case_id)}</td>"
            f"<td>{_EXPECT_LABEL.get(r.expectation, r.expectation)}</td>"
            f"<td>{html.escape(r.query)}</td>"
            f"<td>{detail}</td>"
            f'<td class="ans">{html.escape(r.answer[:300])}</td>'
            f"</tr>"
        )
    table = "\n".join(rows)
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>精卫 RAG 问答质量评测报告</title>
<style>
  body{{font-family:-apple-system,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif;margin:0;background:#f5f7fa;color:#1f2937}}
  .wrap{{max-width:1180px;margin:0 auto;padding:24px}}
  h1{{font-size:22px;margin:0 0 4px}}
  .sub{{color:#6b7280;font-size:13px;margin-bottom:18px}}
  .summary{{display:flex;gap:16px;align-items:center;margin-bottom:18px}}
  .big{{font-size:34px;font-weight:700}}
  .bar{{height:10px;border-radius:6px;background:#e5e7eb;flex:1;overflow:hidden}}
  .bar>div{{height:100%;background:#2563eb}}
  .cards{{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px}}
  .card{{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px 16px;min-width:130px}}
  .cval{{font-size:20px;font-weight:700}}
  .clabel{{font-size:12px;color:#6b7280;margin-top:2px}}
  table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;border:1px solid #e5e7eb}}
  th,td{{text-align:left;padding:10px 12px;border-bottom:1px solid #f0f0f0;vertical-align:top;font-size:13px}}
  th{{background:#f9fafb;color:#374151}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;color:#fff}}
  .badge.pass{{background:#16a34a}}.badge.fail{{background:#dc2626}}
  tr.fail{{background:#fef2f2}}
  .m{{margin:2px 0}}.m.ok{{color:#16a34a}}.m.bad{{color:#dc2626}}
  .ans{{color:#4b5563;max-width:320px;white-space:pre-wrap;word-break:break-word}}
</style></head>
<body><div class="wrap">
  <h1>精卫 RAG 问答质量评测报告</h1>
  <div class="sub">数据集：{html.escape(report.dataset)}　·　生成时间：{generated}</div>
  <div class="summary">
    <div class="big">{pass_rate:.1f}%</div>
    <div class="bar"><div style="width:{pass_rate:.1f}%"></div></div>
    <div>通过 {report.passed} / {report.total}</div>
  </div>
  <div class="cards">{cards}</div>
  <table>
    <thead><tr><th>结果</th><th>用例ID</th><th>类型</th><th>问题</th><th>维度指标</th><th>回答片段</th></tr></thead>
    <tbody>{table}</tbody>
  </table>
</div></body></html>"""


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="精卫 RAG 问答质量评测")
    p.add_argument("--dataset", required=True, help="标准问答对 JSON 路径")
    p.add_argument("--json", default="", help="将报告写入该 JSON 文件")
    p.add_argument("--html", default="", help="将报告写入该 HTML 文件（可视化展示）")
    p.add_argument("--model", default="", help="指定对话模型")
    p.add_argument("--llm-judge", action="store_true", help="真实性(groundedness)改用 LLM-as-judge")
    args = p.parse_args(argv)

    ds = load_dataset(args.dataset)
    report = run_dataset(ds, model=args.model or None, use_llm_judge=args.llm_judge)
    _print_report(report)

    if args.json:
        payload = {
            "dataset": report.dataset,
            "total": report.total,
            "passed": report.passed,
            "aggregate": report.aggregate,
            "results": [
                {
                    "case_id": r.case_id,
                    "expectation": r.expectation,
                    "passed": r.passed,
                    "latency_ms": round(r.latency_ms, 1),
                    "error": r.error,
                    "metrics": r.metrics,
                    "answer": r.answer[:500],
                }
                for r in report.results
            ],
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(f"\nJSON 报告已写入 {args.json}")

    if args.html:
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(generate_html(report))
        print(f"HTML 报告已写入 {args.html}")

    return 0 if report.passed == report.total else 1


if __name__ == "__main__":
    sys.exit(main())
