"""`ACC-USR-MGMT-001`（`MOD-15`）· **管理员闸**的验收断言（§1.5.1 · 用例 `001-02`）。

⚠️ **2026-09-21 自 `test_acc_usr_mgmt.py`（751 行）整块搬出**（`T5` 拆分）—— **断言一字未改**。

两半：
① **管理动作齐备**（建号 / 改密 / 停用启用 / 删除 / 转让管理员）且**不设业务权限配置界面**；
② ⭐ **只有在用管理员能管理账号，且不靠按钮禁用** —— 防线在**域层** ⇒ 直接调写操作也必须被拦。

⚠️ `_admin` 助手的**主人是 `test_acc_usr_mgmt.py`** —— 这里 `import` 过来，⛔ 不另造一份
   （同 `tests.test_classify._rec` 的做法：形状只有一份，别处照抄必然漂）。
"""

from __future__ import annotations

import pytest

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod15_user import domain as D
from app.mod15_user import repository as R
from tests.acc_plugin import acc
from tests.test_acc_usr_mgmt import _admin


@acc("ACC-USR-MGMT-001", "001-02")
def test_管理动作齐备且不设业务权限配置():
    """claim：「**管理动作齐备**（建号 / 改密 / 停用启用 / 删除 / 转让管理员），
    且**不设业务权限配置界面**」（§1.5.1 —— 「两人业务权限**无区别**」）

    ⚠️ 两半各钉各的：
    **① 「齐备」** ⇒ 钉在 **`APIRouter` 自己的路由表**上（⛔ 不是"我搜了一眼源码里有这些函数"）——
       函数存在 ≠ 挂上了端点；只有当**每个动作都有可调用的端点**时，"齐备"才成立。
    **② 「不设业务权限配置」** ⇒ ⭐ 钉在 **建号入口的字段集**上：
       若 `CreateIn` 里出现 `role`/`perm*`，那"两人权限无区别"就**当场被推翻**
       （有字段就迟早有界面）⇒ 这一条比"扫一遍页面找权限设置控件"**硬得多、也稳得多**。
    """
    from app.mod15_user.api import CreateIn, router as m15_router

    paths = {getattr(r, "path", "") for r in m15_router.routes}
    actions = {
        "建号": "/api/m15/actions/create",
        "改密": "/api/m15/actions/password",
        "停用启用": "/api/m15/actions/status",
        "删除": "/api/m15/actions/delete",
        "转让管理员": "/api/m15/actions/transfer",
    }
    missing = [name for name, p in actions.items() if p not in paths]
    assert not missing, (
        f"这些管理动作**没有端点**：{missing}（claim 要求「管理动作齐备」）"
        f"\n  实际端点：{sorted(paths)}")
    assert "/api/m15/users" in paths, "没有整页数据的读端点"

    # ② ⛔ 不设业务权限配置 —— 建号入口**不许有角色/权限字段**
    fields = set(CreateIn.model_fields.keys())
    forbid = {f for f in fields if f == "role" or f.startswith(("perm", "can_", "allow_", "scope"))}
    assert not forbid, (
        f"建号入口出现了 {sorted(forbid)} —— §1.5.1「两人业务权限**无区别**」"
        "⇒ 新增账号**一律普通用户**、**不需要选角色**（claim `001-02` 后半句）。"
        "⚠️ 有字段就迟早有界面 —— 这是「不设权限配置」最靠前的那道闸。")
    assert fields >= {"account", "name", "password"}, f"建号入口字段不全：{sorted(fields)}"

    # ②b 整个 mod15 模块里⛔ 不得出现"权限配置"类端点
    import pathlib

    import app
    mod = pathlib.Path(app.__file__).resolve().parent / "mod15_user"
    import re
    bad = []
    for p in sorted(mod.glob("*.py")):
        for k, ln in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"@router\.(get|post)\([^)]*(perm|scope|role[s]?/)", ln, re.I):
                bad.append(f"{p.name}:{k}  {ln.strip()[:60]}")
    assert not bad, f"mod15 里出现了权限配置端点：{bad}"

    # ③ ⭐ 「齐备」还意味着**真的可用**：用户能触发到的拒绝必须是 `MustReportError`
    #    （API 把它转成 `ok=False` ＋ 原文给用户看），⛔ 不是 `ValueError` —— 那会变成 **HTTP 500**，
    #    用户只看到"请求失败"、原因全丢了。
    #    ⭐ 这条是**真机冒烟抓出来的**：拿一个不存在的 id 调改密 ⇒ 500（而不是"账号不存在"）。
    import inspect

    from app.mod15_user import api as API
    src = inspect.getsource(API._run)
    assert "except AppError" in src, (
        "写动作的兜底没在吞 `AppError` ⇒ 业务拒绝会变成 500（原文就丢给用户看不见了）")
    with session_scope() as s:
        _admin(s)
        actor = D.active_admins(R.all_users(s))[0]
        for label, call in (
            ("改密", lambda: R.set_password(s, 999999, "x")),
            ("停用", lambda: R.set_status(s, 999999, D.STATUS_DISABLED)),
            ("删除", lambda: R.soft_delete(s, 999999, actor=actor)),
            ("恢复", lambda: R.restore(s, 999999)),
            ("状态取值非法", lambda: R.set_status(s, actor.id, "已删除")),
        ):
            # ⚠️ 逐个点名：`pytest.raises(MustReportError)` 会在抛别的异常时**照样红**，
            #    所以这里不需要额外断言"不是 ValueError" —— 它**本来就**只放行这一种。
            with pytest.raises(MustReportError):
                call()
        s.rollback()


@acc("ACC-USR-MGMT-001", "001-02")
def test_只有在用管理员能管理账号_且不靠按钮禁用():
    """claim：「**管理员** | 用户本人为管理员，**可管理其他账号**」（§1.5.1）—— 由 `001-02` 认领。

    ⚠️⚠️ 这条是**片 4b 接壳时照出来的一处口径缺口**：原型只在**壳里**判 `CUR.role!=='admin'`，
       而后端 6 个写动作**谁调都执行** ⇒ ⭐ 正是 claim `001-07` 说的
       「**直接调写操作也必须被拦，不只靠按钮禁用**」的同一个道理。
       ⇒ 本轮补上 `domain.assert_is_admin`，并在这里钉住它。

    ⚠️ 两半都要钉：**非管理员**要拒；**在用管理员**要放行（⛔ 否则就成了"一律拒"的摆设）。
    ⚠️ 还有一条**最容易漏的**：`actor` 取不到时**必须拒**（⛔ 不能"没人就当管理员"）——
       而它偏偏最容易在"兜底"里被放行：片 4b 之前，`delete`/`transfer` 写的是
       `actor or R.ensure_seeded(s)` ⇒ **取不到当前用户就拿首个管理员顶替** ⇒
       那道闸**等于没有**（⭐ 已删掉那个兜底）。
    """
    from app.mod15_user import api as API

    with session_scope() as s:
        R.ensure_seeded(s)
        admin = D.active_admins(R.all_users(s))[0]
        plain = R.create(s, account="__自检_非管理员__", name="非管理员", password="")
        deleted = R.create(s, account="__自检_已删管理员__", name="已删管理员")
        deleted.role = D.ROLE_ADMIN                         # ⚠️ 直接改字段：`transfer` 那条路有"恒一个"约束，这里只想造个"已删的管理员"
        R.soft_delete(s, deleted.id, actor=admin)           # 已删的管理员
        disabled = R.create(s, account="__自检_停用管理员__", name="停用管理员")
        disabled.role = D.ROLE_ADMIN
        R.set_status(s, disabled.id, D.STATUS_DISABLED)
        s.flush()

        # ① 非管理员 / 已删 / 已停用 / 取不到 —— **四种都要拒**
        for label, who in (("普通用户", plain), ("已删除的管理员", deleted),
                           ("已停用的管理员", disabled), ("取不到当前用户", None)):
            with pytest.raises(MustReportError) as e:
                D.assert_is_admin(who)
            assert "管理员" in str(e.value), f"{label} 被拒了，但提示里没说要管理员"
        # ② 在用的管理员 ⇒ 放行（⛔ 不然就是"一律拒"）
        D.assert_is_admin(admin)

        # ③ ⭐ **走 API 那一层**也要被拦（⛔ 不只是 domain 函数会拒）
        real = API._me
        API._me = lambda _s: plain                          # 冒充普通用户在调接口
        try:
            res = API.api_create(API.CreateIn(account="__自检_不该建成__"))
        finally:
            API._me = real
        assert res["ok"] is False, "普通用户**通过 API** 建号竟然成功了 —— 后端没设闸"
        assert "__自检_不该建成__" not in [u.account for u in R.all_users(s)], "被拒了却真建了行"
        s.rollback()
