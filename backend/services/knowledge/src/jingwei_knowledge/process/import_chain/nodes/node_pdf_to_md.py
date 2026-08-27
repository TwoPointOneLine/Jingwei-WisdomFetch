from jingwei_common.logging import node_log
from jingwei_common.web.task_utils import add_done_task, add_running_task

from jingwei_knowledge.process.import_chain.services.pdf_parse_service import (
    parse_pdf_to_markdown,
)
from jingwei_knowledge.process.import_chain.state import ImportGraphState


@node_log("node_pdf_to_md")
def node_pdf_to_md(state: ImportGraphState) -> ImportGraphState:
    add_running_task(state["task_id"], "node_pdf_to_md")
    state = parse_pdf_to_markdown(state)
    add_done_task(state["task_id"], "node_pdf_to_md")
    return state
