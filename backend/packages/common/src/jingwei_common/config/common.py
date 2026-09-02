"""基础配置：环境变量加载与类型安全读取。"""
import os
from pathlib import Path

# ── 根目录定位 ─────────────────────────────────────────────────
# 本仓库是 monorepo，存在两个不同的"根"，必须区分：
#
#   PROJECT_ROOT（= backend/）  uv workspace 根
#       └── 用于运行期产物：logs/、output/ 等在此之下
#   REPO_ROOT（= 仓库根）       monorepo 根，含 .env / frontend/ / deploy/
#       └── 用于加载 .env 配置
#
# ⚠️ 历史坑：早期实现把两者混为一谈，且注释误称 PROJECT_ROOT "即仓库根"。
#    实际 PROJECT_ROOT 命中的是 backend/（因其 pyproject.toml 含 [tool.uv.workspace]），
#    .env 靠 PROJECT_ROOT.parent 兜底才读到——一旦目录布局变化就会静默失效，
#    表现为 BGE_M3_PATH / OPENAI_API_KEY 回退默认值，向量化误走 HuggingFace 远程下载（极慢）。
#
# 独立 wheel 安装到 site-packages 时文件位置上溯会失效，此时用环境变量
# JINGWEI_ROOT 显式指定【仓库根】。


def _find_project_root() -> Path:
    """定位 uv workspace 根（backend/）。不受 JINGWEI_ROOT 影响，语义稳定。"""
    # 特征：pyproject.toml 声明了 [tool.uv.workspace]
    for parent in Path(__file__).resolve().parents:
        pyproject = parent / "pyproject.toml"
        if pyproject.exists() and "[tool.uv.workspace]" in pyproject.read_text(encoding="utf-8"):
            return parent
    # 兼容非 workspace 环境：以包含 uv.lock 的目录作为根
    for parent in Path(__file__).resolve().parents:
        if (parent / "uv.lock").exists():
            return parent
    # 兜底：src layout 下 packages/common/src/jingwei_common/config/common.py
    # 的上溯 4 级即 backend/（packages/common/src/jingwei_common/config -> 4 级）
    return Path(__file__).resolve().parents[4]


def _find_repo_root(project_root: Path) -> Path:
    """定位仓库根（含 .env / frontend / deploy 的 monorepo 根）。"""
    env_root = os.getenv("JINGWEI_ROOT")
    if env_root:
        return Path(env_root).resolve()
    # 仓库根特征：其 deploy/ 下存在 compose.yml
    parent = project_root.parent
    if (parent / "deploy" / "compose.yml").exists():
        return parent
    # 单仓布局（backend 即仓库根）
    return project_root


PROJECT_ROOT = _find_project_root()
REPO_ROOT = _find_repo_root(PROJECT_ROOT)

# ── 环境变量读取 ────────────────────────────────────────────────
from dotenv import load_dotenv  # noqa: E402

# 依次加载 backend/.env 与仓库根 .env。
# override=False 表示【先加载者优先】，且真实环境变量始终最高优先级。
_env_candidates = [PROJECT_ROOT / ".env", REPO_ROOT / ".env"]
_loaded = [p for p in _env_candidates if p.exists()]
for _p in _loaded:
    load_dotenv(_p, override=False)

if not _loaded:
    # 不抛异常：库导入不应因缺配置而失败（测试/CI 可能不需要真实密钥）。
    # 但必须明确告警，否则 BGE 会静默走 HuggingFace 远程下载，表现为极慢而非报错。
    import warnings

    warnings.warn(
        f"未找到 .env（已尝试: {', '.join(str(p) for p in _env_candidates)}）。"
        "BGE_M3_PATH / OPENAI_API_KEY 等将回退代码默认值，"
        "可能导致向量化误走 HuggingFace 远程下载。请复制 "
        "deploy/env/.env.example 为【仓库根】.env，或设置 JINGWEI_ROOT。",
        RuntimeWarning,
        stacklevel=2,
    )


def env_str(key: str, default: str = "") -> str:
    """读取字符串环境变量。"""
    return os.getenv(key, default)


# ── 运行期产物目录 ──────────────────────────────────────────────
# 历史：日志与解析输出曾硬编码在 PROJECT_ROOT（backend/）下的 logs/、output/，
# 与源码混放，且易被误提交。现统一外移到【仓库根】var/ 下（已 gitignore），
# 并支持环境变量覆盖，便于容器部署时挂到独立卷。
#
#   JINGWEI_LOG_DIR     日志目录，默认 <仓库根>/var/log
#   JINGWEI_OUTPUT_DIR  解析输出目录，默认 <仓库根>/var/output

VAR_DIR = REPO_ROOT / "var"
LOG_DIR = Path(os.getenv("JINGWEI_LOG_DIR") or (VAR_DIR / "log")).resolve()
OUTPUT_DIR = Path(os.getenv("JINGWEI_OUTPUT_DIR") or (VAR_DIR / "output")).resolve()


def env_bool(key: str, default: bool = False) -> bool:
    """读取布尔环境变量（true/1/yes 视为 True）。"""
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_int(key: str, default: int = 0) -> int:
    """读取整数环境变量。"""
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_float(key: str, default: float = 0.0) -> float:
    """读取浮点环境变量。"""
    raw = os.getenv(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default
