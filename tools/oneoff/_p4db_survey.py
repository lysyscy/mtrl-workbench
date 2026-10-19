#!/usr/bin/env python
r"""`TAIL-64` **`P4-d-b`** 铺量前的**只读量测**（2026-09-30 · ⛔ 不改任何文件）。

**为什么要它**：`_p4d_pjb.py` 的干跑只报出 **9 处**（且原型 **0 处**），与施工图 §8.7 的
「`pjwrap` 12 处」对不上 ⇒ 那件脚本的开标签正则**只覆盖了一种写法**（壳侧带 `--fscale` 的那种）。
⇒ 照"**以干跑打印的命中清单为准**"（§8.8 末条）之前，**先把"到底有哪几枚"量准**。

**它量什么**（壳全部件 ＋ 仓外原型，逐枚列原文）：
- 每一枚「带 `▼` 的项目选择按钮」：所在件 / `act` / **完整原文**（缩进与换行原样）；
- 两侧的**形态差**（壳 `gap:calc(8px * var(--fscale))` vs 原型 `gap:8px`）—— 这决定了
  「哪些能双边同步、哪些只能只改壳」（§8.8 的第 1 条）。

用法：`python tools/oneoff/_p4db_survey.py`
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web"
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")

#: 一枚按钮 = `<button …>…</button>`（单行或跨行；⛔ 里面不会有嵌套按钮）
BTN = re.compile(r"<button\b[^>]*data-act=\"(\w+)\"[^>]*>.*?</button>", re.S)


def survey(label: str, targets: list[pathlib.Path]) -> dict[str, list[tuple[str, str]]]:
    print("=" * 78)
    print(f" {label}")
    print("=" * 78)
    out: dict[str, list[tuple[str, str]]] = {}
    for p in targets:
        txt = p.read_text(encoding="utf-8").replace("\r\n", "\n")
        hits = [(m.group(1), m.group(0)) for m in BTN.finditer(txt) if "▼" in m.group(0)]
        out[p.name] = hits
        if hits:
            print(f"  · {p.name:<16} {len(hits)} 枚 —— {[a for a, _ in hits]}")
        else:
            print(f"  · {p.name:<16} 0 枚")
    total = sum(len(v) for v in out.values())
    print(f"  ⇒ 合计 **{total}** 枚\n")
    return out


def main() -> int:
    shell_parts = [WEB / "index.html"] + sorted((WEB / "shell").glob("*.js"))
    sh = survey("壳侧（`index.html` ＋ `shell/*.js`）", shell_parts)
    pr = survey("仓外原型（`demo/材料报表自动化工作台-交互原型.html`）",
                [PROTO] if PROTO.exists() else [])
    if not PROTO.exists():
        print("  ⛔ 原型文件不在预期位置 —— 先核对路径\n")

    # ── 形态差（紧凑表 · 决定"能不能双边同步"）：class / style / title / 标签
    print("=" * 78)
    print(" 逐枚形态（壳 ⇄ 原型 · ⛔ 只读）")
    print("=" * 78)
    for tag, src in (("壳", sh), ("原", pr)):
        for name, hits in src.items():
            for act, s in hits:
                one = " ".join(s.split())
                has_dyn_cls = "{{" in one.split("style=")[0] and "${" in one.split('data-act="')[1].split(">")[0]
                cm = re.search(r'^<button class="([^"]*)"', one)
                sm = re.search(r'style="([^"]*)"', one)
                tm = re.search(r'title="([^"]{0,40})', one)
                dyn = ("${" in one.split("data-act=")[1].split(">")[0])
                print(f"  {tag} {name:<14} {act:<18} cls={cm.group(1) if cm else '?':<28}"
                      f" dyn_attr={str(dyn):<5} title={'有' if tm else '无':<2} style={sm.group(1) if sm else '?'}")

    # ── 逐枚原文落文件（供铺量脚本取靶串；⚠️ 别在聊天里截断看）
    out = ROOT / _run_dir() / "_p4db_btn_raw.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for tag, src in (("壳", sh), ("原", pr)):
        for name, hits in src.items():
            for act, s in hits:
                lines.append(f"### {tag} {name} :: {act}\n{s}\n")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n  ⇒ 逐枚原文已落：{out.relative_to(ROOT)}（{len(lines)} 枚）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
