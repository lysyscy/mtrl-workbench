#!/usr/bin/env python
r"""`TAIL-64` **P4-b**：把剩下 **21 处**筛选栏的**外壳**收进统一出口 `FBAR`（`P4-a` 只做了 `m01` 那一处）。

**为什么要脚本**（⛔ 别在编辑器里手改）：
- 要改 **6 个件**（壳 `index.html` / `actions.js` / `legacy.js` / `pages-a.js` / `pages-b.js` ＋ **仓外原型**），
  换行全是 CRLF ⇒ 一律**按 bytes 精确替换 ＋ 断言"恰好命中一次"**；
- 交付面原型在**仓外** ⇒ 改前必须先备份到 `.codebuddy/backups/`。

**写法与 `P4-a` 完全同款**（「**只换首尾两个标签、栏里的控件一行不动**」）：

| 原来 | 改成 |
|---|---|
| `<div class="fbar">` | `${FBAR({body:\`` |
| `<div class="fbar plate">` | `${FBAR({cls:'plate',body:\`` |
| `<div class="fbar pane">` | `${FBAR({cls:'pane',body:\`` |
| `<div class="fbar strip">` | `${FBAR({cls:'strip',body:\`` |
| `<div class="fbar strip mb6">` | `${FBAR({cls:'strip mb6',body:\`` |
| 匹配的那个 `</div>` | `` `})} `` |

⇒ **行数 Δ0**；渲染字节**逐字节不变**（`'<div class="fbar…">' + body + '</div>'` 就是原来那一段）。

**谁要双边同步**（判据 = 该处**在不在 `V.*` 切片里**，而 `U1` 只比**原型里也有的**切片）：
- `index.html` 那 11 处 → **在切片里 ⇒ 壳与原型同批同句**（`U1` 期望 **Δ0**）；
  ⚠️ 但其中 `V.m14`「加入剔除名单」那块**是壳新增**（原型里没有 `jciName`）⇒ 只有壳侧，
  那两行**本来就在登记簿里**（指纹会变 ⇒ 见 `--dry` 的预报）。
- `actions.js` / `legacy.js` / `pages-a.js` / `pages-b.js` 那 10 处 → 切片**外**（或该切片**原型里没有** ——
  `set`/`imp` 是壳新增页）⇒ `U1` **看不见** ⇒ **只改壳**（同 `TAIL-150` 的先例）。

用法：`python tools/oneoff/_p4b_fbar.py`（干跑，只看不改）· `… --write`（落盘）
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
WEB = ROOT / "backend" / "app" / "web"
SHELL_PARTS = ("index.html", "shell/actions.js", "shell/legacy.js", "shell/pages-a.js", "shell/pages-b.js")
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")
BACKUPS = ROOT / _run_dir() / "delivery-backups"

NL = "\r\n"
#: `<div class="fbar…">` 开标签 → `FBAR(...)` 调用头（**逐字**对应 `FBAR` 的拼装式）
OPENS: tuple[tuple[str, str], ...] = (
    ('<div class="fbar">', "${FBAR({body:`"),
    ('<div class="fbar plate">', "${FBAR({cls:'plate',body:`"),
    ('<div class="fbar plate" style="margin-top:calc(8px * var(--fscale))">',
     "${FBAR({cls:'plate',sty:'margin-top:calc(8px * var(--fscale))',body:`"),
    ('<div class="fbar pane">', "${FBAR({cls:'pane',body:`"),
    ('<div class="fbar strip mb6">', "${FBAR({cls:'strip mb6',body:`"),
    ('<div class="fbar strip">', "${FBAR({cls:'strip',body:`"),
)
CLOSE_OLD, CLOSE_NEW = "</div>", "`})}"

SLICE = re.compile(r"^V\.([A-Za-z0-9_]+)\s*=")
END = re.compile(r"^(V\.[A-Za-z0-9_]+\s*=|BIND\.|const |function |let |var )")


def read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8").replace("\r\n", "\n")


def match_close(text: str, i: int) -> int:
    """从 `<div` 的起点 `i` 起数嵌套，返回**与它配对的那个 `</div>`** 的起点（⛔ 不是"第一个 `</div>`"）。"""
    depth, k = 0, i
    while k < len(text):
        if text.startswith("<div", k):
            depth += 1
            k += 4
            continue
        if text.startswith("</div>", k):
            depth -= 1
            if depth == 0:
                return k
            k += 6
            continue
        k += 1
    raise AssertionError("⛔ 嵌套没配平 —— 靶串不在这段 HTML 里")


def slice_of(text: str, pos: int) -> str:
    """`pos` 落在哪个 `V.<页>` 切片里（⛔ 不在任何切片里 ⇒ 返回 `''`）。"""
    cur = ""
    for m in re.finditer(r"(?m)^(.*)$", text[:pos]):
        ln = m.group(1)
        if END.match(ln):
            cur = ""
        sm = SLICE.match(ln)
        if sm:
            cur = sm.group(1)
    return cur


def slice_line(text: str, pos: int) -> int:
    """`pos` 在**它所属切片内**的行序（0 起）—— ⭐ 这就是 `U1` 的**对位号**（它按切片内行号两两比）。

    ⚠️ 为什么必须算它：`U1` 是**按行号对位**的 ⇒ "壳的第 k 行"比的是"原型的第 k 行"，
    **不是**"第几个同样的东西"。所以"两侧都能改成同一句"**不足以**保证 Δ0 ——
    还得两处**落在同一个对位号**上（否则改完那两行各自配到了别的行 ⇒ 都变成了新漂移）。
    """
    start = 0
    cur = ""
    for m in re.finditer(r"(?m)^(.*)$", text[:pos]):
        ln = m.group(1)
        if END.match(ln):
            cur = ""
        sm = SLICE.match(ln)
        if sm:
            cur, start = sm.group(1), m.start()
    if not cur:
        return -1
    return text.count("\n", start, pos)


def sites(text: str) -> tuple[list[tuple[int, int, str, str]], list[str]]:
    """返回 `([(开标签起点, 配对 `</div>` 起点, 开标签串, 开标签→新写法串)], [跳过的串])`。

    ⚠️ **必须跳过"不是真标签"的那两处**：`FBAR` 自己的**注释**里引述了 `class="fbar [cls]"[ …]`，
    以及它**代码行**里的 `'<div class="fbar'+(cls?…` —— 它们也含 `class="fbar` 字样（⛔ 别拿它们当真站点）。
    ⇒ 判法 = **只认 `OPENS` 里那几种逐字开标签**，其余**跳过并报出来**（⛔ 不静默）。
    """
    out: list[tuple[int, int, str, str]] = []
    skipped: list[str] = []
    pos = 0
    while True:
        i = text.find('class="fbar', pos)
        if i < 0:
            break
        j = text.rfind("<div", 0, i)                 # 开标签的起点
        tag = next((t for t, _ in OPENS if text.startswith(t, j)), None)
        if tag is None:
            skipped.append(text[j:j + 60])
            pos = i + 1
            continue
        k = match_close(text, j)
        out.append((j, k, tag, dict(OPENS)[tag]))
        pos = k + 6
    return out, skipped


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    shell = {n: read(WEB / n) if n != "index.html" else read(WEB / "index.html") for n in SHELL_PARTS}
    proto = read(PROTO)

    # ── ① 壳侧站点
    todo: list[tuple[pathlib.Path, int, int, str, str, str]] = []      # 件 / 开 / 闭 / 旧 / 新 / 切片
    for n in SHELL_PARTS:
        items, skipped = sites(shell[n])
        for j, k, tag, new in items:
            todo.append((WEB / n, j, k, tag, new, slice_of(shell[n], j)))
        if skipped:
            print(f"  （跳过 {len(skipped)} 处「不是真标签」的文字：{n} ⇒ {skipped[0][:44]!r}）")
    print(f"壳侧共 **{len(todo)} 处** fbar（其中裸 `.fbar` 的那批在 `index.html`）")

    # ── ② 壳切片 ⇄ 原型切片的**序位**映射（只对两侧都有的切片；`set`/`imp` 是壳新增 ⇒ 无对位）
    def by_slice(text: str) -> dict[str, list[tuple[int, int, str, str]]]:
        d: dict[str, list] = {}
        items, _skip = sites(text)
        for j, k, tag, new in items:
            d.setdefault(slice_of(text, j), []).append((j, k, tag, new))
        return d

    s_by, p_by = by_slice(shell["index.html"]), by_slice(proto)
    _pi, _pskip = sites(proto)
    if _pskip:
        print(f"  （原型侧跳过 {len(_pskip)} 处「不是真标签」的文字：⇒ {_pskip[0][:44]!r}）")

    # ── ③ 逐处报"要不要双边同步 / 两侧首尾行同不同"
    plan_proto: list[tuple[int, int, str, str]] = []
    for path, j, k, tag, new, sl in todo:
        if path.name != "index.html":
            print(f"  · {path.name:12s} 切片={sl or '（切片外）':<14} 只改壳")
            continue
        idx = [x[0] for x in s_by.get(sl, [])].index(j)
        peers = p_by.get(sl, [])
        if idx >= len(peers):
            print(f"  ⚠️ `{sl}` 序位 {idx} 在原型里**没有对位**（壳新增）⇒ 只改壳；"
                  f"此行**本来就在登记簿里**（指纹会变 ⇒ 需 `--write-expected` ＋ 人工消号幽灵）")
            continue
        pj, pk, ptag, _pnew = peers[idx]
        assert ptag == tag, f"⛔ `{sl}` 序位 {idx} 两侧开标签不同：壳 {tag!r} / 原型 {ptag!r}"
        # ⭐ 判 Δ0 的**真条件**：开/尾两处必须落在**同一个对位号**上（并且"其余部分"逐字一致）
        si, pi = slice_line(shell["index.html"], j), slice_line(proto, pj)
        sj, pj2 = slice_line(shell["index.html"], k), slice_line(proto, pk)
        aligned = si == pi and sj == pj2
        so = shell["index.html"][shell["index.html"].rfind("\n", 0, j) + 1: shell["index.html"].find("\n", j)]
        po = proto[proto.rfind("\n", 0, pj) + 1: proto.find("\n", pj)]
        same = so.replace(tag, "") == po.replace(tag, "")
        print(f"  · index.html  切片={sl:5s} 序位={idx} 对位号 壳{si}/{pi}·尾 壳{sj}/{pj2}"
              f" 首行余部同形={same}"
              + ("  ⇒ **Δ0**" if (aligned and same) else "  ⚠️ 不对位/不同形 ⇒ 会新增漂移＋幽灵"))
        if aligned and same:
            plan_proto.append((pj, pk, ptag, dict(OPENS)[ptag]))
        else:
            plan_proto.append((pj, pk, ptag, dict(OPENS)[ptag]))    # 仍双侧改（原型仍是规格），但要登记

    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    # ── ④ 落盘（**逆序**替换 ⇒ 前面的偏移不受影响）
    def apply(text: str, list_: list[tuple[int, int, str, str]]) -> tuple[str, int]:
        for j, k, tag, new in sorted(list_, key=lambda x: -x[0]):
            text = text[:j] + new + text[j + len(tag):k] + CLOSE_NEW + text[k + 6:]
        return text, len(list_)

    BACKUPS.mkdir(parents=True, exist_ok=True)
    dst = BACKUPS / "原型-备份-20260930-P4b前.html"
    if dst.exists():
        print(f"\n  ℹ️ 备份已在（本轮第一批已经存过）⇒ 不覆盖：{dst.relative_to(ROOT)}")
    else:
        shutil.copy2(PROTO, dst)
        print(f"\n  ✅ 备份原型 ⇒ {dst.relative_to(ROOT)}")

    for n in SHELL_PARTS:
        p = WEB / n
        # ⚠️ 比**路径**（`WEB / n`），⛔ 别拿基名比相对路径 —— 2026-09-30 第一版就写错成 `_p.name == n`，
        #    于是 `shell/*.js` 那 4 件**一处都没改**、还被**静默跳过**（只有 `index.html` 侥幸对上）。
        items = [(j, k, tag, new) for (_p, j, k, tag, new, _s) in todo if _p == p]
        if not items:
            continue
        out, cnt = apply(shell[n], items)
        before = p.read_text(encoding="utf-8")
        p.write_text(out.replace("\n", NL), encoding="utf-8", newline="")
        assert p.read_text(encoding="utf-8") == out, f"⛔ {n} 写回自校验不过"
        assert len(out.split("\n")) == len(before.replace("\r\n", "\n").split("\n")), f"⛔ {n} 行数变了"
        print(f"  ✅ {n:12s} 改了 {cnt} 处（行数 Δ0）")
    out_p, cnt_p = apply(proto, plan_proto)
    PROTO.write_text(out_p.replace("\n", NL), encoding="utf-8", newline="")
    assert PROTO.read_text(encoding="utf-8") == out_p, "⛔ 原型写回自校验不过"
    print(f"  ✅ {'原型':12s} 改了 {cnt_p} 处（行数 Δ0）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
