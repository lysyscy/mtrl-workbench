"""React appearance choices share palette roles; account reads never rewrite old choices."""
import re

from fastapi.testclient import TestClient

from app.core import session as cookies
from app.core.db import get_session_factory
from app.main import create_app
from app.mod03_notice import page, theme_react
from app.mod15_user.models import UserAccount


def variables(css):
    return dict(re.findall(r"(--[a-z0-9-]+):([^;]+);", css))


def test_approved_eight_choices_match_served_roles_and_keep_original_pine():
    choices = theme_react.theme_choices()
    assert [item['label'] for item in choices] == ['中性浅色', '松绿', '暖色纸面', '深侧栏', '深色', '高对比', '玫瑰柔粉', '丁香浅紫']
    for item in choices:
        assert item['vars'] == variables(theme_react.render_react_theme(item['name']))
    pine = next(item['vars'] for item in choices if item['name'] == '松绿')
    original = variables(page.render_theme('松绿'))
    assert all(pine[key] == value for key, value in original.items() if value.startswith('#'))
    assert pine['--bg'] == '#eff6f3' and pine['--sb'] == '#081a21'
    assert theme_react.theme_name('米黄') == theme_react.theme_name('靛青') == page.DEFAULT_THEME
    assert theme_react.render_react_theme('米黄') == theme_react.render_react_theme(page.DEFAULT_THEME)


def test_react_fallback_does_not_rewrite_preferences_and_saves_only_current_account(rollback_db):
    with get_session_factory()() as session:
        first = UserAccount(account='appearance-441-a', name='外观甲', role='admin', password='', theme='靛青')
        second = UserAccount(account='appearance-441-b', name='外观乙', role='user', password='', theme='深色', ui_scale='large')
        session.add_all([first, second]); session.flush()
        first_id, second_id = first.id, second.id
        session.commit()
    app = create_app()
    with TestClient(app) as first_client, TestClient(app) as second_client:
        first_client.cookies.set(cookies.COOKIE_NAME, cookies.make('appearance-441-a'))
        second_client.cookies.set(cookies.COOKIE_NAME, cookies.make('appearance-441-b'))
        current = first_client.get('/api/m15/theme?surface=react').json()
        assert current['theme'] == page.DEFAULT_THEME and len(current['themes']) == 8
        legacy = first_client.get('/api/m15/theme').json()
        assert legacy['theme'] == '靛青' and legacy['themes'] == list(page.theme_names())
        with get_session_factory()() as session:
            assert session.get(UserAccount, first_id).theme == '靛青'
        assert first_client.post('/api/m15/theme', json={'theme': '玫瑰柔粉', 'id': second_id}).json()['ok']
        assert first_client.post('/api/m15/ui-scale', json={'ui_scale': 'largest'}).json()['ok']
        reread = first_client.get('/api/m15/theme?surface=react').json()
        assert reread['theme'] == '玫瑰柔粉' and reread['ui_scale'] == 'largest'
        css = variables(first_client.get('/static/theme.css?surface=react').text)
        assert css['--bg'] == '#f9edf2' and css['--sb'] == '#f0d6e3'
        other = second_client.get('/api/m15/theme?surface=react').json()
        assert other['theme'] == '深色' and other['ui_scale'] == 'large'
        assert variables(second_client.get('/static/theme.css?surface=react').text)['--ui-scheme'] == 'dark'
        assert second_client.get('/static/theme.css').text == page.render_theme('深色')
