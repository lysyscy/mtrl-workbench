"""`MOD-06` 过程资料 —— **域内核（纯函数：不连库、不写路由）**。

口径主人：
- 《说明书》**§5.2.1**（它是什么）· **§5.2.2**（17 列列结构）· **§5.2.3**（三个数据来源 ＋ 材料数据单向流）
  · **§5.2.4**（调整单：差异只改库存单据，过程资料是**视图**不是第二份账）· **§5.2.5**（历史段 / 正式段）
- `DEV-R-01`（域主线 = 过程资料）· `DEV-R-07`（数据修正方式 = 调整单）
- ⭐ **材料 5 类别的取值字段与归集规则** ＝ **用户口述 2026-09-16**：
  「**物料性质**分 主材 / 辅材 / 工具 / 劳保 / 周转材料 / 临时设施」⇒ **主材 + 辅材 归为「主辅材」**。
  ⚠️ 这条《说明书》**§5.2.2 只列了列名、没写取值字段** ⇒ 属**待回写**口径（见工程 `.codebuddy/` 记录）。
- 页面 / 交互 = MOD-06及docs/requirements/interaction-rules.md；列名与合计/总求和的分段按现行说明书。

⚠️ **刻意与原型演示实现不同（口径 > 原型，已在代码里写明依据）**：
**核算月取库存单据的「核算年月」**（网格 1 起算第 2/3 列），不是原型的「单据日期前缀」
—— 依据 §9.2（材料报表类按**核算年月**）与 §3.4（导出条件 = 核算年月 + 项目）。
"""

from __future__ import annotations

from decimal import Decimal

from app.core.money import sum_money, to_money
from app.mod08_inv.adjustment_values import effective_value, LABELS

# ============================================================ 材料类别（用户口述 2026-09-16）

MATERIAL_PROPERTIES: tuple[str, ...] = ("主材", "辅材", "工具", "劳保", "周转材料", "临时设施")
PROPERTY_TO_CATEGORY: dict[str, str] = {
    "主材": "主辅材", "辅材": "主辅材", "工具": "工具",
    "劳保": "劳保", "周转材料": "周转材料", "临时设施": "临时设施",
    "周转物资": "周转材料",
}
CATEGORIES: tuple[str, ...] = ("主辅材", "工具", "劳保", "周转材料", "临时设施")   # §5.2.2 的 5 类

# 机械 6 列（⭐ 2026-09-26 用户裁定：**历史段以「过程资料导入」的值为准 · 正式段手录**；
# §5.2.5 —— 改数据源只动 `column_source` / `MECH_SOURCE_BY_SECTION`，**不动页面**）
MECH_COLUMNS: tuple[str, ...] = (
    "租分公司设备", "内租设备", "外租零租含税", "外租包月含税",
    "外租零租不含税", "外租包月不含税",
)

# ============================================================ 17 列列结构（§5.2.2）

YM_KEY = "ym"


def _cols() -> tuple[dict, ...]:
    out: list[dict] = [{"key": YM_KEY, "label": "核算月", "type": "text"}]
    for cat in CATEGORIES:
        out.append({"key": f"in_{cat}", "label": f"入库{cat}", "type": "num"})
    for cat in CATEGORIES:
        out.append({"key": f"out_{cat}", "label": f"出库{cat}", "type": "num"})
    for i, name in enumerate(MECH_COLUMNS):
        out.append({"key": f"mech_{i}", "label": name, "type": "num", "mech": True})
    return tuple(out)


PROC_COLUMNS: tuple[dict, ...] = _cols()
PROC_KEYS: tuple[str, ...] = tuple(c["key"] for c in PROC_COLUMNS)
DATA_KEYS: tuple[str, ...] = tuple(k for k in PROC_KEYS if k != YM_KEY)   # 16 个数据列
MATERIAL_KEYS: tuple[str, ...] = tuple(k for k in DATA_KEYS if not k.startswith("mech_"))
MECH_KEYS: tuple[str, ...] = tuple(k for k in DATA_KEYS if k.startswith("mech_"))

# 「总求和」的**四段**（照原型：`SEG=[1,6,11,15]` ⇒ 入库 5 · 出库 5 · 机械前 4 · 不含税 2）
# ⚠️ 不含税的 2 列**单独成段**、不并入机械前 4 列（用户 2026-09-13 口径，原型已实现）
SUM_SEGMENTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("入库", tuple(f"in_{c}" for c in CATEGORIES)),
    ("出库", tuple(f"out_{c}" for c in CATEGORIES)),
    ("机械", tuple(f"mech_{i}" for i in range(4))),
    ("不含税", tuple(f"mech_{i}" for i in (4, 5))),
)

# ============================================================ 数据来源（§5.2.3 · §5.2.5）

SOURCE_INV = "inv_detail"        # 正式段材料列：**只读引用**库存单据
SOURCE_SNAPSHOT = "proc_history"  # 历史段：**导入的定稿快照**（材料 ＋ 机械，不引用库存单据，§5.2.5）
SOURCE_MANUAL = "manual"         # 机械 6 列**正式段**：手录旁路表

# 两段（§5.2.5）：分界 = **截止核算月**；历史段 ≤ 截止，正式段 > 截止
SECTION_HISTORY = "history"
SECTION_FORMAL = "formal"

#: 材料 10 列的**静态来源**（它们的来源**只看段**：历史 ⇒ 快照 / 正式 ⇒ 库存单据）。
#: ⚠️⚠️ **机械 6 列刻意不在本表里** —— 它们的来源**也按段切**（见 `MECH_SOURCE_BY_SECTION`），
#:    静态表表达不了 ⇒ 塞进来就等于给出一份"恒为手录"的**第二说法**（改前的老毛病）。
COLUMN_SOURCE: dict[str, str] = {k: SOURCE_INV for k in MATERIAL_KEYS}

#: ⭐⭐ **机械 6 列的来源按段切**（用户 2026-09-26 裁定）：
#:   · 历史段（≤ 截止核算月）⇒ **以过程资料导入的定稿快照为准**
#:     （用户原话：「历史机械费都填在过程资料 excel 里」）；
#:   · 正式段（> 截止核算月）⇒ **手录**
#:     （用户原话：「机械费手录仅限于**正式启用系统后**」）。
MECH_SOURCE_BY_SECTION: dict[str, str] = {
    SECTION_HISTORY: SOURCE_MANUAL,
    SECTION_FORMAL: SOURCE_MANUAL,
}


def section_of(ym: str, cutoff_ym: str | None) -> str:
    """该核算月落在哪一段（**未设截止核算月 ⇒ 一律正式段**）。"""
    if cutoff_ym and str(ym) <= str(cutoff_ym):
        return SECTION_HISTORY
    return SECTION_FORMAL


def column_source(key: str, *, ym: str, cutoff_ym: str | None, has_inventory: bool = False) -> str:
    """列来源唯一出口：材料同月优先 i8，无 i8 读有效历史；机械统一有效表。"""
    if key in MECH_KEYS:
        return SOURCE_MANUAL
    if has_inventory:
        return SOURCE_INV
    return SOURCE_SNAPSHOT


def column_editable(key: str, *, ym: str, cutoff_ym: str | None) -> bool:
    """机械任何月份可编辑，材料只读；截止只筛选本次导入。"""
    return key in MECH_KEYS

# ⛔ 本页**不得出现**的自算表述 / 不得提供的入口（001-08：材料费只作引用 · 只读）
FORBIDDEN_PHRASES: tuple[str, ...] = ("理论上 =", "理论上=")
FORBIDDEN_ACTIONS: tuple[str, ...] = ("editMaterial", "edit_material", "materialEdit")


def column_meta(key: str) -> dict | None:
    for col in PROC_COLUMNS:
        if col["key"] == key:
            return col
    return None


def to_category(material_property: str | None) -> str | None:
    """物料性质 → 5 类别之一；**认不出的取值返回 `None`**（不臆造、不兜底）。"""
    return PROPERTY_TO_CATEGORY.get(str(material_property or "").strip())


def normalize_ym(text) -> str:
    """**用户输入的核算月** → `YYYY-MM`（接受 `2026-8` / `2026/08` / `2026.08` / `202608`）。

    ⚠️ **认不出 ⇒ 返回空串**（调用方据此报错）—— 不猜、不取当月顶替（那是另一种臆造）。
    出口唯一：机械手录表单（`mech_ui`）与历史导入解析（`importer`）**都用这一个**。
    """
    raw = str(text or "").strip().replace("/", "-").replace(".", "-")
    if not raw:
        return ""
    if "-" in raw:
        year, _, month = raw.partition("-")
    elif raw.isdigit() and len(raw) == 6:
        year, month = raw[:4], raw[4:]
    else:
        return ""
    if not (year.isdigit() and month.isdigit()) or len(year) != 4:
        return ""
    mm = int(month)
    if not 1 <= mm <= 12:
        return ""
    return f"{int(year):04d}-{mm:02d}"


# ============================================================ 材料列：从库存单据引用（原始 / 调整后）


def row_material_amount(row: dict, *, adjusted: bool):
    """一行库存单据的**材料金额**：`adjusted=True` 取调整后金额（无调整单 ⇒ 取原始），否则取原始。"""
    if adjusted and row.get("adj_amount") not in (None, ""):
        return to_money(row["adj_amount"])
    if row.get("amount") in (None, ""):
        return None
    return to_money(row["amount"])


def material_by_month(
    inv_rows: list[dict], *, warehouse: str, adjusted: bool
) -> dict[str, dict[str, Decimal]]:
    """把某个项目的库存单据汇成 `{核算月: {列 key: 金额}}`（材料 10 列）。

    - 项目键 = **仓库名**（§2.7.4）；
    - 类别 = **物料性质**；⚠️ **认不出类别 / 无金额的行被跳过**（不臆造 0）；
    - **出入库方向**决定落在入库列还是出库列；方向也不是「入库 / 出库」的行**跳过**。
    """
    out: dict[str, dict[str, Decimal]] = {}
    for row in inv_rows or ():
        if str(row.get("warehouse") or "") != warehouse:
            continue
        direction = str(row.get("direction") or "")
        if direction not in ("入库", "出库"):
            continue
        category = to_category(effective_value(row, "material_property") if adjusted else row.get("material_property"))
        if category is None:
            continue
        amount = row_material_amount(row, adjusted=adjusted)
        if amount is None:
            continue
        ym = str(row.get("ym") or "")
        if not ym:
            continue
        key = f"{'in' if direction == '入库' else 'out'}_{category}"
        bucket = out.setdefault(ym, {})
        bucket[key] = (bucket.get(key) or Decimal("0.00")) + amount
    return {ym: {k: to_money(v) for k, v in kv.items()} for ym, kv in out.items()}


def mech_by_month(manual_rows: list[dict], *, warehouse: str) -> dict[str, list[Decimal | None]]:
    """机械 6 列的**手录值**（旁路表）：`{核算月: [6 个金额]}` —— ⭐ **只服务正式段**（见模块头）。

    ⚠️ 历史段的机械费**不走这里**（那是导入的快照值）—— 按段取数是 `build_matrix` 的事。
    """
    out: dict[str, list[Decimal | None]] = {}
    for row in manual_rows or ():
        if str(row.get("warehouse") or "") != warehouse:
            continue
        ym = str(row.get("ym") or "")
        if not ym:
            continue
        out[ym] = [None if row.get(f"mech_{i}") is None else to_money(row[f"mech_{i}"])
                   for i in range(len(MECH_COLUMNS))]
    return out


# ============================================================ 表体（一个月一行 · 月份升序）

TAB_RAW = 0          # 表① 原始表
TAB_ADJUSTED = 1     # 表② 调整后表
TAB_DIFF = 2         # 差异表
TABS: tuple[tuple[int, str], ...] = ((TAB_RAW, "表① 原始表"), (TAB_ADJUSTED, "表② 调整后表"),
                                     (TAB_DIFF, "差异表"))
DEFAULT_TAB = TAB_ADJUSTED      # ⭐ 进入页面默认停在「调整后表」（001-01）


def tab_of(value) -> int:
    try:
        tab = int(value)
    except (TypeError, ValueError):
        return DEFAULT_TAB
    return tab if tab in (TAB_RAW, TAB_ADJUSTED, TAB_DIFF) else DEFAULT_TAB


def snapshot_by_month(
    snapshot_rows: list[dict], *, warehouse: str
) -> dict[str, dict[str, Decimal]]:
    """**历史段**的列值：来自「过程资料历史导入」的**定稿快照**（§5.2.5 ①）—— 材料 10 列 ＋ **机械 6 列**。

    ⚠️ 快照是**独立载体** —— 本函数**只看快照**，**不回落库存单据**（回落就等于历史段被源数据覆盖）。
    ⭐ 2026-09-26：**机械 6 列也走快照**（历史机械费来自导入）；⚠️ 但本函数只负责"把快照摊平"，
       **哪一段读它**由 `build_matrix` 按 `column_source` 决定（⛔ 别在这里判段）。
    """
    out: dict[str, dict[str, Decimal]] = {}
    for row in snapshot_rows or ():
        if row.get('material_manual'):
            continue
        if str(row.get("warehouse") or "") != warehouse:
            continue
        ym = str(row.get("ym") or "")
        if not ym:
            continue
        bucket = out.setdefault(ym, {})
        for key in (MATERIAL_KEYS + MECH_KEYS):
            if row.get(key) not in (None, ""):
                bucket[key] = (bucket.get(key) or Decimal("0.00")) + to_money(row[key])
    return {ym: {k: to_money(v) for k, v in kv.items()} for ym, kv in out.items()}


def build_matrix(
    *,
    inv_rows: list[dict],
    manual_rows: list[dict] | None = None,
    history_rows: list[dict] | None = None,
    warehouse: str,
    adjusted: bool,
    cutoff_ym: str | None = None,
) -> list[dict]:
    """按月份组装有效金额；截止仅保留展示分组兼容，不遮挡任何已写入金额。"""
    formal = material_by_month(inv_rows, warehouse=warehouse, adjusted=adjusted)
    history = snapshot_by_month(history_rows or [], warehouse=warehouse)
    mech = mech_by_month(manual_rows or [], warehouse=warehouse)
    material_manual = {}
    for item in history_rows or []:
        if item.get('material_manual') and item.get('warehouse') == warehouse and item.get('ym', '') <= '2025-11':
            cells = material_manual.setdefault(item['ym'], {})
            cells.update({key: None if item[key] is None else to_money(item[key]) for key in MATERIAL_KEYS if key in item})

    inv_months = {str(r.get("ym") or "") for r in inv_rows or ()
                  if str(r.get("warehouse") or "") == warehouse and r.get("ym")}
    months = sorted(inv_months | set(history) | set(mech) | set(material_manual))
    rows: list[dict] = []
    for ym in months:
        section = section_of(ym, cutoff_ym)
        source = column_source(MATERIAL_KEYS[0], ym=ym, cutoff_ym=cutoff_ym,
                               has_inventory=ym in inv_months)
        bucket = (formal if source == SOURCE_INV else history).get(ym)
        history_bucket = history.get(ym)
        # ⚠️⚠️ 「该月材料有没有数据」**只看材料 10 列**（⛔ 别看 bucket 整体是不是空）：
        #    自 2026-09-26 起历史段的 bucket 里**还装着机械列** ⇒ 若用 `bucket is None` 判，
        #    那种"**只有机械费、材料一列没填**"的月份会被判成"材料也有数"⇒ 材料列从 `None`（空态）
        #    变成 `0.00`（**凭空多一笔 0**）。这正是"空 ≠ 0"要守的地方。
        has_mat = bool(bucket) and any(k in bucket for k in MATERIAL_KEYS)
        overrides = material_manual.get(ym, {}) if source != SOURCE_INV else {}
        row: dict = {YM_KEY: ym, "section": section, "material_empty": not has_mat and not any(v is not None for v in overrides.values()),
                     "material_editable": ym <= '2025-11' and ym not in inv_months}
        for key in DATA_KEYS:
            if key in MECH_KEYS:
                idx = int(key.split("_")[1])
                row[key] = mech.get(ym, [Decimal("0.00")] * len(MECH_COLUMNS))[idx]
            elif key in overrides:
                row[key] = overrides[key]
            elif not has_mat:
                row[key] = None                      # 空态（不臆造 0）
            else:
                row[key] = bucket.get(key, Decimal("0.00"))
        rows.append(row)
    return rows


def difference_rows(raw_rows: list[dict], adjusted_rows: list[dict]) -> list[dict]:
    """**导出的「差异表」** = 两张表**逐格之差**（调整后 − 原始），行形状与 `build_matrix` **完全一致**。

    ⚠️ 与页面的**差异表**（`diff_rows`：逐**单据**列原值 / 调整后 / 差额）是**两个东西**，别混：
       · 页面那张 = 「**哪几张单据被改过**」的明细入口（§5.2.4「差异表是入口不是死表」）；
       · 导出这份 = **逐月逐列的差额网格** —— 用户 **2026-09-18 裁定**：
         「差异表和汇总表的**形态完全相同**，就是数据不一样，最多是导出的文件名不一样」
         ⇒ 同一张 `汇总表` 模板 ＋ 同一套列映射 ＋ 同一套尾块，**只有取数不同**。
    ⚠️ 两表的月集合同源同口径 ⇒ 按月对齐；某一格**两边都空**（空态）⇒ 差额也**空**（⛔ 不写 0）。
    """
    raw_by = {str(r.get(YM_KEY) or ""): r for r in raw_rows or ()}
    adj_by = {str(r.get(YM_KEY) or ""): r for r in adjusted_rows or ()}
    out: list[dict] = []
    for ym in sorted(set(raw_by) | set(adj_by)):
        raw, adj = raw_by.get(ym) or {}, adj_by.get(ym) or {}
        row: dict = {YM_KEY: ym, "section": raw.get("section") or adj.get("section") or "",
                     "material_empty": bool(raw.get("material_empty") and adj.get("material_empty"))}
        for key in DATA_KEYS:
            left, right = raw.get(key), adj.get(key)
            row[key] = None if left is None and right is None else to_money(
                (right if right is not None else Decimal("0.00"))
                - (left if left is not None else Decimal("0.00")))
        out.append(row)
    return out


# ============================================================ 合计 / 总求和（001-05 · 001-06）


def column_totals(rows: list[dict]) -> dict[str, Decimal | None]:
    """**每个数据列**的垂直合计（001-05）—— 表①② 各核一遍。

    ⚠️ **空态格（`None`）不参与求和**；整列都是空态 ⇒ 给 `None`（合计行留空，**不臆造 0**）。
    """
    out: dict[str, Decimal | None] = {}
    for key in DATA_KEYS:
        picked = [r.get(key) for r in rows or () if r.get(key) is not None]
        out[key] = sum_money(picked) if picked else None
    return out


def segment_totals(rows: list[dict]) -> tuple[dict, ...]:
    """「总求和」行的**四段**横向总计（001-06）—— 每段一个合计，跨列数与 `SUM_SEGMENTS` 一致。"""
    totals = column_totals(rows)
    return tuple(
        {"name": name, "keys": keys, "span": len(keys),
         "total": sum_money([totals[k] for k in keys if totals[k] is not None])}
        for name, keys in SUM_SEGMENTS
    )


def grand_total(rows: list[dict]) -> Decimal:
    """全月总计（四段之和）。"""
    return sum_money([seg["total"] for seg in segment_totals(rows)])


# ============================================================ 差异表（001-07 · 001-09）

DIFF_COLUMNS: tuple[dict, ...] = (
    {"key": "doc_no", "label": "单据编号", "type": "text"},
    {"key": "seq", "label": "序号", "type": "text"},
    {"key": "material", "label": "物料", "type": "text"},
    {"key": "warehouse", "label": "仓库", "type": "text"},
    {"key": "before", "label": "原值（i8）", "type": "num"},
    {"key": "after", "label": "调整后", "type": "num"},
    {"key": "delta", "label": "差额", "type": "num"},
    {"key": "remark", "label": "备注", "type": "text"},
    {"key": "operator", "label": "操作人", "type": "text"},
    {"key": "at", "label": "时间", "type": "text"},
    {"key": "ops", "label": "操作", "type": "page"},
)
# ⚠️ 差异表**可求和的列限于三列**（001-07）：原值 / 调整后 / 差额
DIFF_SUM_KEYS: tuple[str, ...] = ("before", "after", "delta")
DIFF_PAGE_ONLY_KEYS: tuple[str, ...] = ("ops",)


def diff_rows(inv_rows: list[dict], *, warehouse: str) -> list[dict]:
    """差异表行：**被调整单改过的**库存单据行（§5.2.4「差异表 = 入口不是死表」）。"""
    out: list[dict] = []
    for row in inv_rows or ():
        if str(row.get("warehouse") or "") != warehouse:
            continue
        if row.get("adj_amount") in (None, "") and not row.get("adjusted_values"):
            continue
        before = to_money(row.get("amount") or 0)
        after = to_money(effective_value(row, "amount") or 0)
        snapshot = row.get("adjustment_before_values") or {}
        changes = []
        for key, value in (row.get("adjusted_values") or {}).items():
            original = row.get(key, snapshot.get(key, ""))
            same = str(original or "") == str(value or "") if key == "material_property" else to_money(original or 0) == to_money(value)
            if not same:
                changes.append(f"{LABELS.get(key, key)}：{original} → {value}")
        out.append({
            "id": row.get("id"),
            "doc_no": row.get("doc_no") or "",
            "seq": row.get("seq") or "",
            "material": row.get("material") or "",
            "warehouse": row.get("warehouse") or "",
            "before": before,
            "after": after,
            "delta": to_money(after - before),
            **({"changes": "；".join(changes)} if "adjusted_values" in row else {}),
            "remark": row.get("adj_remark") or "",
            "operator": row.get("adj_operator") or "",
            "at": row.get("adj_at") or "",
        })
    return out


def diff_totals(rows: list[dict]) -> dict[str, Decimal | None]:
    """差异表「合计」行：**只有三列可求和**，其余列给 `None`（留空，不臆造 0）。"""
    out: dict[str, Decimal | None] = {c["key"]: None for c in DIFF_COLUMNS}
    for key in DIFF_SUM_KEYS:
        picked = [r.get(key) for r in rows or () if r.get(key) not in (None, "")]
        out[key] = sum_money(picked) if picked else None
    return out


# ⚠️ 2026-09-18（`TAIL-27` · `§19` **批 2**）：`jump_query()`（差异行 → `/m08?pj=…&only_adj=1` 的
#    **旧页 URL 拼装**）已删除 —— 旧页整体删除（授权 `D18`）后它**只被测试调用**（`wiring_audit` 的
#    W1b 当场报出来 ✓）。同一 claim（001-09 差异行可跳转到库存单据）现在落在**壳的行内入口**：
#    `data-act="goInvAdj"`（带单据 id）⇒ 断言在 `tests/test_acc_proc_001.py`（壳）与
#    `tests/test_wired_m06.py` 那一组里 ✓。⛔ 别再为了"留个纯函数"把它加回来。


# ============================================================ 导出（§7.1 · ACC-RPT-EXP-001）

EXPORT_DOMAIN = "过程资料"


def tab_name(tab) -> str:
    """**当前表名** —— 导出提示与导出取数**同源**（001-04 的单一出口）。"""
    cur = tab_of(tab)
    return next(label for num, label in TABS if num == cur)


def export_selection(current: str, requested, *, touched: bool) -> list[str]:
    """展开区的项目选择（001-02）：**还没动过** ⇒ 默认选中「本页当前项目」；动过 ⇒ 按所传原样。

    ⚠️ 「动过」由调用点声明（展开区内的任何提交都带令牌）—— 否则「用户清空后点导出」会被
       误判成「没动过」而**静默退回当前项目**（那是一次用户没要求的导出）。
    """
    if not touched:
        return [current] if current else []
    out: list[str] = []
    for p in requested or ():
        p = str(p or "").strip()
        if p and p not in out:
            out.append(p)
    return out


def export_file_name(project: str, *, tab, ym: str) -> str:
    """单份文件名 = `{项目}_{域}_{表名}_{年月}.xlsx`（§7.1：文件名含日期 ＋ 域名称；再加项目以区分份数）。

    ⚠️ 项目名取**页面所显示的那个** —— 本页项目键 = 仓库名（§2.7.4），页面显示的也是仓库名；
       原型行文写「项目展示名」，而本页**没有展示名映射** ⇒ 与「列名与取值口径的唯一主人 = 页面」
       同理，取页面所显示的取值，**不另造一份展示名**。
    """
    return f"{project}_{EXPORT_DOMAIN}_{tab_name(tab)}_{ym}.xlsx"


def export_manifest(selected, *, tab, ym: str) -> dict:
    """导出清单（001-01）：**每个所选项目一份文件**；**≥2 个项目 ⇒ 打成一个 zip**。

    ⚠️ 本函数只给**形态与清单**（与原型一致）；**真实文件写出不在这里** ⇒ 归切片 6 的
       `ACC-X-EXP-001`（那时它把这里列出的清单落成真文件）。
    """
    files = [{"project": p, "name": export_file_name(p, tab=tab, ym=ym)} for p in selected or ()]
    return {
        "tab": tab_of(tab),
        "tab_name": tab_name(tab),
        "ym": ym,
        "files": files,
        "count": len(files),
        "zip": len(files) > 1,
        "zip_name": f"{EXPORT_DOMAIN}_{ym}.zip" if len(files) > 1 else "",
    }


# ============================================================ 硬边界（001-08）

MATERIAL_READONLY = True     # 材料列 = **引用 · 只读**（§5.2.3 · DEV-R-01）


def boundary_violations(html: str, action_ids=()) -> list[str]:
    """本页硬边界自检（空 = 合规）：
    ① 不得出现「理论上 =」这类**自算材料费**的表述；
    ② 不得提供**材料费编辑入口**（材料列只读）。
    """
    bad: list[str] = []
    text = str(html or "")
    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            bad.append(f"本页不得自算材料费（出现「{phrase}」）—— 材料费只作引用（§5.2.3）")
    for act in action_ids or ():
        if str(act) in FORBIDDEN_ACTIONS:
            bad.append(f"本页不得提供材料费编辑入口（动作 {act}）")
    return bad


__all__ = [
    "MATERIAL_PROPERTIES", "PROPERTY_TO_CATEGORY", "CATEGORIES", "MECH_COLUMNS",
    "PROC_COLUMNS", "PROC_KEYS", "DATA_KEYS", "MATERIAL_KEYS", "MECH_KEYS", "YM_KEY",
    "SUM_SEGMENTS", "SOURCE_INV", "SOURCE_SNAPSHOT", "SOURCE_MANUAL", "COLUMN_SOURCE",
    "MECH_SOURCE_BY_SECTION", "SECTION_HISTORY", "SECTION_FORMAL", "section_of",
    "column_source", "column_editable", "snapshot_by_month", "build_matrix",
    "FORBIDDEN_PHRASES", "FORBIDDEN_ACTIONS", "column_meta", "to_category", "normalize_ym",
    "row_material_amount", "material_by_month", "mech_by_month",
    "TAB_RAW", "TAB_ADJUSTED", "TAB_DIFF", "TABS", "DEFAULT_TAB", "tab_of", "build_matrix",
    "difference_rows",
    "column_totals", "segment_totals", "grand_total",
    "DIFF_COLUMNS", "DIFF_SUM_KEYS", "DIFF_PAGE_ONLY_KEYS", "diff_rows", "diff_totals", "jump_query",
    "EXPORT_DOMAIN", "tab_name", "export_selection", "export_file_name", "export_manifest",
    "MATERIAL_READONLY", "boundary_violations",
]
