"""
导入链主图（LangGraph）。

节点顺序：
node_entry -> (PDF ? node_pdf_to_md : node_md_img) -> node_md_img
-> node_document_split -> node_item_name_recognition
-> node_bge_embedding -> node_import_milvus -> END
"""
from langgraph.graph import END, StateGraph

from jingwei_knowledge.process.import_chain.nodes.node_bge_embedding import node_bge_embedding
from jingwei_knowledge.process.import_chain.nodes.node_document_metadata import (
    node_document_metadata,
)
from jingwei_knowledge.process.import_chain.nodes.node_document_split import node_document_split
from jingwei_knowledge.process.import_chain.nodes.node_entry import node_entry
from jingwei_knowledge.process.import_chain.nodes.node_import_milvus import node_import_milvus
from jingwei_knowledge.process.import_chain.nodes.node_item_name_recognition import (
    node_item_name_recognition,
)
from jingwei_knowledge.process.import_chain.nodes.node_md_img import node_md_img
from jingwei_knowledge.process.import_chain.nodes.node_pdf_to_md import node_pdf_to_md
from jingwei_knowledge.process.import_chain.state import ImportGraphState

workflow = StateGraph(ImportGraphState)

workflow.add_node("node_entry", node_entry)
workflow.add_node("node_pdf_to_md", node_pdf_to_md)
workflow.add_node("node_md_img", node_md_img)
workflow.add_node("node_document_split", node_document_split)
workflow.add_node("node_document_metadata", node_document_metadata)
workflow.add_node("node_item_name_recognition", node_item_name_recognition)
workflow.add_node("node_bge_embedding", node_bge_embedding)
workflow.add_node("node_import_milvus", node_import_milvus)

workflow.set_entry_point("node_entry")


def after_entry_node(state: ImportGraphState):
    """入口路由：Markdown 直进图片处理；PDF 先进转 MD；其他结束。"""
    if state["is_md_read_enabled"]:
        return "node_md_img"
    elif state["is_pdf_read_enabled"]:
        return "node_pdf_to_md"
    else:
        return END


workflow.add_conditional_edges(
    "node_entry",
    after_entry_node,
    {
        "node_md_img": "node_md_img",
        "node_pdf_to_md": "node_pdf_to_md",
        END: END,
    },
)

workflow.add_edge("node_pdf_to_md", "node_md_img")
workflow.add_edge("node_md_img", "node_document_metadata")
workflow.add_edge("node_document_metadata", "node_document_split")
workflow.add_edge("node_document_split", "node_item_name_recognition")
workflow.add_edge("node_item_name_recognition", "node_bge_embedding")
workflow.add_edge("node_bge_embedding", "node_import_milvus")
workflow.add_edge("node_import_milvus", END)

kb_import_app = workflow.compile()
