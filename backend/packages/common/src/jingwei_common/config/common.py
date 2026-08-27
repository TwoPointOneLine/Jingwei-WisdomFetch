"""基础配置：环境变量加载与类型安全读取。"""
import os
from pathlib import Path

# ── 项目根目录定位 ─────────────────────────────────────────────
# 优先使用环境变量 JINGWEI_ROOT 指定；否则向上查找包含 uv.lock 的目录
# （即仓库根，该目录同时含 pyproject.toml / docker-compose.yml / start.bat）。
# 公共模块作为独立 wheel 安装到 site-packages 时，文件位置上溯会失效，
# 此时必须通过 JINGWEI_ROOT 显式指定根目录。


def _find_project_root() -> Path:
    env_root = os.getenv("JINGWEI_ROOT")
    if env_root:
        return Path(env_root).resolve()
    # 仓库根特征：pyproject.toml 声明了 [tool.uv.workspace]，且含 docker-compose.yml
    for parent in Path(__file__).resolve().parents:
        pyproject = parent / "pyproject.toml"
        if pyproject.exists() and "[tool.uv.workspace]" in pyproject.read_text(encoding="utf-8"):
            return parent
        # 兼容：同时存在 docker-compose.yml 与 start.bat
        if (parent / "docker-compose.yml").exists() and (parent / "start.bat").exists():
            return parent
    # 兼容非 workspace 环境：以包含 uv.lock 的目录作为根
    for parent in Path(__file__).resolve().parents:
        if (parent / "uv.lock").exists():
            return parent
    # 兜底：src layout 下仓库根 = <pkg 文件的上溯 5 级>
    # packages/common/src/jingwei_common/config/common.py -> parents[5] 为仓库根
    return Path(__file__).resolve().parents[5]


PROJECT_ROOT = _find_project_root()

# ── 环境变量读取 ────────────────────────────────────────────────
from dotenv import load_dotenv  # noqa: E402

# 加载根目录 .env（存在则加载，不存在静默跳过）
load_dotenv(PROJECT_ROOT / ".env", override=False)


def env_str(key: str, default: str = "") -> str:
    """读取字符串环境变量。"""
    return os.getenv(key, default)


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
