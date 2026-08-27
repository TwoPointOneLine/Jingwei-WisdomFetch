"""
提示词（prompt）加载工具。

优先从公共模块自带的 resources/prompts 目录按文件名加载 .md / .txt 提示词模板，
找不到时回退到仓库根 app/resources/prompts（兼容历史布局）。
支持使用 string.Template 进行占位符替换（如 $var / ${var}）。

示例：
    system_prompt = load_prompt("import_intent", topic="工商信息")
"""
from pathlib import Path
from string import Template

from jingwei_common.config.common import PROJECT_ROOT

# 公共模块自带资源目录（随 wheel 分发）
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "resources" / "prompts"
# 历史布局回退目录（Monorepo 开发模式）
LEGACY_PROMPTS_DIR = PROJECT_ROOT / "app" / "resources" / "prompts"


def load_prompt(name: str, **kwargs) -> str:
    """
    加载提示词模板。

    :param name: 提示词文件名（不含扩展名，默认 .md；也支持 .txt）
    :param kwargs: 可选占位符，用于替换模板中的 $var
    :return: 渲染后的提示词文本
    """
    path = _resolve_path(name)
    text = path.read_text(encoding="utf-8")
    if kwargs:
        text = Template(text).safe_substitute(**kwargs)
    return text


def _resolve_path(name: str) -> Path:
    for base in (PROMPTS_DIR, LEGACY_PROMPTS_DIR):
        candidates = [
            base / f"{name}.md",
            base / f"{name}.txt",
            base / name,
        ]
        for p in candidates:
            if p.exists():
                return p
    raise FileNotFoundError(
        f"提示词未找到: {name}（搜索路径: {PROMPTS_DIR} 或 {LEGACY_PROMPTS_DIR}）"
    )


__all__ = ["load_prompt", "PROMPTS_DIR"]
