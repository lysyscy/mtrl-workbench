"""Theme preference writes and fallback through separate account sessions."""

from fastapi.testclient import TestClient

from app.core.db import session_scope
from app.main import app
from app.mod15_user import repository as users


def _login(client: TestClient, account: str) -> None:
    response = client.post("/m15/login", data={"account": account, "password": "", "next": "/app"},
                           follow_redirects=False)
    assert response.status_code == 303


def test_主题偏好按用户保存并解析为松绿(rollback_db):
    account_a, account_b = "theme-check-a", "theme-check-b"
    with session_scope() as session:
        a = users.create(session, account=account_a)
        b = users.create(session, account=account_b)
        aid, bid = a.id, b.id
        users.set_theme(session, aid, "")
        users.set_theme(session, bid, "深色")

    with TestClient(app) as first, TestClient(app) as second:
        _login(first, account_a)
        _login(second, account_b)

        for name in ("默认", "玫瑰柔粉", "不存在的主题", "松绿", ""):
            assert first.post("/api/m15/theme", json={"theme": name, "id": bid}).json()["ok"]
            for client in (first, second):
                data = client.get("/api/m15/theme").json()
                assert data["theme"] == "松绿"
                css = client.get("/static/theme.css")
                assert css.status_code == 200
                assert "--bg:#edf3f0;" in css.text
                assert "--sb:#0b221d;" in css.text
            with session_scope() as session:
                assert users.by_identity(session, account_a).theme == name
                assert users.by_identity(session, account_b).theme == "深色"


def test_主题端点提供松绿标本(rollback_db):
    response = TestClient(app).get("/api/m15/theme")
    assert response.status_code == 200
    data = response.json()
    assert data["theme"] == data["default"] == "松绿"
    assert data["themes"] == ["松绿"]
    sample, = data["palette"]
    assert sample["name"] == "松绿"
    assert sample["pri"] == "#0c6b61"
    assert sample["bg"] == "#edf3f0"
    assert sample["sf"] == "#ffffff"
    assert sample["tx"] == "#182c26"
