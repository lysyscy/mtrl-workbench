"""`MOD-06` 过程资料**历史导入**（§5.2.5 ①②）—— 解析 · 校验 · 预览 · 批次 · 核对报告。

> **为什么需要它**：本系统上线前各项目的过程资料**已在用户 Excel 里定稿**；且部分项目在 i8 里被改过、
> **与库存单据并不一致** ⇒ 只靠「从库存单据引用」（§5.2.3 单向流）搬不进历史账
> ⇒ 需要一条**历史进系统的通道**（与付款域的「历史付款流水导入」同构，§5.2.5 ②）。

## 列契约（**按表头文字认列 · 列序不限**）

| 列 | 含义 | 必填 |
|---|---|---|
| **核算月** | `2026-08`（也接受 `2026/8` · `2026.08` · `202608`；别名 `核算年月` / `月份`） | ✅ |
| `domain.PROC_COLUMNS` 的 10 个材料列 | 入库 / 出库各 5 类（主辅材 · 工具 · 劳保 · 周转材料 · 临时设施） | **至少 1 列** |

- ⭐ **列名的唯一主人 = `domain.PROC_COLUMNS`** —— 本文件不另抄一份列名，只按 label 认列。
- ⚠️ **机械 6 列不导入**：机械列**全段手录**（旁路表 `proc_mech_manual`，见 `mech_ui.py`）
  ⇒ 文件里出现就**显式列出来给人看**（不静默忽略、也不顺手写进快照）。
- ⚠️ 认不出的列**列出来提示**（用户台账常带附注列）—— **不算错**；但**一列材料列都没有 ⇒ 报错**
  （那说明这文件不是过程资料，导进去只会污染历史段）。

## 三条硬纪律

1. **落库前必须预览**：预览阶段**一个字节都不写库**；
2. **异常行逐条列出**（行号 + 原因），**不静默丢弃**；
3. **改历史段 = 再导一次**（同批**整批回滚**后重导 / 另起新批次）—— 回滚只置状态、**不物理删**（§5.2.5 ②）。

⚠️ 本模块**只做 Excel 的解析与编排**：金额判定走 `core.money`，落库走 `repository.import_snapshot`，
   ⛔ 本层**不自己写库**、也**不碰正式段**（库存单据）与**机械手录**。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from app.core.errors import MustReportError
from app.core.money import MoneyError, to_money
from app.mod06_proc import domain as D

MAX_ROWS = 2000
HEADER_SCAN_ROWS = 15          # 表头只在**前若干行**里找（用户台账常有标题行）

# 「核算月」列的**别名**（其余列名一律精确匹配 `domain.PROC_COLUMNS` 的 label —— 不猜）
YM_HEADERS: tuple[str, ...] = ("核算月", "核算年月", "月份")
YM_SUFFIXES: tuple[str, ...] = ("（元）", "(元)", "金额")     # 表头尾缀（"入库主辅材金额" ⇒ "入库主辅材"）


def _norm(value) -> str:
    """表头 / 单元格文本归一：去空白（含全角）⇒ 去掉尾缀。"""
    text = "" if value is None else str(value)
    return text.replace("\u3000", "").replace(" ", "").strip()


def _norm_header(value) -> str:
    text = _norm(value)
    for suffix in YM_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[: -len(suffix)]
    return text


def material_labels() -> dict[str, str]:
    """`{表头 label: 列 key}` —— **材料 10 列的正向映射**（唯一主人 = `domain.PROC_COLUMNS`）。"""
    return {col["label"]: col["key"] for col in D.PROC_COLUMNS if col["key"] in D.MATERIAL_KEYS}


def mech_labels() -> dict[str, str]:
    """`{表头 label: 列 key}` —— 机械 6 列（**认出来只为提示「不导入」**）。"""
    return {col["label"]: col["key"] for col in D.PROC_COLUMNS if col["key"] in D.MECH_KEYS}


def read_sheet(data: bytes) -> list[list]:
    """xlsx 字节 → 网格（**取第一个工作表**；用户给的定稿文件，不假设表名）。

    ⚠️ 读表已收编 `import_kit.readers.read_grid`（`TAIL-69` Phase 2）——
       表头识别（`find_header`/`map_columns`）与核算月归一仍是**本域**口径（§5.2.5）。
    """
    from app.import_kit.readers import read_grid

    return read_grid(data, max_rows=MAX_ROWS)[0]


@dataclass
class ImportPlan:
    """**预览结果** —— 落库前给人看的全部东西。"""

    rows: list[dict] = field(default_factory=list)          # 将写入快照的行（只含非空列）
    anomalies: list[dict] = field(default_factory=list)     # 不入库的行（行号 + 原因）
    ignored_mech: list[str] = field(default_factory=list)   # 文件里出现、但不导入的机械列名
    unknown_headers: list[str] = field(default_factory=list)  # 认不出的列名（提示，不算错）
    header_row: int = 0                                     # 表头在 Excel 里的行号（1 基，报错好定位）

    @property
    def writable(self) -> int:
        return len(self.rows)

    @property
    def months(self) -> list[str]:
        return sorted({str(r.get("ym") or "") for r in self.rows if r.get("ym")})

    @property
    def default_cutoff(self) -> str:
        """**默认截止核算月 = 导入数据里最大的核算月**（§5.2.5 ①）。"""
        months = self.months
        return months[-1] if months else ""


def find_header(grid: list[list]) -> int:
    """定位表头行：前若干行里**同时含「核算月」类列名与至少一个材料列名**的那一行。"""
    mats = set(material_labels())
    for idx, row in enumerate(grid[:HEADER_SCAN_ROWS]):
        cells = {_norm_header(c) for c in row}
        if (cells & set(YM_HEADERS)) and (cells & mats):
            return idx
    raise MustReportError(
        f"在文件的前 {HEADER_SCAN_ROWS} 行里找不到表头（应同时含「核算月」与至少一个材料列名，如"
        f"「入库主辅材」）—— 请核对表头后再导"
    )


def map_columns(header: list) -> dict[str, int]:
    """表头 → `{列 key 或 `ym`: 下标}`；**一列材料列都没有 ⇒ 报错不猜**。"""
    names = [_norm_header(c) for c in header]
    index = {n: i for i, n in enumerate(names) if n}
    out: dict[str, int] = {}
    ym_at = next((index[h] for h in YM_HEADERS if h in index), None)
    if ym_at is None:
        raise MustReportError(f"文件里没有「核算月」列（可写：{' / '.join(YM_HEADERS)}）")
    out["ym"] = ym_at
    for label, key in material_labels().items():
        if label in index:
            out[key] = index[label]
    if not [k for k in out if k != "ym"]:
        raise MustReportError(
            "文件里一列材料列都没认出来 —— 过程资料的列名见 §5.2.2（如「入库主辅材」「出库工具」）；"
            "这份文件看起来不是过程资料"
        )
    return out


def _cell(row: list, at: int) -> str:
    return _norm(row[at]) if at < len(row) else ""


def _money_or_none(text: str, *, label: str, line: int):
    """单元格 → 金额。**空 ⇒ `None`（不写这一列）**；非数字 / 负数 ⇒ `MustReportError`。"""
    if not text:
        return None
    try:
        value = to_money(text.replace(",", "").replace("，", ""))
    except (MoneyError, ArithmeticError, ValueError) as exc:
        raise MustReportError(f"第 {line} 行「{label}」不是数字：{text!r}") from exc
    if value < 0:
        raise MustReportError(f"第 {line} 行「{label}」为负数（{value}）—— 过程资料的金额 ≥ 0")
    return value


def parse_sheet(data: bytes) -> ImportPlan:
    """xlsx 字节 → `ImportPlan`（**纯函数：一个字节都不落库**）。"""
    grid = read_sheet(data)
    if not grid:
        raise MustReportError("文件是空的（没有工作表内容）")
    head = find_header(grid)
    index = map_columns(grid[head])
    labels = {v: k for k, v in material_labels().items()}      # key → label（报错时写列名）

    plan = ImportPlan(header_row=head + 1)
    names = {_norm_header(c) for c in grid[head]}
    plan.ignored_mech = [c["label"] for c in D.PROC_COLUMNS
                         if c["key"] in D.MECH_KEYS and c["label"] in names]
    known = set(material_labels()) | set(mech_labels()) | set(YM_HEADERS) | {""}
    plan.unknown_headers = sorted(n for n in names if n and n not in known)

    for offset, raw in enumerate(grid[head + 1:], start=head + 2):
        if not any(_norm(c) for c in raw):
            continue                                    # 整行空 ⇒ 静默跳过（不算异常）
        ym = D.normalize_ym(_cell(raw, index["ym"]))
        if not ym:
            plan.anomalies.append({"line": offset, "reason":
                                   f"核算月认不出：{_cell(raw, index['ym']) or '（空）'!r} —— 写 2026-08 这种形态"})
            continue
        row: dict = {"ym": ym}
        bad = ""
        for key, at in index.items():
            if key == "ym":
                continue
            try:
                value = _money_or_none(_cell(raw, at), label=labels.get(key, key), line=offset)
            except MustReportError as exc:
                bad = exc.message
                break
            if value is not None:
                row[key] = value
        if bad:
            plan.anomalies.append({"line": offset, "ym": ym, "reason": bad})
            continue
        if len(row) == 1:
            plan.anomalies.append({"line": offset, "ym": ym, "reason":
                                   "只有核算月、一个材料金额都没有 —— 分不清「确实为 0」还是「漏填」，"
                                   "请补 0 或删掉该行"})
            continue
        plan.rows.append(row)
    if not plan.rows:
        why = "；".join(f"行 {a['line']}：{a['reason']}" for a in plan.anomalies[:3]) or "文件里没有数据行"
        raise MustReportError(
            f"文件里没有一行可用的定稿数据（共 {len(plan.anomalies)} 行异常）—— {why}。"
            "历史段未被改动（不写库）"
        )
    return plan


def next_batch(*, at: datetime | None = None) -> str:
    """批次号 = `PROC-<yyyymmddHHMMSS>`（整批回滚按它，§5.2.5 ②）。"""
    return "PROC-" + (at or datetime.now()).strftime("%Y%m%d%H%M%S")


def commit(s, plan: ImportPlan, *, warehouse: str, batch: str, operator: str = "",
           cutoff_ym: str | None = None) -> dict:
    """**落库**（§5.2.5 ①）：写快照 ＋ 记批次 ＋ 设定该项目的**截止核算月**。

    ⭐ 只走 `repository.import_snapshot` ⇒ **只写历史段**：**不碰正式段（库存单据）、不碰机械手录**。
    """
    from app.mod06_proc import repository as repo

    batch_obj = repo.import_snapshot(
        s, warehouse=warehouse, rows=plan.rows, batch_no=batch,
        operator=operator, cutoff_ym=str(cutoff_ym or plan.default_cutoff or ""),
    )
    return {"batch": batch_obj.batch_no, "rows": batch_obj.row_count,
            "cutoff_ym": batch_obj.cutoff_ym, "months": plan.months}


def check_report(s, *, warehouse: str, batch_no: str, cutoff_ym: str) -> dict:
    """⭐ **核对报告**（与付款域同构的「漏记清单」）：本批月份 ＋ **会被显示成空态的月份**。

    「会被显示成空态的月份」= **截止核算月及以前**、**i8 库存单据里有数据**、而**本批快照里没有**的月份
    —— 历史段**不回落** i8（§5.2.5 ①），所以这些月一定印空 ⇒ 要么确实该空，要么**Excel 漏了**。
    """
    from app.mod06_proc import repository as repo

    snap_months = {str(r.get("ym") or "") for r in repo.load_history(s)
                   if str(r.get("warehouse") or "") == warehouse}
    inv_months = {str(r.get("ym") or "") for r in repo.load_inv_rows(s)
                  if str(r.get("warehouse") or "") == warehouse}
    empty_months = sorted(m for m in inv_months
                          if m and cutoff_ym and m <= str(cutoff_ym) and m not in snap_months)
    return {"batch": batch_no, "cutoff_ym": str(cutoff_ym),
            "months": sorted(m for m in snap_months if m),
            "count": len(empty_months), "rows": empty_months}


def rollback(s, *, batch_no: str) -> int:
    """整批回滚（= `repository.rollback_batch`：置 `rolled_back`、**不物理删**）。"""
    from app.mod06_proc import repository as repo

    return repo.rollback_batch(s, batch_no=batch_no)


__all__ = ["MAX_ROWS", "HEADER_SCAN_ROWS", "YM_HEADERS", "YM_SUFFIXES", "ImportPlan",
           "material_labels", "mech_labels", "read_sheet", "find_header", "map_columns",
           "parse_sheet", "next_batch", "commit", "check_report", "rollback"]
