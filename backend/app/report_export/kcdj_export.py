# -*- coding: utf-8 -*-
"""`MOD-08` 库存单据明细 · **成品文件写出（模板法）** —— 逐字移植自交付面素材包
`PRD素材包-20260911/input/kcdj_process.py`（⚠️ 只搬**实现**，口径不反推）。

**交付形态**（`API-03` / §5.4 / `demo/模板/模板清单.md` §一）：**1 个 xlsx**，3 张 sheet ——
  `报表1`（i8 原始明细，28 列）＋「**过程资料**」真透视（行 = 仓库 × 列 = 出入库方向 /
  物料性质）＋「**安全文明施工费**」真透视（页筛选 `cbs名称=安全文明施工费`、行 = 仓库）。
成品 = 以**用户手作成品 xlsx** 为基底做 `zip` 字节替换；两张透视**原样留在模板里**，
只换缓存与行列范围 ＋ `refreshOnLoad="1"`。

⭐ **本仓的三处适配**（其余与原文件逐字一致，改动处都带 `⭐ 本仓适配` 注释）：
1. **模板路径**走 `resources.py`（它已是**唯一出口** ＋ 缺失 / 损坏 **SHA256 闸门**）——
   素材包那个 `ROOT/data/templates/...` 常量删掉。
2. **数据来源 = 调用方给的 i8 源文件字节**（⛔ 模块里**不写死文件路径**）—— 落临时文件后
   `tpl_engine.read_data(...)`（原版 `main(src)` 直接读一份磁盘上的 i8 导出件）。
3. **对账不过 ⇒ 硬失败**（`tpl_engine.rebuild()` 内部已 `raise`，见其 `⭐ 本仓适配` 注释）——
   静默交付一个数字对不上的成品是最坏的失败形态。

⚠️⚠️ **`refreshOnLoad` 的位置**（本仓实测踩过）：它**唯一合法归属** = `pivotCacheDefinition1.xml`
   的 `<pivotCacheDefinition>`（⛔ 放 `<pivotTableDefinition>` 不合 OOXML schema，openpyxl 读回当场
   `TypeError`）—— `tpl_engine.rebuild()` **已经改对了**，本模块**不再自写这一段**。

⚠️⚠️ **`TAIL-43`：两张透视的「显示区」现在由本模块重建**（2026-09-18 真机实测根因）：
   模板法原先只重建「数据 sheet ＋ 缓存 ＋ 透视定义」，**不重建显示区**（`sheet1/2.xml` 里
   Excel 存下的静态渲染值）。本月数据**比模板少**时透视 `location` 会**收缩**，模板旧渲染行
   落到新 `location` **之外** ⇒ **任何应用都不会去清它们**（Excel 实测：新区域照渲染、区域外
   旧值原样留着）⇒ 用户打开读到的是**模板那个月**的数。⇒ 修法 = **自己重建显示区**
   （`aggregate_grid` 聚格子 ＋ `tpl_engine.render_pivot_sheet` 整块换掉 `<sheetData>`），
   并把「**显示区 vs 缓存重算**」作为**独立第二条对账**（`tpl_engine.verify_display`）。
   ⚠️ 顺带实测纠正：`refreshOnLoad` 只保证刷新**缓存**（ECMA-376 `CT_PivotCacheDefinition`），
   **不保证**清掉 `location` 之外的残留 —— 所以"靠打开即刷新来顶"是**靠不住**的。
"""

from __future__ import annotations

import os
import tempfile
import xml.etree.ElementTree as ET
import zipfile

import openpyxl

from app.core.errors import MustReportError
from app.report_export import tpl_engine
from app.report_export.resources import KCDJ_TEMPLATE, require_template

# ===== 列 / 缓存字段定义（**逐字保留素材包取值，不得"优化"**） =====
COL_WAREHOUSE = 18   # 仓库
COL_CBS = 27         # cbs名称
# 数字列（0-based，同时是缓存字段索引）
NUM_COLS = {0, 1, 2, 12, 13, 14, 15, 16, 23}   # 序号/核算年/核算月/数量/不含税单价/含税单价/金额/价税合计/是否作废
EMPTY_FIELDS = (28,)                            # 物料性质2 = 主材+辅材分组字段（缓存空，分组由透视定义处理）
COL_DIR = 17         # 出入库方向（透视的**方向**维度）
COL_NAT = 11         # 物料性质（分组字段的**基础**字段）
COL_NAT2 = 28        # 物料性质2（透视的**分组**维度）
COL_AMT = 15         # 金额（透视的**数值**字段）


def aggregate_grid(data, columns, nat2group, *, wh_col=COL_WAREHOUSE, dir_col=COL_DIR,
                   nat_col=COL_NAT, amt_col=COL_AMT, filter_col=None, filter_val=None):
    """明细 → **两张透视显示区的格子值**（纯函数 · 无 IO）。

    `TAIL-43` 的域内核（尾巴台账 §15 的落点写的就是「按新数据重算渲染值」）：模板法只重建了
    数据/缓存/透视定义，透视的**显示区**（Excel 存下来的渲染结果）没人重建
    ⇒ 本月数据比模板少时旧值会残留。
    ⚠️ 本函数**尚无专属判据点** —— 未绑定断言在 `tests/test_tail43_display.py`（待立新用例）。

    口径（由**模板自身**标定 —— 模板的缓存与显示是同一个月的，逐格复算全部对上）：
      · `cell`（`dir` ＋ `group`）＝ 该方向 × 该物料性质2 分组的金额合计
      · `dir_total`             ＝ 该方向**全部**明细合计（含未落进任何分组的行）
      · `grand`                 ＝ 该仓全部明细合计
      ⭐ **无匹配记录 ⇒ 该格不写值**（`None`）；⛔ **不写 0** —— 0 会被读成「确实为 0」，
        与「这个月没有」是两回事（本片用户看到的就是"明明没有却显示有数"）。

    `nat2group` 由 `tpl_engine.pivot_column_specs` 从模板 `<fieldGroup>` 读出（⛔ 不另立一份）。
    """
    per_wh, over = {}, {}
    for row in data:
        if filter_col is not None and str(row[filter_col]).strip() != filter_val:
            continue
        amt = tpl_engine.norm_num(row[amt_col])
        if amt is None:
            continue
        w = str(row[wh_col]).strip()
        d = str(row[dir_col]).strip()
        g = nat2group.get(str(row[nat_col]).strip())
        for key in ((d, g), (d, None), (None, None)):
            for acc, k in ((per_wh, (w,) + key), (over, key)):
                s, n = acc.get(k, (0.0, 0))
                acc[k] = (round(s + amt, 2), n + 1)

    def mode_key(c):
        if c['mode'] == 'grand':
            return (None, None)
        if c['mode'] == 'dir_total':
            return (c['dir'], None)
        return (c['dir'], c['group'])

    # ⚠️ 行的顺序按**首次出现**（⛔ 不按 `set` 迭代顺序 —— 那是进程内的字符串哈希序，
    #    换个进程可能就不一样；这个顺序会**直接决定显示区每行的位置**，必须确定）
    by_label = {}
    for w in dict.fromkeys(str(r[wh_col]).strip() for r in data):
        cells = {}
        for c in columns:
            got = per_wh.get((w,) + mode_key(c))
            if got:                                  # ⚠️ 无匹配记录 ⇒ 不写（⛔ 不写 0）
                cells[c['letter']] = got[0]
        by_label[w] = cells
    total = {}
    for c in columns:
        got = over.get(mode_key(c))
        if got:
            total[c['letter']] = got[0]
    return by_label, total

#: 数据 sheet 在模板里的部件（`报表1` = `sheet3`）
DATA_SHEET_FILE = "xl/worksheets/sheet3.xml"
#: 成品文件名前缀（命名规则**照素材包不变**：`库存单据明细表_<期间标签>.xlsx`）
FILE_PREFIX = "库存单据明细表"
#: 安全文明施工费透视的**页筛选值**（= `cbs名称` 列的字面值）
SAFE_CBS = "安全文明施工费"
#: 成品必须齐备的关键部件（结构闸门用）
REQUIRED_PARTS: tuple[str, ...] = (
    "xl/workbook.xml",
    "xl/worksheets/sheet1.xml",
    "xl/worksheets/sheet2.xml",
    "xl/worksheets/sheet3.xml",
    "xl/pivotCache/pivotCacheDefinition1.xml",
    "xl/pivotCache/pivotCacheRecords1.xml",
    "xl/pivotTables/pivotTable1.xml",
    "xl/pivotTables/pivotTable2.xml",
    "xl/sharedStrings.xml",
)
#: 成品必须有的工作表（= 模板实际形态；提示语与结构闸门**共用这一份**）
OUTPUT_SHEETS: tuple[str, ...] = ("报表1", "过程资料", "安全文明施工费")


def _read_source(data_bytes: bytes):
    """i8 源文件**字节** → `(表头, 数据行)`。

    ⭐ 本仓适配：字节**落临时文件**后交引擎读（引擎的 `read_data` 走 `openpyxl` 磁盘路径），
    ⛔ 模块里**不写死任何文件路径**（生产的数据来源是 HTTP 现导的响应体）。
    """
    if not data_bytes:
        raise MustReportError("i8 导出内容为空 ⇒ 无法生成成品（该月可能没有数据）。")
    fd, tmp = tempfile.mkstemp(prefix="kcdj-src-", suffix=".xlsx")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data_bytes)
        try:
            return tpl_engine.read_data(tmp, col_count=28)
        except RuntimeError as exc:
            raise MustReportError(
                "i8 导出内容里找不到「库存单据明细」表头"
                "（需含「序号」「金额」）⇒ 无法生成成品：%s" % exc
            ) from exc
    finally:
        try:
            os.remove(tmp)          # 数据已进内存 ⇒ 用完即删（⛔ 不留原始文件）
        except OSError:
            pass


def _structural_gate(out_path: str) -> None:
    """⭐ 本仓适配：**结构闸门**（对账之外的独立一道）—— `zipfile` 关键部件 ＋ `openpyxl` 读回。

    - ⛔ 素材包的 `verify_output()` 把 `'refreshOnLoad="1"' in 字符串` 当结构验证 ⇒ **查不出"属性位置错"**
      （字符串在、位置错，照样通过）—— 这里改成**真读回**。
    - ⚠️ 读回**必须带 `read_only=True`** —— 本表**模板本身**结构就过不了 openpyxl 的透视解析
      （实测 `TypeError: Nested.from_tree() missing 1 required positional argument: 'node'`）。
    - ⚠️ `refreshOnLoad` 的**位置**单点校验：必须在 `pivotCacheDefinition` 上、⛔ 不在 `pivotTable` 上。
    """
    try:
        z = zipfile.ZipFile(out_path)
    except zipfile.BadZipFile as exc:
        raise MustReportError("成品结构损坏：不是合法 xlsx（%s）" % exc) from exc
    try:
        missing = [n for n in REQUIRED_PARTS if n not in z.namelist()]
        if missing:
            raise MustReportError("成品结构缺件：%s" % " / ".join(missing))
        for name in ("xl/pivotCache/pivotCacheDefinition1.xml",
                     "xl/pivotTables/pivotTable1.xml", "xl/pivotTables/pivotTable2.xml"):
            try:
                ET.fromstring(z.read(name))
            except ET.ParseError as exc:
                raise MustReportError("成品结构损坏：%s 不是合法 XML（%s）" % (name, exc)) from exc
        pcd = z.read("xl/pivotCache/pivotCacheDefinition1.xml").decode("utf-8")
        if "refreshOnLoad" not in pcd:
            raise MustReportError("成品缺「打开即刷新」：`refreshOnLoad` 不在 `pivotCacheDefinition` 上。")
        for name in ("xl/pivotTables/pivotTable1.xml", "xl/pivotTables/pivotTable2.xml"):
            if "refreshOnLoad" in z.read(name).decode("utf-8"):
                raise MustReportError(
                    "成品结构不合 schema：`refreshOnLoad` 出现在了 %s 上（唯一合法归属 = `pivotCacheDefinition`）。" % name)
    finally:
        z.close()

    wb = openpyxl.load_workbook(out_path, read_only=True, data_only=True)   # ⚠️ 必须 read_only
    try:
        names = list(wb.sheetnames)
        for sn in OUTPUT_SHEETS:
            if sn not in names:
                raise MustReportError("成品缺工作表：`%s`（现有：%s）" % (sn, names))
    finally:
        wb.close()


def _template_pivots():
    """打开模板读透视定义（只读；`pivotCacheDefinition` ＋ 两张 `pivotTable`）。

    ⭐ `TAIL-43`：显示区的**列结构 / 分组映射 / 页筛选选中项**一律**从模板读出**
    （⛔ 不在代码里另抄一份 —— 模板一换、两份必漂）。
    """
    require_template(KCDJ_TEMPLATE)
    z = zipfile.ZipFile(str(KCDJ_TEMPLATE))
    try:
        return (z.read("xl/pivotCache/pivotCacheDefinition1.xml").decode("utf-8"),
                z.read("xl/pivotTables/pivotTable1.xml").decode("utf-8"),
                z.read("xl/pivotTables/pivotTable2.xml").decode("utf-8"))
    finally:
        z.close()


def display_structure():
    """模板 → 两张透视**显示区的结构**（列 / 分组映射 / 页筛选 / 行区间）—— 不含数值。

    ⭐ `TAIL-43`：结构与分组映射一律**从模板读出**（⛔ 不在代码里另抄一份 —— 模板一换、两份必漂）。
    ⚠️ 页筛选的选中项也从模板读出来核对：模板用「多选 ＋ `h="1"` 标未选」表达，
    ⛔ **不是** `<pageField item="k"/>`（那是单选语义）；读出来必须**就是**本模块那个常量。
    返回 `(specs, layout)`：`specs[i]['by_label']/['total']` 由调用方填值。
    """
    cd, pt1, pt2 = _template_pivots()
    layout = tpl_engine.pivot_column_specs(cd, pt1, COL_DIR, COL_NAT2)
    cols, nat2group = layout["columns"], layout["nat2group"]
    picked = tpl_engine.pivot_page_filter(cd, pt2, COL_CBS)
    if picked != [SAFE_CBS]:
        raise MustReportError(
            "模板「安全文明施工费」透视的页筛选选中项是 %s，与预期 `[%s]` 不符"
            "⇒ 模板已被替换，显示区重建必须重新核对后再放行。" % (picked, SAFE_CBS))
    # ⚠️ 安全文明施工费那张透视**不带列维度**（`colItems` 只有 1 项 = 数值字段）
    #    ⇒ 列 = 单个「金额」；口径 = 该仓在本月**全部**安全文明施工费明细之和。
    safe_cols = [{"letter": "B", "mode": "grand", "dir": None, "group": None}]
    specs = [
        {"pivot": "xl/pivotTables/pivotTable1.xml",
         "sheet_file": "xl/worksheets/sheet1.xml",
         "keep_rows": (), "header_rows": (3, 6), "first_data_row": 7, "label_col": "A",
         "columns": cols, "by_label": {}, "total": {},
         "label_field": COL_WAREHOUSE, "dir_field": COL_DIR, "group_field": COL_NAT2,
         "value_field": COL_AMT, "nat2group": nat2group, "filter": None},
        {"pivot": "xl/pivotTables/pivotTable2.xml",
         "sheet_file": "xl/worksheets/sheet2.xml",
         "keep_rows": (1,), "header_rows": (3, 3), "first_data_row": 4, "label_col": "A",
         "columns": safe_cols, "by_label": {}, "total": {},
         "label_field": COL_WAREHOUSE, "dir_field": None, "group_field": None,
         "value_field": COL_AMT, "nat2group": {}, "filter": (COL_CBS, SAFE_CBS)},
    ]
    return specs, layout


def fill_display(sheets, data, nat2group):
    """按**每张显示区自己的列**把值聚合进去（纯函数 · 无 IO）→ 原样返回 `sheets`。

    ⚠️⚠️ **必须逐张用它自己的 `columns`** —— 两张透视的列结构**不同**（过程资料 13 列、
    安全文明施工费 1 列）。实测踩到：拿「过程资料」那套 13 列去算安全文明费的值，
    `B` 列会变成「入库 × 数据组1」；两个样本恰好都落在该列上 ⇒ **看着全对、其实是错列**
    （静默错列，最坏的一类）。⇒ 把「列」与「值」绑到**同一个 spec 对象**上，杜绝漂移。
    """
    for sp in sheets:
        ff = sp.get("filter")
        sp["by_label"], sp["total"] = aggregate_grid(
            data, sp["columns"], nat2group,
            filter_col=(ff[0] if ff else None), filter_val=(ff[1] if ff else None))
    return sheets


def build_xlsx(src_bytes: bytes, out_dir) -> str:
    """把一期的 **i8 库存单据导出字节** 做成 **1 个成品 xlsx** → 返回**成品路径**。

    - `src_bytes`：i8 源文件字节（= `mod02_i8.report_export.export(..., spec_key="inv")` 的响应体）
    - `out_dir`：成品目录 —— ⭐ **它的 basename 即期间标签**（如 `2026年9月`；命名规则照素材包不变）
    - 产出文件名 = `库存单据明细表_<期间标签>.xlsx`（在 `out_dir` 内）
    """
    require_template(KCDJ_TEMPLATE)          # ⭐ 本仓适配：模板缺失 / 损坏 ⇒ 显式报错
    out_dir = str(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    label = os.path.basename(os.path.normpath(out_dir))     # ⭐ 命名规则照素材包：目录名即期间标签
    out = os.path.join(out_dir, "%s_%s.xlsx" % (FILE_PREFIX, label))

    # ⭐ 本仓适配：数据来自调用方给的**字节**（预读一次，用于计算安全文明施工费的仓库子集）
    _hdr, data = _read_source(src_bytes)
    if not data:
        raise MustReportError(
            "「%s」没有任何库存单据明细 ⇒ **不产出成品文件**"
            "（空文件会被当成「交付了」，比不导出更坏）—— 请先抓取或导入该月数据。" % label
        )
    # ⭐ 本仓适配：**安全文明施工费透视的可用仓库子集** —— 仅当该月**确有**该费用数据时，
    #    该透视才"有内容可对账"。**空集 = 该月确实一个都没有**（⛔ 不是"未配置"）；
    #    这种情况该透视 **0 行项、不参与对账**，下面明确标注「未验证 / 不适用」，
    #    ⛔ 绝不把它塞进 `verify` 让引擎"空 == 空"地静默报"通过"（那是最贵的假绿）。
    safe_wh = {str(r[COL_WAREHOUSE]).strip() for r in data
               if str(r[COL_CBS]).strip() == SAFE_CBS}

    verify_rules = [
        {"name": "过程资料", "row": COL_WAREHOUSE, "cols": (17, 11), "value": 15,
         "group_map": {"主材": "主辅材", "辅材": "主辅材"}},
    ]
    if safe_wh:                                  # 有该费用数据 ⇒ 该透视**参与对账**
        verify_rules.append(
            {"name": "安全文明", "row": COL_WAREHOUSE, "value": 15, "filter": (COL_CBS, SAFE_CBS)})

    # ⭐ `TAIL-43`：**显示区**两张 —— 结构与分组映射从模板读（口径主人 = 模板）。
    sheets, layout = display_structure()
    fill_display(sheets, data, layout["nat2group"])

    cfg = {
        "template": str(KCDJ_TEMPLATE),
        "out": out,
        "data": data,        # ⭐ 预读数据；引擎不再重读（引擎侧 `src` 已不需要）
        "data_sheet": {"names": ("报表1", "Sheet1"), "header_keywords": ("序号", "金额"),
                       "col_count": 28, "num_cols": NUM_COLS},
        "shared": {"sheet_file": DATA_SHEET_FILE},   # 报表1 = sheet3
        "cache": {"field_count": 29, "num_cols": NUM_COLS, "empty_fields": EMPTY_FIELDS,
                  "wh_field": COL_WAREHOUSE,
                  "wh_order_pivot_file": "xl/pivotTables/pivotTable1.xml"},
        "pivots": [
            # 过程资料：全部仓库
            {"file": "xl/pivotTables/pivotTable1.xml",
             "location_ref": lambda n: "A3:N%d" % (7 + n),
             "rowitems_mode": "leading_empty"},
            # 安全文明施工费：仅有该费用数据的仓库
            {"file": "xl/pivotTables/pivotTable2.xml",
             "location_ref": lambda n: "A3:B%d" % (4 + n),
             "rowitems_mode": "plain",
             "warehouses": safe_wh},
        ],
        "verify": verify_rules,
        "sheets": sheets,                        # ⭐ `TAIL-43`：两张透视的显示区
    }
    tpl_engine.rebuild(cfg)                  # ⭐ 对账不过 ⇒ 引擎内部 `raise`（硬失败，不静默交付）

    # ⭐ 本仓适配：**对账范围逐条说清** —— 空集那条必须明说「未验证 / 不适用」，
    #    ⛔ 不许因为"引擎没报错"就默认它通过了（空 == 空的静默通过是最坏的假绿）。
    print("对账范围：过程资料透视（全部仓库）✓ 通过")
    if safe_wh:
        print("对账范围：安全文明施工费透视（%d 个仓库）✓ 通过" % len(safe_wh))
    else:
        print("⚠ 安全文明施工费对账：未验证 / 不适用 —— 该月没有安全文明施工费数据"
              "（该透视 0 行项，未参与对账）")

    _structural_gate(out)                    # ⭐ 本仓适配：结构闸门（读回 ＋ 关键部件 ＋ 位置校验）
    print("✓ 结构闸门通过:", out)
    return out


__all__ = ["COL_WAREHOUSE", "COL_CBS", "COL_DIR", "COL_NAT", "COL_NAT2", "COL_AMT", "NUM_COLS",
           "EMPTY_FIELDS", "DATA_SHEET_FILE", "FILE_PREFIX", "SAFE_CBS", "REQUIRED_PARTS",
           "OUTPUT_SHEETS", "aggregate_grid", "display_structure", "fill_display", "build_xlsx"]
