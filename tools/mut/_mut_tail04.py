# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）—— `TAIL-04` 导出切片的断言 **是否真有区分力**。

做法：把实现**故意改坏**若干处，确认**对应断言确实变红**；每次立刻按 bytes 复原，最后核对 MD5。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_tail04.py`

⚠️ 本仓纪律（memory §十七）：bytes 写入 / 中文片段用 `str+.encode()` / 行尾按目标文件归一 /
变异点必须唯一命中 / 跑完必须再跑一次全套 `pytest`。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH, pick  # noqa: E402  ← `P4`① 读取点收敛

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
FILES = {
    "shell": SHELL_PATH,
    "api": ROOT / "backend" / "app" / "mod07_setl" / "api.py",
    "domain": ROOT / "backend" / "app" / "mod07_setl" / "domain.py",
    "res": ROOT / "backend" / "app" / "report_export" / "resources.py",
    "setl": ROOT / "backend" / "app" / "report_export" / "setl_export.py",
    "svc": ROOT / "backend" / "app" / "report_export" / "service.py",
}

T_NAME = "test_成品名只有一处主人且与实际产出逐字一致"
T_GATE = "test_模板闸门缺失或损坏时显式报错"
T_FAIL = "test_三种失败都不产出文件且带回中文原因"
T_WIRE = "test_壳侧导出按钮已接线且按content_type分流"
T_102 = "test_导出文件名随期间变且不硬编码月份"
T_108 = "test_产出物为分仓库工作簿加总表且份数随仓数实时算"

MUTATIONS: list[tuple[str, str, str, str, str]] = [
    # ---- 001-02 · 文件名随期间变、不硬编码
    ("zip 名硬编码成某个月",
     "domain", '    return f"{ORG_NAME}{period_label(ym)}收发结存表.zip"',
     '    return f"{ORG_NAME}2026年9月收发结存表.zip"', T_102),
    ("期间标签不再转换（直接拿 YYYY-MM 当标签）",
     "domain", '        return f"{int(s[:4])}年{int(s[5:])}月"', "        return s", T_102),
    ("导出端点不读 period（永远导默认月）",
     "api", '    period = str(request.query_params.get("period") or "").strip() or default_month()',
     "    period = default_month()", T_102),
    # ---- 成品名只有一处主人
    ("总表名与 zip 名两套写法（一处用原始期间）",
     "domain", 'def total_workbook_name(ym: str) -> str:\n    return f"{ORG_NAME}{period_label(ym)}收发结存表.xlsx"',
     'def total_workbook_name(ym: str) -> str:\n    return f"{ORG_NAME}{ym}收发结存表.xlsx"', T_NAME),
    # ---- 模板闸门
    ("模板缺失不再拦（静默产出空文件）",
     "res", "    if not p.exists():", "    if False:", T_GATE),
    ("模板内容不符（被回退/损坏）不再拦",
     "res", "        if got != want:", "        if False:", T_GATE),
    # ---- 三种失败必须拒
    ("空数据不再拒（会产出空成品冒充交付）",
     "setl", "    if df.empty:", "    if False:", T_FAIL),
    ("期间格式不再校验（会去导一个不存在的月）",
     "svc", '    if len(ym) != 7 or ym[4] != "-" or not (ym[:4].isdigit() and ym[5:].isdigit()):',
     "    if False:", T_FAIL),
    ("失败不再回 `ok:false`（壳分不出流）",
     "api", '        return JSONResponse(status_code=200, content={"ok": False, "message": str(exc)})',
     '        return JSONResponse(status_code=400, content={})', T_WIRE),
    # ---- 壳侧真下载
    ("壳侧不再按 content-type 分流（JSON 当文件下）",
     "shell", "   if(ct.includes('application/json')){", "   if(false){", T_WIRE),
    # ---- 001-08 现在钉的是「清单 == 真产出」
    ("产出物少一个分仓库文件（清单说 3 个、实际给 2 个）",
     "setl", "    for wh in show_order:\n        sub = df[df['仓库'] == wh].copy()",
     "    for wh in show_order[:1]:\n        sub = df[df['仓库'] == wh].copy()", T_108),
]


def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


def main() -> int:
    orig = {k: p.read_bytes() for k, p in FILES.items()}
    md5_before = {k: hashlib.md5(v).hexdigest() for k, v in orig.items()}
    for k, v in orig.items():
        print(f"{k}: {len(v)} 字节 · MD5 {md5_before[k][:12]}")

    hit = miss = 0
    for i, (label, fkey, old, new, test_name) in enumerate(MUTATIONS, 1):
        # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳是多件 ⇒ 锚点在哪件就改哪件（⛔ 仍逐字节复原）。
        #    ⚠️ 判断基准一律用**原始** `SHELL_PATH`：`FILES["shell"]` 已被上一条改成别的件，
        #    拿它当基准会**累积失效**（实测：第 6 条起全 SKIP）。
        if fkey == "shell":
            FILES["shell"] = pick(SHELL_PATH, old, new)
            orig["shell"] = FILES["shell"].read_bytes()
            md5_before["shell"] = hashlib.md5(FILES["shell"].read_bytes()).hexdigest()
        target = orig[fkey]
        o = _fit(old.encode("utf-8"), target)
        n = _fit(new.encode("utf-8"), target)
        cnt = target.count(o)
        if cnt != 1:
            print(f"  {i:2d}. ⚠️ SKIP（变异点命中 {cnt} 次）—— [{fkey}] {label}")
            miss += 1
            continue
        FILES[fkey].write_bytes(target.replace(o, n))
        r = subprocess.run(
            [str(PY), "-m", "pytest", "-q", "-k", test_name, "tests/"],
            cwd=ROOT / "backend", capture_output=True, text=True,
        )
        bad = r.returncode != 0
        print(f"  {i:2d}. {'✅ 变红' if bad else '⛔ 仍绿（假绿！）'} —— [{fkey}] {label}  [{test_name}]")
        if bad:
            hit += 1
        FILES[fkey].write_bytes(target)

    md5_after = {k: hashlib.md5(p.read_bytes()).hexdigest() for k, p in FILES.items()}
    ok_md5 = all(md5_after[k] == md5_before[k] for k in FILES)
    print(f"\n命中 {hit}/{len(MUTATIONS) - miss} · SKIP {miss} · "
          f"MD5 {'逐字节复原 ✅' if ok_md5 else '⛔ 不一致'}")

    print("重跑全套 pytest（复原态）…")
    full = subprocess.run([str(PY), "-m", "pytest", "-q", "tests/"],
                          cwd=ROOT / "backend", capture_output=True, text=True)
    print("  全套 pytest 退出码 =", full.returncode)
    return 0 if (ok_md5 and miss == 0 and hit == len(MUTATIONS) and full.returncode == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
