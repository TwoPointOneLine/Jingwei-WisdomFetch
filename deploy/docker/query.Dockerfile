# 阶段5：智能问答服务独立镜像（8082）
# 构建上下文 = 仓库根（monorepo 根），Dockerfile 位于 deploy/docker/；基于 uv workspace 多阶段构建
FROM python:3.11-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY --from=ghcr.io/astral-sh/uv:0.7.0 /uv /uvx /bin/

WORKDIR /app

# 1) 先拷贝 workspace 元数据（uv 解析依赖需要全部成员 pyproject）
# 注意：各包 pyproject.toml 均声明 readme = "README.md"，hatchling 在 editable
# 构建时会严格校验其存在，因此 README.md 必须与 pyproject.toml 一并拷贝，
# 否则报 "Readme file does not exist: README.md"。
COPY backend/pyproject.toml backend/README.md backend/uv.lock ./
COPY backend/packages/common/pyproject.toml backend/packages/common/README.md packages/common/
COPY backend/services/query/pyproject.toml backend/services/query/README.md services/query/
COPY backend/services/gateway/pyproject.toml backend/services/gateway/README.md services/gateway/
COPY backend/services/auth/pyproject.toml backend/services/auth/README.md services/auth/
COPY backend/services/user/pyproject.toml backend/services/user/README.md services/user/
COPY backend/services/knowledge/pyproject.toml backend/services/knowledge/README.md services/knowledge/

# 2) 仅安装目标包的外部依赖（命中缓存层；含 torch/langgraph 等推理依赖）
RUN uv sync --package jingwei-query --no-dev --no-install-project

# 3) 拷贝源码并安装项目本身（editable）
COPY backend/packages/common packages/common
COPY backend/services/query services/query
RUN uv sync --package jingwei-query --no-dev

# ---------- runtime ----------
FROM python:3.11-slim AS runtime

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv

EXPOSE 8082
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8082/health', timeout=3)"]
CMD ["uvicorn", "jingwei_query.api.query_server.main:app", "--host", "0.0.0.0", "--port", "8082"]
