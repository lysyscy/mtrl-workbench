"""集采台账 Excel **导入服务**（`M5-8`）—— 预览 ＋ 确认落库。

⭐ **形式**（用户 2026-09-19 定）：**上传他原来的台账** → 预览（含**列名核对**）→ 确认落库。
   ⛔ 不做"下载模板再填"作主路（他**已经有数据**；让表迁就模板 = 让工作方式迁就软件）。

⭐ **为什么不存暂存文件 / 不发 token**（这是本设计的关键取舍）：
   `parse` 只回**预览用的元信息**（工作表 / 列名 / 映射 / 条数 / 样例 / 跳过账），
   **不回全量行**；到 `commit` 时**前端把同一个文件再传一次**（它一直持有那个 `File` 对象）。
   ⇒ 服务端**无状态**：没有 tmp 文件要清理、不怕重启、不怕并发；而且**数据始终由后端自己解析**
     （⛔ 前端回传的"行数据"一律不信 —— 那才是最容易埋雷的做法）。

⭐⭐ **落库口径（2026-09-20 用户定案，覆盖 09-19 的"已存在不动"）**：

> 用户原话：「以**合同价为唯一锚点**，做到**两者互不覆盖**……单个项目同合同价的，就可以进行匹配，
> 用 excel 里的**材料名、发票金额、贸易公司发票金额、备注、存档、存档序号、寄回情况**来**覆盖** i8 抓出来的数据」

⇒ 流程是「**先抓 i8**（合同已在库里）→ **再导 Excel**（Excel 是来**补信息**的）」
  ⇒ 所以 **锚点 = 含税合同价**（`contract_amt`），**范围 = 单个项目内**（实测 347 条里只有 1 组同价：
  许昌安彩 `178600.00` 两条 —— 那是**同一份合同录了两遍**，不是"系统允许同价"）。

| Excel 行 | 动作 |
|---|---|
| 合同价**为空** | ⛔ **不参与匹配**（空值不许去撞任何行）⇒ 列进"配不上" |
| 命中 **1** 条 | ✅ **更新那条**：材料名 / 备注 / 存档三列 ＋ **汇总发票行**（用户列的字段） |
| 命中 **0** 条 | ⚠️ 列进"配不上"（⛔ **不静默新增** —— 锚点找不到 = 有问题，得先看） |
| 命中 **≥2** 条 | ⚠️ 列进"同价冲突"（**不猜** —— 和人挑供应商同一个道理） |

⚠️ **"互不覆盖"的机器化落点**：Excel **只动**它自己的地盘那几列；
  i8 的事实列（合同价 / 供应商 / 合同日期 / 甲方单位）**一个字都不碰**
  （反向由 `repository.FETCH_*` 三分法保证：i8 抓取也不碰 Excel 的地盘）。

⚠️ **发票汇总行**（用户 2026-09-19 定：「直接把台账中的数导入到发票子表里的一条里」）：
  ⛔ **不重复加** —— 该合同**已有同 kind 的发票行** ⇒ 跳过并**报出来**（再导一次不会翻倍）。
  付款**不导**（台账里的"付款"列是**派生**的，导它会**重复计入**，见 `M5-5`）。
"""

from __future__ import annotations

from decimal import Decimal

from app.mod11_jc import repository as R
from app.mod11_jc import excel_parse as P

#: 预览里每张表给几行样例（够人核对列名对不对就行，⛔ 不回全量 —— 见模块头那个取舍）。
SAMPLE_ROWS = 3

#: 预览里最多列几条"跳过的行"（全量太长没人看；落库回执里会给全量）。
SKIP_SHOW = 12

#: ⚠️ 存档三列**走白名单** `update_contract`（它们不在 i8 抓取的刷新范围里 —— 那是**人的地盘**）。
#: ⚠️ 原先还有一个 `_CORE`（"主表字段 → `insert_contract` 入参名"），**2026-09-20 随口径改成
#: "锚点匹配 ⇒ 更新已有"后就没用了** ⇒ **删掉**（本仓纪律：⛔ 不留"已废弃但仍能被调用"的死代码）。
#: ⚠️ 同理，`_EXTRA = ("arch","arch_no","ret_date")` 也随下面的 `EXCEL_COLS` **一起删了** ——
#: 它俩本来就是同一件事的两半，留一半只会让下一个人**再漏一次**（2026-09-20）。

#: ⭐⭐ **Excel 能覆盖的主表列**（= "Excel 的地盘"）—— 用户 2026-09-20 列的字段。
#:
#: | 列 | 用户当时的说法 |
#: |---|---|
#: | `material_name` | 材料名 |
#: | `method` | **付款方式** —— ⚠️ 他表里那列的表头叫「**详细付款方式**」（2026-09-20 晚补加） |
#: | `remark` | 备注 |
#: | `arch` / `arch_no` / `ret_date` | 存档 / 存档序号 / 寄回情况 |
#:
#: ⛔ **不在其中**的 = 来自 i8 的事实列（`contract_amt` / `supplier` / `contract_date` / `party_name`）
#:    —— 两边**互不覆盖**，见模块头。
#:
#: ⚠️⚠️ 为什么要抽成一个常量（而不是像原先那样在循环里写死 `("material_name", "remark")`）：
#:    **漏一列 = 那一列"认得出、白名单也放行、就是不写"，且全程不报错**。
#:    2026-09-20 真机就踩了：`method` 没在里面 ⇒ 用户导完发现"付款方式一个都没进来"。
#:    ⇒ 列的**唯一主人**在这儿；⚠️ 它与 `R.EDITABLE_COLS` 必须**是子集关系**（否则会被静默忽略），
#:    已由 `tests/test_acc_jc_import.py` 的一条断言钉住。
EXCEL_COLS: tuple[str, ...] = ("material_name", "method", "remark", "arch", "arch_no", "ret_date")


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
            # ⚠️⚠️ 认不出**锚点列**（合同价）⇒ 其它列认得再全，也**一条都配不上**
            #    （用户 2026-09-20：「有的合同里根本没有贸易公司合同金额和发票金额这两列，
            #     要注意匹配的问题」）⇒ 提前标出来。
            #    ⭐ `commit` 侧**还会再拦一次**（那里才是真动手的地方，见那段注释）。
            "anchor_missing": (bool(mapping["fields"]) and "contract_amt" not in mapping["fields"]),
            "note": ("⚠️ 没认出「合同价」列（供应商合同总价 / 合同总价 / 合同金额）"
                     "—— 它是**匹配锚点**，认不到就会**一条都配不上**"
                     if mapping["fields"] and "contract_amt" not in mapping["fields"] else ""),
        })
        sheets.append(info)
    # ⚠️ 只**排序**、不筛选：像主台账的排前面（人选起来快），但每张表都在
    sheets.sort(key=lambda s: (not s.get("guess"), -int(s.get("rows") or 0)))
    # ⚠️ `field_labels` 回给前端**显示用**（"系统认成 合同日期"要给人看中文名，⛔ 不是给码看 `contract_date`）
    return {"ok": True, "file": filename, "sheets": sheets, "field_labels": P.FIELD_LABELS}


# ============================================================ 落库

def _amount_key(v) -> str:
    """**锚点键**：金额归一成两位小数的字符串 —— `"100"` 与 `"100.00"` 必须是**同一个锚点**。

    ⚠️ **空 / 0 / 不是数 ⇒ 回空串**（= **不参与匹配**）：
       ⛔ 绝不让一个空锚点去"撞"库里任何一行 —— 那是"静默张冠李戴"最省事的做法。
    ⚠️ 用**字符串**做字典键（`Decimal` 可哈希但 `100` 与 `100.0` 不等价，字符串化后才稳）。
    """
    raw = str(v if v is not None else "").strip().replace(",", "").replace("¥", "")
    if raw == "":
        return ""
    try:
        d = Decimal(raw)
    except Exception:                       # noqa: BLE001 —— 认不出 ⇒ 当"没有锚点"，不是抛错
        return ""
    if d == 0:
        return ""
    return str(d.quantize(Decimal("0.01")))


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

    # ⭐⭐ **锚点列必须在**（用户 2026-09-20：「有的合同里根本没有贸易公司合同金额和发票金额这两列，
    #     要注意匹配的问题」）—— 匹配锚点 = **含税合同价**（`contract_amt`），范围 = 单个项目内。
    #     ⚠️⚠️ 认不到它 ⇒ **每一行都会走进 "配不上"** ⇒ 回执是一大片"配不上"，而人**看不出根因是列没认对**
    #        （会以为"这些合同库里都没有"）⇒ 必须**在动手之前**拦住并说清（禁静默）。
    #     ⚠️ 注意：**缺「贸易公司那两列」不是错**（实测兰考 / 内蒙宜化 / 周口太康就是那样）——
    #        那两列只是"不更新"而已；真正致命的是缺**锚点**这一列。
    if "contract_amt" not in fields:
        return {"ok": False, "kind": "err", "message": (
            "这张表**没认出「合同价」列**（认得的写法：供应商合同总价 / 合同总价 / 合同金额）—— "
            "它是**匹配用的锚点**（在同一个项目里按它找已有合同），认不到就会**一条都配不上**。"
            "请在预览页把那一列点成「供应商合同总价」；若这张表本来就**没有**合同价列，"
            "那它导不了（没有锚点就无从判断该更新哪一条）。")}

    parsed = P.parse_rows(grid, row2=r2, fields=fields)
    rows = parsed["rows"]

    from sqlalchemy import select

    from app.mod11_jc.models import JcContract, JcInvoice

    # ⭐⭐ **锚点索引**：该项目内已有合同的 `合同价 -> [合同…]`（**一次查完** ⇒ ⛔ 不逐行查 = N+1）。
    by_amt: dict[str, list] = {}
    for c in s.execute(select(JcContract).where(JcContract.project_id == int(project_id))).scalars():
        k = _amount_key(c.contract_amt)
        if k:
            by_amt.setdefault(k, []).append(c)

    updated: list[dict] = []
    unmatched: list[dict] = []
    ambiguous: list[dict] = []
    bad: list[dict] = []
    warned: list[dict] = []
    for n, row in enumerate(rows, start=1):
        raw_amt = row.get("contract_amt")
        key = _amount_key(raw_amt)
        if not key:
            unmatched.append({"row_no": n, "amount": str(raw_amt or ""),
                              "material_name": str(row.get("material_name") or ""),
                              "why": "**合同价为空 / 为 0** ⇒ 不参与匹配（⛔ 空值不许去撞库里任何一行）"})
            continue
        cands = by_amt.get(key) or []
        if len(cands) == 0:
            unmatched.append({"row_no": n, "amount": key,
                              "material_name": str(row.get("material_name") or ""),
                              "why": f"该项目内**没有**合同价 = {key} 的合同（⛔ 不静默新增 —— 锚点找不到先看）"})
            continue
        if len(cands) > 1:
            ambiguous.append({"row_no": n, "amount": key,
                              "ids": [int(c.id) for c in cands],
                              "why": f"该项目内有 **{len(cands)}** 条同价合同 ⇒ **不猜**（和人挑供应商同一个道理）"})
            continue

        cur = cands[0]
        cid = int(cur.id)
        problem = _row_problem(row)
        if problem:
            bad.append({"row_no": n, "why": problem})
            continue

        # ⭐ **只更"Excel 的地盘"那几列**（用户 2026-09-20 列的字段）——
        #    ⛔ 合同价 / 供应商 / 合同日期 / 甲方单位**一个字都不碰**（那是 i8 的事实，两边互不覆盖）。
        # ⚠️⚠️ 必读：**拼 cols 这一步漏一列 = 那一列"认得出、白名单也放行、就是不写"**，
        #    而且**全程不报错**（2026-09-20 真机踩到：`method` 就是这么丢的 ——
        #    用户表里那列叫「详细付款方式」，预览页显示"已认成 付款方式"，
        #    落库后**台账里却一个都没有**）。⇒ 列的**唯一主人** = `EXCEL_COLS`，⛔ 别再散在循环里写死。
        cols: dict = {}
        for k in EXCEL_COLS:
            if k in fields:
                cols[k] = row.get(k)
        if cols:
            R.update_contract(s, cid, **cols)

        # ⭐ **汇总发票行**：⛔ **不重复加** —— 已有同 kind 的发票行 ⇒ 跳过并报出来（再导一次不会翻倍）。
        already = {str(x) for x in s.execute(
            select(JcInvoice.kind).where(JcInvoice.contract_id == cid)).scalars()}
        for fld, kind, label in (("inv_sum", "supplier", "供应商"),
                                 ("trade_inv_sum", "trade", "贸易公司")):
            amt = row.get(fld)
            if amt in (None, ""):
                continue
            if kind in already:
                warned.append({"row_no": n, "why": f"合同 #{cid} 已有「{label}发票」行 ⇒ **未重复导入**"
                                                   f"（发票子表是一合同 1..N 张，重导会翻倍）"})
                continue
            date = str(row.get("contract_date") or "").strip() or str(cur.contract_date or "").strip()
            if not date:
                warned.append({"row_no": n, "why": f"{label}发票额没落 —— 这张合同没有日期可用作发票日期"})
                continue
            inv = _add_invoice(s, cid, kind=kind, date=date, amount=amt)
            if not inv.get("ok"):
                warned.append({"row_no": n, "why": f"{label}发票额没落：{inv.get('message')}"})
            else:
                already.add(kind)

        # ⚠️ 落地后**从索引里摘掉**：同一份 Excel 里两行撞同一个锚点 ⇒ 后一行必须被判"已配对"，
        #    ⛔ 不然两行都会去写同一条合同（后写的把先写的**静默覆盖**）。
        by_amt[key] = [c for c in cands if int(c.id) != cid]
        updated.append({"id": cid, "row_no": n, "amount": key,
                        "material_name": str(row.get("material_name") or cur.material_name or ""),
                        "fields": sorted(cols)})

    return {
        "ok": True, "kind": "ok",
        "file": filename, "sheet": sheet, "project_key": project_key,
        "updated": len(updated), "unmatched": len(unmatched),
        "ambiguous": len(ambiguous), "bad": len(bad), "warned": len(warned),
        "header": {"row1": r1 + 1, "row2": r2 + 1},
        "mapping": m,
        "items": updated,
        "unmatched_items": unmatched,
        "ambiguous_items": ambiguous,
        "bad_items": bad,
        "warn_items": warned,
        "skipped_rows": parsed["skipped"],
        "message": (f"导入完成：**按合同价匹配上并更新 {len(updated)} 条**"
                    f" · 配不上 {len(unmatched)} 条 · 同价冲突 {len(ambiguous)} 条"
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


__all__ = ["SAMPLE_ROWS", "SKIP_SHOW", "EXCEL_COLS", "preview", "commit"]
