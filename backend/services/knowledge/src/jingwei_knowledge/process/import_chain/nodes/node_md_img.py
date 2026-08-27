from jingwei_common.logging import node_log
from jingwei_common.web.task_utils import add_done_task, add_running_task

from jingwei_knowledge.process.import_chain.services.markdown_image_service import (
    enrich_markdown_images,
)
from jingwei_knowledge.process.import_chain.state import ImportGraphState


@node_log("node_md_img")
def node_md_img(state: ImportGraphState) -> ImportGraphState:
    add_running_task(state["task_id"], "node_md_img")
    state = enrich_markdown_images(state)
    add_done_task(state["task_id"], "node_md_img")
    return state
