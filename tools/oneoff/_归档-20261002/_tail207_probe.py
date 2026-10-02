"""`TAIL-207` **真机复现**：普通用户改**自己**的密码（走真 HTTP，⛔ 不绕过接口直调库）。

用户 2026-10-01 报：「**207 不行，普通用户点击改密显示只有管理员可以管理账号**」
⇒ 本件照出**它到底走的哪条分支**（`me is None`？还是 `me.id != uid`？）。

⚠️ 非破坏性：自检账号是 `__自检_207普通用户__`（跑完**软删**回收站，⛔ 不碰任何真账号）。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import requests  # noqa: E402

from app.core.db import session_scope  # noqa: E402
from app.mod15_user import domain as D  # noqa: E402
from app.mod15_user import repository as R  # noqa: E402

BASE = "http://127.0.0.1:8000"
ACC = "__自检_207普通用户__"
PW0, PW1 = "旧密207", "新密207"


def _find(s, acc):
    return next((u for u in R.all_users(s) if u.account == acc), None)


# ---------- ① 备一个普通用户（幂等）＋ 取管理员口令（明文口径 §1.5.1） ----------
with session_scope() as s:
    R.ensure_seeded(s)
    admin = D.active_admins(R.all_users(s))[0]
    adm_id, adm_acc, adm_pw = admin.id, admin.account, (admin.password or "")
    u = _find(s, ACC)
    if u is None:
        u = R.create(s, account=ACC, name="自检207", password=PW0)
    else:
        if D.is_deleted(u):
            R.restore(s, u.id)
        R.set_status(s, u.id, D.STATUS_ACTIVE)
        R.set_password(s, u.id, PW0)
    s.flush()
    plain_id = u.id
print(f"准备：管理员 = {adm_acc}(id={adm_id}) · 普通用户 = {ACC}(id={plain_id}) 口令={PW0}")

H = {"Accept": "application/json"}

# ---------- ② 以普通用户登录 ----------
c = requests.Session()
r = c.post(f"{BASE}/m15/login", headers=H,
           data={"account": ACC, "password": PW0, "next": "/app"}, allow_redirects=False, timeout=15)
print(f"\n② 普通用户登录：HTTP {r.status_code} · 跳转={r.headers.get('location')!r} · cookie={sorted(c.cookies.keys())}")
assert r.status_code in (302, 303, 307), "普通用户没登上 —— 先解决登录，别往下猜"

# ---------- ③ 接口眼里的"我是谁"（关键诊断） ----------
r = c.get(f"{BASE}/api/m15/users", headers=H, timeout=15)
try:
    js = r.json()
    me = js.get("me")
    print(f"③ GET /api/m15/users ⇒ `me` = {me!r}")
    print(f"   （若 `me` 为 None ⇒ 是**会话没被这个端点认出来**；若 `me.id` ≠ {plain_id} ⇒ 是**认错了人**）")
except Exception as e:  # noqa: BLE001
    print(f"③ GET /api/m15/users ⇒ HTTP {r.status_code} · 非 JSON：{r.text[:200]}（{e}）")

# ---------- ④ 改【自己】的密码 ----------
r = c.post(f"{BASE}/api/m15/actions/password", headers=H,
           json={"id": plain_id, "password": PW1}, timeout=15)
print(f"\n④ 改【自己】(id={plain_id}) 的密码 ⇒ HTTP {r.status_code} · {r.text[:300]}")

# ---------- ⑤ 改【别人】的密码（应当拒） ----------
r = c.post(f"{BASE}/api/m15/actions/password", headers=H,
           json={"id": adm_id, "password": "不该改成这样"}, timeout=15)
print(f"⑤ 改【别人】(id={adm_id}) 的密码 ⇒ HTTP {r.status_code} · {r.text[:300]}")

# ---------- ⑥ 新密码到底生效没有 ----------
c2 = requests.Session()
r = c2.post(f"{BASE}/m15/login", headers=H,
            data={"account": ACC, "password": PW1, "next": "/app"}, allow_redirects=False, timeout=15)
ok_new = r.status_code in (302, 303, 307)
print(f"⑥ 用**新**密码登录 ⇒ HTTP {r.status_code} · 跳转={r.headers.get('location')!r} ⇒ {'✅ 生效' if ok_new else '❌ 没生效'}")

# ---------- ⑦ 清理：软删自检账号 ----------
c3 = requests.Session()
c3.post(f"{BASE}/m15/login", headers=H,
        data={"account": adm_acc, "password": adm_pw, "next": "/app"}, allow_redirects=False, timeout=15)
r = c3.post(f"{BASE}/api/m15/actions/delete", headers=H, json={"id": plain_id}, timeout=15)
print(f"\n⑦ 清理（软删自检账号）⇒ HTTP {r.status_code} · {r.text[:200]}")
