"""历史付款流水导入（**§4.4.6**）—— 解析 · 校验 · 预览 · 落库 · 核对报告。

> **为什么需要它**：i8 侧**完全没有付款记录**（付款动作在会计的 NC 系统做、两系统不关联）
> ⇒ **历史付款流水的唯一来源 = 本单位 Excel 台账**。

## 列契约（**固定顺序，A 列起**）

| 列 | 含义 | 必填 | 落库字段 |
|---|---|---|---|
| A | **单据号**（i8 `BillNo`） | ✅ | 匹配 `payment_notice.bill_no` |
| B | **付款金额** | ✅ | `amount` |
| C | **付款时间** | ✅ | `pay_date`（统一 `YYYY-MM-DD`） |
| D | **付款方式** | ⭕ 可空 | `pay_method` |
| E | **备注** | ⭕ | `remark` |

## 四条硬纪律（判据 `ACC-FLOW-IMPORT-001~003`）

1. **落库前必须预览**：预览阶段**一个字节都不写库**；
2. **未匹配 / 异常行必须逐条列出来**，**不得静默丢弃**；
3. **付款方式为空 ⇒ 存空**（事实记录不得编造；§4.4.2 的"兜底现汇"只约束**新付款动作**）；
4. **幂等**：同批重导 = 先**整批回滚**（置撤销 ＋ 留痕，**不物理删**）再写新批。

本模块**只做 Excel 的解析与落库编排**：金额 / 付款方式的合法性判定走 `domain`，
重算走 `repository.sync_stat_paid`（**唯一出口**）—— 本层**不另写一遍**。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.core.money import amount_text, to_money      # ⭐ `amount_text`：`TAIL-63` 金额洗净的唯一出口
from app.mod05_flow.models import PAY_METHODS
from app.mod05_flow import repository as repo

# 列契约（**顺序即位置**；界面提示与解析共用同一份 —— 别各写一份）
COLUMNS: tuple[tuple[str, str, bool], ...] = (
    ("A", "单据号（i8 单据编码，如 FKTZS2026090466）", True),
    ("B", "付款金额（数字）", True),
    ("C", "付款时间（如 2026-08-15）", True),
    ("D", "付款方式（可空；现汇 / 承兑 / 供应链 / 其他）", False),
    ("E", "备注（可空）", False),
)

MAX_ROWS = 5000

# 单据号形态（够用即可：字母开头 + 数字；**只用于"首行是不是表头"的判断**）
_BILL_NO_RE = re.compile(r"^[A-Za-z]{2,}\d{6,}$")
_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S",
                 "%Y/%m/%d %H:%M:%S", "%Y年%m月%d日")

# 付款方式归一表（§4.4.2 的四类；**归不进 ⇒ 记「其他」＋原文留备注**，§4.4.6）
_METHOD_ALIASES: dict[str, str] = {}
for _std, _words in (
    ("现汇", ("现汇", "电汇", "网银", "转账", "汇款", "银行转账", "公对公", "对公转账", "汇兑")),
    ("承兑", ("承兑", "银行承兑", "商业承兑", "银承", "商票", "银票")),
    ("供应链", ("供应链", "供应链金融", "供应链票据", "供应链融资")),
    ("其他", ("其他", "其它")),
):
    for _w in _words:
        _METHOD_ALIASES[_w] = _std


@dataclass
class ParsedRow:
    """一行**已解析**的导入数据（`line` = Excel 里的行号，1 基，报错时好定位）。"""

    line: int
    bill_no: str
    amount: Decimal
    pay_date: str
    pay_method: str
    remark: str
    method_recognized: bool = True
    notice_id: int = 0          # 匹配到的本地通知书 id（`split_by_match` 填；预览阶段为 0）


@dataclass
class ImportPlan:
    """**预览结果** —— 落库前给人看的全部东西（四块）。"""

    rows: list[ParsedRow] = field(default_factory=list)        # 将写入
    unmatched: list[dict] = field(default_factory=list)        # 单据号本地不存在
    anomalies: list[dict] = field(default_factory=list)        # 非法行
    unknown_methods: list[str] = field(default_factory=list)   # 未识别的付款方式取值
    skipped_header: bool = False

    @property
    def writable(self) -> int:
        return len(self.rows)


# ---------------------------------------------------------------- 单值解析（纯函数）


def parse_amount(raw) -> Decimal:
    """付款金额：接受数字或"1,234.56"式文本；**必须 > 0**（0 与负无业务意义）。"""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise ValueError("付款金额为空")
    if isinstance(raw, str):
        raw = amount_text(raw)
    try:
        value = to_money(Decimal(str(raw)))
    except (InvalidOperation, ArithmeticError, ValueError) as exc:
        raise ValueError(f"付款金额无法解析：{raw!r}") from exc
    if value <= 0:
        raise ValueError(f"付款金额必须大于 0（实际 {value}）")
    return value


def parse_date(raw) -> str:
    """付款时间：接受 Excel 日期对象或常见文本格式；**统一存 `YYYY-MM-DD`**。"""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        raise ValueError("付款时间为空")
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    if isinstance(raw, date):
        return raw.isoformat()
    text = str(raw).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    raise ValueError(f"付款时间无法解析：{text!r}")


def normalize_method(raw) -> tuple[str, bool]:
    """付款方式归一（§4.4.6）：归得进四类 ⇒ 返回标准值；归不进 ⇒ `("其他", False)`；**空 ⇒ `("", True)`**。

    ⚠️ 空**不算"未识别"**（历史台账常常没记付款方式，那是**合法留白**，不是错误）。
    """
    text = str(raw or "").strip()
    if not text:
        return "", True
    if text in PAY_METHODS:
        return text, True
    for alias, std in _METHOD_ALIASES.items():
        if alias in text:
            return std, True
    return "其他", False


def looks_like_bill_no(raw) -> bool:
    return bool(_BILL_NO_RE.match(str(raw or "").strip()))


# ---------------------------------------------------------------- 解析整表（纯函数）


def parse_rows(raw_rows: list[list]) -> ImportPlan:
    """把"逐行的原始单元格"按**固定列序（A 单据号 · B 金额 · C 时间 · D 方式 · E 备注）**解析成 `ImportPlan`
    （**不碰数据库** ⇒ 可离线单测）。

    ⚠️ **2026-09-23（`TAIL-75` `B5b` 第三步 · 用户裁定 `B`）**：本函数**不再是导入入口**（旧页已下架）
       —— 用户手上的表由**通用导入面按列名映射**到那五列，域钩子 `imp_spec._plan_of` 逐行调本模块的
       **单值判定**（`parse_amount` / `parse_date` / `normalize_method`）。
       ⭐ 本函数**保留**（与 `m06` 撤页时留 `parse_sheet` 同款）：它是域内"五列批解析"的**口径出口**，
       判据 `ACC-FLOW-IMPORT-001` 与 `ACC-INIT-001` 仍钉着它（⛔ 别删 —— 删了那些判据就没落点了）。
    """
    plan = ImportPlan()
    body = list(raw_rows)
    # ① 首行像表头 ⇒ 跳过并提示（用户给的表**可能带表头也可能不带**）
    if body and not looks_like_bill_no((body[0] + [None] * 5)[0]):
        if any(str(c or "").strip() for c in body[0]):
            plan.skipped_header = True
            body = body[1:]
    for offset, cells in enumerate(body):
        line = offset + 1 + (1 if plan.skipped_header else 0) + 1   # Excel 1 基行号
        cells = list(cells) + [None] * (5 - len(cells))
        bill_no, amount_raw, date_raw, method_raw, remark_raw = cells[:5]
        bill_no = str(bill_no or "").strip()
        if not any(str(c or "").strip() for c in (bill_no, amount_raw, date_raw, method_raw, remark_raw)):
            continue                                                # 整行空 ⇒ 静默跳过（不算异常）
        if not bill_no:
            plan.anomalies.append({"line": line, "reason": "单据号为空"})
            continue
        try:
            amount = parse_amount(amount_raw)
        except ValueError as exc:
            plan.anomalies.append({"line": line, "bill_no": bill_no, "reason": str(exc)})
            continue
        try:
            pay_date = parse_date(date_raw)
        except ValueError as exc:
            plan.anomalies.append({"line": line, "bill_no": bill_no, "reason": str(exc)})
            continue
        method, recognized = normalize_method(method_raw)
        remark = str(remark_raw or "").strip()
        if not recognized:                                          # 原文留备注（不丢信息）
            raw_text = str(method_raw or "").strip()
            plan.unknown_methods.append(raw_text)
            remark = (f"原付款方式：{raw_text}；{remark}" if remark else f"原付款方式：{raw_text}")
        plan.rows.append(ParsedRow(line=line, bill_no=bill_no, amount=amount, pay_date=pay_date,
                                   pay_method=method, remark=remark, method_recognized=recognized))
    return plan


def known_notices(s) -> dict[str, int]:
    """`单据号 -> notice_id`（精确匹配用；**只读**，故**预览阶段也安全**）。

    ⭐ **公开出口**（`TAIL-75` `B5b` 第三步）：通用导入面的域钩子（`imp_spec.preview` / `imp_spec.commit`）
       **共用这一份** —— ⛔ 别各写一遍（"同一口径两个主人"是本仓反复踩过的坑）。
       ⚠️ 2026-09-23（用户裁定 `B`）：原先域自己的 JSON API（`import_api._known`）**已随件删除**
       ⇒ 现在只有域钩子一个调用方（它仍在生产链路上）。
    """
    return {str(n.bill_no or "").strip(): int(n.id)
            for n in repo.notice_rows(s) if str(n.bill_no or "").strip()}


def split_by_match(plan: ImportPlan, known: dict[str, int]) -> ImportPlan:
    """按**本地已有单据号**分出「可写」与「未匹配」（§4.4.6：未匹配**必须列出来**）。"""
    out = ImportPlan(skipped_header=plan.skipped_header, anomalies=list(plan.anomalies),
                     unknown_methods=list(plan.unknown_methods))
    for r in plan.rows:
        if str(r.bill_no) in known:
            r.notice_id = int(known[str(r.bill_no)])        # 精确匹配（1:1）
            out.rows.append(r)
        else:
            out.unmatched.append({"line": r.line, "bill_no": r.bill_no, "amount": str(r.amount),
                                  "pay_date": r.pay_date})
    return out


def read_workbook(data: bytes) -> list[list]:
    """读 `.xlsx` 的首个工作表（**只取值**）。

    ⚠️ 读表已收编 `import_kit.readers.read_grid`（`TAIL-69` Phase 2）——
       首行表头判断（`looks_like_bill_no`）与金额/日期的**域内硬判定**仍归本文件（§4.4.6）。
    """
    from app.import_kit.readers import read_grid

    return read_grid(data, max_rows=MAX_ROWS)[0]


# ---------------------------------------------------------------- 落库 / 回滚 / 报告


def next_batch(*, at: datetime | None = None) -> str:
    """批次号 = `IMP-<yyyymmddHHMMSS>`（幂等与回滚都按它）。"""
    return "IMP-" + (at or datetime.now()).strftime("%Y%m%d%H%M%S")


def months_of(plan: ImportPlan) -> list[str]:
    """该批涉及的月份（按**付款时间**归月）—— 核对报告的取数范围。"""
    return sorted({r.pay_date[:7] for r in plan.rows if r.pay_date})


def commit(s, plan: ImportPlan, *, batch: str, operator: str = "") -> dict:
    """**落库**（§4.4.6）：一条付款 = 一条独立流水；来源 = `imported`、批次 = `batch`。

    ⚠️ 每条都经 `repo.create_flow` ⇒ **自动走重算唯一出口**（`sync_stat_paid`）——
       导入后「统计付款金额」立即跟上（§4.4.7），不需要本层再算一遍。
    """
    written = 0
    for r in plan.rows:
        if not r.notice_id:
            continue                       # 未匹配的行**绝不落库**（由预览页报出来给人看）
        repo.create_flow(
            s, notice_id=int(r.notice_id), project_id=None, amount=r.amount,
            pay_date=r.pay_date, pay_method=r.pay_method,
            source=repo.FLOW_SOURCE_IMPORTED, import_batch=batch, remark=r.remark,
        )
        written += 1
    return {"batch": batch, "written": written, "operator": str(operator or "")}


def rollback(s, batch: str, *, changed_by: str = "") -> dict:
    """整批回滚（= `repository.rollback_batch`，留痕、不物理删）。"""
    return repo.rollback_batch(s, batch, changed_by=changed_by)


def check_report(s, batch: str) -> dict:
    """⭐ **核对报告**（§4.4.6）—— 两部分，都由该批流水的**月份**划定范围：

    ① `rows` / `count` —— 该批月份里、**一条生效流水都没有**的通知书（供发现 **Excel 漏记**）；
    ② `overpaid` / `overpaid_count` —— 该批月份里、**实付合计 > 审批金额**的通知书
       （§4.4.6 第一句的第三半「**核对报告单列**」：`P4` 超付处置三半的最后一半；
       ⚠️ 与界面上的「超付」提醒是**同一判据的两处落点** —— 提醒那半在
       `mod03_notice/list_view.NoticeRow.is_overpaid` → 壳 `V.m03`，见 `TAIL-49`）。

    ⚠️ 两块**都从该批月份的流水算起**（`flows_in_batch`）⇒ 回滚后重算同一个批次，两块一起变。
    """
    months = sorted({str(f.pay_date or "")[:7] for f in repo.flows_in_batch(s, batch)
                     if str(f.pay_date or "").strip()})
    rows = repo.notices_without_flow(s, months)
    overpaid = repo.notices_overpaid(s, months)
    return {"batch": batch, "months": months, "count": len(rows), "rows": rows,
            "overpaid": overpaid, "overpaid_count": len(overpaid)}


__all__ = [
    "COLUMNS", "MAX_ROWS", "ParsedRow", "ImportPlan",
    "parse_amount", "parse_date", "normalize_method", "looks_like_bill_no",
    "parse_rows", "split_by_match", "known_notices", "read_workbook",
    "next_batch", "months_of", "commit", "rollback", "check_report",
]
