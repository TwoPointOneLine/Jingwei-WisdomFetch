"""
导入链全局状态定义（TypedDict）。

所有节点共享同一状态对象，按文档 4.1 设计，字段含流程标记、路径、内容数据、向量数据。
"""
import copy
from typing import TypedDict

from jingwei_common.constants import DEFAULT_KB


class ImportGraphState(TypedDict):
    task_id: str

    # --- 流程控制标记 ---
    is_md_read_enabled: bool
    is_pdf_read_enabled: bool

    # --- 路径相关 ---
    local_dir: str          # 文件夹地址 (pdf -> md -> 输出的文件夹地址)
    local_file_path: str    # 传入文件地址 不确定 md/pdf
    file_title: str
    file_ext: str           # 小写后缀（.pdf / .md / ...）
    pdf_path: str           # pdf 地址文件 <- local_file_path
    md_path: str            # md 地址文件 <- local_file_path

    # --- 可选输入源（resolve_input_file 支持）---
    file_id: str            # minio 文件 id（URL/file_id 导入用）
    url: str                # 临时外链

    # --- 内容数据 ---
    md_content: str
    raw_markdown: str       # 解析后的 Markdown 原文（PDF 转 MD / MD 直读）
    is_markdown_ready: bool # raw_markdown 是否就绪
    image_list: list        # Markdown 图片清单 [{alt, src, is_local}]
    chunks: list
    item_name: str

    # --- 文档级结构化元数据（FR-IMP-03）---
    doc_meta: dict

    # --- 归属与可见性（普通用户知识库隔离，多级）---
    owner: str          # 上传者用户名
    visibility: str     # "private"（仅本人）| "team"（团队可见）| "shared"（全员共享检索）
    team_id: str        # 所属团队 ID（仅 visibility=team 时有效；用于团队空间共享检索）
    kb_name: str        # 目标知识库（逻辑库）；同一 Milvus 集合内以 kb_name 字段区分

    # --- 数据库相关 ---
    embeddings_content: list
    done_count: int         # 入库条数（node_import_milvus 回写）


graph_default_state: ImportGraphState = {
    "task_id": "",
    "is_pdf_read_enabled": False,
    "is_md_read_enabled": False,
    "local_dir": "",
    "local_file_path": "",
    "file_ext": "",
    "pdf_path": "",
    "md_path": "",
    "file_id": "",
    "url": "",
    "file_title": "",
    "md_content": "",
    "raw_markdown": "",
    "is_markdown_ready": False,
    "image_list": [],
    "chunks": [],
    "item_name": "",
    "doc_meta": {},
    "owner": "",
    "visibility": "private",
    "team_id": "",
    "kb_name": DEFAULT_KB,
    "embeddings_content": [],
    "done_count": 0,
}


def create_default_state(**overrides) -> ImportGraphState:
    """创建默认状态，支持覆盖。"""
    state = copy.deepcopy(graph_default_state)
    state.update(overrides)
    return state


def get_default_state() -> ImportGraphState:
    """返回新的状态实例，避免全局变量污染。"""
    return copy.deepcopy(graph_default_state)
