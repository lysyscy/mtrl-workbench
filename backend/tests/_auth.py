"""测试用的 `TestClient`：**默认带上管理员会话票**（`ACC-USR-MGMT-001/001-14` 的配套）。

⚠️ 为什么要有它（2026-09-25 补「未登录 ⇒ 写动作一律拒」之后）：
   打**写**端点的测试如果跑在"未登录"态，会被新闸**正当**拒掉（401）⇒ 那批红**不是**测试错了，
   而是它们**该以"已登录"的身份跑** —— 与真机自检 `_shell_smoke.py` **同一个做法**（先播会话票）。
⛔ 这不是"把闸绕过去"：闸还在、还生效；这里只是**如实扮演一个已登录的用户**。
⭐ 票上的名字 = `current_operator()` 的**回落值**（= 没有会话时本会用的那个）⇒
   留痕里的「操作人」一个字不变 ⇒ 断言"操作人是谁"的测试不受影响。
"""

from __future__ import annotations

from fastapi.testclient import TestClient as _TestClient

from app.core import session as SESS
from app.core.identity import current_operator


def _ticket() -> str:
    return SESS.make(current_operator() or "科室用户")


class TestClient(_TestClient):
    """`fastapi.testclient.TestClient` 的**同签名**薄壳：建好就把会话票播上。"""

    def __init__(self, *args, **kwargs):                    # noqa: ANN002, ANN003
        super().__init__(*args, **kwargs)
        self.cookies.set(SESS.COOKIE_NAME, _ticket())


__all__ = ["TestClient"]
