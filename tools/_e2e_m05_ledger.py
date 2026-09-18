# -*- coding: utf-8 -*-
"""台账成品（`TAIL-04` 片 2＋3）—— **真机端到端**（连服务 · 连真 Excel）。

跑什么（**只读**：本脚本不写库）：
  ① 现读现取一个**真项目**（候选键 = 仓库名，来自 `/api/m09/fee` 的候选 —— 它就是档案里的键）；
  ② `GET /api/m05/ledger/export` 取**一本工作簿** ⇒ 逐 sheet 核对：
     · 三个 sheet 齐（`辅材` / `机械` / `特殊费用月报表`）；
     · 标题 = **展示名 ＋ 模板后缀**（⛔ 不许留着模板里"别的项目名"）；
     · 台账尾块 = 「合计：」＋ 三列金额 = **各数据行之和**（独立复算）；
     · 特殊费用月报表 = **3 列**（压成一列），表头 = `<M>月份`；
     · **零残留**（模板示例项目名一格不得留）。
  ③ 选 **2 个项目** ⇒ 必须打成一个 **zip**，内含两本工作簿；
  ④ ⭐ **用真 Excel 打开**（COM）读**显示文本** —— 只有真 Excel 才能暴露"要修复"，
     也才能看出「月份」列有没有被**按日期显示**（`清单 §四-4` 那条裁定的一半就在这儿）。

⚠️ 「几个月才有一个有数据」是常态：脚本按 `ym` 候选依次试，**全部失败 ⇒ 如实报出后端的理由**（不算脚本失败）。
用法： backend/.venv/Scripts/python.exe tools/_e2e_m05_ledger.py
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

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8000"
SHEETS = ["辅材", "机械", "特殊费用月报表"]
YM_TRY = ["", "2026-09", "2026-08", "2026-07", "2026-06"]

_ok = _bad = 0


def ck(name: str, got, want=True) -> None:
    global _ok, _bad
    good = (got == want)
    print(("PASS  " if good else "FAIL  ") + name + ("" if good else f"（实得 {got!r}，期望 {want!r}）"))
    _ok, _bad = _ok + good, _bad + (not good)


def get_json(path: str) -> dict:
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def export(projects: list[str], ym: str = "") -> tuple[bytes | dict, str, str]:
    """→ `(内容, content-type, 文件名)`；失败时第一个元素 = 后端给的 JSON dict。"""
    url = f"{BASE}/api/m05/ledger/export?" + urllib.parse.urlencode(
        {"projects": ",".join(projects), "ym": ym})
    with urllib.request.urlopen(url, timeout=180) as r:
        body = r.read()
        ct = r.headers.get("content-type", "")
        fn = urllib.parse.unquote(r.headers.get("x-export-filename", "") or "")
    if "application/json" in ct:
        return json.loads(body.decode("utf-8")), ct, fn
    return body, ct, fn


def rows_of(content: bytes, sheet: str) -> list[list]:
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    try:
        ws = wb[sheet]
        return [[ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
                for r in range(1, ws.max_row + 1)]
    finally:
        wb.close()


def dec(v) -> Decimal:
    return Decimal(str(v)) if v not in (None, "") else Decimal("0")


def excel_probe(path: Path, sheets: list[str]) -> dict:
    """⭐ **用真 Excel 打开**逐 sheet 读**显示文本**（前若干行 × 前若干列）＋ `UsedRange`。

    ⚠️ ps1 **必须带 BOM 写**（`utf-8-sig`）—— PowerShell 5.1 按 ANSI 读无 BOM 的脚本，
       sheet 名里的中文会乱码 ⇒ 拿不到表。
    """
    out = Path(tempfile.gettempdir()) / "ledger_probe_out.json"
    ps = "\n".join([
        "$ErrorActionPreference='Stop'",
        "[Console]::OutputEncoding=[Text.Encoding]::UTF8",
        f"$p='{path}'",
        "$xl=New-Object -ComObject Excel.Application",
        "$xl.Visible=$false; $xl.DisplayAlerts=$false",
        "$wb=$xl.Workbooks.Open($p)",
        "$out=@{}",
        "foreach($ws in $wb.Worksheets){",
        "  $u=$ws.UsedRange",
        "  $rows=@()",
        "  for($r=1;$r -le [Math]::Min($u.Rows.Count,10);$r++){",
        "    $line=@()",
        "    for($c=1;$c -le [Math]::Min($u.Columns.Count,7);$c++){ $line+=[string]$ws.Cells.Item($r,$c).Text }",
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
    psf = Path(tempfile.gettempdir()) / "ledger_probe.ps1"
    psf.write_text(ps, encoding="utf-8-sig")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(psf)],
                   capture_output=True, text=True, timeout=240)
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:  # noqa: C901
    cands = (get_json("/api/m09/fee") or {}).get("projects") or []
    if len(cands) < 2:
        raise SystemExit("档案里的项目不足 2 个 ⇒ 真机验证做不了（先建档）")
    key_a, disp_a = cands[0]["key"], cands[0]["display"]
    key_b = cands[1]["key"]
    print(f"样本（现读现取）：项目 {disp_a}（{key_a}）· 备选 {key_b}\n")

    # ② 一本工作簿（按 ym 候选试，直到某个月**导得出且台账有数据行** —— 否则月份列没有样本可查）
    chosen, content, fn = "", None, ""
    for ym in YM_TRY:
        got, ct, got_fn = export([key_a], ym)
        if isinstance(got, dict):
            print(f"  （ym={ym or '默认'} 导不出：{got.get('message', '')[:70]}…）")
            continue
        if not any(len(rows_of(got, s)) > 3 for s in ("辅材", "机械")):
            print(f"  （ym={ym or '默认'} 导得出，但两个口径都**没有台账数据行** ⇒ 换一个月取样本）")
            continue
        chosen, content, fn = ym, got, got_fn
        ck("导出回的是 xlsx", "spreadsheetml" in ct, True)
        break
    if chosen == "" and isinstance(content, dict):
        print("\n⚠️ 试过的报告月都没数据 —— 后端如实给了理由（脚本不算失败）；"
              "先抓一期通知书 / 库存单据再来。")
        return 0
    print(f"报告月 = {chosen or '默认'} · 文件名 = {fn}\n")

    # 结构：三个 sheet 齐 ＋ 标题替换 ＋ 单月列
    wb = openpyxl.load_workbook(io.BytesIO(content))
    try:
        names = wb.sheetnames
    finally:
        wb.close()
    ck("三个 sheet 齐（一本工作簿）", names, SHEETS)
    for sheet, suffix in zip(SHEETS, ["辅材欠款", "机械费欠款", "费用汇总表"]):
        ck(f"[{sheet}] 标题 = 展示名＋后缀", str(rows_of(content, sheet)[0][0]), f"{disp_a}{suffix}")
    ck("特殊费用月报表压成一列（3 列）", len(rows_of(content, "特殊费用月报表")[0]), 3)

    # 台账尾块 = 各数据行之和（独立复算：直接对成品的**数据区**求和）
    for sheet in ("辅材", "机械"):
        rows = rows_of(content, sheet)
        data = rows[2:-1]
        tail = rows[-1]
        ck(f"[{sheet}] 尾块首格 = 「合计：」", str(tail[1] or ""), "合计：")
        for i, col in ((2, "其他支出金额"), (3, "付款"), (4, "欠款")):
            ck(f"[{sheet}] 合计 {col} = 各数据行之和",
               dec(tail[i]) == sum((dec(r[i]) for r in data), Decimal("0")), True)
        ck(f"[{sheet}] 尾块紧随数据行（下面不留行）", len(rows), 2 + len(data) + 1)

    # 零残留：模板里的示例项目名一格不许留
    hits = [(s, str(v)) for s in SHEETS for row in rows_of(content, s) for v in row
            if "龙源纸业" in str(v or "")]
    ck("模板示例数据一格不留", hits, [])

    # ④ 真 Excel：打开（会不会要"修复"）＋ 显示文本（月份列有没有被按日期显示）
    tmp = Path(tempfile.gettempdir()) / "ledger_real.xlsx"
    tmp.write_bytes(content if isinstance(content, bytes) else b"")
    probe = excel_probe(tmp, SHEETS)
    ck("真 Excel 打开：三个 sheet 都在", sorted(probe.keys()), sorted(SHEETS))
    for sheet in SHEETS:
        used = probe[sheet]["used"]
        ck(f"[{sheet}] UsedRange 形状正常", bool(used) and used.startswith("A1:"), True)
    # 月份列只在**数据行**里取（末行是「合计：」尾块 —— 上一版把尾块当样本读，误报了一次）
    month_cells = []
    for sheet in ("辅材", "机械"):
        for row in probe[sheet]["rows"][2:-1]:
            part = row.split("|")
            if len(part) > 1 and part[1].strip():
                month_cells.append(part[1].strip())
    ck("月份列有样本可查（报告月那一行）", bool(month_cells), True)
    ck("⭐ 真 Excel 里「月份」显示为文本（没被按日期吃掉）",
       all(("截止" in m) or ("-" in m) for m in month_cells), True)
    print("     月份列显示 =", month_cells)
    print("     特殊费用月报表表头 =", probe["特殊费用月报表"]["rows"][1])

    # ③ ≥2 个项目 ⇒ 一个 zip
    zcontent, zct, zfn = export([key_a, key_b], chosen)
    ck("两个项目 ⇒ 回的是 zip", isinstance(zcontent, bytes) and "zip" in zct, True)
    if isinstance(zcontent, bytes):
        with zipfile.ZipFile(io.BytesIO(zcontent)) as zf:
            ck("zip 里两本工作簿都在", len(zf.namelist()), 2)
            print("     zip 内容 =", zf.namelist())

    print(f"\n===== {_ok} 通过 / {_bad} 失败 =====")
    return 1 if _bad else 0


if __name__ == "__main__":
    sys.exit(main())
