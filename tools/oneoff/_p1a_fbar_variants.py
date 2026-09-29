"""`P1-a`（方案 `A`）：把 9 处展开区**各自手写的外框/间距**收进 4 个**变体类**（⛔ HTML 结构不动）。
每组一行：`原样 style="…"` → `class="fbar <变体>"`，**声明原样搬进 CSS** ⇒ 外观逐像素不变。
⛔ 临时件，用完即删。"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(r"D:\dev\mtrl-workbench")
WEB = ROOT / "backend" / "app" / "web"
FILES = [WEB / "index.html", *sorted((WEB / "shell").glob("*.js"))]

#: (原 style 值, 变体类名)
PAIRS: list[tuple[str, str]] = [
    ("border:1px solid var(--bd);border-radius:var(--r)", "pane"),
    ("margin:0 0 calc(8px * var(--fscale));border:1px solid var(--bd);border-radius:6px;"
     "background:var(--sf2);padding:calc(8px * var(--fscale)) calc(10px * var(--fscale))", "strip"),
    ("margin-bottom:calc(6px * var(--fscale));border:1px solid var(--bd);border-radius:6px;"
     "background:var(--sf2);padding:calc(8px * var(--fscale)) calc(10px * var(--fscale))", "strip mb6"),
    ("border:1px solid var(--bd2);border-radius:6px;margin-bottom:calc(10px * var(--fscale))", "plate"),
]

CSS_ANCHOR = (".fbar .fi input,.fbar .fi select{min-width:calc(112px * var(--fscale));width:auto}")
CSS_ADD = (CSS_ANCHOR + "\n"
           "/* ⭐ P1-a（2026-09-28）：展开区**外框/间距的四个变体** —— 原先是 9 处**各写一遍内联 style**；\n"
           "   声明**原样搬过来**（⛔ 一个值都没改）⇒ 外观逐像素不变，只是不再散落在 9 处模板里。\n"
           "   「.strip」＋「.mb6」= **同一个外观、只差下边距**（⛔ 不并为一条：并了要动值 = 改外观）。 */\n"
           ".fbar.pane{border:1px solid var(--bd);border-radius:var(--r)}\n"
           ".fbar.strip{margin:0 0 calc(8px * var(--fscale));border:1px solid var(--bd);border-radius:6px;"
           "background:var(--sf2);padding:calc(8px * var(--fscale)) calc(10px * var(--fscale))}\n"
           ".fbar.strip.mb6{margin-bottom:calc(6px * var(--fscale))}\n"
           ".fbar.plate{border:1px solid var(--bd2);border-radius:6px;"
           "margin-bottom:calc(10px * var(--fscale))}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    total = 0
    for f in FILES:
        t = f.read_text(encoding="utf-8")
        n0 = t.count('class="fbar" style="')
        for old, cls in PAIRS:
            needle = f'class="fbar" style="{old}"'
            n = t.count(needle)
            if n:
                print(f"  {f.name}: ×{n} → `class=\"fbar {cls}\"`  （{old[:46]}…）")
                t = t.replace(needle, f'class="fbar {cls}"')
                total += n
        if n0 and 'class="fbar" style="' in t:
            print(f"  ⚠️ {f.name} 还有 {t.count('class=\"fbar\" style=\"')} 处没匹配上！")
        if f.name == "index.html" and args.apply:
            assert CSS_ANCHOR in t, "CSS 锚点没找到"
            t = t.replace(CSS_ANCHOR, CSS_ADD, 1)
        if args.apply:
            f.write_text(t, encoding="utf-8")
    print(f"\n合计替换 {total} 处" + ("" if args.apply else "（dry-run：未写）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
