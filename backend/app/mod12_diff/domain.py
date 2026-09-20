"""`MOD-12` 差异登记的**判定**（纯函数，不连库、不碰 ORM）—— 唯一口径出口。

依据：《说明书》**§5.8.3**（差异登记正文）· **§8.3**（状态机 待核对 → 已核对 / 差异保留）·
     §5.10 `DEV-R-06` · `PRD/02-功能规格/MOD-12.md`（契约，**刻意不含取值** ⇒ 取值一律回上面两节）。

⚠️ **本文件是"判定"的唯一主人**：路由 / 壳都只转述它给的结论与那句中文，
   ⛔ 不许在别处再写一份（「同一件事实现两遍」是本项目反复踩的坑）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.core.errors import MustReportError

# ---------------------------------------------------------------- 取值（主人 = §5.8.3 / §8.3）

OWNER_INV = "库存单据"
"""**归属的唯一取值**（§5.8.3：「差异归属枚举**恒为「库存单据」** ——
不再按「发现位置」区分过程资料 / 库存单据」）。

⚠️ 正因为只有这一个值，才**更要把它写成一列**：
    `001-10` 钉的是"**不存在**归属为过程资料的记录" ——
    若归属只是"反正没人写别的"的默认值，日后有人加个参数就**静默破了口径**。
"""

STATUS_PENDING = "待核对"
STATUS_VERIFIED = "已核对"
STATUS_KEPT = "差异保留"
STATUSES: tuple[str, ...] = (STATUS_PENDING, STATUS_VERIFIED, STATUS_KEPT)
"""状态取值（§8.3：「待核对 → 已核对 / 差异保留」，**手工标记**）。"""

DEFAULT_STATUS = STATUS_PENDING
"""新登记的默认状态（判据点 `001-02`：「新登记的默认状态为**待核对态**」）。"""

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


# ---------------------------------------------------------------- 校验


@dataclass
class DiffInput:
    """一次登记的**入参**（已归一）。⚠️ **没有 `owner` 字段** —— 它不由调用方给（见 `to_record`）。"""

    month: str
    project_name: str
    detail: str
    amount: Decimal
    status: str = DEFAULT_STATUS
    remark: str = ""


def parse_amount(raw) -> Decimal:
    """金额出口 —— **唯一判据在这一点**（判据点 `001-04`）。

    ⚠️ 三条，一条都不能少（与原型 `badMoney(v,{signed:1})` **同口径**，⛔ 不另立）：
    - **非数字被拒**（含空 / `abc` / 纯符号）；
    - ⭐ **负数必须放行**（§5.8.3「金额带符号：+ 上调 / − 下调」）——
      ⛔ 不许拿"金额一般是非负数"的直觉在这里拦它，那正是 `001-04` 要钉的东西；
    - ⛔ **无上限**：差异金额**不设 cap**（与"统计两金额 ≤ 审批金额"那条**不是一回事**）。
    """
    text = str("" if raw is None else raw).strip()
    if text == "":
        raise MustReportError("「差异金额」必填 —— 请填数字（可带正负号，+ 上调 / − 下调）")
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise MustReportError(
            "「差异金额」不合法：请填**数字**（可带正负号，+ 上调 / − 下调）") from exc
    if not value.is_finite():
        raise MustReportError("「差异金额」不合法：不允许 NaN / Infinity")
    return value


def validate(payload: dict) -> DiffInput:
    """**必填校验 ＋ 归一** —— 不通过就抛 `MustReportError`（带**可直接给人看**的中文）。

    ⚠️ 判据点 `001-03`：「核算月 / 项目 / 差异内容**缺一即拒**」，并特别注明
       「**金额即便合法也不得替它挡枪**」⇒ 三个必填**各判各的**，
       ⛔ 不许写成"金额合法就放行"（那样缺了核算月也会被放进库）。
    ⚠️ 校验顺序与原型 `dfSave` **逐条对齐**（先月、再项目、再内容、最后金额）——
       用户看到的**第一句提示**必须是同一个（否则同一份输入在两个入口得到不同的话）。
    """
    month = str((payload or {}).get("month") or "").strip()
    if not _MONTH_RE.match(month):
        raise MustReportError(
            "「核算月」必填且格式为 YYYY-MM —— 它决定这笔差异**归到哪个月**（对账按核算月看）")

    project_name = str((payload or {}).get("project_name") or "").strip()
    if not project_name:
        raise MustReportError("「项目」必填 —— 候选 = 全部已建档项目（含归档；壳除外，§2.7.4）")

    detail = str((payload or {}).get("detail") or "").strip()
    if not detail:
        raise MustReportError("「差异内容」必填 —— 一句话说明**差在哪**（半年度对账时要能看懂）")

    amount = parse_amount((payload or {}).get("amount"))

    status = str((payload or {}).get("status") or "").strip() or DEFAULT_STATUS
    if status not in STATUSES:
        raise MustReportError(
            f"「状态」取值不合法：{status!r}（只允许 {' / '.join(STATUSES)} —— 主人 = §8.3 状态机）")

    return DiffInput(month=month, project_name=project_name, detail=detail,
                     amount=amount, status=status,
                     remark=str((payload or {}).get("remark") or "").strip())


def to_record(data: DiffInput) -> dict:
    """入参 → **落库字段**。

    ⚠️⚠️ **归属在这里定死**，⛔ **不看调用方给了什么** —— 判据点 `001-10`：
       「归属**恒为**「库存单据」：不存在归属为过程资料的记录」。
       若写成 `data.owner or OWNER_INV`，就等于**开了一个口子**（谁传都能改口径）。
    """
    return {
        "month": data.month,
        "owner": OWNER_INV,          # ⛔ 常量，不是"默认值"
        "project_name": data.project_name,
        "detail": data.detail,
        "amount": data.amount,
        "status": data.status,
        "remark": data.remark,
    }


# ---------------------------------------------------------------- 编号


def next_seq(existing: list[int]) -> int:
    """下一个**序号** = `max(已有序号) + 1`（空表 ⇒ 1）。

    ⚠️⚠️ 判据点 `001-02` 要求「编号**不撞既有行**」—— 而本页**可以删行** ⇒
       ⛔ **不能**用"条数 + 1"：登记 3 条得 `DF01..DF03`，删掉 `DF02` 再登记一条，
       条数还是 3 ⇒ 又发一个 `DF03` ⇒ **撞号**（而且两条内容不同，事后极难查）。
       ⇒ 与原型 `nextDfId` 同一算法（那里也是 `max(序号) + 1`），**删行不回退**。
    """
    return max([int(x) for x in (existing or []) if str(x).strip() != ""] or [0]) + 1


def code_of(seq: int) -> str:
    """序号 → 业务编号（`1 → DF01`）。⚠️ 补零到 2 位，与原型一致（`DF01` 而不是 `DF1`）。"""
    return f"DF{int(seq):02d}"


__all__ = [
    "DEFAULT_STATUS", "OWNER_INV", "STATUSES",
    "STATUS_KEPT", "STATUS_PENDING", "STATUS_VERIFIED",
    "DiffInput", "code_of", "next_seq", "parse_amount", "to_record", "validate",
]
