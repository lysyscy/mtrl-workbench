"""`ACC-USR-MGMT-001` 补判据点 `001-14`：**未登录 ⇒ 写动作一律拒**（读放行）。

口径 =《说明书》§1.5.1（2026-09-21 用户裁定「未登录 = 无身份」）：
「未登录**只能看**，**写动作一律拒**」＋顶栏「未登录 · 去登录」。
⚠️ 口径**不是**「未登录只能访问登录页」（那更严、会把不带会话的真机自检全打白屏）⇒ 本判据专钉"**读放行**"这一半。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core import session as SESS
from app.main import create_app
from tests.acc_plugin import acc

#: 既不存在、也不碰业务的路径 —— 用它**单看闸门的裁决**（⛔ 不惊动任何数据）
GHOST = "/api/__gate_probe__"


@acc("ACC-USR-MGMT-001", "001-14")
def test_未登录只能看_写动作一律拒():
    """未登录：**读放行**（落到路由层 404）· **写一律拒**（闸门先拦 401）· 登录/登出本身放行 · 带票写放行。"""
    anon = TestClient(create_app())

    # ① 读：未登录也**放行**（口径 =「只能看」，⛔ 不是"只能看登录页"）
    assert anon.get(GHOST).status_code == 404, "未登录的读被拦了 —— 与 §1.5.1「只能看」冲突"

    # ② 写：未登录 ⇒ **闸门先拦**（401，且**不是** 404 ⇒ 证明是进业务之前拦的）
    for method in ("post", "put", "patch", "delete"):
        r = getattr(anon, method)(GHOST)
        assert r.status_code == 401, f"未登录的 {method.upper()} 没被拦（{r.status_code}）"
        assert "未登录" in r.json().get("message", ""), "401 得说清原因（禁静默）"

    # ③ 登录 / 登出本身放行（否则永远登不进来）
    assert anon.post("/api/m15/logout").status_code != 401, "登出被自己的闸拦住了"

    # ④ 带有效会话票 ⇒ 写**放行**（落到路由层 ⇒ 404）
    logged = TestClient(create_app())
    logged.cookies.set(SESS.COOKIE_NAME, SESS.make("闸门自检"))
    assert logged.post(GHOST).status_code == 404, "带票的写被拦了 —— 那已登录的人也没法干活"
