# -*- coding: utf-8 -*-
"""TAIL-43 一次性取证：模板 / 成品 的「透视显示区」到底长什么样。

只读，不写任何产物。用法：
    backend/.venv/Scripts/python.exe tools/_probe_tail43.py
"""
from __future__ import annotations

import re
import sys
import zipfile
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "backend" / "app" / "resources" / "templates" / "模板_库存单据明细表.xlsx"
PROD = ROOT / "artifacts" / "exports" / "库存单据明细表" / "2026年9月" / "库存单据明细表_2026年9月.xlsx"


def ss(ss_xml: str):
    strs = []
    for si in re.findall(r"<si>(.*?)</si>", ss_xml, re.S):
        ts = re.findall(r"<t[^>]*>([^<]*)</t>", si)
        strs.append(unescape("".join(ts)))
    return strs


def dump_sheet(z, part, strs, limit=40):
    print("\n===== %s =====" % part)
    xml = z.read(part).decode("utf-8")
    (z.read("xl/sharedStrings.xml").decode("utf-8"))
    print("  len=%d" % len(xml))
    for m in re.finditer(r'<row r="(\d+)"([^>]*)>(.*?)</row>', xml, re.S):
        r = m.group(1)
        cells = []
        for cm in re.finditer(r'<c r="([A-Z]+\d+)"([^>]*?)(?:/>|>(.*?)</c>)', m.group(3), re.S):
            ref, attrs, body = cm.group(1), cm.group(2), cm.group(3) or ""
            t = re.search(r't="(\w+)"', attrs)
            v = re.search(r"<v>([^<]*)</v>", body)
            val = v.group(1) if v else ""
            if t and t.group(1) == "s" and val != "":
                val = "#" + val + "=" + strs[int(val)]
            cells.append("%s%s=%s" % (ref, ("(" + t.group(1) + ")") if t else "", val))
        print("  row %-4s %s | %s" % (r, m.group(2)[:60], " ".join(cells)))
        if int(r) > limit:
            print("  ...")
            break


def dump_pivot(z, part):
    print("\n===== %s =====" % part)
    xml = z.read(part).decode("utf-8")
    print(xml)


def main():
    for label, path in (("模板", TPL), ("成品", PROD)):
        print("\n" + "#" * 70)
        print("# %s : %s  (exists=%s)" % (label, path.name, path.exists()))
        print("#" * 70)
        if not path.exists():
            continue
        z = zipfile.ZipFile(path)
        print("\n-- parts --")
        for n in z.namelist():
            if n.startswith("xl/") and (n.endswith(".xml") or n.endswith(".rels")):
                print("   %-55s %7d" % (n, z.getinfo(n).file_size))
        strs = ss(z.read("xl/sharedStrings.xml").decode("utf-8"))
        print("\nsharedStrings: %d 条" % len(strs))
        # 透视所在 sheet：按 pivotTable 的 location ref 找
        for pt in ("xl/pivotTables/pivotTable1.xml", "xl/pivotTables/pivotTable2.xml"):
            if pt in z.namelist():
                x = z.read(pt).decode("utf-8")
                loc = re.search(r'<location ref="([^"]*)"[^>]*/?>', x)
                print("%s location=%s" % (pt, loc.group(1) if loc else "?"))
        for s in ("xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"):
            if s in z.namelist():
                dump_sheet(z, s, strs)
        for pt in ("xl/pivotTables/pivotTable1.xml", "xl/pivotTables/pivotTable2.xml"):
            if pt in z.namelist():
                dump_pivot(z, pt)
        z.close()


if __name__ == "__main__":
    sys.exit(main())
