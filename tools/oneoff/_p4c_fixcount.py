#!/usr/bin/env python
"""`TAIL-64` **P4-c 前哨**：把「口径说明 · N 条」里**手抄的 N** 改成**数出来的**（2026-09-30）。

**为什么必须先做它**（`P4-c` 还没定"哪些算"，但这一处**不是口径问题、是错数字**）：
`tools/oneoff/_p4cd_survey.py` 量出 **`m02` 那一块屏幕写着「口径说明 · 6 条」，实际有 7 个 `<li>`**
（⚠️ **原型那侧同样错** —— 同一位点、同样 6/7）⇒ 用户在屏幕上读到的是一个**假的条数**
（守则 §4.2「状态必须真实」· §2.6「能算出来的别让人自己数」）。
⇒ 本件**只改那一个数字**（⛔ 不删不改任何一条口径），并让 `P4-c` 去负责把它**变成算出来的**。

⚠️ **靶必须按块定位**：`<details class="tip"><summary>口径说明 · 6 条 …` 这**一整行在 4 个页上逐字相同**
（`m01`/`m02`/`m09`/`m11`）⇒ ⛔ 用"替换第一处/全文替换"必错（本仓老课：`V.m10`/`V.m14` 那次）。
⇒ 本件**逐块**数 `<li>`、**只改对不上的那几块**，并断言"改的块数 == 预期"。

用法：`python tools/oneoff/_p4c_fixcount.py`（干跑）· `… --write`（落盘 · 原型改前先备份）
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import argparse
import pathlib
import re
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHELL = ROOT / "backend" / "app" / "web" / "index.html"
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")
BACKUPS = ROOT / _run_dir() / "delivery-backups"

HEAD = '<details class="tip"><summary>口径说明 · '
BLOCK = re.compile(r'<details class="tip"><summary>口径说明 · (\d+) 条')
NL = "\r\n"


def patches(text: str, path: pathlib.Path) -> list[tuple[int, int, str]]:
    """返回 `[(改前数字区间起, 终, 新数字)]` —— 只收"声明 ≠ 实际 `<li>` 数"的那些块。"""
    out: list[tuple[int, int, str]] = []
    for m in BLOCK.finditer(text):
        seg = text[m.start(): m.start() + 4000]
        end = seg.find("</details>")
        seg = seg[:end if end > 0 else len(seg)]
        real = str(len(re.findall(r"<li>", seg)))
        if real != m.group(1):
            out.append((m.start(1), m.end(1), real))
            print(f"  ⚠️ {path.name}：声明 {m.group(1)} 条 ⇒ 实际 {real} 条（第 "
                  f"{text.count(chr(10), 0, m.start()) + 1} 行）")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    shell = SHELL.read_text(encoding="utf-8").replace("\r\n", "\n")
    proto = PROTO.read_text(encoding="utf-8").replace("\r\n", "\n")
    ps, pp = patches(shell, SHELL), patches(proto, PROTO)
    print(f"⇒ 壳 {len(ps)} 块 · 原型 {len(pp)} 块需要订正")
    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    dst = BACKUPS / "原型-备份-20260930-P4c前哨.html"
    if not dst.exists():
        shutil.copy2(PROTO, dst)
        print(f"  ✅ 备份原型 ⇒ {dst.relative_to(ROOT)}")

    def apply(text: str, items: list[tuple[int, int, str]]) -> str:
        for a, b, new in sorted(items, key=lambda x: -x[0]):
            text = text[:a] + new + text[b:]
        return text

    for p, text, items in ((SHELL, shell, ps), (PROTO, proto, pp)):
        if not items:
            continue
        out = apply(text, items)
        assert len(out.split("\n")) == len(text.split("\n")), f"⛔ {p.name} 行数变了"
        p.write_text(out.replace("\n", NL), encoding="utf-8", newline="")
        assert p.read_text(encoding="utf-8") == out, f"⛔ {p.name} 写回自校验不过"
        print(f"  ✅ {p.name}：订正 {len(items)} 块（行数 Δ0）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
