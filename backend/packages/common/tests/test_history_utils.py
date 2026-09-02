"""历史会话工具测试：会话隔离（登录用户/匿名访客）与登录归并。"""

from datetime import datetime, timedelta
from itertools import count

import pytest
from jingwei_common.clients import mongo_history_utils as mh
from jingwei_common.clients.mongo_client import mongo_client


class _FakeResult:
    def __init__(self, modified_count: int):
        self.modified_count = modified_count


class _FakeCursor:
    def __init__(self, docs: list[dict]):
        self._docs = list(docs)

    def sort(self, key: str, direction: int = 1):
        self._docs.sort(
            key=lambda d: d.get(key) or datetime.min,
            reverse=(direction == -1),
        )
        return self

    def limit(self, n: int):
        return _FakeCursor(self._docs[:n])

    def __iter__(self):
        return iter(self._docs)


class _FakeCollection:
    """最小内存假集合：支持本模块用到的 find/insert/update/delete。"""

    def __init__(self):
        self._docs: list[dict] = []

    # ── 查询匹配 ─────────────────────────────
    @staticmethod
    def _match(doc: dict, query: dict) -> bool:
        for key, expected in query.items():
            cur = doc
            for part in key.split("."):
                cur = cur.get(part) if isinstance(cur, dict) else None
            if cur != expected:
                return False
        return True

    @staticmethod
    def _apply(doc: dict, update: dict) -> None:
        if "$set" in update:
            for key, value in update["$set"].items():
                parts = key.split(".")
                cur = doc
                for part in parts[:-1]:
                    cur = cur.setdefault(part, {})
                cur[parts[-1]] = value
        # 真实 MongoDB 支持 $unset（此处用于归并后移除 meta.anon_id）
        if "$unset" in update:
            for key in update["$unset"]:
                parts = key.split(".")
                cur = doc
                for part in parts[:-1]:
                    if not isinstance(cur.get(part), dict):
                        break
                    cur = cur[part]
                else:
                    cur.pop(parts[-1], None)

    # ── Mongo 接口 ───────────────────────────
    def find_one(self, query: dict) -> dict | None:
        for doc in self._docs:
            if self._match(doc, query):
                return dict(doc)
        return None

    def insert_one(self, doc: dict):
        self._docs.append(dict(doc))

    def find(self, query: dict) -> _FakeCursor:
        return _FakeCursor([dict(d) for d in self._docs if self._match(d, query)])

    def update_one(self, query: dict, update: dict) -> _FakeResult:
        for doc in self._docs:
            if self._match(doc, query):
                self._apply(doc, update)
                return _FakeResult(1)
        return _FakeResult(0)

    def update_many(self, query: dict, update: dict) -> _FakeResult:
        count = 0
        for doc in self._docs:
            if self._match(doc, query):
                self._apply(doc, update)
                count += 1
        return _FakeResult(count)

    def delete_many(self, query: dict) -> _FakeResult:
        before = len(self._docs)
        self._docs = [d for d in self._docs if not self._match(d, query)]
        return _FakeResult(before - len(self._docs))


@pytest.fixture
def fake_mongo(monkeypatch):
    collections: dict[str, _FakeCollection] = {}

    def get_collection(name: str) -> _FakeCollection:
        if name not in collections:
            collections[name] = _FakeCollection()
        return collections[name]

    monkeypatch.setattr(mongo_client, "get_collection", get_collection)

    # Windows 上 datetime.now() 分辨率约 15ms，连续插入的多条消息会落在同一 tick，
    # 使「按时间取最近 N 条」的排序不可判定。此处注入每次调用前进 1ms 的时钟，
    # 保证用例可重复（真实环境消息间隔远大于此，产品代码无需特殊处理）。
    class _StepDatetime(datetime):
        _steps = count(1)

        @classmethod
        def now(cls, tz=None):
            return super().now(tz) + timedelta(milliseconds=next(cls._steps))

    monkeypatch.setattr(mh, "datetime", _StepDatetime)
    return get_collection


def _make_session(session_id: str, username: str = "guest", anon_id: str | None = None, title: str = ""):
    meta: dict = {"username": username}
    if anon_id:
        meta["anon_id"] = anon_id
    if title:
        meta["title"] = title
    mh.create_session_if_not_exists(session_id, meta)


# ── 会话隔离：匿名访客按 anon_id 过滤 ──────────────
def test_list_sessions_guest_isolated_by_anon_id(fake_mongo):
    _make_session("s-a1", username="guest", anon_id="anon-1")
    _make_session("s-a2", username="guest", anon_id="anon-2")

    got = mh.list_sessions(username="guest", anon_id="anon-1")
    assert [s["session_id"] for s in got] == ["s-a1"]

    got = mh.list_sessions(username="guest", anon_id="anon-2")
    assert [s["session_id"] for s in got] == ["s-a2"]


def test_list_sessions_login_filter_by_username(fake_mongo):
    _make_session("s-alice", username="alice")
    _make_session("s-bob", username="bob")
    _make_session("s-guest", username="guest", anon_id="anon-x")

    got = mh.list_sessions(username="alice")
    assert [s["session_id"] for s in got] == ["s-alice"]

    got = mh.list_sessions(username="bob")
    assert [s["session_id"] for s in got] == ["s-bob"]


def test_list_sessions_guest_without_anon_id_returns_empty(fake_mongo):
    """guest 未带 anon_id 时不应泄露任何会话。"""
    _make_session("s-guest", username="guest", anon_id="anon-1")
    assert mh.list_sessions(username="guest") == []


def test_list_sessions_title_fallback(fake_mongo):
    _make_session("s-t", username="alice", title="我的会话")
    _make_session("s-topic", username="alice")
    mh.update_session_meta("s-topic", {"username": "alice", "topic": "工商"})

    by_title = {s["session_id"]: s["title"] for s in mh.list_sessions(username="alice")}
    assert by_title["s-t"] == "我的会话"
    assert by_title["s-topic"] == "工商"


# ── 登录即归并：reassign_session（单条，首次发消息） ──────────
def test_reassign_session_moves_guest_to_user(fake_mongo):
    _make_session("s-1", username="guest", anon_id="anon-1")
    mh.append_message("s-1", "user", "你好")

    mh.reassign_session("s-1", "alice")

    meta = mh.get_session_meta("s-1")
    assert meta["username"] == "alice"
    assert meta.get("anon_id") is None
    # 归并后不再按 anon_id 可见，按用户名可见
    assert mh.list_sessions(username="guest", anon_id="anon-1") == []
    assert [s["session_id"] for s in mh.list_sessions(username="alice")] == ["s-1"]
    # 历史不丢
    assert mh.get_history("s-1") == [{"role": "user", "content": "你好"}]


def test_reassign_session_ignores_guest_target(fake_mongo):
    _make_session("s-1", username="guest", anon_id="anon-1")
    mh.reassign_session("s-1", "guest")
    mh.reassign_session("s-1", "")
    assert mh.get_session_meta("s-1")["username"] == "guest"
    assert mh.get_session_meta("s-1")["anon_id"] == "anon-1"


def test_reassign_session_does_not_touch_other_user(fake_mongo):
    _make_session("s-1", username="bob")
    mh.reassign_session("s-1", "alice")
    assert mh.get_session_meta("s-1")["username"] == "bob"


# ── 登录即归并：claim_guest_sessions（批量，切换账号） ──────────
def test_claim_guest_sessions_batch(fake_mongo):
    _make_session("s-g1", username="guest", anon_id="anon-1")
    _make_session("s-g2", username="guest", anon_id="anon-1")
    _make_session("s-g3", username="guest", anon_id="anon-2")
    _make_session("s-alice", username="alice")

    count = mh.claim_guest_sessions("anon-1", "alice")

    assert count == 2
    assert mh.get_session_meta("s-g1")["username"] == "alice"
    assert mh.get_session_meta("s-g1").get("anon_id") is None
    assert mh.get_session_meta("s-g2")["username"] == "alice"
    # 其他 anon_id 的 guest 会话不受影响
    assert mh.get_session_meta("s-g3")["username"] == "guest"
    assert mh.get_session_meta("s-g3")["anon_id"] == "anon-2"
    # 原登录会话不受影响
    assert mh.get_session_meta("s-alice")["username"] == "alice"


def test_claim_guest_sessions_guard(fake_mongo):
    _make_session("s-g1", username="guest", anon_id="anon-1")
    assert mh.claim_guest_sessions("", "alice") == 0
    assert mh.claim_guest_sessions("anon-1", "guest") == 0
    assert mh.claim_guest_sessions("anon-1", "") == 0
    assert mh.get_session_meta("s-g1")["username"] == "guest"


def test_claim_guest_sessions_no_match(fake_mongo):
    assert mh.claim_guest_sessions("anon-none", "alice") == 0


# ── get_session_meta ────────────────────────────────
def test_get_session_meta_missing(fake_mongo):
    assert mh.get_session_meta("no-such") == {}


def test_get_session_meta_with_meta(fake_mongo):
    _make_session("s-1", username="guest", anon_id="anon-1")
    meta = mh.get_session_meta("s-1")
    assert meta["username"] == "guest"
    assert meta["anon_id"] == "anon-1"


# ── 基础能力：历史/清理/重命名 ─────────────────────
def test_history_roundtrip_and_limit(fake_mongo):
    mh.create_session_if_not_exists("s-1")
    for i in range(5):
        mh.append_message("s-1", "user", f"m{i}")
    msgs = mh.get_history("s-1", limit=3)
    assert [m["content"] for m in msgs] == ["m2", "m3", "m4"]
    assert mh.get_history("s-1") == [
        {"role": "user", "content": f"m{i}"} for i in range(5)
    ]


def test_clear_session(fake_mongo):
    _make_session("s-1", username="alice")
    mh.append_message("s-1", "user", "hi")
    mh.clear_session("s-1")
    assert mh.get_session_meta("s-1") == {}
    assert mh.get_history("s-1") == []
    assert mh.list_sessions(username="alice") == []


def test_rename_session(fake_mongo):
    _make_session("s-1", username="alice")
    mh.rename_session("s-1", "新标题")
    assert mh.get_session_meta("s-1")["title"] == "新标题"
    assert mh.list_sessions(username="alice")[0]["title"] == "新标题"


def test_create_session_idempotent(fake_mongo):
    _make_session("s-1", username="alice")
    _make_session("s-1", username="bob")
    # 已存在则忽略，不覆盖 meta
    assert mh.get_session_meta("s-1")["username"] == "alice"
