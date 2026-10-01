#!/usr/bin/env python
"""`TAIL-68` **反向灵敏度**：证明 `tests/test_export_save.py` 真有区分力。

| 变异 | 怎么改 | 期望（必须变红） |
|---|---|---|
| A · 落盘件**不再建目录** | 删掉 `p.parent.mkdir(parents=True, exist_ok=True)` | `test_落盘到不存在的多级目录也要成功` ＋ `test_总欠款导出走落盘件_且文件名按口径` |
| B · 塞回一处**裸 `wb.save(`** | `save_workbook(wb, out_path)` ⇒ `wb.save(out_path)`（`setl_export` 当年的形态） | `test_落盘出口只剩一个`（静态扫描） |

跑法：`backend/.venv/Scripts/python.exe tools/_mut_save.py`（rc=0 = 两处都抓到且**逐字节复原**）。
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
BACKEND = ROOT / "backend"
APP = BACKEND / "app"
#: ⚠️ 2026-10-01（`TAIL-204` 第 7 步）换落点：原 `.workbuddy/scratch` 那个根已不存在（+ 下面 `mkdir` ⇒ 复活旧根）。
BAK = ROOT / ".codebuddy" / "work" / "00-scratch"
BAK.mkdir(parents=True, exist_ok=True)
PY = BACKEND / ".venv" / "Scripts" / "python.exe"
TEST = "tests/test_export_save.py"

SAVE = APP / "report_export" / "save.py"
SETL = APP / "report_export" / "setl_export.py"

MUTS = [
    ("A · 落盘件不再建目录", SAVE,
     "    p = Path(out)\n    p.parent.mkdir(parents=True, exist_ok=True)\n    wb.save(str(p))",
     "    p = Path(out)\n    wb.save(str(p))   # 变异A：mkdir 被摘掉",
     None),                                   # 整支测试跑
    ("B · 塞回裸 wb.save(", SETL,
     "    save_workbook(wb, out_path)",
     "    wb.save(out_path)   # 变异B：退回「不带 mkdir 的裸落盘」",
     "test_落盘出口只剩一个"),
]


def run(node: str | None = None) -> int:
    cmd = [str(PY), "-m", "pytest", "-q", TEST if node is None else f"{TEST}::{node}",
           "-p", "no:cacheprovider", "--tb=no"]
    return subprocess.run(cmd, cwd=str(BACKEND), capture_output=True, text=True,
                          encoding="utf-8", errors="replace").returncode


def main() -> int:
    paths = {SAVE, SETL}
    origs = {p: p.read_bytes() for p in paths}
    for p in origs:
        shutil.copy2(p, BAK / (p.name + ".bak-mutsave"))
    h0 = {p: hashlib.md5(b).hexdigest() for p, b in origs.items()}
    rc = 0
    try:
        base = run()
        print(f"基线：pytest {TEST} ⇒ rc={base}（应为 0）")
        if base != 0:
            print("❌ 基线就是红的 ⇒ 先修测试再谈变异")
            return 1
        for label, path, old, new, node in MUTS:
            raw = origs[path]
            nl = "\r\n" if b"\r\n" in raw else "\n"
            # ⚠️ 用 bytes.decode() **不转换换行** ⇒ CRLF 文件里 `\n` 锚点永远匹配不上
            #    （本仓纪律：工作区 CRLF）⇒ 先归一到 \n 匹配，写回时**还原原行尾**。
            t = raw.decode("utf-8").replace("\r\n", "\n")
            if old not in t:
                print(f"❌ {label}：找不到锚点（代码改过 ⇒ 本脚本要同步改）")
                return 1
            path.write_bytes(t.replace(old, new, 1).replace("\n", nl).encode("utf-8"))
            m = run(node)
            ok = m != 0
            print(f"{label}：{node or '整支'} ⇒ rc={m} {'✅ 抓到' if ok else '❌ 没抓到（假绿！）'}")
            rc = rc if ok else 1
            path.write_bytes(origs[path])
    finally:
        for p, b in origs.items():
            p.write_bytes(b)
    same = all(hashlib.md5(p.read_bytes()).hexdigest() == h for p, h in h0.items())
    print(f"复原：MD5 {'一致 ✅' if same else '❌ 不一致'}")
    if same:
        for p in origs:
            (BAK / (p.name + ".bak-mutsave")).unlink(missing_ok=True)
    return rc if same else 1


if __name__ == "__main__":
    sys.exit(main())
