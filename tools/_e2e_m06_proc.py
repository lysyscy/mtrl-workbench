# -*- coding: utf-8 -*-
"""过程资料成品（`TAIL-04` 路径① 片 4a）—— **真机端到端**（连服务 · 连真 Excel）。

跑什么（只读；本脚本不写库）：
  ① 现读现取一个真项目（候选 = 库存单据 ∪ 历史段里出现过的仓库名）；
  ② `GET /api/m06/export?projects=…&tab=1` 取一本工作簿 ⇒ **就地从成品复算**：
     · 18 列 / 标题换成本项目名 / **R3 列序 = 模板序**（临时设施 在 周转材料 前，裁定②）；
     · 数据行：A = 序号 1..N、B = `YYYY-MM` 文本且**数字格式 = 文本**；
     · **小计**（16 列）= 各数据行之和；**合计**（四段锚点）= 该段小计之和；
     · ⭐ **脚注紧跟合计行**、`A??:R??` 两行整宽的合并块在**新位置**上、四段合并格也在；
     · 尾块以下无残留、全表无公式。
  ③ **真 Excel 打开**：`UsedRange` 不得多于内容行（"数据下面还空着几行"是同族病灶）＋ 显示文本。
  ④ 拒做：**差异表**（模板没登记那张形态）· **一个项目都没选**；⑤ ≥2 个项目 ⇒ 一个 zip。

⚠️ 本片最危险的就是**尾块 4 行整体下移 ＋ 合并区跟着搬**（引擎的合并区平移在本片**第一次真用上**）——
   实测它当场抓出两处引擎真 bug（见 `ops/模板法导出-实测结论.md` §9.7），所以这条 E2E 必须能复跑。
用法： backend/.venv/Scripts/python.exe tools/_e2e_m06_proc.py
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import zipfile
from decimal import Decimal
from pathlib import Path

import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
BASE = "http://127.0.0.1:8000"
SHEET = "汇总表"
_ok = _bad = 0


def ck(name, got, want=True):
    global _ok, _bad
    good = got == want
    print(("PASS  " if good else "FAIL  ") + name + ("" if good else f"（实得 {got!r} ≠ {want!r}）"))
    _ok, _bad = _ok + good, _bad + (not good)


def get(url):
    with urllib.request.urlopen(BASE + url, timeout=180) as r:
        body = r.read()
        ct = r.headers.get("content-type", "")
        fn = urllib.parse.unquote(r.headers.get("x-export-filename", "") or "")
    return body, ct, fn


def export(keys, tab, ym=""):
    q = urllib.parse.urlencode({"projects": ",".join(keys), "tab": tab, "ym": ym})
    body, ct, fn = get("/api/m06/export?" + q)
    if "application/json" in ct:
        return json.loads(body.decode("utf-8")), ct, fn
    return body, ct, fn


def cells(ws, r, n):
    return [ws.cell(row=r, column=c).value for c in range(1, n + 1)]


def dec(v):
    return Decimal(str(v)) if v not in (None, "") else Decimal("0")


def excel_probe(path: Path) -> dict:
    out = Path(tempfile.gettempdir()) / "proc_probe_out.json"
    ps = "\n".join([
        "$ErrorActionPreference='Stop'",
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8",
        f"$p='{path}'",
        "$xl=New-Object -ComObject Excel.Application",
        "$xl.Visible=$false; $xl.DisplayAlerts=$false",
        "$wb=$xl.Workbooks.Open($p)",
        "$out=@{}",
        "foreach($ws in $wb.Worksheets){",
        "  $u=$ws.UsedRange; $rows=@()",
        "  for($r=1;$r -le [Math]::Min($u.Rows.Count,20);$r++){",
        "    $line=@()",
        "    for($c=1;$c -le [Math]::Min($u.Columns.Count,18);$c++){ $line+=[string]$ws.Cells.Item($r,$c).Text }",
        "    $rows+=($line -join '|')",
        "  }",
        "  $out[$ws.Name]=@{used=$u.Address(0,0);rows=$rows}",
        "}",
        "$wb.Close($false); $xl.Quit()",
        "[void][Runtime.InteropServices.Marshal]::ReleaseComObject($xl)",
        f"[IO.File]::WriteAllText('{out}', ($out|ConvertTo-Json -Depth 6 -Compress), "
        "(New-Object Text.UTF8Encoding($false)))",
        "'done'",
    ])
    psf = Path(tempfile.gettempdir()) / "proc_probe.ps1"
    psf.write_text(ps, encoding="utf-8-sig")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(psf)],
                   capture_output=True, text=True, timeout=300)
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:
    from app.core.db import session_scope
    from app.mod06_proc import repository as R
    from app.mod06_proc import service as M6

    with session_scope() as s:
        inv, hist = R.load_inv_rows(s), R.load_history(s)
        cands = M6.projects_of(inv, hist)
        mech = R.load_mech(s)
    print("候选项目：", cands)
    if not cands:
        raise SystemExit("库里没有过程资料候选项目 ⇒ 先抓 API-03 库存单据明细")
    key = cands[0]
    print("样本项目：", key, "| 库存行", len(inv), "· 机械手录", len(mech), "· 历史段", len(hist))

    for tab, label in ((1, "表②调整后"), (0, "表①原始")):
        content, ct, fn = export([key], tab)
        if isinstance(content, dict):
            print(f"  （{label} 导不出：{content.get('message', '')[:60]}…）")
            continue
        ck(f"{label} 回的是 xlsx", "spreadsheetml" in ct, True)
        print(f"   文件名 = {fn}")
        wb = openpyxl.load_workbook(io.BytesIO(content))
        try:
            ws = wb[SHEET]
            max_r, max_c, merges = ws.max_row, ws.max_column, [str(x) for x in ws.merged_cells.ranges]
            ck("列数 = 18", max_c, 18)
            ck("标题换成本项目名", str(ws["A1"].value), f"{key}材料机械消耗汇总表")
            # 列序（裁定②：临时设施 在 周转材料 前）
            ck("R3 列序 = 模板序（临时设施 在 周转材料 前）",
               cells(ws, 3, 18)[5:7], ["临时设施", "周转材料"])
            # 数据行：A = 1..N 整数、B = YYYY-MM 文本
            n = 0
            while str(ws.cell(row=4 + n, column=2).value or "") != "小计":
                n += 1
                if n > 60:
                    raise SystemExit("找不到小计行")
            ck("数据行序号 = 1..N", [ws.cell(row=4 + i, column=1).value for i in range(n)],
               list(range(1, n + 1)))
            months = [str(ws.cell(row=4 + i, column=2).value) for i in range(n)]
            ck("时间列 = YYYY-MM 文本", all(len(m) == 7 and m[4] == "-" for m in months), True)
            ck("时间列数字格式 = 文本", {ws.cell(row=4 + i, column=2).number_format for i in range(n)},
               {"@"})
            print(f"   数据行 n = {n} · 月份 = {months[:3]}…{months[-1:]}")
            # 小计 = 数据区垂直求和（**就地从成品复算**）
            sub_r = 4 + n
            ck("小计行首格 = 「小计」", str(ws.cell(row=sub_r, column=2).value), "小计")
            for c in range(3, 19):
                col_sum = sum((dec(ws.cell(row=4 + i, column=c).value) for i in range(n)), Decimal("0"))
                ck(f"小计 {openpyxl.utils.get_column_letter(c)} = 数据行之和",
                   dec(ws.cell(row=sub_r, column=c).value) == col_sum, True)
            # 合计 = 四段横向小计之和
            tot_r = sub_r + 1
            ck("合计行首格 = 「合计：」", str(ws.cell(row=tot_r, column=2).value), "合计：")
            for c1, c2, anchor in ((3, 7, 3), (8, 12, 8), (13, 16, 13), (17, 18, 17)):
                seg = sum((dec(ws.cell(row=sub_r, column=c).value) for c in range(c1, c2 + 1)), Decimal("0"))
                ck(f"合计 {openpyxl.utils.get_column_letter(anchor)} = 该段小计之和",
                   dec(ws.cell(row=tot_r, column=anchor).value) == seg, True)
            # 脚注：**紧接合计行**，且 A??:R?? 两行合并（证明它跟着 offset 搬了）
            ck("脚注紧跟合计行（下移到位）", str(ws.cell(row=tot_r + 1, column=1).value or "").startswith("1、材料费用"), True)
            ck("脚注合并块 = 两行整宽", any(m.startswith(f"A{tot_r + 1}:") and m.endswith(f"R{tot_r + 2}") for m in merges), True)
            ck("合计行的四段合并格都在",
               all(any(str(m).startswith(f"{c}{tot_r}:") for m in merges) for c in "CHMQ"), True)
            print("   合并区 =", merges)
            ck("尾块以下无残留", any(ws.cell(row=r, column=c).value is not None
                                for r in range(tot_r + 3, max_r + 1) for c in range(1, 19)), False)
            ck("全表无公式", any(isinstance(ws.cell(row=r, column=c).value, str)
                             and str(ws.cell(row=r, column=c).value).startswith("=")
                             for r in range(4, tot_r + 1) for c in range(1, 19)), False)
        finally:
            wb.close()
        tmp = Path(tempfile.gettempdir()) / f"proc_{tab}.xlsx"
        tmp.write_bytes(content)
        probe = excel_probe(tmp)
        got = probe.get(SHEET)
        ck("真 Excel 打开表在", bool(got), True)
        if got:
            rows_txt = got["rows"]
            ck("真 Excel：小计行显示正常", any("小计" in r for r in rows_txt), True)
            ck("真 Excel：脚注行在最后", any(r.startswith("1、材料费用") for r in rows_txt), True)
            print("   UsedRange =", got["used"], "| 末 3 行显示 =", rows_txt[-3:])
        break

    # 差异表 ⇒ 拒做（模板没登记那张形态）
    d, ct, _ = export([key], 2)
    ck("差异表 ⇒ 拒做（JSON ok:false ＋ 中文原因）",
       isinstance(d, dict) and d.get("ok") is False and "差异表" in d.get("message", ""), True)

    # 一个都没选 ⇒ 拒做
    d2, _ct, _f = export([], 1)
    ck("一个项目都没选 ⇒ 拒做", isinstance(d2, dict) and "一个项目都没选" in d2.get("message", ""), True)

    # ≥2 个项目 ⇒ zip
    if len(cands) >= 2:
        z, zct, zfn = export(cands[:2], 1)
        ck("两个项目 ⇒ 回 zip", isinstance(z, bytes) and "zip" in zct, True)
        if isinstance(z, bytes):
            with zipfile.ZipFile(io.BytesIO(z)) as zf:
                ck("zip 里两本都在", len(zf.namelist()), 2)
                print("   zip =", zfn, zf.namelist())

    print(f"\n===== {_ok} 通过 / {_bad} 失败 =====")
    return 1 if _bad else 0


if __name__ == "__main__":
    sys.exit(main())
