# -*- coding: utf-8 -*-
"""透视**缓存**的重建（`pivotCacheDefinition` / `pivotCacheRecords`）＋ **缓存级对账**。

**来源**：逐字移植自交付面 `PRD素材包-20260911/input/common_tpl.py`（⚠️ 只搬实现，口径不反推）；
2026-09-18 从 `tpl_engine.py` 拆出（该文件加完 `TAIL-43` 显示区后 >600 行 = 禁合入）。

**对账口径**：从**新文件的新缓存**重算 vs 从**原数据**重算，逐项比对 ⇒
这不是"生成了一眼看着像"的检查，是"两条独立路径算同一笔数"的检查。
⚠️ 它**看不见「显示区」**（显示区是 Excel 存的渲染结果）⇒ 那份对账在 `sheet_display.py`。
"""
import re
import zipfile
from html import unescape
from xml.sax.saxutils import escape

from app.core.errors import MustReportError
from app.report_export.xl_common import NS, fmt_num, norm_num, parse_shared_items


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
                new_seg = new_seg.replace('</sharedItems>', extra + '</sharedItems>', 1)
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
                new_seg = new_seg.replace('</sharedItems>', extra + '</sharedItems>', 1)
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
