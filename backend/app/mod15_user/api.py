"""`MOD-15` 用户管理的 **JSON API** —— 前端壳直接接数据（同 `mod07` / `mod09` / `mod11` 的做法）。

⚠️ 本层**不写任何判定**：全部调 `repository`，而 `repository` 又调 `domain` 的断言
   （claim `001-07` 那句「**直接调写操作也必须被拦**」在这里表现为：**API 里没有第二份校验**）。

⚠️ 写动作**恒 HTTP 200**，成败看 `ok` 标志（同 `mod03` / `mod07` / `mod09` 的约定）——
   「账号重复」「不能停用最后一个管理员」都是 §1.5.1 规定的**可预期的拒绝**，
   要把那句话**原样给用户看**；若回 HTTP 400，壳只会看到"请求失败"、原因就丢了。

⚠️⚠️ **出参一律不带密码**（⛔ 连 `i8_password` 也不带）—— 列表接口是**最容易被顺手带出去**的地方。
   明文裁定的理由之一是"管理员能读出密码告诉用户"，但**壳里并没有这个出口**
   （列表列是 登录账号/姓名/角色/状态/最近登录/操作）⇒ ⛔ 我不自己发明一个"查看密码"端点；
   要不要给这个出口**登记待裁定**（见计划）。

⚠️ 关于「**当前登录用户**」（⭐ 2026-09-21 更新，旧说明已作废）：
   登录态已接上（登录页 ＋ 自签 cookie ＋ 中间件）⇒ 本层**只看登录态**
   （`core/session.current_name()` ＋ `repository.by_identity`）；
   ⛔ **没有会话就返回 `None`** —— 不再回落到"首个在用管理员"（见 `_me` 的注释：那个回落
   会让**任何不带 cookie 的请求**拿到管理员权限）。

⚠️ ⚠️ 本页**不设业务权限配置**（§1.5.1「两人业务权限**无区别**」）⇒ 本文件里⛔ 不会有
   任何 "权限 / perm / scope" 之类的端点或字段 —— claim `001-02` 后半句的机械化落点。
"""

from __future__ import annotations

import re

from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel

from app.core import session as SESS
from app.core.db import session_scope
from app.core.errors import AppError, MustReportError
from app.mod15_user import domain as D
from app.mod15_user import login as LG
from app.mod15_user import repository as R
from app.mod15_user.models import UserAccount
from app.mod15_user.page import login_html

router = APIRouter(tags=["mod15"])


# ============================================================ 形状


def _row(u: UserAccount) -> dict:
    """一个账号 → JSON。

    ⚠️⚠️ **逐个字段列出来**（⛔ 不是 `{c.name: getattr(u, c.name)}` 那种"整个模型倒出去"）——
       后者会在**下一次加列**时（比如加个 `token` / `reset_code`）**静默**把新字段泄出去。
       ⭐ 白名单是"默认安全"的写法：漏列一个字段，用户看得见（少一列）；
         黑名单漏一个，**没人看得见**（除非出事）。
    """
    return {
        "id": u.id,
        "account": u.account,
        "name": u.name,
        "role": u.role,
        "state": D.state_of(u),                 # 三态：在用 / 已停用 / 已删除
        "deleted": D.is_deleted(u),
        "deleted_by": u.deleted_by or "",
        # ⚠️ i8 账号**只出账号名、不出密码**（§7.8：每人一份 ⇒ 界面要能看出"还没填"）
        "i8_user": u.i8_user or "",
        "i8_bound": bool((u.i8_user or "").strip()),
        # 最近登录（⭐ 2026-09-20 补口径）：**空串 = 从未登录过**。
        # ⚠️ 空串与"有值"要区分得出来 —— ⛔ 别用建号时间冒充（那是假话），
        #    也别把"从未登录"渲染成 `—`（那长得像"数据没取到"）。
        "last_login_at": (u.last_login_at.strftime("%Y-%m-%d %H:%M") if u.last_login_at else ""),
    }


def _me(s) -> UserAccount | None:
    """**当前登录用户** → 账号行（走 `repository.by_identity` —— 那是**唯一**的身份判定出口）。

    ⭐⭐ 2026-09-21（用户裁定「**收紧：未登录不回落首个管理员**」）——
       **身份判定只认登录态**（`core/session.current_name()`）：⛔ 没有会话就**返回 `None`**。

    ⚠️⚠️ 为什么必须掐掉那个回落（**实测复现过**）：原先"名字对不上账号"时会**回落到首个在用管理员**
       ⇒ 于是**任何人**——**连 cookie 都没有的请求**——都会被当成**管理员**：
       不带 cookie 调 `/api/m15/users`，返回的 `me` 就是那行 admin。
       而所有写动作的闸都是 `assert_is_admin(_me(s))` ⇒ **建号 / 删号 / 停用 / 转让管理员全部放行**。
       登录页上线之后（片 3），这条兜底**只会掩盖"会话丢了"**，不再有任何存在理由。

    ⚠️ 与 `core/identity.py::current_operator()` 的**分工**（⛔ 别把两者混成一件，它们是两套口径）：
       · `current_operator()` 管「**留痕写谁**」—— 它**保留** `.env` / 占位兜底：
         定时抓取、命令行脚本、测试进程都不带 cookie，删了兜底它们会把留痕写成人空；
       · 本函数管「**谁有权**」—— **只认登录态**，⛔ 不碰 `.env`、⛔ 不回落到任何人。

    ⚠️ 取不到会话时**各处行为本来就已经写好了**（本轮**没新增分支**）：写动作被
       `assert_is_admin(None)` 拒；主题落 `D.effective_theme(None)` = 默认套
       （那个函数的注释里早就写了"③ `u` 为 `None`（没登录）⇒ 回落默认套"）；
       壳的 `CUR` 为空 ⇒ 顶栏「身份未取到」＋ 按钮禁用（`V.m15` 也早有这条分支）。
    """
    from app.core.session import current_name

    who = current_name()  # 保留账号/旧标签类型；直接strip会丢掉新票的账号语义。
    if not who:
        return None
    return R.by_identity(s, who)


def _payload(s) -> dict:
    """整页数据：账号列表 ＋ 当前登录用户 ＋ 三态计数。

    ⚠️ 返回**全部**账号（**含已删除**）—— §1.5.1 说软删后"账号名保留、历史留痕里的人名仍认得出来"，
       页面上也要能看见那一行（`V.m15` 里就有"已删除"这一态和"恢复"按钮）。
       ⛔ 别在这里"默认过滤掉已删除的"。
    """
    me = _me(s)
    users = R.all_users(s)
    return {
        "users": [_row(u) for u in users],
        # ⭐ 2026-09-27（`TAIL-129`）：**当前登录用户**这一块多带两项**界面偏好**（主题 ＋ 界面大小）。
        #    ⚠️ 为什么挂在这里：`/api/m15/users` 是**启动时就会拉**的那一路（壳 `boot()` 的
        #    `reloadWho`）⇒ 界面大小**首屏就生效**，⛔ 不必为它新开一路请求（也别塞进
        #    `PAGE_LOAD['set']` —— 那样只有进过设置页才生效，正是主题踩过的那个坑）。
        #    ⚠️ `ui_scale_css` 是**倍率字符串**（给 CSS `--fscale` 直接用）：壳⛔ 不拿键去查表。
        "me": (None if me is None else {
            **_row(me),
            "theme": D.effective_theme(me),
            "ui_scale": D.effective_ui_scale(me),
            "ui_scale_css": D.ui_scale_css(me),
        }),
        "counts": {
            "total": len(users),
            "active": sum(1 for u in users if D.state_of(u) == D.STATUS_ACTIVE),
            "disabled": sum(1 for u in users if D.state_of(u) == D.STATUS_DISABLED),
            "deleted": sum(1 for u in users if D.is_deleted(u)),
        },
        "roles": list(D.ROLES),
        "states": [D.STATUS_ACTIVE, D.STATUS_DISABLED, D.STATE_DELETED],
    }


def _flash(kind: str, message: str) -> dict:
    return {"ok": kind == "ok", "kind": kind, "message": message}


def _run(fn) -> dict:
    """跑一个写动作：**可预期的拒绝**返回 `ok=False` ＋ 原文（⛔ 不抛 400）。

    ⚠️ 只吞 `AppError`（业务可预期）—— ⛔ 别写成裸 `except Exception`：
       那会把真 bug（`AttributeError` / 库错误）也变成一句"操作失败"，从此没人查得动。
    """
    try:
        return _flash("ok", fn() or "已完成")
    except AppError as e:
        return _flash("err", e.message)


# ============================================================ 登录 / 登出（§1.5.1）


def _safe_next(raw: str) -> str:
    """把 `?next=` **收窄到站内路径**（⛔ 防开放跳转）。

    ⚠️ 只放行**以单个 `/` 开头**的值 —— `//evil.com` 与 `https://evil.com` 都要拒掉：
       前者在浏览器里会被当成**协议相对的绝对地址**（`//host/path`），是开放跳转的经典绕过。
    """
    v = (raw or "").strip()
    if v.startswith("/") and not v.startswith("//"):
        return v
    return "/app"


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
def api_login_page(next: str = "/app") -> HTMLResponse:  # noqa: A002 —— 名字照 §1.5.1 的用法
    """登录页（§1.5.1「退出后**回到登录页**」）。"""
    return HTMLResponse(login_html(next_url=_safe_next(next)))


@router.post("/m15/login", include_in_schema=False)
def api_do_login(account: str = Form(""), password: str = Form(""),
                 next: str = Form("/app")) -> Response:  # noqa: A002
    """**登录动作**（纯表单 POST ⇒ 303 回跳；⛔ 不用 JS —— 见 `page.py` 顶部说明）。

    ⚠️ 失败时**回登录页并带一句原因**（⛔ 不是 JSON）—— 这是**表单**路径，
       浏览器只会显示返回的 HTML；回 JSON 的话用户看到一屏 `{"ok":false,...}`。
    """
    target = _safe_next(next)
    try:
        with session_scope() as s:
            row = LG.sign_in(s, account=account, password=password)
            account_identity = row.account
    except AppError as e:
        return HTMLResponse(login_html(error=e.message, next_url=target),
                            status_code=200)                 # ⚠️ 200：浏览器要正常渲染这一页
    resp = RedirectResponse(target, status_code=303)          # 303 = POST 之后换 GET（PRG）
    resp.set_cookie(
        SESS.COOKIE_NAME, SESS.make(account_identity),
        max_age=SESS.COOKIE_MAX_AGE_SECONDS,
        httponly=True,          # ⛔ JS 读不到（壳里不需要读它）
        samesite="lax",         # ⛔ 跨站请求不带它（CSRF 的第一道）
        # ⚠️ `secure=False`：本系统是**局域网 http**（§技术栈：内网部署）——
        #    设 True 会让 cookie 在 http 下**完全不发**，那是"配了安全、结果登不上"。
        secure=False,
        path="/",
    )
    return resp


@router.post("/api/m15/logout")
def api_logout(request: Request) -> dict:  # noqa: ARG001 —— 与别的写动作同形
    """**登出**（§1.5.1）—— ⚠️ 只清 cookie，**不碰任何业务数据**（"退出后业务数据不受影响"）。

    ⚠️ 返回 `{ok, message}` 同本模块其它写动作；⭐ **清 cookie 由本端点自己做**
       （壳那边只管发请求、看到 `ok` 就跳登录页 —— 让壳去清 cookie 就多一份"清法"）。
    """
    from fastapi.responses import JSONResponse

    out = JSONResponse({"ok": True, "kind": "ok", "message": "已退出登录"})
    out.delete_cookie(SESS.COOKIE_NAME, path="/")
    return out


# ============================================================ 主题（`ACC-UI-THEME-001/001-06`）


def _palette(name: str) -> dict:
    """一套主题的**配色标本**（给壳的「每套一张卡」用）—— ⭐ 2026-09-21 加。

    ⚠️⚠️ 取值一律从 `page.render_theme(name)` 里**解析**（唯一真源），
       ⛔ **不在这里、也不在壳里写死任何色值** —— 主题名的合法性、取值都只有一处主人
       （`mod03_notice.page`，`ACC-UI-THEME-001/001-03`「单一真源」钉着它）。
    ⚠️ 为什么要给这么几个角色（而不是只给主色）：用户 2026-09-21 反馈「换主题**感觉不到颜色变化**」——
       真因是**浅色系那几套只差一个主色**，在满屏表格里看不出来。
       ⇒ 让每一套用它**自己的一小片配色**（底色 / 表面 / 边框 / 文字）画一张卡，
         明暗差异**一眼可见**（深色系那几套尤其明显）。
    """
    from app.mod03_notice import page as P

    css = P.render_theme(name)
    out = {"name": name}
    for key in ("pri", "bg", "sf", "bd", "tx", "on"):
        m = re.search(rf"--{key}:\s*([^;\n]+);", css)
        out[key] = (m.group(1).strip() if m else "")
    # ⭐ **适用场景 / 设计风格**（用户 2026-09-21 要求「每个主题需明确其适用场景与设计风格」）——
    #   取自 `page.THEME_SPEC`（与种子表**同一处真源**），壳只负责显示。
    spec = P.THEME_SPEC.get(name) or {}
    out["scene"] = spec.get("scene", "")
    out["style"] = spec.get("style", "")
    return out


@router.get("/api/m15/theme")
def api_theme() -> dict:
    """**当前登录用户**的主题（＋ 可选清单 ＋ 每套的配色标本）。

    ⚠️ 返回的是"**该用哪套**"（`domain.effective_theme` 已经把"未设置 ⇒ 默认"判完了），
       ⛔ 不是原样回 `u.theme` —— 后者会在"未设置"时回一个空串，壳还得再判一次
       （那就又把那条口径复制到前端去了）。
    """
    from app.mod03_notice import page as P

    names = list(P.theme_names())
    with session_scope() as s:
        me = _me(s)
        return {
            "ok": True,
            "theme": D.effective_theme(me),
            "themes": names,
            "default": P.DEFAULT_THEME,
            # ⭐ 每套一张"配色标本"卡（见 `_palette` 的注释）—— 壳只负责画，取值全在这儿
            "palette": [_palette(n) for n in names],
            # ⭐⭐ 2026-09-27（`TAIL-129` 界面大小）：**档位清单的真源在后端**（`domain.UI_SCALES`）——
            #    壳拿它画按钮、⛔ 不写死档位映射（加一档要改两处就是两份真源）；
            #    `css` 是喂 `--fscale` 的倍率字符串（壳直接用，⛔ 不用键去查表）。
            "ui_scale": D.effective_ui_scale(me),
            "scales": [{"key": k, "label": lb, "css": css} for k, lb, css in D.UI_SCALES],
        }


class UiScaleIn(BaseModel):
    """界面大小**档位键**（`standard` / `large` / `larger` / `largest`）。"""

    ui_scale: str = ""


@router.post("/api/m15/ui-scale")
def api_set_ui_scale(req: UiScaleIn) -> dict:
    """存**自己的**界面大小档位（`TAIL-129` · 用户裁定走方案 B：字号＋行距走 CSS 变量）。

    ⚠️⚠️ **不接 `id`**（与主题那条同款）：只能改**当前登录用户自己**的那一行 —— 这正是
       「A 选了"更大"不妨碍 B 保持标准」的另一半（前半在"读的时候各读各的"）。
    ⚠️ 非法档位**显式拒绝**（`domain.assert_ui_scale_usable`）—— ⭐ 与主题的"非法名静默回落"
       **有意不同**：主题的乱名页面还看得见一套样式（用户能察觉），而界面大小的乱值
       **什么都不会发生**（`--fscale` 算不出来 ⇒ 看起来就是"点了没反应"）⇒ 必须当场说清。
    """
    with session_scope() as s:
        me = _me(s)
        if me is None:
            return _flash("err", "没有当前登录用户 —— 请先登录再改界面大小。")
        try:
            key = D.assert_ui_scale_usable(req.ui_scale)
        except MustReportError as exc:
            return _flash("err", str(exc))
        R.set_ui_scale(s, me.id, key)
        label = {k: lb for k, lb, _ in D.UI_SCALES}.get(key, key)
        return _flash("ok", f"界面大小已改为「{label}」")


class ThemeIn(BaseModel):
    """主题名；⭐ **空串合法** = 回到"未设置"（⇒ 跟着默认套走）。"""

    theme: str = ""


@router.post("/api/m15/theme")
def api_set_theme(req: ThemeIn) -> dict:
    """存**自己的**主题偏好。

    ⚠️⚠️ **不接 `id`** —— 本动作只能改**当前登录用户自己**的那一行，这正是
       「A 与 B 各自的选择**互不影响**」的另一半（前半在"读的时候各读各的"）。
       ⛔ 别"顺手"加一个可选 `id`（那会立刻变成"管理员能改别人主题"，
         而口径里没有这条，且它会让这条判据**测不出隔离**）。
    """
    with session_scope() as s:
        me = _me(s)
        if me is None:
            return _flash("err", "没有当前登录用户 —— 请先登录再选主题。")
        R.set_theme(s, me.id, req.theme)
        return _flash("ok", f"主题已改为「{D.effective_theme(me)}」")


# ============================================================ 读


@router.get("/api/m15/users")
def api_users(request: Request) -> dict:  # noqa: ARG001 —— 形状与别的模块一致（便于将来加筛选）
    """账号列表 ＋ 当前登录用户（`MOD-15` 的整页数据）。"""
    with session_scope() as s:
        return _payload(s)


# ⭐ 「查看密码」—— **明文裁定的显式出口**（2026-09-20 用户裁定「要加」）
#
# ⚠️ 为什么它是一个**单独的动作**、而不是让列表直接带出密码来：
#   ① **列表是最容易被看到的地方** —— 打开页面就全在屏上（还容易被截图/转发）；
#      单独动作则要**指名要哪一个**，多一道"用户确实是来看这个的"。
#   ② 密码是**明文**（用户裁定）⇒ 它**必须能被管理员读出来告诉同事**（这也是选明文的原因之一）
#      —— 那就得有一个**说得清**的出口，⛔ 而不是"藏在某个大对象里顺带泄出去"。
#   ③ 出参形状上它与列表**互不影响** ⇒ 将来要加"看密码要留痕"之类，改这一个端点即可。


@router.get("/api/m15/password")
def api_view_password(id: Any = 0) -> dict:
    """**查看某个账号的密码**（明文 —— 供管理员告诉同事）。

    ⚠️ 这是**有意的**出口：本系统是科室内部 2 人的局域网工具（§1.5.1），
       密码是管理员**帮同事建号/重置**的产物 ⇒ "读出来念给他"是**正常运维动作**。
    ⚠️ 但它**只出一个账号的密码**（⛔ 不提供"列出全部密码"）——
       "看一个"与"一次拿到全表"的风险差一个量级，⛔ 别顺手加后者。
    """
    def go():
        with session_scope() as s:
            row = R.get(s, _uid(id))
            if row is None:
                raise AppError(f"账号不存在：id={id!r}")
            if D.is_deleted(row):
                raise AppError(f"账号「{row.account}」**已删除** —— 先恢复它再看密码。")
            return {"ok": True, "kind": "ok", "account": row.account, "name": row.name,
                    "password": row.password or "", "has_password": bool(row.password or ""),
                    # ⭐ 2026-09-21：**同一个出口带出 i8 绑定**（§7.8「每人一份」）——
                    #   ⚠️ 仍只出**一个账号**的、仍要**指名要哪一个**；⛔ 不提供"列出全部"。
                    #   与系统密码放在同一个动作里，是因为对管理员而言那是**同一件运维事**
                    #   （"把这个同事的凭据念给他"）—— ⛔ 分成两个弹窗只会更绕。
                    "i8_user": row.i8_user or "", "i8_password": row.i8_password or "",
                    "i8_bound": bool((row.i8_user or "").strip()),
                    "i8_has_password": bool(row.i8_password or "")}
    try:
        return go()
    except AppError as e:
        return _flash("err", e.message)


# ============================================================ 写（5 类管理动作 · §1.5.1）


class CreateIn(BaseModel):
    """建号：账号（**非空 + 不重复**，⛔ 不限格式与长度）＋ 姓名 ＋ 初始密码（**可为空**）。"""

    account: str = ""
    name: str = ""
    password: str = ""


class IdIn(BaseModel):
    """只认一个账号 id（删除 / 恢复 / 转让）。"""

    id: Any = 0


class PwdIn(BaseModel):
    """改密：⚠️ `password` **无格式要求**（⛔ 不 strip —— 前后空格也是密码的一部分）。"""

    id: Any = 0
    password: str = ""


class I8In(BaseModel):
    """i8 绑定（§7.8）：账号 ＋ 密码。

    ⚠️⚠️ `i8_password=None`（**请求里省略**）⇒ **不改密码**；空串 ⇒ 清空。
       理由见 `repository.set_i8`：列表出参不带 i8 密码 ⇒ 界面上那个框是空的，
       把"空"当成"清空"会让"只改账号"这一步**静默抹掉**同事的 i8 密码。
    ⚠️ `i8_user` 空串 = 解绑（⇒ 抓取回落 `.env`），**密码一并清空**。
    """

    id: Any = 0
    i8_user: str = ""
    i8_password: str | None = None


@router.post("/api/m15/actions/i8")
def api_set_i8(req: I8In) -> dict:
    """**绑定 / 解绑某个账号的 i8 账号密码**（§7.8：「i8 的账号与密码…**绑定到本系统账号、每人一份**」）。

    ⭐ 这是**"每人一份"的写入出口**；读取出口是 `core/identity.py::current_i8_credentials()`
      （抓取 / 导出**建会话时**才取 —— 见 `mod02_i8/client.py` 的 `_creds`）。

    ⚠️ 闸与「改密」同款（§1.5.1）：**改自己的**不用管理员（同事要能自己填自己的 i8 账号），
      改**别人**的要管理员。⛔ 别把这条收得太紧 —— 那会变成"必须麻烦管理员才能填自己的账号"。
    ⚠️ 出参**不回密码**（同列表口径）：只回一句"已绑定 / 已解绑（未填 ⇒ 抓取会被拦下并提示先填）"。
    """
    def go() -> str:
        with session_scope() as s:
            me = _me(s)
            uid = _uid(req.id)
            if me is None or me.id != uid:
                D.assert_is_admin(me)
            u = R.set_i8(s, uid, i8_user=req.i8_user, i8_password=req.i8_password)
            who = u.name or u.account
            if (u.i8_user or "").strip():
                return f"{who} 的 i8 绑定已保存：账号「{u.i8_user}」" + (
                    "" if (u.i8_password or "") else
                    "（i8 密码为空 —— 抓取时会拿它去登录 i8，登录会失败）")
            return (f"{who} 的 i8 绑定已清空 —— 之后抓取会被拦下并提示先填"
                    "（不会改用共享账号顶掉别人的会话，§7.8 · 2026-09-30 起）")
    return _run(go)


class StatusIn(BaseModel):
    """停用 / 启用（≤ 两个动作；`已删除` 不在这里 —— 那是"删除"，见 `/delete` 与 `/restore`）。"""

    id: Any = 0
    status: str = ""


def _uid(x: Any) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        raise AppError(f"账号 id 不合法：{x!r}") from None


@router.post("/api/m15/actions/create")
def api_create(req: CreateIn) -> dict:
    """**建号**（§1.5.1 管理动作之一）——新账号**一律「在用 · 普通用户」**（claim `001-04`）。

    ⚠️ ⛔ **不接受 `role`**：管理员只能靠**转让**产生（§1.5.1「恒只有一个管理员」）
       ⇒ API 里就没有"建一个管理员"这条路（有入口就有人用）。
    """
    def go() -> str:
        with session_scope() as s:
            D.assert_is_admin(_me(s))
            u = R.create(s, account=req.account, name=req.name, password=req.password)
            return f"已创建普通用户 {u.name or u.account}（{u.account}）"
    return _run(go)


@router.post("/api/m15/actions/password")
def api_password(req: PwdIn) -> dict:
    """**改密**（建号设密与它**同一个出口** ⇒ 「建号与改密同一规则」，claim `001-06`）。"""
    def go() -> str:
        with session_scope() as s:
            me = _me(s)
            uid = _uid(req.id)
            # ⭐ **改密闸 = 域层的具名函数**（2026-10-01 `TAIL-207` 从这里的 `if` 挪过去 ——
            #    理由同 `assert_is_admin`：**防线在域层**，且纯函数好钉判据、不用起会话）。
            #    **本人改自己 ⇒ 放行**（哪怕只是普通用户）；改**别人** ⇒ 仍要管理员。
            #    出处 = 用户 2026-10-01「普通用户应该有改自己账户密码的权限」（决策件 `D28`）。
            D.assert_may_set_password(me, uid)
            u = R.set_password(s, uid, req.password)
            return f"{u.name or u.account} 的密码已更新" + ("" if req.password else "（已清空 · 密码可为空）")
    return _run(go)


@router.post("/api/m15/actions/status")
def api_status(req: StatusIn) -> dict:
    """**停用 / 启用**（§1.5.1）—— ⚠️ 与"删除"是两回事（claim `001-08`：只碰 `status`）。"""
    def go() -> str:
        with session_scope() as s:
            D.assert_is_admin(_me(s))
            u = R.set_status(s, _uid(req.id), req.status)
            return (f"账号 {u.name or u.account} 已停用 · 停用不删除，历史留痕里仍能认出这个人"
                    if u.status == D.STATUS_DISABLED
                    else f"账号 {u.name or u.account} 已启用")
    return _run(go)


@router.post("/api/m15/actions/delete")
def api_delete(req: IdIn) -> dict:
    """**删除 = 软删**（§1.5.1：账号名保留、不销毁数据、必要时可恢复）。

    ⚠️ 两条防锁死闸都在 `repository`（不能删自己 ＋ 不能删最后一个在用管理员）——
       本层**不重复判断**（⛔ 两份判断必漂）。
    """
    def go() -> str:
        with session_scope() as s:
            actor = _me(s)
            D.assert_is_admin(actor)
            # ⚠️ ⛔ **不要**再写 `actor or R.ensure_seeded(s)` 那种兜底 ——
            #    那会在"取不到当前登录用户"时**悄悄拿首个管理员顶替**，
            #    于是刚加的那道 `assert_is_admin` **等于没有**（兜底把闸口绕过去了）。
            u = R.soft_delete(s, _uid(req.id), actor=actor)
            return f"账号 {u.name or u.account} 已删除（软删）· 账号名保留，历史留痕里仍能认出这个人"
    return _run(go)


@router.post("/api/m15/actions/restore")
def api_restore(req: IdIn) -> dict:
    """**恢复**软删的账号（§1.5.1「必要时可恢复」）—— ⚠️ 恢复**不改 `status`**（停用是另一回事）。"""
    def go() -> str:
        with session_scope() as s:
            D.assert_is_admin(_me(s))
            u = R.restore(s, _uid(req.id))
            return f"账号 {u.name or u.account} 已恢复" + ("" if u.status == D.STATUS_ACTIVE else "（该账号仍是「已停用」）")
    return _run(go)


@router.post("/api/m15/actions/transfer")
def api_transfer(req: IdIn) -> dict:
    """**转让管理员**（§1.5.1）—— 转让后对方为管理员、自己转为普通用户 ⇒ **恒只有一个管理员**。"""
    def go() -> str:
        with session_scope() as s:
            actor = _me(s)
            D.assert_is_admin(actor)          # ⚠️ 同样⛔ 不用 `or ensure_seeded` 兜底（会把闸口绕过去）
            target = R.get(s, _uid(req.id))
            if target is None:
                raise AppError(f"账号不存在：id={req.id!r}")
            promote, demote = R.transfer_admin(s, actor, target)
            return (f"管理员已转让给 {promote.name or promote.account}；"
                    f"{demote.name or demote.account} 现在是普通用户，不再能管理账号")
    return _run(go)


__all__ = ["router"]
