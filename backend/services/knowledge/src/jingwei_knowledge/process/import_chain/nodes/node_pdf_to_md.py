from jingwei_common.logging import node_log
from jingwei_common.web.task_utils import add_done_task, add_running_task

from jingwei_knowledge.process.import_chain.services.pdf_parse_service import (
    parse_pdf_to_markdown,
)
from jingwei_knowledge.process.import_chain.state import ImportGraphState


@node_log("node_pdf_to_md")
def node_pdf_to_md(state: ImportGraphState) -> ImportGraphState:
    task_id = state["task_id"]
    add_running_task(task_id, "node_pdf_to_md")
    state = parse_pdf_to_markdown(state)
    state["task_id"] = task_id  # service 返回值不含 task_id，回填保证状态追踪可用
    add_done_task(task_id, "node_pdf_to_md")
    return state
