"""`MOD-15` 账号域的**规则出口**（《说明书》§1.5.1）。

⚠️ 本模块是**纯函数**（⛔ 不碰会话、不落库）—— 规则在这里、落库在 `repository.py`，
   这样"**直接调写操作也必须被拦**"（claim `001-07` 的硬要求）能靠**同一个出口**保证：
   仓储与将来的 JSON API **都调这里的断言**，⛔ 不各写一份。

⚠️ **旧口径一律按作废处理**（§1.5.1 明确列出）：
   ⛔ 账号名「字母开头且 ≥3 位」· ⛔ 密码「≥6 位」· ⛔「只停用、不物理删除」· ⛔ **「不能停用自己」**。
   ⭐ 最后一条特别容易"顺手加回来"（看着像防误操作）—— 但口径明写废了它，⛔ 不加。
"""

from __future__ import annotations

from typing import Iterable

from app.core.errors import MustReportError

ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLES = (ROLE_ADMIN, ROLE_USER)

STATUS_ACTIVE = "在用"
STATUS_DISABLED = "已停用"
STATUSES = (STATUS_ACTIVE, STATUS_DISABLED)

#: 三态里的第三态（⛔ 不是 `status` 的取值，是「`deleted_at` 非空」的**显示名**）
STATE_DELETED = "已删除"


def is_deleted(u) -> bool:
    """软删 = `deleted_at` 非空（⚠️ 判据**只看这一处**，⛔ 别各处自己写 `status == '已删除'`）。"""
    return getattr(u, "deleted_at", None) is not None


def state_of(u) -> str:
    """三态显示名：已删除 / 已停用 / 在用（⚠️ 「删除」优先于「停用」—— 两个标记同时为真时它算已删）。"""
    if is_deleted(u):
        return STATE_DELETED
    return STATUS_DISABLED if u.status == STATUS_DISABLED else STATUS_ACTIVE


def active_admins(users: Iterable) -> list:
    """**在用的管理员**（既没被删、也没被停用）—— 防锁死判据的**唯一**依据。

    ⚠️ 「在用」= `status == 在用` **且** `deleted_at is None`，**两个条件都要**
       —— 只查 `role == admin` 会把"已停用的管理员"也算进去 ⇒ **防锁死就失效了**。
    """
    return [u for u in users if u.role == ROLE_ADMIN and u.status == STATUS_ACTIVE and not is_deleted(u)]


def assert_last_admin_protected(users: Iterable, target) -> None:
    """⛔ **不能停用 / 删除「最后一个在用管理员」**（§1.5.1「防锁死」）。

    ⚠️ 为什么必须**在域层拦**（⛔ 不能只靠壳把按钮禁用）：claim `001-07` 明写
       「**直接调写操作也必须被拦，不只靠按钮禁用**」—— 壳的 `disabled` 只是**体验**，
       真正的防线在这里（JSON API / 将来的批处理都会走这里）。
    ⚠️ 只在**真的会减少**在用管理员时才拦：动一个**普通用户**、或动一个**本来就不是在用管理员**的账号
       ⇒ 不拦（否则"停用普通用户"也会报错，那是另一种错）。
    """
    if target.role != ROLE_ADMIN or target.status != STATUS_ACTIVE or is_deleted(target):
        return
    remaining = [u for u in active_admins(users) if u is not target and getattr(u, "id", None) != getattr(target, "id", None)]
    if not remaining:
        raise MustReportError(
            "不能停用 / 删除**最后一个在用管理员** —— 那会**把系统锁死**（§1.5.1 防锁死）："
            "没人能再管理账号，也就没人能把它改回来。"
            "⇒ 先把管理员**转让**给另一个在用账号，再来动它。")


def assert_is_admin(actor) -> None:
    """⛔ **只有「在用的管理员」能管理账号**（§1.5.1「**管理员** | 用户本人为管理员，**可管理其他账号**」）。

    ⚠️⚠️ 为什么这条必须**在后端**、⛔ 不能只写在壳里（`CUR.role!=='admin'`）：
       壳里那句只是**体验**（早点告诉用户"你不行"、别让他填完表单才被拒）；
       真正拦人的地方在这里 —— ⭐ 与 claim `001-07` 那句
       「**直接调写操作也必须被拦，不只靠按钮禁用**」是同一个道理：
       JSON API / 将来的批处理 / 命令行都会走到这一层，⛔ 别处没有第二道闸。
    ⚠️ 这一步**之前**没有 —— 2026-09-20 片 4b 接壳时才发现的：原型只在壳里判了角色，
       后端 6 个写动作**谁调都执行**（⭐ 这是"接壳"顺带照出来的一处口径缺口）。
    ⚠️ `actor` 为 `None`（**取不到当前登录用户**）时**一律拒** —— ⛔ 别"没人就当管理员"。
    """
    if actor is None or actor.role != ROLE_ADMIN or actor.status != STATUS_ACTIVE or is_deleted(actor):
        who = "（取不到当前登录用户）" if actor is None else f"「{actor.account}」"
        raise MustReportError(
            f"只有**在用的管理员**能管理账号（§1.5.1）—— 当前登录用户 {who} 不是管理员。"
            "⇒ 请让管理员来操作，或先**转让管理员**给你。")


def assert_may_set_password(actor, target_id) -> None:
    """**改密闸**：**本人改自己不受"必须是管理员"限制**；⛔ 改**别人**的才要管理员。

    ⭐ 出处 = 用户 **2026-10-01** 拍板（`TAIL-207` · 决策件 `.codebuddy/work/40-decisions/D28-普通用户可改自己密码.md`）：
       「**普通用户应该有改自己账户密码的权限**」。
    口径依据：§1.5.1 只要求管理员**能管理「其他」账号**（"用户本人为管理员，可管理**其他**账号"）——
       ⛔ 它**没有**说"只有管理员能碰密码"；把本人关在门外是**另一种错**
       （每个人只能找管理员改密 ⇒ 管理员变成人工密码机）。

    ⚠️ 两半都要钉（与 `assert_is_admin` 同一个哲学）：
       ① **本人**（哪怕只是普通用户）⇒ **放行**；
       ② **改别人** ⇒ 仍走 `assert_is_admin`；**取不到当前登录用户**（`actor is None`）⇒ **一律拒**
          （⛔ 别"没人就当本人" —— 那比"没人就当管理员"更隐蔽）。

    ⚠️⚠️ 为什么它在**域层**、而不是留在 `api.py` 里那个 `if`（2026-10-01 `TAIL-207` 挪的）：
       与 `assert_is_admin` 同一条理由 —— **防线在域层**（命令行 / 批处理 / 将来的别处调用都会过这一层）；
       而且它是**纯函数**（⛔ 不碰库）⇒ 判据可直接调它，不用起会话、不写一行库。
    """
    if actor is not None and getattr(actor, "id", None) == target_id:
        return
    assert_is_admin(actor)


def assert_not_self_delete(actor, target) -> None:
    """⛔ **不能删除自己**（§1.5.1「防锁死」后半句）。

    ⚠️ 注意**只有"删除"这一条** —— 旧口径里的「不能停用自己」**已作废**（§1.5.1 明列），
       ⛔ 别把它一起加上（那会让"停用自己"这个合法动作被拒）。
    """
    if getattr(actor, "id", None) is not None and actor.id == target.id:
        raise MustReportError("不能删除自己（§1.5.1 防锁死）—— 请让另一个管理员来删。")


def effective_theme(u) -> str:
    """这个账号**实际该用**的主题名（`ACC-UI-THEME-001/001-06`）。

    ⚠️ 三件事在这里一次说清（⛔ 别让调用方各自判）：
      ① **未设置**（`theme` 为空）⇒ 回落默认套；
      ② **非法名** ⇒ 也回落默认套（那条口径已由 `page.render_theme` 实现，这里只是**跟上**
         它的裁决 —— ⚠️ 判断题只有一处：`render_theme`；本函数只负责"给出该用哪个名字"）；
      ③ `u` 为 `None`（**没登录**）⇒ 回落默认套（未登录也要有样式，⛔ 不能白屏）。

    ⚠️ ⛔ **别在这里再判一遍"名字合不合法"** —— 那会造出第二份"哪些名字算合法"，
       而它迟早和 `page.THEME_SEEDS` 漂（新加一套主题时最容易漏掉这里）。
       本函数只做**取值**（空 ⇒ 默认），合法性交给**唯一的那个出口**。
    """
    from app.mod03_notice import page as P

    if u is None:
        return P.DEFAULT_THEME
    got = (getattr(u, "theme", "") or "").strip()
    return got or P.DEFAULT_THEME


# ---------------------------------------------------------------- ⭐ 界面大小（`TAIL-129`）

#: ⭐⭐ **界面大小档位的唯一真源**（`TAIL-129` · 用户 2026-09-27 裁定走**方案 B**：字号＋行距走 CSS 变量）。
#:  `(键, 名称, 倍率)` —— 键**存库**（留痕可读）、倍率是给 CSS `--fscale` 用的字符串。
#:  ⚠️ ⛔ **壳里不写死这张表**（加一档要改两处 = 两份真源）：壳从 `/api/m15/theme` 拿 `scales` 清单。
#:  ⚠️ ⛔ **别存倍率**（库里存的是键）：想调"更大"到底多大，改这一处即对所有人生效。
#:  ⚠️ 档位只做 **≥ 标准**（用户的原话是"看不清"，⛔ 不提供缩小 —— 少一档少一处误触面）。
UI_SCALES: tuple[tuple[str, str, str], ...] = (
    ("standard", "标准", "1"),
    ("large", "大一点", "1.12"),
    ("larger", "更大", "1.25"),
    ("largest", "最大", "1.4"),
)
#: 未设置 / 认不出 ⇒ 用哪一档（⛔ 别散落成字面量）。
DEFAULT_UI_SCALE = "standard"
_SCALE_CSS: dict[str, str] = {k: s for k, _, s in UI_SCALES}


def effective_ui_scale(u) -> str:
    """这个账号**实际该用**的界面大小**档位键**（空 / 未设置 / 认不出 ⇒ 标准档）。

    ⚠️ 与 `effective_theme` **同款三件事**（未设置 / 非法 / 未登录 ⇒ 都回落到标准档）——
       前端拿到的永远是**一个能用的键**，⛔ 不是空串（否则壳还得再判一次"空算什么"）。
    ⚠️ 用户**存的是键**（`large`），不是倍率 —— 倍率由本模块的 `UI_SCALES` 一处说了算。
    """
    got = (getattr(u, "ui_scale", "") or "").strip()
    return got if got in _SCALE_CSS else DEFAULT_UI_SCALE


def ui_scale_css(u) -> str:
    """档位 → 喂给 CSS `--fscale` 的**倍率字符串**（如 `"1.25"`）。

    ⚠️ 壳**直接用这个值**（`document.documentElement.style.setProperty('--fscale', v)`）——
       ⛔ 别让壳自己拿键去查倍率：那是把这张表复制成第二份。
    """
    return _SCALE_CSS[effective_ui_scale(u)]


def assert_ui_scale_usable(value: str) -> str:
    """校验用户传来的档位键（⛔ **不静默回落** —— 与主题那边\"非法名静默回落\"**有意不同**）。

    ⚠️ 为什么这一处要显式拒绝：主题的非法名**看得见**（页面还是有一套样式，用户能察觉），
       而界面大小的非法值**什么都不会发生**（`--fscale` 设成一个乱值 ⇒ CSS 计算无效 ⇒
       **看起来像"点了没反应"**）⇒ 必须当场说清"只能选这几档"。
    """
    v = (value or "").strip()
    if v in _SCALE_CSS:
        return v
    allowed = " / ".join(f"{k}（{label}）" for k, label, _ in UI_SCALES)
    raise MustReportError(
        f"界面大小只能选这几档：{allowed} —— 当前「{v or '（空）'}」"
    )


def normalize_account(account: str | None) -> str:
    """登录账号**只做去空白**（§1.5.1：*不限制字符与长度*）—— ⛔ 不校验格式。

    ⚠️ 「去空白」不算"限制格式"：它保证" 张伟 "与"张伟"**不成为两个账号**（那是**重复**，
       而"不重复"是口径明写的）；⛔ 此外一律原样（大小写、符号、长度都保持用户所写）。
    """
    return (account or "").strip()


def assert_account_usable(account: str, existing: Iterable) -> str:
    """账号**非空 + 不重复**（§1.5.1）⇒ 返回归一化后的账号，不合格当场报错。

    ⚠️⚠️ 判"重复"时 **`existing` 必须包含已删除的行** —— §1.5.1 说软删**保留账号名**
       （"必要时可恢复"），所以那个名字**还在占用**；claim `001-05` 也要求
       「登录账号重复或为空时必须拒绝创建（**不得新增行**）」。
       ⛔ 若这里只比对"在用的"，就制造了一个**恢复时会撞名**的坑。
    """
    acc = normalize_account(account)
    if not acc:
        raise MustReportError("登录账号**不能为空**（§1.5.1）—— 请填一个账号名。")
    for u in existing:
        if normalize_account(u.account) == acc:
            if is_deleted(u):
                raise MustReportError(
                    f"账号「{acc}」**已被一个已删除的账号占用** —— §1.5.1 规定软删**保留账号名**"
                    "（历史留痕里的人名要认得出来、且必要时可恢复）⇒ 换个名字，"
                    "或先把那个账号**恢复**出来再用。")
            raise MustReportError(f"账号「{acc}」**已存在**（§1.5.1：账号名非空 + 不重复）。")
    return acc


def transfer_plan(actor, target) -> dict:
    """**转让管理员**：返回"谁改成什么"（⛔ 不落库 —— 落库在仓储层）。

    §1.5.1：「管理员可把管理员身份**转让**给另一个**在用**账号；转让后对方为管理员、
    自己转为普通用户 ⇒ 系统内**恒只有一个管理员**」。
    ⚠️ 三条都要拦（少一条转让就会把系统搞成两个管理员或零个）：
      ① 目标必须是**在用**（"在用"含未删未停用 —— ⛔ 不能转给一个停用/已删的账号）；
      ② 目标不能是**自己**（自己转给自己 = 什么都不变，却会被当成"转让成功"）；
      ③ **执行者必须是在用管理员**（否则普通用户也能把自己提成管理员）。
    """
    if actor.role != ROLE_ADMIN or actor.status != STATUS_ACTIVE or is_deleted(actor):
        raise MustReportError("只有**在用的管理员**才能转让管理员身份（§1.5.1）。")
    if target.id == actor.id:
        raise MustReportError("不能把管理员身份**转让给自己**（§1.5.1）—— 请选另一个在用账号。")
    if target.status != STATUS_ACTIVE or is_deleted(target):
        raise MustReportError(
            f"不能把管理员转让给「{state_of(target)}」的账号 —— §1.5.1 要求目标是**在用**账号"
            "（否则一转让就是零个在用管理员 ⇒ 系统锁死）。")
    return {"promote": target, "demote": actor}


__all__ = [
    "ROLE_ADMIN", "ROLE_USER", "ROLES",
    "STATUS_ACTIVE", "STATUS_DISABLED", "STATUSES", "STATE_DELETED",
    "active_admins", "assert_account_usable", "assert_is_admin", "assert_may_set_password",
    "assert_last_admin_protected", "assert_not_self_delete", "effective_theme",
    "UI_SCALES", "DEFAULT_UI_SCALE", "effective_ui_scale", "ui_scale_css",
    "assert_ui_scale_usable",
    "is_deleted", "normalize_account", "state_of", "transfer_plan",
]
