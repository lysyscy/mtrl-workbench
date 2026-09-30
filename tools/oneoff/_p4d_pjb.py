#!/usr/bin/env python
r"""`TAIL-64` **P4-d**：把「项目选择**按钮**」收进统一出口 `PJB`（造出口 ＋ 试点一条龙 · 先干跑）。

**为什么是它**（`P4-d` 的两档里选了第 ② 档 —— 见施工图 §8.7）：
- 第 ① 档「只收 `pjwrap` 那层外壳」**收益≈0** —— 那层已经逐处一样（`class="fi pjwrap"`），抽不出东西；
- 第 ② 档（本件）收的是**里面那枚 ▾ 按钮**：它现在**逐处手写**同一串
  `style="min-width:Npx;display:inline-flex;align-items:center;justify-content:space-between;gap:calc(8px * var(--fscale))"`
  ＋ 同一个 `<span class="mut" …>▼</span>`，而 `min-width` 实测有 **6 种值** ⇒ 守则 §4.4「相似元素不制造歧义」。

**改法**（同 `FBAR`：**只换首尾两段、中间那截标签表达式留在原地** ⇒ 行数 Δ0）：
```
<button class="btn" data-act="X" style="min-width:126px;…"><span>LABEL</span><span class="mut" …>▼</span></button>
             ↓
${PJB({act:'X',w:126,label:LABEL})}
```
⭐ 首尾两段都在**同一行**上 ⇒ 行数 Δ0；渲染字节也**逐字节不变**（`PJB` 就是照原样拼回去）。

**谁要双边同步**（判据 = 该处**在不在原型的 `V.*` 切片里**）：`index.html` 那 7 处在切片里 ⇒ 壳与原型同批同句；
`legacy.js`（`V.imp` —— 原型**没有**该页）与 `pages-a/b.js`（顶层 `const` 造的条）⇒ **只改壳**。

用法：`python tools/oneoff/_p4d_pjb.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web"
PARTS = ("index.html", "shell/legacy.js", "shell/pages-a.js", "shell/pages-b.js")
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")
BACKUPS = ROOT / "artifacts" / "delivery-backups"
NL = "\r\n"

#: 开段：`<button … data-act="X" style="min-width:Npx;…"><span>`（⚠️ 逐字 —— 对不上就不动它，并且**要报出来**）
OPEN = re.compile(
    r'<button class="btn" data-act="([A-Za-z0-9_]+)" '
    r'style="min-width:(\d+)px;display:inline-flex;align-items:center;justify-content:space-between;'
    r'gap:calc\(8px \* var\(--fscale\)\)"><span>')
#: 收段：关 `</span>` ＋ 那枚 ▾ ＋ 关按钮
CLOSE = '</span><span class="mut" style="font-size:calc(9px * var(--fscale))">▼</span></button>'


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def find_pairs(text: str) -> list[tuple[int, int, int, str, int]]:
    """返回 `[(开段起, 收段起, 开段终, act, w)]`（按位置升序 · 每段都在**同一行**里配好对）。"""
    out = []
    for m in OPEN.finditer(text):
        j = text.find(CLOSE, m.end())
        assert j > 0, f"⛔ 找不到配对的收段（act={m.group(1)}）"
        assert "\n" not in text[m.start():j], f"⛔ 开/收段跨了行（{m.group(1)}）—— 本件按「同一行」设计"
        out.append((m.start(), j, m.end(), m.group(1), int(m.group(2))))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    shell = {n: read(WEB / n) for n in PARTS}
    proto = read(PROTO)
    todo: list[tuple[pathlib.Path, int, int, int, str, int]] = []
    for n in PARTS:
        ps = find_pairs(shell[n])
        print(f"  · {n:16s} 命中 {len(ps)} 处" + (f" —— {[p[3] for p in ps]}" if ps else ""))
        for a, b, e, act, w in ps:
            todo.append((WEB / n, a, b, e, act, w))
    print(f"⇒ 壳侧共 **{len(todo)}** 处")

    # ── 原型那侧（只有 `index.html` 的站点需要；原型**没有** `set`/`imp` 页）
    pp = find_pairs(proto)
    print(f"  · 原型            命中 {len(pp)} 处 —— {[p[3] for p in pp]}")
    shell_acts = [t[4] for t in todo if t[0].name == "index.html"]
    proto_acts = [p[3] for p in pp]
    print(f"⇒ `index.html` 的 act 序：{shell_acts}")
    print(f"⇒ 原型的   act 序：{proto_acts}")
    same_seq = shell_acts == [a for a in proto_acts if a in shell_acts]
    print(f"⇒ 壳的 `index.html` 站点是不是原型的**子序**（序位映射的前提）：{same_seq}")

    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    dst = BACKUPS / "原型-备份-20260930-P4d前.html"
    if not dst.exists():
        shutil.copy2(PROTO, dst)
        print(f"\n  ✅ 备份原型 ⇒ {dst.relative_to(ROOT)}")

    def apply(text: str, items: list[tuple[int, int, int, str, int]]) -> str:
        for a, b, e, act, w in sorted(items, key=lambda x: -x[0]):
            text = text[:a] + f"${{PJB({{act:'{act}',w:{w},label:" + text[e:b] + "})}" + text[b + len(CLOSE):]
        return text

    for n in PARTS:
        items = [(a, b, e, act, w) for (_p, a, b, e, act, w) in todo if _p == WEB / n]
        if not items:
            continue
        out = apply(shell[n], items)
        assert len(out.split("\n")) == len(shell[n].split("\n")), f"⛔ {n} 行数变了"
        (WEB / n).write_text(out.replace("\n", NL), encoding="utf-8", newline="")
        assert read(WEB / n) == out, f"⛔ {n} 写回自校验不过"
        print(f"  ✅ {n:16s} 改了 {len(items)} 处（行数 Δ0）")

    if pp:
        out_p = apply(proto, pp)
        assert len(out_p.split("\n")) == len(proto.split("\n")), "⛔ 原型行数变了"
        PROTO.write_text(out_p.replace("\n", NL), encoding="utf-8", newline="")
        assert read(PROTO) == out_p, "⛔ 原型写回自校验不过"
        print(f"  ✅ {'原型':14s} 改了 {len(pp)} 处（行数 Δ0）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
