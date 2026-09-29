"""`P0-c`（方案 `C`）：给内联 `style="…"` 里**该缩放的属性**的 `px` 值套上 `calc(Npx * var(--fscale))`。

⭐ 口径来源（⛔ 不新立口径）：守则 **§5.11** ＋ `index.html` 样式块注释里**已经写死的那一套** ——
   原话：「本页所有 `font-size` / `padding` / `margin` / `gap` 都写成 `calc(Npx * var(--fscale))`」
   ⇒ **只动这四类**（含 `margin-*` / `padding-*` / `row-gap` / `column-gap`）。
   ⛔ 不动：颜色 / 边框 / `border-radius` / 宽高 / `line-height` / `top·left`。

⭐ **只改数值本身**（保留原来的空格 / 分号 / 其余声明）⇒ diff 最小、最不容易碰到"钉整串"的判据。
⚠️ 跳过：已经含 `var(--fscale)` 的串（防双重缩放）。
⛔ 临时件，用完即删。
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(r"D:\dev\mtrl-workbench")
WEB = ROOT / "backend" / "app" / "web"
FILES = [WEB / "index.html", *sorted((WEB / "shell").glob("*.js"))]

STYLE = re.compile(r'style="([^"]*)"')
PX = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)px")
PROP = re.compile(r"(?P<prop>(?:margin|padding|font-size|gap|row-gap|column-gap)(?:-[a-z]+)?)"
                  r"(?P<sep>\s*:\s*)(?P<val>[^;]*)", re.I)


def scale_css(css: str) -> str:
    if "var(--fscale)" in css:
        return css

    def one(m: re.Match) -> str:
        val = PX.sub(lambda x: f"calc({x.group(1)}px * var(--fscale))", m.group("val"))
        return f"{m.group('prop')}{m.group('sep')}{val}"

    return PROP.sub(one, css)


def changed(text: str) -> list[tuple[str, str]]:
    out = []
    for m in STYLE.finditer(text):
        new = scale_css(m.group(1))
        if new != m.group(1):
            out.append((m.group(1), new))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真写（默认 dry-run）")
    args = ap.parse_args()

    total = 0
    for f in FILES:
        text = f.read_text(encoding="utf-8")
        pair = changed(text)
        total += len(pair)
        print(f"  {f.relative_to(ROOT)}  =  {len(pair)} 处")
        if args.apply and pair:
            f.write_text(STYLE.sub(lambda m: f'style="{scale_css(m.group(1))}"', text),
                         encoding="utf-8")
    print(f"\n合计 {total} 处内联 style 会被改")

    if not args.apply:
        print("\n样例（前 8 条）：")
        for a, b in changed(FILES[0].read_text(encoding="utf-8"))[:8]:
            print(f"  - {a}\n  + {b}")
        print("\n（dry-run：未写）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
