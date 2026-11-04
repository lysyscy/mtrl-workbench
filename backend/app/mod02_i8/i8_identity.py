"""MOD-02 横切：**i8 可见身份的核对规则**（账号 / 组织），浏览器通道的连接前置校验全在这里。

## 为什么需要这一层

浏览器里那个 i8 标签登录的是"某个账号 + 某个组织"，而工作台取数用的是"本人绑定的 i8 账号 +
配置里的组织范围"。两者必须**真的对上**才允许连接 —— ⛔ 不能只看页面自己声明的字符串就放行，
也 ⛔ 不能把"两个不同的标识类型"直接比相等。

## 三种组织标识（⚠️ 不是同一个东西，不能互相比较）

| 标识 | 例子 | 来源 | 用途 |
|---|---|---|---|
| **内部 id** | `3700000000000014` | 取数表单 `orgQuery` / `clientfilter` 里的 `curOrg` | 决定**请求实际带哪个组织** |
| **可见短码** | `109` | i8 页面账号面板的「组织」行（`组织名称 ｜ 短码`） | 页面**显示**给用户看的 |
| **名称** | 见下表 | 同上 | 给人读的 |

⇒ 核对方式 = 先由内部 id 查**本部署已核映射**，再拿映射里的短码/名称跟页面可见值比。
   **未知内部 id ⇒ 直接失败**（不许猜、不许放过）。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.errors import DataConflictError
from app.mod02_i8.browser_relay import expected_org_id
from app.mod02_i8.browser_session import StrictSessionUnavailable, StrictTargetMismatch


class UnknownOrgMapping(DataConflictError):
    """内部组织 id 没有已核映射 ⇒ **停**（⛔ 不猜一个短码出来）。"""

    code = "i8_unknown_org_mapping"

    def __init__(self, message: str) -> None:
        super().__init__(message)


#: ⭐ **本部署已核映射**：内部 id → (可见短码, 名称)。
#: ⚠️ 只收**已核实是同一组织**的项；来源：`sources.WH_PARAMS` 的机构号注释（内部号属该机构）
#:    + 主控现场只读核对的账号面板组织行（名称/短码）。⛔ 没核过的别往里加，宁可让它失败。
#: ⛔ 这里**只放组织级**信息（不含任何个人账号/姓名）。
ORG_MAP: dict[str, tuple[str, str]] = {
    "3700000000000014": ("109", "第四工程公司"),
}


@dataclass(frozen=True)
class VisibleIdentity:
    """浏览器里实际读到的身份（扩展按已核 DOM 结构读出，**不是**用户手填）。"""

    account: str = ""
    org_code: str = ""
    org_name: str = ""
    origin: str = ""
    tab_title: str = field(default="", repr=False)

    def masked(self) -> dict[str, str]:
        """可进日志/证据的形态：账号打码、组织只留短码与名称。"""
        account = self.account
        if len(account) > 2:
            account = f"{account[0]}{'*' * (len(account) - 2)}{account[-1]}"
        return {"account": account, "org_code": self.org_code, "org_name": self.org_name}


def org_of(org_id: str | None = None) -> tuple[str, str]:
    """内部 id ⇒ `(短码, 名称)`；未知 id ⇒ `UnknownOrgMapping`（⛔ 不回落、不猜）。"""
    key = (org_id if org_id is not None else expected_org_id()).strip()
    mapped = ORG_MAP.get(key)
    if mapped is None:
        raise UnknownOrgMapping(
            "工作台取数使用的组织还没有登记可见名称与短码，无法核对浏览器里的组织；"
            "本次未建立连接（未发请求）。请联系维护人补登记后再试。"
        )
    return mapped


def check_identity(visible: VisibleIdentity, *, bound_user: str,
                   org_id: str | None = None) -> None:
    """逐项核对"浏览器可见身份"与"工作台这条取数链应有的身份"。

    ⛔ 缺一项即停、不符即停；⛔ 不用页面声明的 `origin` 充当站点校验（站点另有 origin 比对）。
    """
    # 「读不到」与「对不上」分开：前者是无法核实（缺材料 ⇒ 400 停），后者是目标不符（⇒ 409 停）。
    account = (visible.account or "").strip()
    if not account:
        raise StrictSessionUnavailable(
            "没读到 i8 页面上的登录账号，无法确认这个会话是本人的。"
            "请在 i8 页面展开右上角的账号面板（让它显示账号与组织）后再点连接；本次未建立连接。"
        )
    expected_user = (bound_user or "").strip()
    if not expected_user:
        raise StrictSessionUnavailable(
            "工作台这个账号还没有绑定 i8 账号，无法确认浏览器里的会话属于本人；本次未建立连接。"
        )
    if account != expected_user:
        raise StrictTargetMismatch(
            "i8 页面当前登录的账号与工作台本人绑定的 i8 账号不一致，本次未建立连接。"
            "请确认浏览器里登录的是本人的 i8 账号，或到工作台「设置」核对绑定。"
        )

    want_code, want_name = org_of(org_id)
    code = (visible.org_code or "").strip()
    name = (visible.org_name or "").strip()
    if not code or not name:
        raise StrictSessionUnavailable(
            "没读到 i8 页面上的组织（名称与短码），无法确认取数范围与本人组织一致。"
            "请在 i8 页面展开账号面板（显示当前组织）后再点连接；本次未建立连接。"
        )
    if code != want_code or name != want_name:
        raise StrictTargetMismatch(
            "浏览器里 i8 当前组织与工作台取数使用的组织不一致，本次未建立连接。"
            "请在 i8 页面切换到正确组织后再连接。"
        )


__all__ = ["ORG_MAP", "UnknownOrgMapping", "VisibleIdentity", "check_identity", "org_of"]
