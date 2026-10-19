# -*- coding: utf-8 -*-
"""`TAIL-43` 验证工具（可复跑）：显示区重建 → 三条独立路径对账 ＋ **反向自检**。

**它证什么**
  ① **口径标定**：用**模板自身**复算它的每一个显示格（模板缓存与显示同月）——逐格对上
     ⇒ 说明「列位置 ↔ 口径」的映射真的搞懂了（⛔ 不是照印象写的）。
  ② **修好了**：新成品的显示区 = 本月数；该月确无该费用时**如实为空**；**无僵尸行**。
  ③ **三条独立路径**：`报表1`(源) → 缓存 → 显示区，逐格一致；再与 **Excel 真机渲染值**对照。
  ④ **反向自检**：把同一把尺子套到**修前**那份成品上 ⇒ **必须报红**（否则这把尺子是假绿）。

用法：
    backend/.venv/Scripts/python.exe tools/_verify_tail43.py          # 离线（源 = 现有成品）
    backend/.venv/Scripts/python.exe tools/_verify_tail43.py <成品.xlsx>   # 指定成品做 ②③④
"""
from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import io
import re
import sys
import tempfile
import zipfile
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

TPL = ROOT / "backend" / "app" / "resources" / "templates" / "模板_库存单据明细表.xlsx"
PROD = ROOT / _run_dir() / "exports" / "库存单据明细表" / "2026年9月" / "库存单据明细表_2026年9月.xlsx"
#: Excel 真机打开「修前」成品后渲染出来的值（2026-09-18 实测，见 memory 日志）
EXCEL_REF = {"A7": "安徽国风项目", "B7": 17939.35}
SCRATCH = Path(tempfile.mkdtemp(prefix="t43-"))

OK, BAD = [], []


def chk(cond, msg):
    (OK if cond else BAD).append(msg)
    print(("  ✓ " if cond else "  ✗ ") + msg)


# ---------------- 通用小工具 ----------------
def rows_of(path, part):
    z = zipfile.ZipFile(path)
    try:
        xml = z.read(part).decode("utf-8")
    finally:
        z.close()
    return {int(m.group(1)): m.group(0)
            for m in re.finditer(r'<row r="(\d+)"[^>]*>.*?</row>', xml, re.S)}


def strings_of(path):
    z = zipfile.ZipFile(path)
    try:
        if "xl/sharedStrings.xml" not in z.namelist():
            return []
        raw = z.read("xl/sharedStrings.xml").decode("utf-8")
    finally:
        z.close()
    return [unescape("".join(re.findall(r"<t[^>]*>([^<]*)</t>", si)))
            for si in re.findall(r"<si>(.*?)</si>", raw, re.S)]


def num_of(row_xml, ref):
    m = re.search(r'<c r="%s"(?:\s[^>]*)?>(.*?)</c>' % ref, row_xml or "", re.S)
    if not m:
        return None
    v = re.search(r"<v>([^<]*)</v>", m.group(1))
    return float(v.group(1)) if v else None


def label_of(rows, strs, ref):
    m = re.search(r'<c r="%s"[^>]*t="s"[^>]*>(.*?)</c>' % ref, rows.get(int(re.sub(r"\D", "", ref)), ""), re.S)
    if not m:
        return None
    v = re.search(r"<v>(\d+)</v>", m.group(1))
    return strs[int(v.group(1))] if v else None


def cache_data(path):
    """成品/模板的**缓存** → 与 `报表1` 同构的 28 列元组（用于"路径 B/C"复算）。"""
    import xml.etree.ElementTree as ET
    from app.report_export import tpl_engine
    NS = tpl_engine.NS
    z = zipfile.ZipFile(path)
    try:
        cd = ET.fromstring(z.read("xl/pivotCache/pivotCacheDefinition1.xml"))
        cr = ET.fromstring(z.read("xl/pivotCache/pivotCacheRecords1.xml"))
    finally:
        z.close()
    fvals, fgrp = [], []
    for f in cd.findall("{%s}cacheFields/{%s}cacheField" % (NS, NS)):
        si = f.find("{%s}sharedItems" % NS)
        fvals.append([(float(c.get("v")) if c.tag.endswith("n") else str(c.get("v")))
                      for c in si] if si is not None else [])
        fg = f.find("{%s}fieldGroup" % NS)
        # ⚠️ 基础字段自己也带 `<fieldGroup par="N"/>`（空壳）⇒ 只有带 groupItems/discretePr 的才算分组
        gi = fg.find("{%s}groupItems" % NS) if fg is not None else None
        dd = fg.find("{%s}discretePr" % NS) if fg is not None else None
        if fg is None or gi is None or dd is None:
            fgrp.append(None)
        else:
            fgrp.append({"items": [c.get("v") for c in gi],
                         "map": [int(c.get("v")) for c in dd], "base": int(fg.get("base"))})
    out = []
    for r in cr.findall("{%s}r" % NS):
        xs = [(int(x.get("v")) if x.get("v") is not None else None)
              for x in r.findall("{%s}x" % NS)]
        row = []
        for fi in range(len(fvals)):
            g = fgrp[fi]
            if g is not None:
                bk = xs[g["base"]] if g["base"] < len(xs) else None
                gi = g["map"][bk] if bk is not None and bk < len(g["map"]) else None
                row.append(g["items"][gi] if gi is not None and gi < len(g["items"]) else "")
                continue
            k = xs[fi] if fi < len(xs) else None
            row.append(fvals[fi][k] if k is not None and k < len(fvals[fi]) else "")
        out.append(tuple(row))
    return out


def source_bytes(path):
    """把成品的 `报表1` 抠出来当"i8 源文件"（离线复现用，⛔ 不碰 i8）。"""
    import openpyxl
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    rows = [list(r) for r in wb["报表1"].iter_rows(values_only=True)]
    wb.close()
    wb2 = openpyxl.Workbook()
    ws = wb2.active
    ws.title = "报表1"
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb2.save(buf)
    return buf.getvalue()


def order_from(path, wh_field):
    """成品里透视的行顺序（模板顺序优先）→ 显示标签顺序。"""
    from app.report_export import tpl_engine
    z = zipfile.ZipFile(path)
    try:
        cd = z.read("xl/pivotCache/pivotCacheDefinition1.xml").decode("utf-8")
        pt = z.read("xl/pivotTables/pivotTable1.xml").decode("utf-8")
    finally:
        z.close()
    tpl_order = tpl_engine.template_wh_order(cd, pt, wh_field)
    wh_set = {str(r[wh_field]).strip() for r in cache_data(path) if str(r[wh_field]).strip()}
    return tpl_engine.warehouse_order(tpl_order, wh_set)


def _rows_of_source(path):
    """→ `(表头行, [数据行…])`（离线复现/边界样本用）。"""
    import openpyxl
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    rows = [tuple(r) for r in wb["报表1"].iter_rows(values_only=True)]
    wb.close()
    return rows[0], rows[1:]


def _xlsx_of(rows, header_row):
    """按给定明细行造一份"i8 源"（离线边界样本用）。"""
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "报表1"
    ws.append(list(header_row))
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _specs_for(rows):
    """按给定明细行构造 `verify_display` 用的显示 spec（行标签顺序 = 引擎同款规则）。"""
    from app.report_export import kcdj_export, tpl_engine
    specs, _layout = kcdj_export.display_structure()
    z = zipfile.ZipFile(TPL)
    try:
        cd = z.read("xl/pivotCache/pivotCacheDefinition1.xml").decode("utf-8")
        pt = z.read("xl/pivotTables/pivotTable1.xml").decode("utf-8")
    finally:
        z.close()
    all_wh = {str(r[kcdj_export.COL_WAREHOUSE]).strip() for r in rows}
    safe_wh = {str(r[kcdj_export.COL_WAREHOUSE]).strip() for r in rows
               if str(r[kcdj_export.COL_CBS]).strip() == kcdj_export.SAFE_CBS}
    order = tpl_engine.warehouse_order(
        tpl_engine.template_wh_order(cd, pt, kcdj_export.COL_WAREHOUSE), all_wh)
    return [dict(specs[0], rows=[(w, {}) for w in order]),
            dict(specs[1], rows=[(w, {}) for w in order if w in safe_wh])]


# ---------------- 主流程 ----------------
def main():
    from app.report_export import kcdj_export, tpl_engine
    prod = Path(sys.argv[1]) if len(sys.argv) > 1 else PROD
    specs, layout = kcdj_export.display_structure()
    cols = layout["columns"]

    print("=" * 78)
    print("① 口径标定：用**模板自身**复算它的每一个显示格（模板缓存与显示同月 ⇒ 必须逐格对上）")
    print("=" * 78)
    print("  推导列 = %s" % [(c["letter"], c["dir"], c["group"]) for c in cols])
    chk(len(cols) == 13, "推导出 13 列 = 2 方向 ×(5 分组 ＋ 汇总) ＋ 总计")
    tpl_data = cache_data(TPL)
    by, total = kcdj_export.aggregate_grid(tpl_data, cols, layout["nat2group"])
    r1, strs = rows_of(TPL, "xl/worksheets/sheet1.xml"), strings_of(TPL)
    mis = []
    for r in range(7, 14):
        lb = label_of(r1, strs, "A%d" % r)
        for c in cols:
            exp, got = by.get(lb, {}).get(c["letter"]), num_of(r1[r], "%s%d" % (c["letter"], r))
            if (exp is None) != (got is None) or (exp is not None and abs(exp - got) > 0.01):
                mis.append((lb, c["letter"], got, exp))
    chk(not mis, "模板 7 个仓库 × 13 列**逐格复算**全部对上（差 %d 处 %s）" % (len(mis), mis[:4]))
    mis_t = [(c["letter"], num_of(r1[14], "%s14" % c["letter"]), total.get(c["letter"]))
             for c in cols if total.get(c["letter"]) is not None
             and abs((num_of(r1[14], "%s14" % c["letter"]) or 0) - total[c["letter"]]) > 0.01]
    chk(not mis_t, "模板**总计行**逐格对上（差 %s）" % mis_t)
    # 安全文明施工费那张：模板 5 个仓库 × 金额
    r2 = rows_of(TPL, "xl/worksheets/sheet2.xml")
    sby, stot = kcdj_export.aggregate_grid(tpl_data, specs[1]["columns"], layout["nat2group"],
                                           filter_col=kcdj_export.COL_CBS,
                                           filter_val=kcdj_export.SAFE_CBS)
    mis2 = []
    for r in range(4, 9):
        lb = label_of(r2, strs, "A%d" % r)
        exp, got = sby.get(lb, {}).get("B"), num_of(r2[r], "B%d" % r)
        if (exp is None) != (got is None) or (exp is not None and abs(exp - got) > 0.01):
            mis2.append((lb, got, exp))
    chk(not mis2, "模板「安全文明施工费」5 个仓库复算对上（差 %s）" % mis2)
    chk(not (num_of(r2[9], "B9") or 0) or abs(num_of(r2[9], "B9") - stot.get("B", 0)) < 0.01,
        "模板「安全文明施工费」总计复算对上（%s vs %s）" % (num_of(r2[9], "B9"), stot.get("B")))
    picked = tpl_engine.pivot_page_filter(
        zipfile.ZipFile(TPL).read("xl/pivotCache/pivotCacheDefinition1.xml").decode("utf-8"),
        zipfile.ZipFile(TPL).read("xl/pivotTables/pivotTable2.xml").decode("utf-8"),
        kcdj_export.COL_CBS)
    chk(picked == [kcdj_export.SAFE_CBS],
        "页筛选选中项从模板读出 = %s（多选 h=1 形态，⛔ 不是 pageField item）" % picked)

    print("\n" + "=" * 78)
    print("② 生成：离线跑一次 build_xlsx（源 = 成品的 `报表1`，⛔ 不碰 i8）")
    print("=" * 78)
    out = kcdj_export.build_xlsx(source_bytes(prod), SCRATCH / "2026年9月")
    print("  产物 %s (%d B)" % (out, Path(out).stat().st_size))

    print("\n" + "=" * 78)
    print("③ 新成品的显示区（本月 / 如实为空 / 无僵尸行 / 三路一致）")
    print("=" * 78)
    n_wh = len(order_from(prod, kcdj_export.COL_WAREHOUSE))
    n_safe = len({str(r[kcdj_export.COL_WAREHOUSE]).strip() for r in cache_data(prod)
                  if str(r[kcdj_export.COL_CBS]).strip() == kcdj_export.SAFE_CBS})
    new1, new2 = rows_of(out, "xl/worksheets/sheet1.xml"), rows_of(out, "xl/worksheets/sheet2.xml")
    nstrs = strings_of(out)
    chk(max(new1) == 7 + n_wh, "过程资料：行区间 3..%d（= 表头 3..6 ＋ %d 仓 ＋ 总计）⇒ **无僵尸行**"
        % (7 + n_wh, n_wh))
    chk(sorted(new1) == list(range(3, 7)) + list(range(7, 8 + n_wh)),
        "过程资料：行号正好是 3..6 ＋ 7..%d，一格不多" % (7 + n_wh))
    chk(max(new2) == 4 + n_safe, "安全文明施工费：行区间 1,3..%d（本月该费用共 %d 个仓库）⇒ **无僵尸行**"
        % (4 + n_safe, n_safe))
    chk(sorted(new2) == [1] + list(range(3, 5 + n_safe)),
        "安全文明施工费：行号正好是 1 ＋ 3..%d" % (4 + n_safe))
    # 该月确无该费用 ⇒ 总计行不得有值
    if n_safe == 0:
        chk(num_of(new2[4], "B4") is None,
            "该月确实没有安全文明施工费 ⇒ 总计行**如实为空**（⛔ 不是 0，也不是模板旧值）")
    # 三路一致：源(报表1) ↔ 缓存 ↔ 显示区
    src = [r for r in source_bytes(prod) and [] or []]  # 占位，下面用 openpyxl 直读
    import openpyxl
    wb = openpyxl.load_workbook(out, read_only=True, data_only=True)
    data = [tuple(r) for r in wb["报表1"].iter_rows(values_only=True)][1:]
    wb.close()
    a_by, _ = kcdj_export.aggregate_grid(data, cols, layout["nat2group"])
    b_by, _ = kcdj_export.aggregate_grid(cache_data(out), cols, layout["nat2group"])
    d_by = {}
    for r in range(7, 8 + n_wh):
        lb = label_of(new1, nstrs, "A%d" % r)
        d_by[lb] = {c["letter"]: num_of(new1[r], "%s%d" % (c["letter"], r))
                    for c in cols if num_of(new1[r], "%s%d" % (c["letter"], r)) is not None}
    diff = [(lb, l, a_by.get(lb, {}).get(l), b_by.get(lb, {}).get(l), d_by.get(lb, {}).get(l))
            for lb in set(a_by) | set(b_by)
            for l in {c["letter"] for c in cols}
            if (a_by.get(lb, {}).get(l), b_by.get(lb, {}).get(l), d_by.get(lb, {}).get(l))
            != (None, None, None) and not (
                (a_by.get(lb, {}).get(l) or 0) == (b_by.get(lb, {}).get(l) or 0)
                == (d_by.get(lb, {}).get(l) or 0))]
    chk(not diff, "**三路一致**：报表1(源) == 缓存 == 显示区（差 %d 处 %s）" % (len(diff), diff[:3]))
    chk(label_of(new1, nstrs, "A7") == EXCEL_REF["A7"]
        and num_of(new1[7], "B7") is not None
        and abs(num_of(new1[7], "B7") - EXCEL_REF["B7"]) < 0.01,
        "与 Excel 真机渲染值一致：A7=%s B7=%s（Excel 实测 %s / %s）"
        % (label_of(new1, nstrs, "A7"), num_of(new1[7], "B7"), EXCEL_REF["A7"], EXCEL_REF["B7"]))

    print("\n" + "=" * 78)
    print("⑤ 两个边界样本（各自重跑一次真产物，⛔ 不碰 i8）")
    print("=" * 78)
    import openpyxl
    hdr, base = _rows_of_source(prod)
    # ⑤a 仓库**变少**（7 月→本月只有 2 个仓）⇒ 模板旧行落在新 location **之外**，最易残留
    few = [r for r in base if str(r[18]).strip() in ("安徽国风项目", "内蒙石灰窑项目")]
    o1 = kcdj_export.build_xlsx(_xlsx_of(few, hdr), SCRATCH / "2026年9月")
    a1, s1 = rows_of(o1, "xl/worksheets/sheet1.xml"), strings_of(o1)
    chk(sorted(a1) == list(range(3, 7)) + [7, 8, 9] and max(a1) == 9,
        "仓库只 2 个 ⇒ 过程资料行号 = 3..6 ＋ 7..9（**旧行 10..14 已清掉**，无僵尸行）")
    chk(label_of(a1, s1, "A9") == "总计" and label_of(a1, s1, "A8") == "内蒙石灰窑项目",
        "收缩后标签顺序与明细一致（A8=%s A9=%s）" % (label_of(a1, s1, "A8"), label_of(a1, s1, "A9")))
    chk(not tpl_engine.verify_display(o1, _specs_for(few)), "该样本自身通过显示区对账")
    # ⑤b 该月**确有**安全文明施工费 ⇒ 第二张透视要**真的显示出来**
    #     ⚠️ 安全费**同时**放进「入库×数据组1」与「出库×数据组1」两列 —— 否则「两张透视
    #     共用一套列」这类静默错列会**恰好算对**（实测踩到过：单列样本"侥幸通过"）。
    withsafe = list(base)
    for i, (wh, amt) in enumerate((("安徽国风项目", 111.5), ("内蒙石灰窑项目", 888.5))):
        for d, amt2 in (("入库", amt), ("出库", amt * 2)):
            row = list(hdr)
            row[0], row[2] = "补充%d%s" % (i, d), 9
            row[11], row[15] = "主材", amt2
            row[17], row[18], row[27] = d, wh, kcdj_export.SAFE_CBS
            withsafe.append(tuple(row))
    o2 = kcdj_export.build_xlsx(_xlsx_of(withsafe, hdr), SCRATCH / "2026年9月")
    b2, s2 = rows_of(o2, "xl/worksheets/sheet2.xml"), strings_of(o2)
    chk(sorted(b2) == [1] + list(range(3, 7)),
        "有安全费 ⇒ 安全文明施工费行号 = 1 ＋ 3..6（2 个仓 ＋ 总计），行数随之长出来")
    chk(num_of(b2[4], "B4") == 111.5 * 3 and num_of(b2[5], "B5") == 888.5 * 3
        and num_of(b2[6], "B6") == (111.5 + 888.5) * 3,
        "该费用**两个方向都算进去**了、总计也对：%s / %s / 总计 %s"
        % (num_of(b2[4], "B4"), num_of(b2[5], "B5"), num_of(b2[6], "B6")))
    chk(not tpl_engine.verify_display(o2, _specs_for(withsafe)), "该样本自身通过显示区对账")

    print("\n" + "=" * 78)
    print("④ 反向自检：把新成品的显示区**换回模板旧值** ⇒ 守卫必须报红（这把尺子才有区分力）")
    print("=" * 78)
    caches = SCRATCH / "修前形态_2026年9月.xlsx"
    zin, tplz = zipfile.ZipFile(out), zipfile.ZipFile(TPL)
    with zipfile.ZipFile(caches, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename.startswith("xl/worksheets/") and \
                    item.filename.endswith(("sheet1.xml", "sheet2.xml")):
                zout.writestr(item, tplz.read(item.filename))     # 换回模板旧渲染值 = 修前形态
            else:
                zout.writestr(item, zin.read(item.filename))
    zin.close()
    tplz.close()
    old_problems = tpl_engine.verify_display(str(caches), _specs_for(cache_data(caches)))
    print("  修前形态报出 %d 条：" % len(old_problems))
    for p in old_problems[:6]:
        print("     · %s" % p)
    chk(bool(old_problems), "反向自检：修前形态被**报红**（否则这把尺子是假绿）")
    chk(any("僵尸旧值" in p for p in old_problems),
        "其中包含「显示区之外还有行（僵尸旧值）」—— 正是本片病灶")
    chk(any("vs 缓存重算" in p for p in old_problems),
        "还包含「格子的数与缓存对不上」（模板旧值 vs 本月重算）")

    print("\n" + "=" * 78)
    print("结果：%d 通过 / %d 失败 ｜ 中间产物 %s" % (len(OK), len(BAD), SCRATCH))
    print("=" * 78)
    return 1 if BAD else 0


if __name__ == "__main__":
    sys.exit(main())
