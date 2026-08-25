"""
shopkeeper-user 冒烟测试（不依赖真实 MongoDB，使用内存假集合）。

覆盖：app 加载、鉴权拦截、档案 CRUD、角色授权（admin/member）、
角色列表与权限查询、异常映射（401/403/404）。
"""
import pytest
from fastapi.testclient import TestClient


class FakeCollection:
    """内存版 MongoDB 集合（覆盖 find/insert/update/delete 子集）。"""

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

    def update_one(self, query: dict, update: dict):
        doc = self.find_one(query)
        if not doc:
            return
        for i, d in enumerate(self._store._docs[self._name]):
            if all(d.get(k) == v for k, v in query.items()):
                for key, value in update.get("$set", {}).items():
                    self._store._docs[self._name][i][key] = value
                break

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
    from shopkeeper_common.clients.mongo_client import mongo_client

    from shopkeeper_user.api.user_server.main import app

    store = FakeMongoStore()
    # 预置 token -> 用户
    store.collection("auth_tokens").insert_one({"token": "tk-admin", "username": "admin"})
    store.collection("auth_tokens").insert_one({"token": "tk-mike", "username": "mike"})
    # 预置档案
    store.collection("user_profiles").insert_one(
        {"username": "admin", "nickname": "Admin", "role": "admin"}
    )
    store.collection("user_profiles").insert_one(
        {"username": "mike", "nickname": "Mike", "role": "member"}
    )
    monkeypatch.setattr(mongo_client, "get_collection", lambda name: store.collection(name))
    return TestClient(app)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_app_import_chain():
    from shopkeeper_user import __version__
    from shopkeeper_user.api.user_server.main import app
    from shopkeeper_user.infra.user.user_service import get_profile, set_role

    assert __version__ == "0.1.0"
    assert app.title
    assert callable(get_profile)
    assert callable(set_role)


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_requires_auth(client):
    resp = client.get("/user/profile/mike")
    assert resp.status_code == 401
    assert resp.json()["code"] == 401


def test_read_profile(client):
    resp = client.get("/user/profile/mike", headers=_auth("tk-mike"))
    assert resp.status_code == 200
    assert resp.json()["data"]["username"] == "mike"
    assert resp.json()["data"]["role"] == "member"


def test_profile_not_found(client):
    resp = client.get("/user/profile/nobody", headers=_auth("tk-mike"))
    assert resp.status_code == 404
    assert resp.json()["code"] == 404


def test_update_own_profile(client):
    resp = client.patch(
        "/user/profile/mike",
        json={"nickname": "Mikey", "organization": "ACME"},
        headers=_auth("tk-mike"),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["nickname"] == "Mikey"
    assert resp.json()["data"]["organization"] == "ACME"


def test_member_cannot_update_others(client):
    resp = client.patch(
        "/user/profile/admin",
        json={"nickname": "Hacked"},
        headers=_auth("tk-mike"),
    )
    assert resp.status_code == 403


def test_member_cannot_assign_role(client):
    resp = client.post(
        "/user/profile",
        json={"username": "carol", "role": "admin"},
        headers=_auth("tk-mike"),
    )
    assert resp.status_code == 403


def test_member_cannot_set_other_role(client):
    resp = client.post("/user/carol/role", json={"role": "member"}, headers=_auth("tk-mike"))
    assert resp.status_code == 403


def test_admin_assign_role(client):
    resp = client.post(
        "/user/profile",
        json={"username": "carol", "nickname": "Carol", "role": "member"},
        headers=_auth("tk-admin"),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "member"

    resp = client.post("/user/carol/role", json={"role": "admin"}, headers=_auth("tk-admin"))
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "admin"


def test_list_roles(client):
    resp = client.get("/user/roles", headers=_auth("tk-mike"))
    assert resp.status_code == 200
    roles = {r["role"]: r for r in resp.json()["data"]["roles"]}
    assert set(roles) == {"admin", "member", "guest"}
    assert "*" in roles["admin"]["permissions"]


def test_get_permissions(client):
    resp = client.get("/user/mike/permissions", headers=_auth("tk-mike"))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["role"] == "member"
    assert "chat.query" in data["permissions"]


def test_invalid_role_rejected(client):
    resp = client.post("/user/mike/role", json={"role": "superuser"}, headers=_auth("tk-admin"))
    assert resp.status_code == 400
