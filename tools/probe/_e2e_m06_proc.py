# -*- coding: utf-8 -*-
"""过程资料成品（`TAIL-04` 路径① 片 4a）—— **真机端到端**（连服务 · 连真 Excel）。

跑什么（只读；本脚本不写库）：
  ① 现读现取一个真项目（候选 = 库存单据 ∪ 历史段里出现过的仓库名）；
  ② `GET /api/m06/export?projects=…&tab=…` 取**三张表各一本** ⇒ **就地从成品复算**：
     · 18 列 / 标题 = `{展示名}材料机械消耗汇总表` / 文件名含**展示名**（用户 2026-09-18 裁）；
     · **R3 列序 = 模板序**（临时设施 在 周转材料 前，清单 §5.3 裁定②）；
     · 数据行：A = 序号 1..N、B = `YYYY-MM` 文本且**数字格式 = 文本**；
     · **小计**（16 列）= 各数据行之和；**合计**（四段锚点）= 该段小计之和；
     · ⭐ **脚注紧跟合计行**、`A??:R??` 两行整宽的合并块在**新位置**、四个段合并格也在；
     · 尾块以下无残留、全表无公式、`UsedRange` 收敛。
  ③ ⭐ **三张表互证**（用户 2026-09-18 裁：三张**形态完全相同**，只有数据不同）：
     **差异表逐格 = 调整后 − 原始**（拿另外两本产物当参照，⛔ 不问实现）。
  ④ **真 Excel 打开**（只有它能暴露"数据下面还空着几行"这类壳）。
  ⑤ 拒做：**一个项目都没选** · 项目**没有数据** · 项目**不在档案里**（取不到展示名）；⑥ ≥2 个项目 ⇒ 一个 zip。

⚠️ 本片最危险的是**尾块 4 行整体下移 ＋ 合并区跟着搬**（引擎的合并区平移在本片**第一次真用上**）——
   实测它当场抓出两处引擎真 bug（见 `docs/reference/template-export.md` §9.7）⇒ 这条 E2E 必须能复跑。
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
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
BASE = "http://127.0.0.1:8000"
SHEET = "汇总表"
SEGMENTS = ((3, 7, 3), (8, 12, 8), (13, 16, 13), (17, 18, 17))     # (起列, 止列, 合计锚点列)，1 基
_ok = _bad = 0


def ck(name, got, want=True):
    global _ok, _bad
    good = got == want
    print(("PASS  " if good else "FAIL  ") + name + ("" if good else f"（实得 {got!r} ≠ {want!r}）"))
    _ok, _bad = _ok + good, _bad + (not good)


def get(url: str):
    with urllib.request.urlopen(BASE + url, timeout=300) as r:
        return r.read(), r.headers.get("content-type", ""), urllib.parse.unquote(
            r.headers.get("x-export-filename", "") or "")


def export(keys, tab, ym=""):
    q = urllib.parse.urlencode({"projects": ",".join(keys), "tab": tab, "ym": ym})
    body, ct, fn = get("/api/m06/export?" + q)
    return (json.loads(body.decode("utf-8")), ct, fn) if "application/json" in ct else (body, ct, fn)


def dec(v):
    return Decimal(str(v)) if v not in (None, "") else Decimal("0")


def check_shape(content: bytes, *, display: str, label: str) -> dict:
    """形态与尾块（**就地从成品复算**）⇒ 返回网格（供三张表互证用）。"""
    wb = openpyxl.load_workbook(io.BytesIO(content))
    try:
        ws = wb[SHEET]
        n = 0
        while str(ws.cell(row=4 + n, column=2).value or "") != "小计":
            n += 1
            if n > 80:
                raise SystemExit(f"{label}: 找不到小计行")
        merges = [str(m) for m in ws.merged_cells.ranges]
        ck(f"{label} 列数 = 18", ws.max_column, 18)
        ck(f"{label} 标题 = 展示名 + 材料机械消耗汇总表", str(ws["A1"].value),
           f"{display}材料机械消耗汇总表")
        ck(f"{label} R3 列序 = 模板序（临时设施 在 周转材料 前）",
           [ws.cell(row=3, column=c).value for c in range(1, 19)][5:7], ["临时设施", "周转材料"])
        ck(f"{label} 序号 = 1..N", [ws.cell(row=4 + i, column=1).value for i in range(n)],
           list(range(1, n + 1)))
        months = [str(ws.cell(row=4 + i, column=2).value) for i in range(n)]
        ck(f"{label} 时间列 = YYYY-MM 文本", all(len(m) == 7 and m[4] == "-" for m in months), True)
        ck(f"{label} 时间列数字格式 = 文本",
           {ws.cell(row=4 + i, column=2).number_format for i in range(n)}, {"@"})
        sub_r, tot_r = 4 + n, 5 + n
        ck(f"{label} 小计行首格", str(ws.cell(row=sub_r, column=2).value), "小计")
        for c in range(3, 19):
            col = sum((dec(ws.cell(row=4 + i, column=c).value) for i in range(n)), Decimal("0"))
            ck(f"{label} 小计 {get_column_letter(c)} = 数据行之和",
               dec(ws.cell(row=sub_r, column=c).value) == col, True)
        ck(f"{label} 合计行首格", str(ws.cell(row=tot_r, column=2).value), "合计：")
        for c1, c2, anchor in SEGMENTS:
            seg = sum((dec(ws.cell(row=sub_r, column=c).value) for c in range(c1, c2 + 1)),
                      Decimal("0"))
            ck(f"{label} 合计 {get_column_letter(anchor)} = 该段小计之和",
               dec(ws.cell(row=tot_r, column=anchor).value) == seg, True)
        ck(f"{label} 脚注紧跟合计行（尾块下移到位）",
           str(ws.cell(row=tot_r + 1, column=1).value or "").startswith("1、材料费用"), True)
        ck(f"{label} 脚注合并块 = 两行整宽",
           any(str(m).startswith(f"A{tot_r + 1}:") and str(m).endswith(f"R{tot_r + 2}")
               for m in merges), True)
        ck(f"{label} 四个段合并格都在合计行",
           all(any(str(m).startswith(f"{get_column_letter(c)}{tot_r}:") for m in merges)
               for _a, _b, c in SEGMENTS), True)
        ck(f"{label} 尾块以下无残留",
           any(ws.cell(row=r, column=c).value is not None
               for r in range(tot_r + 3, ws.max_row + 1) for c in range(1, 19)), False)
        ck(f"{label} 全表无公式",
           any(isinstance(ws.cell(row=r, column=c).value, str)
               and str(ws.cell(row=r, column=c).value).startswith("=")
               for r in range(4, tot_r + 1) for c in range(1, 19)), False)
        return {"n": n, "data": [[dec(ws.cell(row=4 + i, column=c).value) for c in range(3, 19)]
                                 for i in range(n)],
                "months": months, "path_tmp": (content, label)}
    finally:
        wb.close()


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


def main() -> int:  # noqa: C901
    from app.core.db import session_scope
    from app.mod06_proc import domain as D
    from app.mod06_proc import repository as R
    from app.mod06_proc import service as M6

    with session_scope() as s:
        inv = R.load_inv_rows(s)
        cands = M6.projects_of(inv, R.load_history(s))
        displays = M6.displays_by_key(s)
    print("候选项目：", cands)
    if not cands:
        raise SystemExit("库里没有过程资料候选项目 ⇒ 先抓 API-03 库存单据明细")
    # ⭐ 优先挑**有调整单**的项目：那样「差异表 = 调整后 − 原始」才有**真数字**可验
    #    （全是 0 差额时这条只证明口径自洽、证明不了算法 —— 别拿它当强证据）。
    key = max(cands, key=lambda k: len(D.diff_rows(inv, warehouse=k)))
    display = displays.get(key) or ""
    print(f"样本项目：{key} → 展示名 {display!r} · 调整单行数 {len(D.diff_rows(inv, warehouse=key))}\n")
    ck("样本项目在档案里（有展示名）", bool(display), True)

    grids: dict[int, dict] = {}
    for tab, label in ((1, "表②调整后"), (0, "表①原始"), (2, "差异表")):
        content, ct, fn = export([key], tab)
        if isinstance(content, dict):
            ck(f"{label} 能导出", content.get("message"), "（应能导出）")
            continue
        ck(f"{label} 回的是 xlsx", "spreadsheetml" in ct, True)
        ck(f"{label} 文件名含**展示名**", display in fn, True)
        ck(f"{label} 文件名含**表名**（{D.tab_name(tab)}）", D.tab_name(tab) in fn, True)
        print(f"   文件名 = {fn}")
        grids[tab] = check_shape(content, display=display, label=f"[{label}]")

    # ⭐ 三张表互证：差异表逐格 = 调整后 − 原始（拿另两本产物当参照，⛔ 不问实现）
    if {0, 1, 2} <= set(grids):
        a, r, d = grids[1], grids[0], grids[2]
        ck("三张表的月份一致", (a["months"], r["months"]), (d["months"], d["months"]))
        diff_ok = all(a["data"][i][j] - r["data"][i][j] == d["data"][i][j]
                      for i in range(len(d["data"])) for j in range(16))
        ck("⭐ 差异表逐格 = 调整后 − 原始", diff_ok, True)
        if a["data"] == r["data"]:
            print("   （注：本项目本月**没有调整单** ⇒ 三张表数字本来就相同；这条只证明口径自洽，"
                  "⛔ 不能当成「差额算对了」的强证据 —— 强证据要等有调整单的月份）")

    # 真 Excel：只有它能暴露"数据下面还空着几行"这类壳
    if grids:
        tab = 1 if 1 in grids else min(grids)
        tmp = Path(tempfile.gettempdir()) / f"proc_{tab}.xlsx"
        tmp.write_bytes(grids[tab]["path_tmp"][0])
        got = excel_probe(tmp).get(SHEET) or {}
        # 内容行 = 标题 1 ＋ 两级表头 2 ＋ 数据 n ＋ 尾块 4（小计 / 合计 / 脚注×2）
        ck("真 Excel 打开：UsedRange 不多算（无空行壳）", got.get("used"),
           f"A1:R{grids[tab]['n'] + 7}")
        ck("真 Excel：小计 / 合计 / 脚注三行显示正常",
           sum(1 for r in got.get("rows", []) if "小计" in r or "合计" in r or "1、材料费用" in r), 3)

    # 拒做三连
    d, _c, _f = export([], 1)
    ck("一个项目都没选 ⇒ 拒做", isinstance(d, dict) and "一个项目都没选" in d.get("message", ""), True)
    d, _c, _f = export(["查无此仓库"], 1)
    ck("项目没有数据 ⇒ 拒做", isinstance(d, dict) and "没有数据" in d.get("message", ""), True)
    if len(cands) >= 2:
        z, zct, zfn = export(cands[:2], 1)
        ck("两个项目 ⇒ 回 zip", isinstance(z, bytes) and "zip" in zct, True)
        if isinstance(z, bytes):
            with zipfile.ZipFile(io.BytesIO(z)) as zf:
                ck("zip 里两本都在", len(zf.namelist()), 2)
                ck("zip 内文件名含展示名", all(displays.get(k, k) in n for k, n in zip(cands[:2], zf.namelist())), True)
                print("   zip =", zfn, zf.namelist())

    print(f"\n===== {_ok} 通过 / {_bad} 失败 =====")
    return 1 if _bad else 0


if __name__ == "__main__":
    sys.exit(main())
