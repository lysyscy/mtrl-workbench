# -*- coding: utf-8 -*-
"""`MOD-07` 收发结存 · **成品文件写出（模板法）** —— 逐字移植自交付面素材包
`PRD素材包-20260911/input/sfjc_process.py`（⚠️ 只搬**实现**，口径不反推）。

**交付形态**（《说明书》§5.3.2）：`N` 个分仓库 xlsx ＋ 1 个总表 → **打包成一个 zip**；
总表里 `Sheet1` = 按仓聚合、`报表1` = 全量明细、并带**真·透视表**（原样留在模板里，
只换缓存与行列范围 ＋ `refreshOnLoad="1"`）。⚠️ 金额按 2 位小数对平、**容差 0**。

⭐ **本仓的两处适配**（其余与原文件逐字一致，改动处都带 `⭐ 本仓适配` 注释）：
1. **数据来源 = 库**（`frame_from_rows`）—— 原版 `read_raw(path)` 读 i8 原始导出件；
   本仓的明细已在 `setl_detail`（17 列与导出表头一一对应）⇒ 不必留原始文件、
   也能导出**历史月份**与**手动导入**来的月份。
2. **删掉模块级 `warnings.filterwarnings('ignore')`** —— 理由同 `tpl_engine`（库不该全局静音）。

⚠️⚠️ **`TAIL-43` 同族缺陷（2026-09-18 一并复核并修）**：`Sheet1` 就是**透视的显示区**。
   本表**原实现已经会写显示区**（`update_sheet_data` 用 openpyxl 逐行写 仓库 ＋ 4 个金额），
   所以**当时没暴露** —— 2026-09 的仓库数（8）比模板（7）多，行是"长出来"的，没有旧行残留。
   但它**只写新行、不清旧行** ⇒ 一旦某月仓库**变少**，模板旧渲染行就落到了新 `location`
   之外（`patch_pivot` 只改 `location`/`rowItems`，Excel 只重画 `location` 之内），
   **任何应用都不会去清它们** ⇒ 用户读到**上个月**的数。
   ⇒ 已补：写完后**删掉新显示区之外的行**，并在 `verify()` 里加**「显示区之外不许再有行」**守卫。
   ⚠️ **和库存单据表的差异（有意不同）**：那张走 `tpl_engine.render_pivot_sheet`（整块换
   `<sheetData>`、`zip` 字节替换）；本表走 **openpyxl 直接改单元格 ＋ `delete_rows`** ——
   两条路都能满足"显示区之外不留旧值"，本表**不改动既有机制**（已验收面，最小改动）。
"""

from __future__ import annotations

import os
import re
import zipfile
from copy import copy
from html import unescape
from xml.sax.saxutils import escape

import openpyxl
import pandas as pd
import xlsxwriter

from app.core.errors import MustReportError
from app.core.logging import get_logger
from app.report_export.resources import SETL_TEMPLATE, require_template
from app.report_export.schema_cols import (SFJC_COL_WIDTHS, SFJC_HEADER,
                                           SFJC_NUM_FIELDS, SFJC_TEXT_FIELDS)
from app.report_export.save import save_workbook      # ⭐ `TAIL-68`：落盘唯一出口

#: ⚠️⚠️ **本文件原先用 `print` 输出进度**（素材包移植过来的脚本习惯）——
#:   2026-09-20 实测踩到：`print('✓ …')` 在 **Windows 控制台（GBK）** 下抛
#:   `UnicodeEncodeError: 'gbk' codec can't encode character '\u2713'`
#:   ⇒ **整条导出 500** ⇒ 页面上只是"导不出来"，而**日志里才看得到真因**。
#:   ⇒ 一律改走 `logger`（它走 UTF-8 的文件 handler，⛔ 不看控制台编码的脸色）。
logger = get_logger()

# ===== 列定义（唯一来源 = `schema_cols`，⛔ 本模块不另抄一份） =====
HEADER_COLS = SFJC_HEADER
NUM_COLS = SFJC_NUM_FIELDS
TEXT_COLS = SFJC_TEXT_FIELDS
COL_WIDTHS = SFJC_COL_WIDTHS


#: 域内字段 → 导出表头（**列映射的唯一出口**；与 `mod07_setl.importer.COLUMN_MAP` 反向同构）
FIELD_TO_HEADER: tuple[tuple[str, str], ...] = (
    ("warehouse_name", "仓库"),
    ("resource_class", "资源分类"),
    ("resource_code", "资源编码"),
    ("resource_name", "资源名称"),
    ("spec", "规格型号"),
    ("unit", "计量单位"),
    ("material_property", "物料性质"),
    ("begin_qty", "期初数量"),
    ("begin_amt", "期初金额"),
    ("in_qty", "收数量"),
    ("in_price", "收单价"),
    ("in_amt", "收金额"),
    ("out_qty", "发数量"),
    ("out_price", "发单价"),
    ("out_amt", "发金额"),
    ("end_qty", "结存数量"),
    ("end_amt", "结存金额"),
)

#: 导出里的**合计行**（按素材包口径剔除：它按仓库汇总、不是明细）
TOTAL_WAREHOUSE = "合计"


def _num(value):
    """库值 → 数字或 `None`（空 = `None`，⛔ 不冒充 0 —— 与 §7.1「不可得 ≠ 0」同一条纪律）。"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return float(value)


def frame_from_rows(detail_rows) -> pd.DataFrame:
    """`setl_detail` 明细行 → **与导出同构的 DataFrame**（列序 = `SFJC_HEADER`）。

    ⚠️ 只做**形态转换**，不做任何判定（合计行早在 `mod07_setl.importer` 落库前就剔除了）。
    ⛔ 列映射只此一处 —— `setl_detail` 的列与导出表头**一一对应**（`models.SetlDetail` 的注释即写明）。
    """
    records = []
    for r in detail_rows:

        def g(field):
            return getattr(r, field, None) if not isinstance(r, dict) else r.get(field)

        rec = {}
        for field, header in FIELD_TO_HEADER:
            v = g(field)
            rec[header] = _num(v) if header in SFJC_NUM_FIELDS else ("" if v is None else str(v))
        records.append(rec)
    df = pd.DataFrame(records, columns=SFJC_HEADER)
    # 防回退：万一库里混进"合计"行，按素材包口径照样剔掉（导出件里它本就不该在）
    if not df.empty:
        df = df[df["仓库"] != TOTAL_WAREHOUSE].copy()
    return df


TEMPLATE = str(SETL_TEMPLATE)
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
MONEY_FIELDS = ['期初金额', '收金额', '发金额', '结存金额']


def fmt_num(x):
    s = ('%.10f' % float(x)).rstrip('0').rstrip('.')
    return s if s not in ('', '-0') else '0'


def write_warehouse_file(df, path):
    wb = xlsxwriter.Workbook(path)
    ws = wb.add_worksheet('Sheet1')
    header_fmt = wb.add_format({'bold': True, 'bg_color': '#ED7D31', 'font_color': '#1A1B1C',
                                'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_size': 11})
    text_fmt = wb.add_format({'border': 1, 'valign': 'vcenter', 'align': 'left', 'font_size': 11})
    num_fmt = wb.add_format({'border': 1, 'valign': 'vcenter', 'align': 'right',
                             'num_format': '#,##0.00', 'font_size': 11})
    for j, col in enumerate(HEADER_COLS):
        ws.write(0, j, col, header_fmt)
    for i, (_, row) in enumerate(df.iterrows(), start=1):
        for j, col in enumerate(HEADER_COLS):
            fmt = text_fmt if col in TEXT_COLS else num_fmt
            v = row[col]
            if col in NUM_COLS and pd.isna(v):
                v = None
            ws.write(i, j, v, fmt)
    for letter, width in COL_WIDTHS.items():
        ws.set_column(f'{letter}:{letter}', width)
    ws.set_row(0, 33)
    for r in range(1, len(df) + 1):
        ws.set_row(r, 28)
    wb.close()


def update_sheet_data(df, out_path, show_order):
    wb = openpyxl.load_workbook(TEMPLATE)
    ws = wb['报表1']
    data = df.values.tolist()
    n = len(data)
    for i in range(n):
        r = 2 + i
        for c in range(1, 18):
            cell = ws.cell(row=r, column=c)
            if r > ws.max_row:
                tpl = ws.cell(row=ws.max_row, column=c)
                cell._style = copy(tpl._style)
            cell.value = data[i][c - 1]
    for r in range(2 + n, ws.max_row + 1):
        for c in range(1, 18):
            ws.cell(row=r, column=c).value = None
    # 删除尾部多余行（模板674数据行 vs 实际n行）
    if n < ws.max_row - 1:
        ws.delete_rows(2 + n, ws.max_row - (1 + n))
    ws1 = wb['Sheet1']
    pv = df.groupby('仓库')[MONEY_FIELDS].sum()
    grand = pv.sum()
    for i, wh in enumerate(show_order):
        r = 4 + i
        ws1.cell(row=r, column=1).value = wh
        for j, m in enumerate(MONEY_FIELDS):
            ws1.cell(row=r, column=2 + j).value = float(pv.loc[wh, m])
    r_grand = 4 + len(show_order)
    ws1.cell(row=r_grand, column=1).value = '总计'
    for j, m in enumerate(MONEY_FIELDS):
        ws1.cell(row=r_grand, column=2 + j).value = float(grand[m])
    # ⚠️⚠️ `TAIL-43` 同族缺陷（2026-09-18 实测查实 · **本表当时靠"仓库数没变"侥幸没犯**）：
    #    这张 `Sheet1` 就是**透视的显示区**。只写新行**不清旧行**的话，本月仓库**变少**时，
    #    模板旧渲染行会留在新 `location` **之外** —— 而 `patch_pivot` 只改 `location`/`rowItems`，
    #    Excel 只会重画 `location` 之内 ⇒ 区域外的旧值**任何应用都不会去清**，
    #    用户打开就读到**上个月**的数（`TAIL-43` 在库存单据表上就是这么暴露的）。
    #    ⇒ 这里必须把「新显示区之外的行」**删掉**（不是清空 —— 留着空行仍会撑大 `dimension`）。
    last = r_grand
    if ws1.max_row > last:
        ws1.delete_rows(last + 1, ws1.max_row - last)
    save_workbook(wb, out_path)          # ⭐ `TAIL-68`：这里原本**没有 mkdir**（换目录就崩）
    return pv, grand


def patch_pivot(in_path, out_path, df, show_order):
    """基于8月模板patch：cacheDefinition + records + pivotTable1(动态适配仓库)"""
    zt = zipfile.ZipFile(TEMPLATE)
    cd = zt.read('xl/pivotCache/pivotCacheDefinition1.xml').decode('utf-8')
    pt_orig = zt.read('xl/pivotTables/pivotTable1.xml').decode('utf-8')
    zt.close()

    # ===== 1) cacheDefinition: sharedItems追加 + recordCount + sourceReference =====
    field_maps = []
    new_parts = []
    for col in df.columns:
        m = re.search(r'<cacheField name="' + re.escape(col) + r'"[^>]*>(.*?)</cacheField>', cd, re.S)
        seg = m.group(1)
        is_num = col in NUM_COLS
        if is_num:
            items = re.findall(r'<n v="([^"]*)"', seg)
            seen = [float(x) for x in items]
        else:
            items = re.findall(r'<s v="([^"]*)"', seg)
            seen = [unescape(x) for x in items]
        idx = {v: i for i, v in enumerate(seen)}
        add_nodes = []
        for v in df[col]:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v = ''
            key = float(v) if is_num else str(v)
            if key not in idx:
                idx[key] = len(seen)
                seen.append(key)
                add_nodes.append(key)
        extra = ''
        for k in add_nodes:
            if is_num:
                extra += f'<n v="{fmt_num(k)}"/>'
            else:
                extra += f'<s v="{escape(str(k), {chr(34): "&quot;", chr(39): "&apos;"})}"/>'
        if is_num:
            nums = [float(x) for x in seen]
            new_seg = re.sub(r'minValue="[^"]*"', f'minValue="{fmt_num(min(nums))}"', seg)
            new_seg = re.sub(r'maxValue="[^"]*"', f'maxValue="{fmt_num(max(nums))}"', new_seg)
            new_seg = re.sub(r'count="\d+"', f'count="{len(nums)}"', new_seg)
        else:
            new_seg = re.sub(r'count="\d+"', f'count="{len(seen)}"', seg)
        new_seg = new_seg[:-len('</sharedItems>')] + extra + '</sharedItems>'
        new_parts.append(new_seg)
        field_maps.append(idx)
    cd_new = re.sub(r'(<cacheFields count="17">).*?(</cacheFields>)',
                    lambda mo: mo.group(1) + ''.join(
                        f'<cacheField name="{escape(col)}" numFmtId="0">{seg}</cacheField>'
                        for col, seg in zip(df.columns, new_parts)) + mo.group(2),
                    cd, flags=re.S)
    cd_new = re.sub(r'recordCount="\d+"', f'recordCount="{len(df)}"', cd_new)
    cd_new = re.sub(r'ref="A1:Q\d+"', f'ref="A1:Q{len(df) + 1}"', cd_new)

    # ===== 2) records重建 =====
    rows = []
    for _, row in df.iterrows():
        xs = []
        for j, col in enumerate(df.columns):
            v = row[col]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                v = ''
            key = float(v) if col in NUM_COLS else str(v)
            xs.append(f'<x v="{field_maps[j][key]}"/>')
        rows.append('<r>' + ''.join(xs) + '</r>')
    cr_new = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
              f'<pivotCacheRecords xmlns="{NS}" count="{len(df)}">'
              + ''.join(rows) + '</pivotCacheRecords>')

    # ===== 3) pivotTable1: 动态适配新仓库 =====
    # 仓库缓存索引
    wh_cache_idx = {w: field_maps[0][w] for w in df['仓库'].unique()}
    axis_items = [wh_cache_idx[w] for w in show_order]
    pt = pt_orig
    # location
    r_grand = 4 + len(show_order)
    loc_ref = f'A3:E{r_grand}'
    pt = re.sub(r'<location ref="[^"]*"', f'<location ref="{loc_ref}"', pt)
    # axisRow pivotField items
    pat_axis = re.compile(r'<pivotField axis="axisRow"[^>]*><items count="\d+">.*?</items></pivotField>', re.S)
    m = pat_axis.search(pt)
    if m:
        head = m.group(0)[:m.group(0).find('<items')]
        items_xml = (f'<items count="{len(axis_items) + 1}">'
                     + ''.join(f'<item x="{i}"/>' for i in axis_items)
                     + '<item t="default"/></items></pivotField>')
        pt = pt[:m.start()] + head + items_xml + pt[m.end():]
    # dataField pivotField items（4个金额字段）
    pat_df = re.compile(r'<pivotField dataField="1"[^>]*><items count="\d+">.*?</items></pivotField>', re.S)
    dmatches = list(pat_df.finditer(pt))
    for mm, col in zip(reversed(dmatches), reversed(MONEY_FIELDS)):
        uniq_n = len(field_maps[list(df.columns).index(col)])
        head = mm.group(0)[:mm.group(0).find('<items')]
        items_xml = (f'<items count="{uniq_n + 1}">'
                     + ''.join(f'<item x="{i}"/>' for i in range(uniq_n))
                     + '<item t="default"/></items></pivotField>')
        pt = pt[:mm.start()] + head + items_xml + pt[mm.end():]
    # rowItems
    pat_rows = re.compile(r'<rowItems count="\d+">.*?</rowItems>', re.S)
    m = pat_rows.search(pt)
    if m:
        row_items = ('<rowItems count="' + str(len(show_order) + 1) + '">'
                     + '<i><x/></i>'
                     + ''.join(f'<i><x v="{k}"/></i>' for k in range(1, len(show_order)))
                     + '<i t="grand"><x/></i></rowItems>')
        pt = pt[:m.start()] + row_items + pt[m.end():]

    # ===== 3.5) 「打开即刷新」（⭐ 本仓适配 · 位置经两轮实测才订正） =====
    # ⚠️⚠️ **实测纠正（本仓接入时发现）**：`refreshOnLoad` 的**唯一合法归属**是
    #    **`xl/pivotCache/pivotCacheDefinition1.xml` 的 `<pivotCacheDefinition>`** 元素
    #    （依据 = OOXML 的 `CT_PivotCacheDefinition`；openpyxl 把它建模在
    #    `openpyxl.pivot.cache.CacheDefinition.refreshOnLoad`）。
    #    放错位置的两种写法都会产出**不符合 schema** 的文件，且 openpyxl 读该工作簿**当场报错**：
    #      · 放 `<pivotTableDefinition>` ⇒ `TableDefinition … unexpected keyword 'refreshOnLoad'`
    #      · 放 `workbook.xml` 的 `<pivotCache>` ⇒ `PivotCache … unexpected keyword 'refreshOnLoad'`
    #    ⚠️ 素材包原版放在 pivotTable 上（实测结论 §一 第 6 处也是那么写的），而它的核对只是
    #       `'refreshOnLoad="1"' in 字符串` ⇒ **字符串在、属性位置错，照样通过**
    #       ——「存在性检查」看不见结构错。口径依据仍是「让 Excel 打开即刷新」（§一），
    #       **位置以此处为准**（该文档 §六 已同步纠正）。
    cd_new = re.sub(r'<pivotCacheDefinition\b(?![^>]*refreshOnLoad)([^>]*?)>',
                    r'<pivotCacheDefinition\1 refreshOnLoad="1">', cd_new, count=1)

    # ===== 4) 写回 =====
    zin = zipfile.ZipFile(in_path)
    zout = zipfile.ZipFile(out_path, 'w', zipfile.ZIP_DEFLATED)
    for item in zin.infolist():
        data = zin.read(item.filename)
        if item.filename == 'xl/pivotCache/pivotCacheDefinition1.xml':
            data = cd_new.encode('utf-8')
        elif item.filename == 'xl/pivotCache/pivotCacheRecords1.xml':
            data = cr_new.encode('utf-8')
        elif item.filename == 'xl/pivotTables/pivotTable1.xml':
            data = pt.encode('utf-8')
        zout.writestr(item, data)
    zout.close()
    zin.close()


def verify(out_path, df, pv, grand, show_order):
    import xml.etree.ElementTree as ET
    problems = []
    zf = zipfile.ZipFile(out_path)
    for name in ['xl/pivotCache/pivotCacheDefinition1.xml', 'xl/pivotCache/pivotCacheRecords1.xml',
                 'xl/pivotTables/pivotTable1.xml']:
        try:
            ET.fromstring(zf.read(name))
        except Exception as e:
            problems.append(f'{name}: {e}')
    cd = ET.fromstring(zf.read('xl/pivotCache/pivotCacheDefinition1.xml'))
    cr = ET.fromstring(zf.read('xl/pivotCache/pivotCacheRecords1.xml'))
    fields = cd.findall(f'{{{NS}}}cacheFields/{{{NS}}}cacheField')
    fvals = []
    for f in fields:
        si = f.find(f'{{{NS}}}sharedItems')
        vals = [float(ch.get('v')) if ch.tag.endswith('n') else str(ch.get('v')) for ch in si]
        fvals.append(vals)
    money_idx = [list(df.columns).index(m) for m in MONEY_FIELDS]
    sums = {m: {} for m in MONEY_FIELDS}
    for r in cr.findall(f'{{{NS}}}r'):
        xs = [int(x.get('v', 0)) for x in r.findall(f'{{{NS}}}x')]
        wh = fvals[0][xs[0]]
        for k, m in enumerate(MONEY_FIELDS):
            sums[m][wh] = sums[m].get(wh, 0.0) + fvals[money_idx[k]][xs[money_idx[k]]]
    for m in MONEY_FIELDS:
        for wh in show_order:
            got = round(sums[m].get(wh, 0), 2)
            exp = round(pv.loc[wh, m], 2)
            if abs(got - exp) > 0.01:
                problems.append(f'对账失败 {m}/{wh}: {got} vs {exp}')
        if abs(round(sum(sums[m].values()), 2) - round(grand[m], 2)) > 0.01:
            problems.append(f'总计对账失败 {m}')
    zf.close()
    # ⭐ `TAIL-43` 同族守卫：**显示区之外不许再有行**（否则就是模板旧渲染值残留）。
    wb = openpyxl.load_workbook(out_path)
    try:
        ws = wb['Sheet1']
        last = 4 + len(show_order)                    # 行 3 = 表头、4..(3+n) = 各仓、4+n = 总计
        if ws.max_row > last:
            problems.append(
                'Sheet1 显示区之外还有 %d 行（僵尸旧值）：max_row=%d > %d'
                % (ws.max_row - last, ws.max_row, last))
    finally:
        wb.close()
    return problems


def build_zip(rows_or_df, out_dir, label):
    """把一期的收发结存明细做成 **zip**（分仓库 xlsx ＋ 总表）→ 返回 zip 路径。

    - `rows_or_df`：`setl_detail` 明细行（**本仓主路径**）或已建好的 DataFrame
    - `out_dir`：中间目录（**会被清空** —— 防"月与月之间仓库集合变化"时旧文件残留，
      这是素材包原有行为，保留）
    - `label`：期间标签（如 `2026年9月`）；成品名 = `第四工程公司{label}收发结存表`（同素材包命名）
    """
    require_template(SETL_TEMPLATE)      # ⭐ 本仓适配：模板缺失 / 损坏 ⇒ 显式报错
    df = rows_or_df if isinstance(rows_or_df, pd.DataFrame) else frame_from_rows(rows_or_df)
    if df.empty:
        raise MustReportError(
            '「%s」没有任何收发结存明细 ⇒ **不产出成品文件**'
            '（空文件会被当成"交付了"，比不导出更坏）—— 请先抓取或导入该月数据。' % label
        )

    out_dir = str(out_dir)
    if os.path.isdir(out_dir):
        for f in os.listdir(out_dir):
            try:
                os.remove(os.path.join(out_dir, f))
            except OSError:
                pass
    os.makedirs(out_dir, exist_ok=True)
    show_order = [w for w in df['仓库'].unique() if w == w]
    logger.info("收发结存导出：%d 行 | 仓库 %d 个：%s", len(df), len(show_order), show_order)

    files = []
    for wh in show_order:
        sub = df[df['仓库'] == wh].copy()
        fn = os.path.join(out_dir, f'{wh}.xlsx')
        write_warehouse_file(sub, fn)
        files.append(fn)
        logger.info("  分仓库 %s：%d 行", os.path.basename(fn), len(sub))

    work = os.path.join(out_dir, '_work.xlsx')
    main_fn = os.path.join(out_dir, f'第四工程公司{label}收发结存表.xlsx')
    pv, grand = update_sheet_data(df, work, show_order)
    patch_pivot(work, main_fn, df, show_order)
    os.remove(work)
    files.append(main_fn)

    problems = verify(main_fn, df, pv, grand, show_order)
    # ⭐ 本仓适配：对账不过 ⇒ **硬失败**（素材包只是打印出来给人看；生产里静默交付一个
    #    数字对不上的成品是最坏的失败形态 —— 文件看着正常、数是错的）
    if problems:
        raise MustReportError(
            '成品文件**透视表对账未通过** ⇒ 已中止，未交付：'
            + '；'.join(problems[:5])
            + ('' if len(problems) <= 5 else '（等共 %d 条）' % len(problems))
        )
    logger.info("✓ 透视表对账全部通过 | 总计: 期初%.2f 收%.2f 发%.2f 结存%.2f",
                grand["期初金额"], grand["收金额"], grand["发金额"], grand["结存金额"])

    zip_fn = os.path.join(out_dir, f'第四工程公司{label}收发结存表.zip')
    with zipfile.ZipFile(zip_fn, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fn in files:
            zf.write(fn, os.path.basename(fn))
    logger.info("✓ 打包: %s", os.path.basename(zip_fn))
    # 输出目录只保留 zip（分仓库/总表已进 zip，删除中间 xlsx）
    for fn in files:
        try:
            os.remove(fn)
            logger.info("  清理中间文件: %s", os.path.basename(fn))
        except OSError:
            pass
    return zip_fn


if __name__ == '__main__':          # 仅供人工试跑：`python setl_export.py <out_dir> <label>`
    import sys as _sys

    print(build_zip([], _sys.argv[1], _sys.argv[2] if len(_sys.argv) > 2 else ''))
