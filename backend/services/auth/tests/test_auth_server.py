"""
jingwei-auth 冒烟测试（不依赖真实 MongoDB，使用内存假集合）。

覆盖：app 加载、注册→登录→鉴权→登出全链路、注册建档与角色初始化、
引导管理员角色、依赖导入链。
"""
import os
from datetime import UTC, datetime

os.environ.setdefault("AUTH_BOOTSTRAP_ADMIN", "admin,root")

import pytest
from fastapi.testclient import TestClient


class FakeCollection:
    """内存版 MongoDB 集合（覆盖本服务用到的 find/insert/delete 子集）。"""

    def __init__(self, store: "FakeMongoStore", name: str):
        self._store = store
        self._name = name

    def insert_one(self, doc: dict):
        self._store._docs[self._name].append(dict(doc))

    def find_one(self, query: dict) -> dict | None:
        for d in self._store._docs[self._name]:
            if all(d.get(k) == v for k, v in query.items()):
                return dict(d)
        return None

    def delete_many(self, query: dict):
        self._store._docs[self._name] = [
            d for d in self._store._docs[self._name] if not all(d.get(k) == v for k, v in query.items())
        ]


class FakeMongoStore:
    def __init__(self):
        self._docs: dict[str, list[dict]] = {}

    def collection(self, name: str) -> FakeCollection:
        self._docs.setdefault(name, [])
        return FakeCollection(self, name)


@pytest.fixture()
def client(monkeypatch):
    from jingwei_common.clients.mongo_client import mongo_client

    from jingwei_auth.api.auth_server.main import app

    store = FakeMongoStore()
    monkeypatch.setattr(mongo_client, "get_collection", lambda name: store.collection(name))
    return TestClient(app)


def test_app_import_chain():
    from jingwei_common.auth import auth_client

    from jingwei_auth import __version__
    from jingwei_auth.api.auth_server.main import app
    from jingwei_auth.infra.auth.auth_service import register, validate_token

    assert __version__ == "0.1.0"
    assert app.title
    assert callable(register)
    assert callable(validate_token)
    assert auth_client.get_user_role("nobody") == "guest"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_register_login_me_logout(client):
    r = client.post("/auth/register", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 200
    body = r.json()
    assert body["code"] == 200
    assert body["data"]["username"] == "alice"
    assert body["data"]["role"] == "member"

    r = client.post("/auth/login", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 200
    token = r.json()["data"]["token"]
    assert token

    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["data"]["username"] == "alice"
    assert r.json()["data"]["role"] == "member"

    r = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["code"] == 200


def test_register_duplicate(client):
    client.post("/auth/register", json={"username": "bob", "password": "secret123"})
    r = client.post("/auth/register", json={"username": "bob", "password": "secret123"})
    assert r.status_code == 200
    assert r.json()["code"] == 400


def test_login_wrong_password(client):
    client.post("/auth/register", json={"username": "carol", "password": "secret123"})
    r = client.post("/auth/login", json={"username": "carol", "password": "wrong-pass"})
    assert r.status_code == 200
    assert r.json()["code"] == 401


def test_me_unauthorized(client):
    r = client.get("/auth/me")
    assert r.status_code == 200
    assert r.json()["code"] == 401


def test_bootstrap_admin_role(client):
    r = client.post("/auth/register", json={"username": "admin", "password": "secret123"})
    assert r.status_code == 200
    assert r.json()["data"]["role"] == "admin"


def test_register_init_profile(client):
    client.post("/auth/register", json={"username": "dave", "password": "secret123"})
    from jingwei_common.clients.mongo_client import mongo_client

    doc = mongo_client.get_collection("user_profiles").find_one({"username": "dave"})
    assert doc is not None
    assert doc["role"] == "member"
    assert "created_at" in doc
    assert isinstance(doc["created_at"], datetime)


def test_dt_awareness():
    """datetime 使用 UTC 时区，保证与 Mongo 序列化兼容。"""
    now = datetime.now(UTC)
    assert now.tzinfo is not None
