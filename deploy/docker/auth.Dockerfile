# 阶段5：认证服务独立镜像（8083）
# 构建上下文 = 项目根目录；基于 uv workspace 多阶段构建
FROM python:3.11-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY --from=ghcr.io/astral-sh/uv:0.7.0 /uv /uvx /bin/

WORKDIR /app

# 1) 先拷贝 workspace 元数据（uv 解析依赖需要全部成员 pyproject）
COPY pyproject.toml uv.lock ./
COPY packages/common/pyproject.toml packages/common/pyproject.toml
COPY services/gateway/pyproject.toml services/gateway/pyproject.toml
COPY services/auth/pyproject.toml services/auth/pyproject.toml
COPY services/user/pyproject.toml services/user/pyproject.toml
COPY services/knowledge/pyproject.toml services/knowledge/pyproject.toml
COPY services/query/pyproject.toml services/query/pyproject.toml

# 2) 仅安装目标包的外部依赖（命中缓存层）
RUN uv sync --package shopkeeper-auth --no-dev --no-install-project

# 3) 拷贝源码并安装项目本身（editable）
COPY packages/common packages/common
COPY services/auth services/auth
RUN uv sync --package shopkeeper-auth --no-dev

# ---------- runtime ----------
FROM python:3.11-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv

EXPOSE 8083
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8083/health', timeout=3)"]
CMD ["uvicorn", "shopkeeper_auth.api.auth_server.main:app", "--host", "0.0.0.0", "--port", "8083"]
