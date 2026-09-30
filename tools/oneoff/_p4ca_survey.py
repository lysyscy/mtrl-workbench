#!/usr/bin/env python
"""`TAIL-64` **`P4-c-a` 开工前量测**（2026-09-30 · 只读 · ⛔ 不改任何文件）。

**为什么要它**：施工图 §8.10 说 `P4-c-a` = 「立出口 ＋ 1 处试点」，但**没写**"那 14 块长什么样"
（每块的 `<li>` 是不是单行？行尾是 `CRLF` 还是 `LF`？`<ul style>` 那串是不是逐字同款？）。
本仓老课：**先量再定，别按记忆铺**（`fbar` 115 处 / `pjwrap` 12 处都栽过）。

**它量什么**（全部只读）：
 0. 壳的每一件是 `CRLF` 还是 `LF`（⚠️ **它决定"渲染字节"里那些换行是什么** —— 出口件与调用点
    若不在一件里、行尾又不同，硬拼 `\\n` 就会与原文**差两个字节**，而那正是本批唯一的硬证据）；
 1. 14 块逐块点名：落在哪一页（`V.mXX`）、第几行到第几行、声明几条 / 实际几个 `<li>`；
 2. 逐块核「**能安全换进出口**」的三条前提：
    ① 每个 `<li>` **各自单行**（`<li>…</li>` 一开一合都在同一行）；
    ② 条目正文里**没有反引号**（`item` 要用模板字面量包 ⇒ 里面有 `` ` `` 就崩）；
    ③ `<summary>` 那行 / `<ul>` 那行**逐块同款**（只有这样才收得进一个出口）。
 3. 报出每块正文的**行尾类型**（`CRLF` / `LF`）—— 给出口件定 `\\r\\n` 还是 `\\n` 用。

用法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_p4ca_survey.py`
"""

from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web"
PARTS = [WEB / "index.html"] + sorted((WEB / "shell").glob("*.js"))

BLOCK = re.compile(r'<details class="tip"><summary>口径说明 · (\d+) 条')
SUMMARY_HEAD = '<details class="tip"><summary>口径说明 · '
UL_RE = re.compile(r'<ul style="([^"]*)">')
LI_RE = re.compile(r"^(\s*)<li>(.*)</li>\s*$")


def page_of(text: str, idx: int) -> tuple[str, int]:
    """`idx` 落在哪一页（最近的前一个 `V.<页>=`）＋ 该页起点行号（1 起）。"""
    cur, head = "（切片外）", 0
    for m in re.finditer(r"(?m)^V\.([A-Za-z0-9_]+)\s*=", text[:idx]):
        cur, head = m.group(1), m.end()
    return cur, text.count("\n", 0, head) + 1


def main() -> int:
    raw = {p: p.read_bytes() for p in PARTS}

    print("=" * 78)
    print(" 0. 壳各件的行尾（CRLF / LF / 混用）")
    print("=" * 78)
    for p in PARTS:
        b = raw[p]
        crlf, lf = b.count(b"\r\n"), b.count(b"\n")
        kind = "CRLF" if lf and crlf == lf else ("LF" if crlf == 0 else f"混用（CRLF {crlf} / 总 LF {lf}）")
        print(f"   {str(p.relative_to(ROOT)):<34} {kind}")

    print("\n" + "=" * 78)
    print(" 1. 14 块逐块点名（声明 N ⇄ 实际 <li> · 行范围 · 行尾 · 形态前提）")
    print("=" * 78)

    sums: dict[str, set[str]] = {}
    uls: dict[str, set[str]] = {}
    n_blocks = n_bad = 0
    picked: list[tuple[int, int, str, int, str]] = []   # (行数, li 数, 页, 起始行, 件名)

    for p in PARTS:
        text = raw[p].decode("utf-8")
        nl = "\r\n" if b"\r\n" in raw[p] else "\n"
        lines = text.split(nl)
        # 逐行找块首（⛔ 不跨行匹配 —— 本件要报"那一行的行号"）
        for i, ln in enumerate(lines, 1):
            m = BLOCK.search(ln)
            if not m:
                continue
            n_blocks += 1
            page, _ = page_of(text, sum(len(x) + len(nl) for x in lines[: i - 1]))
            # 找到该块的 </details>（本行或后续行）
            j = i - 1
            body_lines: list[str] = []
            while j < len(lines):
                body_lines.append(lines[j])
                if "</details>" in lines[j]:
                    break
                j += 1
            body = nl.join(body_lines)
            real = len(re.findall(r"<li>", body))
            decl = int(m.group(1))
            if decl != real:
                n_bad += 1
            # 前提①：每个 <li> 各自单行（含正文不许跨行）
            li_lines = [x for x in body_lines if "<li>" in x]
            li_ok = all(LI_RE.match(x) for x in li_lines) and len(li_lines) == real
            # 前提②：正文无反引号 / 无 `${` 表达式（要用模板字面量包条目 ⇒ 两样都不许有）
            backtick = any("`" in x for x in li_lines)
            expr = any("${" in x for x in li_lines)
            # 前提③：summary 行 / ul 行 逐块同款
            sums.setdefault("summary", set()).add(lines[i - 1].replace(m.group(1), "N", 1))
            um = UL_RE.search(body)
            uls.setdefault("ul", set()).add(um.group(1) if um else "（没找到 <ul>）")
            flags = ("" if li_ok else " ⛔`<li>`不单行") + (" ⛔正文有反引号" if backtick else "") \
                + (" ⛔正文有 ${} 表达式" if expr else "")
            print(f"   {page:<5} 第 {i:>5}~{j + 1:<5} 行（{j - i + 2:>2} 行）· 声明 {decl} / 实际 {real}"
                  f" · {'CRLF' if nl == chr(13) + chr(10) else 'LF'}{flags}")
            picked.append((j - i + 2, real, page, i, str(p.relative_to(ROOT))))

    print(f"   ⇒ 共 {n_blocks} 块 · 已漂 {n_bad} 块"
          f"（⛔ 漂的那块是**另一个病** —— 见 `_p4c_fixcount.py`）")

    print("\n" + "=" * 78)
    print(" 2. 前提③：summary 行 / <ul> 行 是不是逐块同款")
    print("=" * 78)
    for k, v in sums.items():
        print(f"   {k}：{len(v)} 种形态")
        for x in sorted(v):
            print(f"      · {x[:150]}")
    for k, v in uls.items():
        print(f"   {k}：{len(v)} 种形态")
        for x in sorted(v):
            print(f"      · {x[:150]}")

    print("\n" + "=" * 78)
    print(" 3. 试点候选（按「块最小 / 条目最少」排 —— ⚠️ 只是**候选**，还要看有没有别的判据钉着那一页）")
    print("=" * 78)
    for rows, li, page, start, part in sorted(picked)[:6]:
        print(f"   {rows:>2} 行 · {li} 个 <li> · {page:<5} 起始第 {start} 行 · {part}")

    print("\n===== 读法 =====")
    print("  · 前提①/②/③ 全 ✅ 的块才适合 `P4-c-a` 试点；⛔ 别一上来铺 14 处。")
    print("  · ⚠️ 出口件若与调用点**不在同一件**、且两件行尾不同 ⇒ 出口里的换行必须照调用点那份写。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
