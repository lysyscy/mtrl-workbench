"""Both theme endpoints resolve old preferences without rewriting them."""

import re

from fastapi.testclient import TestClient

from app.core import session as cookies
from app.core.db import get_session_factory
from app.main import create_app
from app.mod03_notice import theme_react
from app.mod15_user.models import UserAccount


def variables(css):
    return dict(re.findall(r"(--[a-z0-9-]+):([^;]+);", css))


def test_only_pine_choice_matches_served_roles():
    choice, = theme_react.theme_choices()
    assert choice["name"] == choice["label"] == "松绿"
    assert choice["vars"] == variables(theme_react.render_react_theme("松绿"))
    assert choice["vars"]["--bg"] == "#edf3f0"
    assert choice["vars"]["--sb"] == "#0b221d"


def test_react_fallback_does_not_rewrite_preferences_and_saves_only_current_account(rollback_db):
    with get_session_factory()() as session:
        first = UserAccount(account="appearance-441-a", name="外观甲", role="admin", password="", theme="靛青")
        second = UserAccount(account="appearance-441-b", name="外观乙", role="user", password="",
                             theme="深色", ui_scale="large")
        session.add_all([first, second])
        session.flush()
        first_id, second_id = first.id, second.id
        session.commit()

    app = create_app()
    with TestClient(app) as first_client, TestClient(app) as second_client:
        first_client.cookies.set(cookies.COOKIE_NAME, cookies.make("appearance-441-a"))
        second_client.cookies.set(cookies.COOKIE_NAME, cookies.make("appearance-441-b"))
        for client in (first_client, second_client):
            for endpoint in ("/api/m15/theme", "/api/m15/theme?surface=react"):
                result = client.get(endpoint).json()
                assert result["theme"] == result["default"] == "松绿"
                assert result["themes"] == ["松绿"]
                assert [choice["name"] for choice in result["palette"]] == ["松绿"]
            css = variables(client.get("/static/theme.css?surface=react").text)
            assert css["--pri"] == "#0c6b61"
            assert css["--bd3"] == "#6b8177"

        before = second_client.get("/api/m15/theme?surface=react").json()
        assert first_client.post("/api/m15/ui-scale", json={"ui_scale": "largest", "id": second_id}).json()["ok"]
        assert first_client.get("/api/m15/theme?surface=react").json()["ui_scale"] == "largest"
        assert second_client.get("/api/m15/theme?surface=react").json() == before

    with get_session_factory()() as session:
        assert session.get(UserAccount, first_id).theme == "靛青"
        assert session.get(UserAccount, second_id).theme == "深色"
