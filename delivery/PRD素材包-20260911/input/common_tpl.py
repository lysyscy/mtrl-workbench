# -*- coding: utf-8 -*-
"""
模板法重建引擎 v1（通用）
=====================================
基于"用户手作成品 xlsx"做基底，动态重建当月文件：
  1) sharedStrings：保留模板全部字符串 + 追加当月新字符串
  2) 数据 sheet：表头保留模板原样，数据行按模板行样式生成（28 列内通用）
  3) pivotCacheDefinition：各字段 sharedItems 按当月数据动态（追加新值）
  4) pivotCacheRecords：记录重建（空值 <x/>，分组空字段按配置）
  5) pivotTable：location / axisRow items / rowItems 动态 + refreshOnLoad="1"
  6) 缓存级对账：从新缓存重算 vs 从原数据重算，逐项核对

用法：各具体表写薄配置脚本，调用 rebuild()：
    cfg = {
        'data_sheet': {...},   # 读原数据
        'shared': {...},       # 数据 sheet 生成
        'cache': {...},        # 缓存字段定义
        'pivots': [...],       # 每个透视的动态规则
        'verify': [...],       # 对账规则
        'template': ..., 'src': ..., 'out': ...,
    }
"""
import re
import zipfile
import warnings
from html import unescape
from xml.sax.saxutils import escape

import openpyxl
from openpyxl.utils import get_column_letter

warnings.filterwarnings('ignore')

NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'


# ================= 基础工具 =================
def fmt_num(x):
    s = ('%.10f' % float(x)).rstrip('0').rstrip('.')
    return s if s not in ('', '-0') else '0'


def norm_num(v):
    """数字/数字字符串 -> float；空 -> None"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).replace(',', '').strip()
    if s == '' or s == '-':
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_shared_items(seg):
    """从 cacheField 的 sharedItems 段解析 -> (typ, [values], attrs)"""
    si = re.search(r'<sharedItems([^>]*)>(.*?)</sharedItems>', seg, re.S)
    if not si:
        return None, [], {}
    attrs = dict(re.findall(r'(\w+)="([^"]*)"', si.group(1)))
    body = si.group(2)
    vals = []
    typ = None
    for m in re.finditer(r'<(n|s|b|d)\s[^>]*v="([^"]*)"', body):
        typ = m.group(1)
        vals.append(unescape(m.group(2)))
    return typ, vals, attrs


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


# ================= 透视缓存重建 =================
def rebuild_cache_def(tpl_pcd, data, num_cols, field_count, empty_fields=()):
    """重建 pivotCacheDefinition：字段 sharedItems 按当月数据动态；返回 (xml, field_maps[value->idx])"""
    fields = re.findall(r'<cacheField\b([^>]*)>(.*?)</cacheField>', tpl_pcd, re.S)
    assert len(fields) == field_count, '模板 cacheField 数=%d 期望 %d' % (len(fields), field_count)
    field_maps = []
    new_parts = []
    for i, (attrs, body) in enumerate(fields):
        if i in empty_fields:
            field_maps.append(None)
            new_parts.append(body)
            continue
        typ0, seen0, _ = parse_shared_items(body)
        is_num = i in num_cols
        col_vals = []
        for row in data:
            v = row[i]
            if is_num:
                nv = norm_num(v)
                col_vals.append(nv if nv is not None else '')
            else:
                col_vals.append(str(v) if v is not None and str(v).strip() != '' else '')
        if not seen0:
            if any(v != '' for v in col_vals):
                typ = 'n' if is_num else 's'
                seen = []
            else:
                new_parts.append(body)
                field_maps.append({})
                continue
        else:
            if is_num:
                seen = []
                for x in seen0:
                    if x in ('-', ''):
                        continue
                    try:
                        seen.append(float(x))
                    except ValueError:
                        pass
            else:
                seen = [str(x) for x in seen0]
            typ = 'n' if is_num else 's'
            if is_num and not seen and not any(v != '' for v in col_vals):
                new_parts.append(body)
                field_maps.append({})
                continue
        idx = {}
        if typ == 'n':
            for j, v in enumerate(seen):
                idx[float(v)] = j
            added = []
            for v in col_vals:
                if v == '':
                    continue
                f = float(v)
                if f not in idx:
                    idx[f] = len(seen)
                    seen.append(f)
                    added.append(f)
            extra = ''.join('<n v="%s"/>' % fmt_num(k) for k in added)
            new_seg = body
            nums = [float(x) for x in seen]
            m = re.search(r'<sharedItems([^>]*)>', new_seg)
            if m:
                a2 = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
                if nums:
                    a2['minValue'] = fmt_num(min(nums))
                    a2['maxValue'] = fmt_num(max(nums))
                a2['count'] = str(len(nums))
                attr_s = ''.join(' %s="%s"' % (k, v) for k, v in a2.items())
                new_seg = new_seg[:m.start()] + '<sharedItems%s>' % attr_s + new_seg[m.end():]
            new_seg = re.sub(r'count="\d+"', 'count="%d"' % len(nums), new_seg)
            if added:
                new_seg = new_seg[:-len('</sharedItems>')] + extra + '</sharedItems>'
        else:
            for j, v in enumerate(seen):
                idx[str(v)] = j
            added = []
            for v in col_vals:
                if v == '':
                    continue
                sv = str(v)
                if sv not in idx:
                    idx[sv] = len(seen)
                    seen.append(sv)
                    added.append(sv)
            extra = ''.join('<s v="%s"/>'
                            % escape(str(k), {chr(34): '&quot;', chr(39): '&apos;'}) for k in added)
            new_seg = re.sub(r'count="\d+"', 'count="%d"' % len(seen), body)
            if added:
                new_seg = new_seg[:-len('</sharedItems>')] + extra + '</sharedItems>'
        field_maps.append(idx)
        new_parts.append(new_seg)
    names = []
    for a, _ in fields:
        m = re.search(r'name="([^"]*)"', a)
        names.append(m.group(1) if m else 'f')
    m = re.search(r'<cacheFields count="\d+">(.*?)</cacheFields>', tpl_pcd, re.S)
    new_cd = (tpl_pcd[:m.start()]
              + '<cacheFields count="%d">' % field_count
              + ''.join('<cacheField name="%s" numFmtId="0">%s</cacheField>'
                        % (escape(nm, {chr(34): '&quot;', chr(39): '&apos;'}), seg)
                        for nm, seg in zip(names, new_parts))
              + '</cacheFields>' + tpl_pcd[m.end():])
    new_cd = re.sub(r'recordCount="\d+"', 'recordCount="%d"' % len(data), new_cd)
    new_cd = re.sub(r'ref="[^"]*"', 'ref="A1:AB%d"' % (len(data) + 1), new_cd)
    return new_cd, field_maps


def rebuild_records(data, field_maps, num_cols, empty_fields=()):
    rows = []
    for i, row in enumerate(data, start=1):
        xs = []
        for f in range(len(field_maps)):
            if f in empty_fields or field_maps[f] is None:
                xs.append('<x v="0"/>' if f in empty_fields else '<x/>')
                continue
            idx = field_maps[f]
            if f in num_cols:
                nv = norm_num(row[f])
                if nv is None:
                    xs.append('<x/>')
                else:
                    xs.append('<x v="%d"/>' % idx[float(nv)])
            else:
                v = row[f]
                sv = str(v) if v is not None and str(v).strip() != '' else ''
                if sv == '':
                    xs.append('<x/>')
                else:
                    xs.append('<x v="%d"/>' % idx[sv])
        rows.append('<r>%s</r>' % ''.join(xs))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<pivotCacheRecords xmlns="%s" count="%d">%s</pivotCacheRecords>'
            % (NS, len(data), ''.join(rows)))


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
    if 'refreshOnLoad' not in pt:
        pt = re.sub(r'<pivotTableDefinition[^>]*>',
                    lambda mo: mo.group(0)[:-1] + ' refreshOnLoad="1">', pt, count=1)
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


# ================= 对账 =================
def verify_cache(out_path, data, verify_rules, empty_fields=()):
    """从新文件缓存重算 vs 原数据重算。
    verify_rules: [{name, row, cols:(...), value, group_map:{旧:新}, filter:(字段,值), filter_cols:(...)}]"""
    import xml.etree.ElementTree as ET
    problems = []
    zf = zipfile.ZipFile(out_path)
    for name in ('xl/pivotCache/pivotCacheDefinition1.xml', 'xl/pivotCache/pivotCacheRecords1.xml'):
        try:
            ET.fromstring(zf.read(name))
        except Exception as e:
            problems.append('%s: %s' % (name, e))
            zf.close()
            return problems
    cd = ET.fromstring(zf.read('xl/pivotCache/pivotCacheDefinition1.xml'))
    cr = ET.fromstring(zf.read('xl/pivotCache/pivotCacheRecords1.xml'))
    fields = cd.findall('{%s}cacheFields/{%s}cacheField' % (NS, NS))
    fvals = []
    for f in fields:
        si = f.find('{%s}sharedItems' % NS)
        vals = []
        if si is not None:
            for ch in si:
                if ch.tag.endswith('n'):
                    vals.append(float(ch.get('v')))
                else:
                    vals.append(str(ch.get('v')))
        fvals.append(vals)

    def _gv(xs, f):
        v = xs[f].get('v')
        if v is None or f >= len(fvals):
            return None
        return fvals[f][int(v)]

    for rule in verify_rules:
        cache_sum = {}
        for r in cr.findall('{%s}r' % NS):
            xs = r.findall('{%s}x' % NS)
            if len(xs) < len(fvals):
                continue
            if rule.get('filter'):
                ff, fv = rule['filter']
                if _gv(xs, ff) != fv:
                    continue
            rowv = _gv(xs, rule['row'])
            amt = _gv(xs, rule['value'])
            if rowv is None or amt is None:
                continue
            gm = rule.get('group_map')
            colv = []
            for c in rule.get('cols', ()):
                v = _gv(xs, c)
                if v is not None and gm and v in gm:
                    v = gm[v]
                colv.append(v)
            key = (rowv,) + tuple(colv)
            cache_sum[key] = cache_sum.get(key, 0.0) + amt
        data_sum = {}
        for row in data:
            amt = norm_num(row[rule['value']])
            if amt is None:
                continue
            if rule.get('filter'):
                if str(row[rule['filter'][0]]).strip() != rule['filter'][1]:
                    continue
            rowv = str(row[rule['row']]).strip()
            colv = []
            for c in rule.get('cols', ()):
                v = str(row[c]).strip()
                gm = rule.get('group_map')
                if gm and v in gm:
                    v = gm[v]
                colv.append(v)
            key = (rowv,) + tuple(colv)
            data_sum[key] = data_sum.get(key, 0.0) + amt
        for key in set(cache_sum) | set(data_sum):
            got = round(cache_sum.get(key, 0.0), 2)
            exp = round(data_sum.get(key, 0.0), 2)
            if abs(got - exp) > 0.01:
                problems.append('%s 对账失败 %s: %.2f vs %.2f' % (rule.get('name', '?'), key, got, exp))
    if len(data) != len(cr.findall('{%s}r' % NS)):
        problems.append('记录数 %d != 数据行 %d' % (len(cr.findall('{%s}r' % NS)), len(data)))
    zf.close()
    return problems


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
    src = cfg['src']
    out = cfg['out']
    ds = cfg['data_sheet']
    sh = cfg['shared']
    ca = cfg['cache']
    hdr, data = read_data(src, ds.get('names', ('报表1', 'Sheet1')),
                          ds.get('header_keywords', ('序号', '金额')),
                          ds.get('col_count', 28))
    if 'data' in cfg and cfg['data']:
        data = cfg['data']
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
    wh_set = set()
    for row in data:
        w = str(row[wh_field]).strip()
        if w:
            wh_set.add(w)
    order = warehouse_order(tpl_order, wh_set)
    print('仓库(%d): %s' % (len(order), order))
    wh_cache_idx = field_maps[wh_field]

    new_pivots = {}
    for pv in cfg['pivots']:
        z2 = zipfile.ZipFile(template)
        tpl_pt = z2.read(pv['file']).decode('utf-8')
        z2.close()
        # 透视可用仓库：默认全部；可配置子集（按 order 顺序过滤）
        whs = order if not pv.get('warehouses') else [w for w in order if w in pv['warehouses']]
        loc = pv['location_ref'](len(whs)) if callable(pv['location_ref']) else pv['location_ref']
        new_pivots[pv['file']] = patch_pivot_row(tpl_pt, whs, wh_cache_idx, loc,
                                                 pv.get('rowitems_mode', 'leading_empty'))

    zin = zipfile.ZipFile(template)
    zout = zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED)
    for item in zin.infolist():
        db = zin.read(item.filename)
        if item.filename == 'xl/sharedStrings.xml':
            db = ss_xml(strs).encode('utf-8')
        elif item.filename == sh['sheet_file']:
            db = new_sheet.encode('utf-8')
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
    if problems:
        print('!! 验证问题:')
        for p in problems:
            print('  -', p)
    else:
        print('✓ 缓存对账全部通过')
    return out
