"""测试用的 `TestClient`：**默认带上管理员会话票**（`ACC-USR-MGMT-001/001-14` 的配套）。

⚠️ 为什么要有它（2026-09-25 补「未登录 ⇒ 写动作一律拒」之后）：
   打**写**端点的测试如果跑在"未登录"态，会被新闸**正当**拒掉（401）⇒ 那批红**不是**测试错了，
   而是它们**该以"已登录"的身份跑**，所以先播会话票。
⛔ 这不是"把闸绕过去"：闸还在、还生效；这里只是**如实扮演一个已登录的用户**。
⭐ 测试标签若能唯一对应账号，就签该账号；无账号的纯业务探针仍用自身假身份。
   姓名仅用于留痕，不把显示标签当作新会话账号。
"""

from __future__ import annotations

from fastapi.testclient import TestClient as _TestClient

from app.core import session as SESS
from app.core.identity import current_operator


def _ticket() -> str:
    from app.core.db import session_scope
    from app.mod15_user import repository as R

    label = current_operator() or "科室用户"
    with session_scope() as s:
        row = R.by_identity(s, label)
        return SESS.make(row.account if row is not None else label)


class TestClient(_TestClient):
    """`fastapi.testclient.TestClient` 的**同签名**薄壳：建好就把会话票播上。"""

    def __init__(self, *args, **kwargs):                    # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self.cookies.set(SESS.COOKIE_NAME, _ticket())


__all__ = ["TestClient"]
