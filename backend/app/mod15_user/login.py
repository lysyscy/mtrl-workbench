"""`MOD-15` **登录**的动作出口。

⚠️ 判定放这里（⛔ 不放壳里、也不放路由里）：与 `repository`/`domain` 一样，
   路由只是**形状**，规则只有一个地方。

⚠️⚠️ **能登录的条件**（三条缺一不可 —— 少一条都会出现"能登进去但不该登进去"的形态）：
  ① 账号**存在**；
  ② **不是"已删除"**（§1.5.1 软删 = 账号名保留但**不可用**）；
  ③ **不是"已停用"**（§1.5.1「停用 = **暂不可登录**、可再启用」← 这句话就是本条的依据）。
  ⚠️ ②③ 都拦、但**提示必须不一样** —— 用户要知道"是被停用了（找管理员启用）"
     还是"被删了（找管理员恢复）"，否则只会看到一句"登录失败"、无从下手。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import MustReportError
from app.mod15_user import domain as D
from app.mod15_user import repository as R
from app.mod15_user.models import UserAccount

#: 提示语统一在这里 —— ⚠️ **不区分**"账号不存在"与"密码不对"（那会告诉别人
#: "这个账号是存在的"，是登录框的经典错误）。⛔ 别为了"友好"把它拆开。
BAD_CREDENTIALS = "账号或密码不正确。"


def sign_in(s: Session, *, account: str, password: str) -> UserAccount:
    """登录 ⇒ 返回账号行（⚠️ 由调用方负责下 cookie；本函数**不碰 HTTP**）。

    ⚠️ 密码是**明文**（用户 2026-09-20 裁定）⇒ 这里就是 `==` 比较。
       ⚠️ 明文下的一个重要后果：**空密码账号**（§1.5.1「密码可为空」）
       ⇒ 空着也能登进去 —— 那是**口径允许**的（"无格式要求、可为空"），
       ⛔ 不是漏洞，别在这里"顺手"加一道非空校验。
    """
    acc = D.normalize_account(account)
    row = R.by_account(s, acc)
    if row is None or (row.password or "") != (password or ""):
        raise MustReportError(BAD_CREDENTIALS)
    if D.is_deleted(row):
        raise MustReportError(
            f"账号「{row.account}」**已被删除**（软删）—— 账号名还保留着，"
            "但不能再登录。请让管理员**恢复**它。")
    if row.status == D.STATUS_DISABLED:
        raise MustReportError(
            f"账号「{row.account}」**已停用** —— 停用 = 暂不可登录（§1.5.1），"
            "请让管理员**启用**后再试。")
    return R.touch_login(s, row.id)          # ⭐ 「最近登录」只在**成功这一刻**记一次


__all__ = ["BAD_CREDENTIALS", "sign_in"]
