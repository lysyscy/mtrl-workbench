"""`TAIL-207` **浏览器完整流程**：普通用户点「改密」→ 弹窗 → 存 → 真生效？

用户 2026-10-01 报「207 不行，普通用户点击改密显示只有管理员可以管理账号」——
⭐ 真因 = **壳里那道动作闸**（`ACT.userPwd` 里的 `if(CUR.role!=='admin')`）**没跟按钮一起放开**：
   按钮亮了（改了置灰条件），一点却被壳**自己**弹走（后端两个端点本来就放行"本人"）。
⚠️ 本件**必须走完整流程**（点下去 + 保存 + 验新密码），⛔ 只照"按钮亮不亮"会漏掉这个坑
   —— 2026-10-01 我第一次就是这么漏的（只照了亮灭 ⇒ 漏看"一点就弹走"）。

⛔ 自建自清：自检账号跑完软删。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "tools" / "probe"))

import requests  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from app.core import session as SESS  # noqa: E402
from app.core.db import session_scope  # noqa: E402
from app.mod15_user import domain as D  # noqa: E402
from app.mod15_user import repository as R  # noqa: E402

BASE = "http://127.0.0.1:8000"
ACC = "__自检_207普通用户__"
PW0, PW1 = "旧密207", "新密207b"

with session_scope() as s:
    R.ensure_seeded(s)
    u = next((x for x in R.all_users(s) if x.account == ACC), None)
    if u is None:
        u = R.create(s, account=ACC, name="自检207", password=PW0)
    else:
        if D.is_deleted(u):
            R.restore(s, u.id)
        R.set_status(s, u.id, D.STATUS_ACTIVE)
        R.set_password(s, u.id, PW0)
    s.flush()
    who, uid = (u.name or u.account), int(u.id)
print(f"普通用户 = {who}(id={uid})")

with sync_playwright() as p:
    b = p.chromium.launch(args=["--no-sandbox"])
    page = b.new_page()
    page.context.add_cookies([{"name": SESS.COOKIE_NAME, "value": SESS.make(who), "url": BASE}])
    page.goto(f"{BASE}/app", wait_until="networkidle")
    from _shell_common import goto
    goto(page, "m15")
    page.wait_for_timeout(500)

    btn = page.query_selector(f'[data-act="userPwd"][data-id="{uid}"]')
    print(f"\n① 自己那行的「改密」按钮：{'找到' if btn else '⛔ 没找到'} · 灰={btn.is_disabled() if btn else None}"
          f" · title={(btn.get_attribute('title') if btn else '')!r}")
    btn.click()
    page.wait_for_timeout(500)

    # ② 点下去之后：是**弹窗**（对）还是**被壳自己弹走**（错）？
    has_modal = page.evaluate("() => !!document.querySelector('#upV')")
    t0 = page.evaluate("() => { const t=document.querySelector('.toast'); return t? t.innerText : ''; }")
    print(f"② 点后：弹窗在={has_modal} · toast={t0[:120]!r}")
    if not has_modal:
        print("   ⛔ **没弹出改密弹窗** ⇒ 壳里那道动作闸又把本人挡了（正是用户报的这件事）")
        b.close()
        raise SystemExit(1)

    # ③ 填新密码并保存
    page.fill("#upV", PW1)
    page.click('[data-act="userPwdOk"]')
    page.wait_for_timeout(1500)
    t1 = page.evaluate("() => { const t=document.querySelector('.toast'); return t? t.innerText : ''; }")
    print(f"③ 保存后 toast = {t1[:200]!r}")
    b.close()

# ④ 真生效吗（走真登录，⛔ 不看界面说了什么）
c = requests.Session()
r = c.post(f"{BASE}/m15/login", data={"account": ACC, "password": PW1, "next": "/app"},
           allow_redirects=False, timeout=15)
ok = r.status_code in (302, 303, 307)
print(f"④ 用新密码登录 ⇒ HTTP {r.status_code} ⇒ {'✅ 真生效' if ok else '❌ 没生效'}")

# ⑤ 清理
with session_scope() as s:
    row = next((x for x in R.all_users(s) if x.account == ACC), None)
    if row is not None and not D.is_deleted(row):
        R.soft_delete(s, row.id, actor=D.active_admins(R.all_users(s))[0])
print("⑤ 已软删自检账号")
