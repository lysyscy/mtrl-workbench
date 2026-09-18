# -*- coding: utf-8 -*-
"""模板法重建引擎（**编排 ＋ 数据侧**）—— 逐字移植自交付面素材包
`PRD素材包-20260911/input/common_tpl.py`（⚠️ 只搬**实现**，口径不反推）。

**它做什么**：以「用户手作的那份成品 xlsx」为基底做 `zip` 字节替换，动态重建当月文件：
  1) sharedStrings：保留模板全部字符串 + 追加当月新字符串
  2) 数据 sheet：表头保留模板原样，数据行按模板行样式生成（28 列内通用）
  3) pivotCacheDefinition / pivotCacheRecords → `pivot_cache.py`
  4) pivotTable：location / axisRow items / rowItems 动态
  5) **透视显示区**（`TAIL-43`）→ `sheet_display.py`
  6) 对账：数据 ↔ 缓存（`pivot_cache.verify_cache`）＋ 缓存 ↔ 显示区（`sheet_display.verify_display`）

## 拆件（2026-09-18 · `TAIL-43` 之后本文件曾 934 行 > 600 = 禁合入）
| 文件 | 职责 |
|---|---|
| `xl_common.py` | 最底层原语（`NS` / `fmt_num` / `norm_num` / `parse_shared_items`）· **中立件** |
| `pivot_cache.py` | 缓存两件重建 ＋ **缓存级对账** |
| `sheet_display.py` | **显示区**重建 ＋ 显示区对账（`TAIL-43`） |
| `tpl_engine.py` | 本文件 = 编排（`rebuild()`）＋ 数据侧（读数据 / sharedStrings / 数据 sheet / pivotTable） |

⚠️ 三个中立件里的函数**本文件一律再导出**（`from … import …`）—— 全站引用都是
   `tpl_engine.X` 形式（实测 grep 过），再导出 ⇒ 调用方**零改动**。

⭐ **本仓的三处适配**（其余与原文件逐字一致）：
1. **数据优先由调用方给**（`cfg['data']`）—— 生产环境的数据主人在**库里**；
   ⛔ 仍保留走 `src` 文件的能力（`cfg` 不给 `data` 时按原逻辑读）。
2. **对账不过 ⇒ 硬失败**（素材包只是打印；生产里必须 `raise`）。
3. **删掉模块级 `warnings.filterwarnings('ignore')`** —— 那是**库**，import 就全局静音全站告警。
"""
import re
import zipfile
from html import unescape
from xml.sax.saxutils import escape

import openpyxl
from openpyxl.utils import get_column_letter

from app.core.errors import MustReportError
# ⭐ 再导出：全站引用都是 `tpl_engine.X` ⇒ 拆件对外**零改动**
from app.report_export.pivot_cache import rebuild_cache_def, rebuild_records, verify_cache
from app.report_export.sheet_display import (pivot_column_specs, pivot_page_filter,
                                            render_pivot_sheet, verify_display)
from app.report_export.xl_common import NS, fmt_num, norm_num, parse_shared_items


# ================= 读原数据 =================
def read_data(src, sheet_names=('报表1', 'Sheet1'), header_keywords=('序号', '金额'),
              col_count=28, date_fmt='%Y-%m-%d'):
    """读导出数据：智能找表头行，返回 (表头列表, 数据行列表[col_count 列元组])"""
    wb = openpyxl.load_workbook(src, read_only=True, data_only=True)
    ws = None
    for name in sheet_names:
        if name in wb.sheetnames:
            ws = wb[name]
            break
    if ws is None:
        ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    hi = None
    for i, r in enumerate(rows):
        if not r:
            continue
        strs = [str(x) if x is not None else '' for x in r[:col_count]]
        if all(k in strs for k in header_keywords):
            hi = i
            break
    if hi is None:
        raise RuntimeError('找不到表头行（需含 %s）' % str(header_keywords))
    hdr = list(rows[hi])
    data = []

    def _fmt(v):
        from datetime import datetime, date
        if isinstance(v, datetime):
            return v.strftime(date_fmt)
        if isinstance(v, date):
            return v.strftime(date_fmt)
        return v

    for r in rows[hi + 1:]:
        if r is None or r[0] is None or str(r[0]).strip() == '':
            continue
        row = [_fmt(x) for x in list(r[:col_count])] + [''] * max(0, col_count - len(r))
        data.append(tuple(row))
    wb.close()  # 释放文件句柄，否则原始导出无法删除
    return hdr, data



# ================= sharedStrings =================
def build_sharedstrings(tpl_ss_xml, data):
    """模板 sharedStrings + 追加新字符串 -> (strs列表, str->idx映射)"""
    strs = []
    for si in re.findall(r'<si>(.*?)</si>', tpl_ss_xml, re.S):
        ts = re.findall(r'<t[^>]*>([^<]*)</t>', si)
        strs.append(unescape(''.join(ts)))
    idx = {s: i for i, s in enumerate(strs)}
    for row in data:
        for v in row:
            if isinstance(v, str) and v not in idx:
                idx[v] = len(strs)
                strs.append(v)
    return strs, idx


def ss_xml(strs):
    parts = []
    for s in strs:
        parts.append('<si><t xml:space="preserve">%s</t></si>'
                     % escape(s, {chr(34): '&quot;', chr(39): '&apos;'}))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<sst xmlns="%s" count="%d" uniqueCount="%d">%s</sst>'
            % (NS, len(strs), len(strs), ''.join(parts)))



# ================= 数据 sheet 生成 =================
def gen_data_sheet(tpl_sheet, data, str_idx, num_cols, col_count,
                   header_row=1, data_start=2, style_row=2):
    """表头行保留模板，数据行按模板 style_row 的列样式生成"""
    m1 = re.search(r'<row r="%d"[^>]*>.*?</row>' % header_row, tpl_sheet, re.S)
    row1 = m1.group(0) if m1 else ''
    m2 = re.search(r'<row r="%d"[^>]*>.*?</row>' % style_row, tpl_sheet, re.S)
    row2 = m2.group(0) if m2 else ''
    col_style = {}
    for cm in re.finditer(r'<c r="([A-Z]+)%d"\s+[^>]*s="(\d+)"' % style_row, row2):
        col_style[cm.group(1)] = cm.group(2)
    col_text_style, col_num_style = {}, {}
    for col, s in col_style.items():
        if re.search(r'<c r="%s%d"[^>]*t="s"' % (col, style_row), row2):
            col_text_style[col] = s
        else:
            col_num_style[col] = s
    mra = re.match(r'<row r="%d"([^>]*)>' % style_row, row2)
    rattr = mra.group(1) if mra else ''

    def cell_xml(letter, col_num, v, row_idx):
        ref = '%s%d' % (letter, row_idx)
        if v is None or (isinstance(v, str) and v.strip() == ''):
            return '<c r="%s" s="%s"/>' % (ref, col_style.get(letter, '4'))
        if col_num in num_cols or isinstance(v, (int, float)):
            s = col_num_style.get(letter, '3')
            n = norm_num(v)
            if n is None:
                return '<c r="%s" s="%s"/>' % (ref, s)
            return '<c r="%s" s="%s"><v>%s</v></c>' % (ref, s, fmt_num(n))
        s = col_text_style.get(letter, col_style.get(letter, '4'))
        return '<c r="%s" s="%s" t="s"><v>%d</v></c>' % (ref, s, str_idx[str(v)])

    letters = [get_column_letter(c) for c in range(1, col_count + 1)]
    data_rows = []
    for i, row in enumerate(data, start=data_start):
        cells = ''.join(cell_xml(letters[c], c, row[c], i) for c in range(col_count))
        data_rows.append('<row r="%d"%s>%s</row>' % (i, rattr, cells))
    new = re.sub(r'<sheetData>.*?</sheetData>',
                 lambda mo: '<sheetData>%s%s</sheetData>' % (row1, ''.join(data_rows)),
                 tpl_sheet, flags=re.S)
    new = re.sub(r'<dimension ref="[^"]*"',
                 '<dimension ref="A1:%s%d"' % (get_column_letter(col_count), data_start + len(data) - 1),
                 new)
    return new



# ================= pivotTable 动态 =================
def patch_pivot_row(pt, warehouses, wh_cache_idx, location_ref, rowitems_mode='leading_empty'):
    """动态行透视：location / axisRow items / rowItems；列字段等其余保留模板。
    rowitems_mode: 'leading_empty'（首项空 <i><x/></i>）或 'plain'（直接 v=1..N）"""
    pt = re.sub(r'<location ref="[^"]*"', '<location ref="%s"' % location_ref, pt)
    pat_axis = re.compile(r'<pivotField axis="axisRow"[^>]*><items count="\d+">.*?</items></pivotField>', re.S)
    m = pat_axis.search(pt)
    if m:
        head = m.group(0)[:m.group(0).find('<items')]
        items_xml = ('<items count="%d">' % (len(warehouses) + 1)
                     + ''.join('<item x="%d"/>' % wh_cache_idx[w] for w in warehouses)
                     + '<item t="default"/></items></pivotField>')
        pt = pt[:m.start()] + head + items_xml + pt[m.end():]
    pat_rows = re.compile(r'<rowItems count="\d+">.*?</rowItems>', re.S)
    m = pat_rows.search(pt)
    if m:
        n = len(warehouses)
        if rowitems_mode == 'plain':
            row_items = ('<rowItems count="%d">' % (n + 1)
                         + ''.join('<i><x v="%d"/></i>' % k for k in range(1, n + 1))
                         + '<i t="grand"><x/></i></rowItems>')
        else:
            row_items = ('<rowItems count="%d">' % (n + 1)
                         + '<i><x/></i>'
                         + ''.join('<i><x v="%d"/></i>' % k for k in range(1, n))
                         + '<i t="grand"><x/></i></rowItems>')
        pt = pt[:m.start()] + row_items + pt[m.end():]
    # ⚠️⚠️ **本仓适配（实测纠正，2026-09-18）**：原实现在这里往 `<pivotTableDefinition>` 上
    #    加 `refreshOnLoad="1"` —— 但该属性**既不在 `pivotTable` schema 里**，**也不在
    #    `workbook.xml` 的 `<pivotCache>` 里**（两处都试过，openpyxl 分别报 `TableDefinition`
    #    / `PivotCache ... unexpected keyword argument`）。它的**唯一合法归属**是
    #    **`xl/pivotCache/pivotCacheDefinition1.xml` 的 `<pivotCacheDefinition>`**
    #    （`openpyxl.pivot.cache.CacheDefinition.refreshOnLoad`）⇒ 见 `rebuild()` 里的那一段。
    #    ⚠️ 素材包的核对只查 `'refreshOnLoad="1"' in 字符串` ⇒ **字符串在、位置错，照样通过**
    #       ——「存在性检查」看不见结构错。
    return pt


def template_wh_order(tpl_pcd, tpl_pt, wh_field):
    """模板透视显示顺序：从 pivotTable 的 axisRow items + cacheField 还原仓库名顺序"""
    flds = re.findall(r'<cacheField\b([^>]*)>(.*?)</cacheField>', tpl_pcd, re.S)
    _, t_vals, _ = parse_shared_items(flds[wh_field][1])
    tpl_wh = [unescape(x) for x in t_vals]
    m = re.search(r'<pivotField axis="axisRow"[^>]*><items[^>]*>(.*?)</items>', tpl_pt, re.S)
    ax = [int(x) for x in re.findall(r'<item x="(\d+)"', m.group(1))] if m else list(range(len(tpl_wh)))
    return [tpl_wh[i] for i in ax if i < len(tpl_wh)]


def warehouse_order(tpl_wh_order, wh_set):
    """模板顺序优先（保持手作顺序），新仓库按首现追加"""
    order = [w for w in tpl_wh_order if w in wh_set]
    for w in wh_set:
        if w not in order:
            order.append(w)
    return order



# ================= 高层入口 =================
def rebuild(cfg):
    """cfg:
      template/src/out
      data_sheet: {names, header_keywords, col_count, num_cols}
      shared: {sheet_file:'xl/worksheets/sheet3.xml', header_row, data_start, style_row}
      cache: {field_count, num_cols, empty_fields, wh_field, wh_order_pivot_file}
      pivots: [{file, location_ref(函数:n->ref), rowitems_mode}]
      verify: [规则...]
    返回 out_path
    """
    template = cfg['template']
    out = cfg['out']
    ds = cfg['data_sheet']
    sh = cfg['shared']
    ca = cfg['cache']
    # ⭐ 本仓适配：**数据优先由调用方给** —— 生产的数据主人在库里，导出不依赖 i8 原始件；
    #    不给 `data` 时才回落到「读 src 文件」（原逻辑）。
    if cfg.get('data'):
        data = cfg['data']
        hdr = cfg.get('header') or []
    else:
        hdr, data = read_data(cfg['src'], ds.get('names', ('报表1', 'Sheet1')),
                              ds.get('header_keywords', ('序号', '金额')),
                              ds.get('col_count', 28))
    print('数据: %d 行 x %d 列' % (len(data), len(hdr)))

    z = zipfile.ZipFile(template)
    tpl_ss = z.read('xl/sharedStrings.xml').decode('utf-8')
    tpl_sheet = z.read(sh['sheet_file']).decode('utf-8')
    tpl_pcd = z.read('xl/pivotCache/pivotCacheDefinition1.xml').decode('utf-8')
    tpl_pt1 = z.read(ca.get('wh_order_pivot_file', cfg['pivots'][0]['file'])).decode('utf-8')
    z.close()

    strs, str_idx = build_sharedstrings(tpl_ss, data)
    print('sharedStrings: %d (追加 %d)' % (len(strs), max(0, len(strs) - len(re.findall(r'<si>', tpl_ss)))))

    new_sheet = gen_data_sheet(tpl_sheet, data, str_idx, ds['num_cols'], ds.get('col_count', 28),
                               sh.get('header_row', 1), sh.get('data_start', 2), sh.get('style_row', 2))
    cd, field_maps = rebuild_cache_def(tpl_pcd, data, ca['num_cols'], ca['field_count'], ca.get('empty_fields', ()))
    cr = rebuild_records(data, field_maps, ca['num_cols'], ca.get('empty_fields', ()))

    # 仓库顺序（模板优先）
    wh_field = ca.get('wh_field', 18)
    tpl_order = template_wh_order(tpl_pcd, tpl_pt1, wh_field)
    # ⚠️ **按首次出现顺序去重**，⛔ 不用 `set` —— `set` 的迭代顺序对字符串是**进程内的
    #    哈希顺序**（`PYTHONHASHSEED` 一变就变）⇒ 模板里没有的新仓库，行顺序会**每次跑不一样**。
    #    以前只影响透视定义，`TAIL-43` 之后它**直接决定显示区每行的位置** ⇒ 必须确定。
    wh_set = {}
    for row in data:
        w = str(row[wh_field]).strip()
        if w:
            wh_set.setdefault(w, None)
    order = warehouse_order(tpl_order, list(wh_set))
    print('仓库(%d): %s' % (len(order), order))
    wh_cache_idx = field_maps[wh_field]

    new_pivots = {}
    wh_order = {}
    for pv in cfg['pivots']:
        z2 = zipfile.ZipFile(template)
        tpl_pt = z2.read(pv['file']).decode('utf-8')
        z2.close()
        # 透视可用仓库：默认全部；可配置子集（按 order 顺序过滤）
        # ⛔ **不能用 falsy 判断**（`if not pv.get('warehouses')`）—— 空集(`set()`) 是
        #    "**这个透视确实一个仓库都没有**"（应得 **0 行项**），⛔ 不是"**未配置**"（未配置才用全部）；
        #    两者语义相反，falsy 会把空集误当"未传" ⇒ 该透视凭空冒出**全部**仓库。
        pvw = pv.get('warehouses')
        whs = order if pvw is None else [w for w in order if w in pvw]
        loc = pv['location_ref'](len(whs)) if callable(pv['location_ref']) else pv['location_ref']
        new_pivots[pv['file']] = patch_pivot_row(tpl_pt, whs, wh_cache_idx, loc,
                                                 pv.get('rowitems_mode', 'leading_empty'))
        wh_order[pv['file']] = whs

    # ⭐ 本仓适配：「打开即刷新」写进 **`pivotCacheDefinition`**（唯一合法归属 —— 见
    #    `patch_pivot_row` 末尾那段实测纠正）。幂等：已带 `refreshOnLoad` 的不再重复加。
    cd = re.sub(r'<pivotCacheDefinition\b(?![^>]*refreshOnLoad)([^>]*?)>',
                r'<pivotCacheDefinition\1 refreshOnLoad="1">', cd, count=1)

    zin = zipfile.ZipFile(template)
    zout = zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED)
    # ⭐ `TAIL-43`：**显示区重建** —— 见本节顶部那段实测根因。
    #    ⚠️ 标签的顺序由引擎定（= 上面算出的 `whs`，与 `rowItems` 同序），**格子的值由调用方给**
    #    （域内核只知道"数是多少"，不知道"哪一格"；`by_label` 以标签为键）。
    new_sheets, display_specs = {}, []
    for sp in cfg.get('sheets', []):
        tz = zipfile.ZipFile(template)
        try:
            tpl_sheet = tz.read(sp['sheet_file']).decode('utf-8')
        finally:
            tz.close()
        rows = [(str(w).strip(), sp['by_label'].get(str(w).strip(), {}))
                for w in (sp.get('labels') or wh_order[sp['pivot']])]
        full = dict(sp, rows=rows,
                    total=(sp.get('total_label', '总计'), sp.get('total', {})))
        new_sheets[sp['sheet_file']] = render_pivot_sheet(tpl_sheet, full, str_idx).encode('utf-8')
        display_specs.append(full)
    for item in zin.infolist():
        db = zin.read(item.filename)
        if item.filename == 'xl/sharedStrings.xml':
            db = ss_xml(strs).encode('utf-8')
        elif item.filename == sh['sheet_file']:
            db = new_sheet.encode('utf-8')
        elif item.filename in new_sheets:
            db = new_sheets[item.filename]
        elif item.filename == 'xl/pivotCache/pivotCacheDefinition1.xml':
            db = cd.encode('utf-8')
        elif item.filename == 'xl/pivotCache/pivotCacheRecords1.xml':
            db = cr.encode('utf-8')
        elif item.filename in new_pivots:
            db = new_pivots[item.filename].encode('utf-8')
        zout.writestr(item, db)
    zout.close()
    zin.close()
    print('输出:', out)

    problems = verify_cache(out, data, cfg.get('verify', []), ca.get('empty_fields', ()))
    problems += verify_display(out, display_specs)      # ⭐ `TAIL-43` 独立第二条路径
    # ⭐ 本仓适配：对账不过 ⇒ **硬失败**（素材包只是打印；生产里静默交付一个对不上的成品
    #    是最坏的失败形态 —— 文件看着正常、数字是错的）。
    if problems:
        raise MustReportError(
            '成品文件**缓存级对账未通过** ⇒ 已中止，未交付：'
            + '；'.join(problems[:5])
            + ('' if len(problems) <= 5 else '（等共 %d 条）' % len(problems))
        )
    print('✓ 缓存对账 ＋ 显示区对账 全部通过')
    return out
