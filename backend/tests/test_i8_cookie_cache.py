"""i8 **Cookie 磁盘缓存复用** —— 离线接线断言（`monkeypatch` 打桩，⛔ **绝不真连 i8**）。

守的是本片新增的**离线可判**行为（都在函数体内取区间、不受别处同名串喂饱）：

1. **缓存命中 ⇒ 不登录**（`http_login` spy 计数 = 0）；
2. **缓存命中也不绕过 `allow_kick` 授权语义**（命中根本不登录 ⇒ 无论真假都不踢）；
3. **无缓存 ⇒ 登录一次，且 cookie 被写进缓存**；
4. **401 ⇒ 重登一次（计数 = 1）且缓存被更新**；
5. **重登后仍 401 ⇒ 清掉已知不可用的缓存**（异常照旧抛）；
6. **缺少正确站点绑定的旧格式一律不复用**；
7. **缓存文件不进 git**（`.gitignore` 里有那条显式规则）。

⚠️ 本片**不新增判据点** ⇒ 全部用 `@acc()` 显式声明不绑定，避免被"未绑定测试体检"误报。
⚠️ 全程**打桩**：`I8Client._ensure_session` 换成假会话、`client.http_login` 换成 spy
   ⇒ 既不建真连接、也不碰 `.env` 里的真凭据。
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from app.core.config import get_settings
from app.core.errors import ExternalServiceError
from app.mod02_i8 import client as C
from app.mod02_i8 import cookie_store as CS
from app.mod02_i8.login import LoginResult

REPO_ROOT = Path(__file__).resolve().parents[2]
GITIGNORE = REPO_ROOT / ".gitignore"
TEST_ACCOUNT = "SGY_TEST"


# --------------------------------------------------------------------- 打桩件


class _FakeResp:
    """假 httpx 响应：只需 `status_code` / `json`（`_is_session_invalid` 认这两样）。"""

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.content = b""
        self.text = ""

    def json(self) -> dict:
        return {}


class _FakeSession:
    """假 httpx 会话：记 `headers` 与调用；可预置若干响应（用于 401 → 重登 → 重试）。"""

    def __init__(self, responses: list[_FakeResp] | None = None) -> None:
        self.headers: dict = {}
        self.responses: list[_FakeResp] = list(responses or [])
        self.calls: list[tuple] = []

    def request(self, method: str, path: str, **kwargs):  # noqa: ANN001, ANN003
        self.calls.append((method, path))
        return self.responses.pop(0) if self.responses else _FakeResp(200)

    def close(self) -> None:  # pragma: no cover
        pass


class _Spy:
    """`http_login` 替身：只记「被调了几次」，并回一个可控的 `LoginResult`。"""

    def __init__(self, cookie: str = "NEW") -> None:
        self.count = 0
        self.cookie = cookie

    def __call__(self, **kwargs) -> LoginResult:  # noqa: ANN003
        self.count += 1
        return LoginResult(ok=True, cookie=self.cookie, detail="stub")


@pytest.fixture
def env(monkeypatch, tmp_path):  # noqa: ANN001
    """缓存目录 → 临时目录 · 账号 → 固定值 · 会话与登录全打桩。返回 `(假会话, spy)`。"""
    monkeypatch.setattr(CS, "CACHE_DIR", tmp_path / "i8_cookie")
    monkeypatch.setenv("I8_USER", TEST_ACCOUNT)
    monkeypatch.setattr(CS, "i8_base_of", lambda _: "https://i8-a.example.test")
    monkeypatch.setattr(C, "i8_base_of", CS.i8_base_of)
    get_settings.cache_clear()
    session = _FakeSession()

    def _stub_session(self):  # noqa: ANN001
        # ⚠️ 必须**照真身**把 `self._session` 也设上 —— 否则 `_apply_cookie`（它读 `self._session`）
        #    会静默跳过 ⇒ 断言测的是桩、不是真实路径。
        self._session = session
        return session

    monkeypatch.setattr(C.I8Client, "_ensure_session", _stub_session)
    spy = _Spy()
    monkeypatch.setattr(C, "http_login", spy)
    return session, spy


# --------------------------------------------------------------------- 断言


def test_缓存命中则不登录(env):  # noqa: ANN001
    """⭐ **缓存命中 ⇒ 根本不登录**（这是本片的**核心**：导出不再次次撞单会话）。"""
    session, spy = env
    CS.save("CACHED-COOKIE", source="t")
    resp = C.I8Client().request("GET", "/x")
    assert resp.status_code == 200
    assert spy.count == 0, "缓存命中却仍去登录 ⇒ 又回到「每次导出都撞会话」"
    assert session.headers.get("Cookie") == "CACHED-COOKIE", "缓存里的 cookie 没被用上"


def test_缓存命中也不绕过强踢授权语义(env):  # noqa: ANN001
    """缓存命中 ⇒ 根本不登录 ⇒ 无论 `allow_kick` 真假都**不踢人**（授权语义不被绕过）。"""
    _session, spy = env
    CS.save("CACHED-COOKIE", source="t")
    C.I8Client(allow_kick=True).request("GET", "/x")
    assert spy.count == 0, "缓存命中却走了登录 ⇒ 强踢授权语义被绕过"


def test_无缓存则登录一次且写进缓存(env):  # noqa: ANN001
    """无缓存 ⇒ 登录一次；成功后 cookie **落盘**（下次才可能命中）。"""
    _session, spy = env
    spy.cookie = "FRESH"
    C.I8Client().request("GET", "/x")
    assert spy.count == 1, "无缓存时应恰好登录一次"
    assert CS.load() == "FRESH", "登录成功后 cookie 没落盘 ⇒ 下次还得再登一次"


def test_401时重登一次并更新缓存(env):  # noqa: ANN001
    """会话失效（401）⇒ **重登一次**（D9：不得循环）且**缓存被更新**。"""
    session, spy = env
    CS.save("OLD", source="t")
    spy.cookie = "RENEWED"
    session.responses = [_FakeResp(401), _FakeResp(200)]
    resp = C.I8Client().request("GET", "/x")
    assert resp.status_code == 200
    assert spy.count == 1, "401 应恰好重登一次（反复重登 = 反复顶号，D9 禁止）"
    assert CS.load() == "RENEWED", "重登成功后缓存没更新（下次还会拿旧的再撞 401）"


def test_重登后仍401则清掉已知不可用的缓存(env):  # noqa: ANN001
    """重登后**仍 401** ⇒ 该 cookie 已知不可用 ⇒ 从缓存抹掉（异常照旧抛，判定不变）。"""
    session, spy = env
    CS.save("OLD", source="t")
    spy.cookie = "STILL-BAD"
    session.responses = [_FakeResp(401), _FakeResp(401)]
    with pytest.raises(ExternalServiceError):
        C.I8Client().request("GET", "/x")
    assert spy.count == 1
    assert CS.load() is None, "已知不可用的 cookie 不该留在盘上（下次进程启动会先白撞一次 401）"


@pytest.mark.parametrize("legacy", [
    "LEGACY-COOKIE", '{"cookie":"NO-ORIGIN"}', '{"cookie":"WRONG-SITE","origin":"https://wrong.test"}',
])
def test_cache_requires_matching_origin(env, legacy):
    session, spy = env
    path = CS.cookie_path(TEST_ACCOUNT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(legacy, encoding="utf-8")
    assert CS.load_meta(TEST_ACCOUNT) == (None, "", "")
    C.I8Client().request("GET", "/x")
    assert spy.count == 1
    assert session.headers["Cookie"] == spy.cookie


def test_switching_site_never_sends_the_other_sites_cookie(monkeypatch, tmp_path):
    site_a = "https://i8-a.example.test"
    site_b = "https://i8-b.example.test"
    monkeypatch.setattr(CS, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(C, "current_i8_credentials", lambda: (TEST_ACCOUNT, ""))
    normalized_a = CS.save("sid=old", user=TEST_ACCOUNT, origin="https://I8-A.example.test:443/login")
    assert normalized_a == CS.cookie_path(TEST_ACCOUNT, site_a)
    assert json.loads(normalized_a.read_text(encoding="utf-8"))["origin"] == site_a
    assert CS.load(TEST_ACCOUNT, site_b) is None

    login, requests = [], []
    client_type = httpx.Client
    def authenticate(**kwargs):
        login.append(kwargs["base_url"])
        return LoginResult(ok=True, cookie="sid=fresh-on-b")
    def respond(request):
        requests.append((str(request.url), request.headers.get("cookie")))
        return httpx.Response(200, json={})
    monkeypatch.setattr(C, "http_login", authenticate)
    monkeypatch.setattr(C.httpx, "Client", lambda **kw: client_type(**kw, transport=httpx.MockTransport(respond)))
    for origin in (site_a, site_b, site_b):
        monkeypatch.setattr(C, "i8_base_of", lambda _, current=origin: current)
        client = C.I8Client()
        try:
            client.request("GET", "/sample")
        finally:
            client.close()
    assert requests == [
        (site_a + "/sample", "sid=old"),
        (site_b + "/sample", "sid=fresh-on-b"),
        (site_b + "/sample", "sid=fresh-on-b"),
    ]
    assert login == [site_b]
    assert CS.clear(TEST_ACCOUNT, site_b)
    assert CS.load(TEST_ACCOUNT, site_a) == "sid=old"


def test_缓存文件不进git():
    """⚠️ cookie 是**凭证** ⇒ 落点必须在 `artifacts/` 下，且 `.gitignore` 有**显式规则行**。

    ⚠️ 判的是**规则行**（非注释行）—— 注释里提一嘴不算（那挡不住 git）。
    """
    text = GITIGNORE.read_text(encoding="utf-8")
    rules = {
        ln.strip() for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    }
    assert "var/state/i8_cookie/" in rules, "`.gitignore` 里没有 i8 cookie 缓存的**显式规则行**"
    rel = str(CS.CACHE_DIR).replace("\\", "/")
    assert rel.endswith("/var/state/i8_cookie"), f"缓存落点不在 artifacts/ 下：{rel}"
