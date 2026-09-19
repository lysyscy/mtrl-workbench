"""集采台账 Excel **导入服务**（`M5-8`）—— 预览 ＋ 确认落库。

⭐ **形式**（用户 2026-09-19 定）：**上传他原来的台账** → 预览（含**列名核对**）→ 确认落库。
   ⛔ 不做"下载模板再填"作主路（他**已经有数据**；让表迁就模板 = 让工作方式迁就软件）。

⭐ **为什么不存暂存文件 / 不发 token**（这是本设计的关键取舍）：
   `parse` 只回**预览用的元信息**（工作表 / 列名 / 映射 / 条数 / 样例 / 跳过账），
   **不回全量行**；到 `commit` 时**前端把同一个文件再传一次**（它一直持有那个 `File` 对象）。
   ⇒ 服务端**无状态**：没有 tmp 文件要清理、不怕重启、不怕并发；而且**数据始终由后端自己解析**
     （⛔ 前端回传的"行数据"一律不信 —— 那才是最容易埋雷的做法）。

⚠️ **幂等** = **已存在的行不动**（同 `m04` 计划导入 / `m08` 库存导入的既有套路）。
   集采合同**没有合同编号**（用户台账里就没有）⇒ 幂等键 = **自然键**
   `(合同日期, 材料名称, 供应商, 合同金额)`，**范围 = 该项目内**（不同项目同材料同金额是正常的）。

⚠️ **只建主表行 ＋ 两条汇总发票行**（用户 2026-09-19 定：「直接把台账中的数导入到发票子表里的一条里，
   没必要再重新录了」）。付款**不导**（付款有它自己的两条来源：引用付款流水 / 手工录入，
   见 `M5-5` —— 台账里的"付款"列是**派生**出来的，导它会**重复计入**）。
"""

from __future__ import annotations

from decimal import Decimal

from app.mod11_jc import repository as R
from app.mod11_jc import excel_parse as P

#: 预览里每张表给几行样例（够人核对列名对不对就行，⛔ 不回全量 —— 见模块头那个取舍）。
SAMPLE_ROWS = 3

#: 预览里最多列几条"跳过的行"（全量太长没人看；落库回执里会给全量）。
SKIP_SHOW = 12

#: 主表字段 → `insert_contract` 的入参名（同名，这里只为"读起来一眼能对上"）。
#: ⚠️ 存档三列（`arch` / `arch_no` / `ret_date`）**不在** `insert_contract` 里 ⇒ 走白名单 `update_contract`。
_CORE = ("contract_date", "material_name", "supplier", "contract_amt",
         "trade_co", "trade_contract_amt", "remark")
_EXTRA = ("arch", "arch_no", "ret_date")


# ============================================================ 预览

def preview(data: bytes, filename: str) -> dict:
    """文件 ⇒ **每张工作表**的预览（列名 / 映射 / 条数 / 样例 / 跳过账）。

    ⚠️ ⛔ **不"取第 N 张表"**：用户样例的**第 1 张就是空表**（真数据在第 2 张）
       ⇒ 一律把表列出来，只给个"像主台账"的**提示**（`guess`），由人选。
    """
    sheets: list[dict] = []
    for name in P.sheet_names(data, filename):
        info: dict = {"name": name}
        try:
            grid = P.read_grid(data, filename, name)
        except Exception as exc:                       # noqa: BLE001 —— 单表读坏不该拖垮整个预览
            info.update({"error": f"{type(exc).__name__}: {exc}"[:120], "guess": False})
            sheets.append(info)
            continue
        rows = len(grid)
        cols = max((len(r) for r in grid), default=0)
        info.update({"rows": rows, "cols": cols})
        if rows == 0 or cols == 0:
            info.update({"guess": False, "note": "空表（没什么可导的）"})
            sheets.append(info)
            continue

        r1, r2 = P.detect_header(grid)
        labels = P.header_labels(grid, row1=r1, row2=r2)
        mapping = P.map_columns(labels)
        parsed = (P.parse_rows(grid, row2=r2, fields=mapping["fields"])
                  if mapping["fields"] else {"rows": [], "skipped": []})
        info.update({
            "header": {"row1": r1 + 1, "row2": r2 + 1},          # ⚠️ 给人看 ⇒ 1 基
            "labels": labels,
            "mapping": mapping,
            "counts": {"data": len(parsed["rows"]), "skipped": len(parsed["skipped"])},
            "sample": parsed["rows"][:SAMPLE_ROWS],
            "skipped": parsed["skipped"][:SKIP_SHOW],
            # 「像主台账」= 认出了字段 **且** 真有数据行
            "guess": bool(mapping["fields"]) and len(parsed["rows"]) > 0,
        })
        sheets.append(info)
    # ⚠️ 只**排序**、不筛选：像主台账的排前面（人选起来快），但每张表都在
    sheets.sort(key=lambda s: (not s.get("guess"), -int(s.get("rows") or 0)))
    # ⚠️ `field_labels` 回给前端**显示用**（"系统认成 合同日期"要给人看中文名，⛔ 不是给码看 `contract_date`）
    return {"ok": True, "file": filename, "sheets": sheets, "field_labels": P.FIELD_LABELS}


# ============================================================ 落库

def _natural_key(row: dict) -> tuple:
    """幂等键（**项目内**比较）：`(合同日期, 材料名称, 供应商, 合同金额)`。

    ⚠️ 集采合同**没有合同编号**（用户台账里就没有这一列）⇒ 只能用**自然键**。
    ⚠️ 金额归一成 `Decimal` 再比（`"100"` 与 `"100.00"` 必须算同一行），空 ⇒ `0`。
    """
    amt = row.get("contract_amt")
    return (
        str(row.get("contract_date") or "").strip(),
        str(row.get("material_name") or "").strip(),
        str(row.get("supplier") or "").strip(),
        str(Decimal(str(amt)) if amt not in (None, "") else Decimal("0")),
    )


def _row_problem(row: dict) -> str:
    """这行为什么**不能落库**（`""` = 可以）。⚠️ 返回**给人看的一句话**。"""
    if not str(row.get("material_name") or "").strip() and not str(row.get("supplier") or "").strip():
        return "材料名称与供应商都空着（认不出这是一条什么合同）"
    return ""


def commit(s, data: bytes, filename: str, *, sheet: str, project_key: str,
           mapping: dict | None = None, row1: int | None = None, row2: int | None = None) -> dict:
    """确认落库（**幂等**：已存在的行不动）。

    `row1` / `row2` 是**人看的两行表头号（1 基）**（前端预览里可改）；不给就用探测值。
    `mapping` = 人在预览页手改的列映射（`{"列下标": "字段名"}`，值 `""` = 忽略）⇒ **优先于**别名表。

    ⚠️ 只用**主表行** ＋ **两条汇总发票行**；**付款不导**（见模块头）。
    """
    project_id = R.project_id_by_key(s, project_key)
    if project_id is None:
        return {"ok": False, "kind": "err",
                "message": f"找不到项目（仓库名 {project_key!r}）—— 请先在「项目档案」建好"}

    grid = P.read_grid(data, filename, sheet)
    d1, d2 = P.detect_header(grid)
    r1 = (int(row1) - 1) if row1 else d1
    r2 = (int(row2) - 1) if row2 else d2
    labels = P.header_labels(grid, row1=r1, row2=r2)
    m = P.map_columns(labels, mapping=mapping)
    fields = m["fields"]
    if "contract_date" not in fields and "material_name" not in fields:
        return {"ok": False, "kind": "err",
                "message": "列名还没对上：至少要认出「合同日期」或「材料名称」—— 请在预览页把列名点对"}

    parsed = P.parse_rows(grid, row2=r2, fields=fields)
    rows = parsed["rows"]

    # 幂等键集合：该项目**已有**的行（一次查完，⛔ 不逐行查、⛔ 不猜 `list_contracts` 的参数名）
    from sqlalchemy import select

    from app.mod11_jc.models import JcContract

    seen: set[tuple] = set()
    for c in s.execute(select(JcContract).where(JcContract.project_id == int(project_id))).scalars():
        seen.add(_natural_key({"contract_date": c.contract_date, "material_name": c.material_name,
                               "supplier": c.supplier, "contract_amt": c.contract_amt}))

    added: list[dict] = []
    exists: list[dict] = []
    bad: list[dict] = []
    warned: list[dict] = []
    for n, row in enumerate(rows, start=1):
        key = _natural_key(row)
        if key in seen:
            exists.append({"row_no": n, "why": "库里已经有这一条了（**不动它**）"})
            continue
        problem = _row_problem(row)
        if problem:
            bad.append({"row_no": n, "why": problem})
            continue

        kwargs = {k: row.get(k) for k in _CORE if k in fields}
        kwargs["project_id"] = int(project_id)
        res = _add_contract(s, kwargs)
        if not res.get("ok"):
            bad.append({"row_no": n, "why": str(res.get("message") or "落库失败")})
            continue
        cid = int(res["id"])
        # 存档三列走**白名单** update（`insert_contract` 不收它们）
        extra = {k: row.get(k) for k in _EXTRA if k in fields}
        if extra:
            R.update_contract(s, cid, **extra)
        # 两条**汇总发票行**（用户定的：台账里的发票额就落一条，⛔ 不必逐张重录）
        for fld, kind, label in (("inv_sum", "supplier", "供应商"),
                                 ("trade_inv_sum", "trade", "贸易公司")):
            amt = row.get(fld)
            if amt in (None, ""):
                continue
            date = str(row.get("contract_date") or "").strip()
            if not date:
                warned.append({"row_no": n, "why": f"{label}发票额没落 —— 这条没有合同日期可用作发票日期"})
                continue
            inv = _add_invoice(s, cid, kind=kind, date=date, amount=amt)
            if not inv.get("ok"):
                warned.append({"row_no": n, "why": f"{label}发票额没落：{inv.get('message')}"})
        seen.add(key)
        added.append({"id": cid, "row_no": n,
                      "material_name": row.get("material_name"), "contract_amt": str(row.get("contract_amt") or 0)})

    return {
        "ok": True, "kind": "ok",
        "file": filename, "sheet": sheet, "project_key": project_key,
        "added": len(added), "exists": len(exists), "bad": len(bad), "warned": len(warned),
        "header": {"row1": r1 + 1, "row2": r2 + 1},
        "mapping": m,
        "items": added,
        "exists_items": exists,
        "bad_items": bad,
        "warn_items": warned,
        "skipped_rows": parsed["skipped"],
        "message": (f"导入完成：新增 {len(added)} 条 · 已存在 {len(exists)} 条（未动）"
                    f" · 不合格 {len(bad)} 条 · 提醒 {len(warned)} 条"),
    }


def _add_contract(s, kwargs: dict) -> dict:
    """走 `service.act_add_contract`（**判定归一处**：三态默认「纳入台账」由它给）。"""
    from app.mod11_jc import service as SV

    return SV.act_add_contract(s, **kwargs)


def _add_invoice(s, contract_id: int, *, kind: str, date: str, amount) -> dict:
    """走 `service.act_add_invoice`（校验在 `domain.invoice_problem`，⛔ 本层不另判）。"""
    from app.mod11_jc import service as SV

    return SV.act_add_invoice(s, contract_id=contract_id, kind=kind, date=date, amount=amount)


__all__ = ["SAMPLE_ROWS", "SKIP_SHOW", "preview", "commit"]
