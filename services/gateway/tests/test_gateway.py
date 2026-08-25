"""网关单元测试：路由转发 / 前缀剥离 / 鉴权前置 / SSE 透传 / 健康检查 / 限流。"""
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from shopkeeper_gateway.api.gateway_server import main as gateway_main


def _mock_backend(request: httpx.Request) -> httpx.Response:
    """模拟后端服务。"""
    path = request.url.path
    if path == "/models":
        return httpx.Response(200, json={"code": 0, "data": ["bge-m3"]})
    if path == "/auth/login":
        body = json.loads(request.content)
        return httpx.Response(200, json={"code": 0, "data": {"username": body.get("username"), "token": "tk"}})
    if path == "/user/profile/alice":
        return httpx.Response(200, json={"code": 0, "data": {"username": "alice", "role": "member"}})
    if path == "/chat/stream/s1":
        sse_body = 'data: {"delta": "你好"}\n\ndata: [DONE]\n\n'.encode()
        return httpx.Response(200, content=sse_body, headers={"Content-Type": "text/event-stream"})
    return httpx.Response(404, json={"code": 404, "message": "not found"})


@pytest.fixture
def client(monkeypatch):
    recorded: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        recorded.append(request.url.path)
        return _mock_backend(request)

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://backend")
    monkeypatch.setattr(gateway_main.proxy, "client", async_client)

    def _validate(token: str) -> str | None:
        return "alice" if token == "valid-token" else None

    monkeypatch.setattr(gateway_main.auth_client, "validate_token", _validate)
    monkeypatch.setattr(gateway_main.gateway_auth, "mode", "optional")
    with TestClient(gateway_main.app) as test_client:
        test_client.recorded = recorded
        yield test_client


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "up"
    assert "/api/auth" in data["backends"]
    assert "/api/query" in data["backends"]


def test_forward_get(client):
    resp = client.get("/api/query/models")
    assert resp.status_code == 200
    assert resp.json()["data"] == ["bge-m3"]


def test_forward_post_body(client):
    # 前端实际路径：/api/auth/auth/login（网关剥离 /api/auth → 后端 /auth/login）
    resp = client.post("/api/auth/auth/login", json={"username": "alice", "password": "x"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["username"] == "alice"
    assert data["token"] == "tk"


def test_prefix_stripped_before_forward(client):
    """前缀剥离：/api/query/models → 后端 /models；/api/auth/auth/login → /auth/login。"""
    client.get("/api/query/models")
    client.post("/api/auth/auth/login", json={"username": "alice", "password": "x"})
    assert "/models" in client.recorded
    assert "/auth/login" in client.recorded


def test_auth_optional_anonymous_passthrough(client):
    """optional 模式：未携带 token 放行（guest）。"""
    resp = client.get("/api/user/user/profile/alice")
    assert resp.status_code == 200


def test_auth_invalid_token_401(client):
    resp = client.get("/api/user/user/profile/alice", headers={"Authorization": "Bearer bad-token"})
    assert resp.status_code == 401
    assert resp.json()["code"] == 401


def test_auth_valid_token_passthrough(client):
    resp = client.get("/api/user/user/profile/alice", headers={"Authorization": "Bearer valid-token"})
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "member"


def test_auth_strict_requires_token(client):
    gateway_main.gateway_auth.mode = "strict"
    try:
        resp = client.get("/api/user/user/profile/alice")
        assert resp.status_code == 401
    finally:
        gateway_main.gateway_auth.mode = "optional"


def test_auth_strict_public_path_passthrough(client):
    gateway_main.gateway_auth.mode = "strict"
    try:
        resp = client.get("/api/query/models")
        assert resp.status_code == 200
        resp = client.post("/api/auth/auth/login", json={"username": "alice", "password": "x"})
        assert resp.status_code == 200
    finally:
        gateway_main.gateway_auth.mode = "optional"


def test_sse_streaming_proxy(client):
    """SSE 经网关逐块透传，保留 text/event-stream。"""
    resp = client.get("/api/query/chat/stream/s1")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "你好" in resp.text
    assert "[DONE]" in resp.text


def test_unknown_route_forwarded_404(client):
    resp = client.get("/api/unknown/foo")
    assert resp.status_code == 404


def test_rate_limit_429(client):
    gateway_main.rate_limiter.limit = 1
    gateway_main.rate_limiter.window = 60
    gateway_main.rate_limiter._buckets.clear()
    try:
        assert client.get("/api/query/models").status_code == 200
        assert client.get("/api/query/models").status_code == 429
    finally:
        gateway_main.rate_limiter.limit = 0
        gateway_main.rate_limiter._buckets.clear()
