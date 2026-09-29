"""`P2-a` 拆件（**一次一件**）——把 `index.html` 内联脚本里的**非切片**代码按件搬进 `web/shell/*.js`。

## 口径（⛔ 别改）

- ⭐ **计划 §23 那条**：**原型切片 `V.*` 不许搬出 `index.html`**（`ui_parity` 的 `U1` 逐行比它）
  ⇒ 搬运范围**先算 `V.*` 切片的跨度**（口径与 `ui_parity.slices()` 同一套：`V.<名>=` 起、到下一个
  顶声明为止，**含它尾部的注释与章节横幅**），再从搬运集里**扣掉**；并逐条断言。
- ⛔ **`const V={}, BIND={};` 必须留在 `index.html`** —— `index.html` 里那些 `V.*=` / `BIND.*=`
  是**加载期赋值语句**，要在这个声明之后跑（搬走 = TDZ `ReferenceError`）。
- ⚠️ **新件必须两处登记**：`index.html` 的 `<script src>` ＋ **`main.py` 的一条路由**
  （缺 ⇒ 浏览器 404 ⇒ `ReferenceError` 整支崩，**离线断言全看不见** —— 判据 `tests/test_shell_part_routes.py`）。
- ⚠️ **新件的 `<script src>` 一律插在 `actions.js` 之前** ⇒ 新件之间的顺序 = 插入顺序 = 搬运范围的文档顺序
  （保持原相对顺序）；且保证 `actions.js` / `core.js` **加载期求值的表**仍能见到它们。
- 搬运是**纯行剪切**（逐字不改）⇒ `U1` 一律 **0 漂移**（V 切片一个字节没动）。
- 换行：`index.html` 与 `web/shell/*.js` **都是 CRLF** ⇒ 插入的行必须带 `\\r`（⛔ 不混行尾）。

## 用法

    backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_p2a_split.py --file base --check
    backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_p2a_split.py --file base
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "backend" / "app" / "web"
INDEX = WEB / "index.html"
MAIN = REPO / "backend" / "app" / "main.py"
BARE = '  <script src="/static/shell/actions.js"></script>'
V_DECL = re.compile(r"^V\.[A-Za-z0-9_]+\s*=")
END_RE = re.compile(r"^(V\.[A-Za-z0-9_]+\s*=|BIND\.|const |function |let |var )")   # ＝ `ui_parity.END_RE`
DECL = re.compile(r"^(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=|^function\s+([A-Za-z_$][\w$]*)\s*\(")
NEW_FILES = ("base.js", "view.js", "ui.js", "proj.js", "pages-a.js", "pages-b.js")
KEEP = ("const V={}, BIND={};",)


def script_span(lines: list[str]) -> tuple[int, int]:
    a = [i for i, ln in enumerate(lines) if ln.rstrip("\r") == "<script>"]
    b = [i for i, ln in enumerate(lines) if ln.rstrip("\r") == "</script>"]
    assert len(a) == 1 and len(b) == 1, f"⛔ 内联 `<script>` 边界不唯一（{len(a)} / {len(b)}）"
    return a[0] + 1, b[0]


def seg_spans(lines: list[str], lo: int, hi: int) -> dict[str, tuple[int, int]]:
    """顶层段 → `(起, 止)`（0 基、止为开区间）—— 口径同 `ui_parity.END_RE`。"""
    ends = [i for i in range(lo, hi) if END_RE.match(lines[i].rstrip("\r"))]
    out: dict[str, tuple[int, int]] = {}
    for k, i in enumerate(ends):
        m = DECL.match(lines[i].rstrip("\r"))
        if not m:
            continue
        out[m.group(1) or m.group(2)] = (i, ends[k + 1] if k + 1 < len(ends) else hi)
    return out


def late_names() -> set[str]:
    """**晚于 `index.html` 加载**的那些件里声明的名字（＝内联脚本⛔ 不许在加载期引用它们）。"""
    out: set[str] = set()
    for n in NEW_FILES:
        p = WEB / "shell" / n
        if not p.exists():
            continue
        for ln in p.read_text(encoding="utf-8", newline="").split("\n"):
            m = DECL.match(ln.rstrip("\r"))
            if m:
                out.add(m.group(1) or m.group(2))
    return out

#: 各件的规格。`anchor` 一律**短子串**：起点锚点要求全文件唯一（横幅带 3 个前导空格以避开目录里的引用）；
#: 终点锚点取**起点之后的第一处**。`ranges` 每项 = `(起点锚点, 起点偏移, 终点锚点, 终点偏移)`。
MANIFEST: dict[str, dict] = {
    "base": {
        "file": "base.js",
        "what": "公共常量 · 纯函数 · 表头排序内核（原 §1 工具层 / §1.5 表头排序 ＋ §0 里的数据常量）",
        "why": "这三章是**谁都要用**的底座（金额 / 日期 / 枚举 / 取值出口 / 排序内核）⇒ 单开一件，改页面时不必读它。",
        # ⚠️ **时钟簇必须留在 `index.html`**：`index.html` 里 7 处筛初值**加载期就调 `bjMonth()`**
        #    （`fNt` / `plf` / `plImportM` / `lgCut` / `fExt` / `fIvYm` …）—— 而新件在它**之后**加载
        #    ⇒ 搬走 = 内联脚本当场 `bjMonth is not defined` 中断（后面所有 `const` 停在 TDZ，页面空白）。
        "keep": ["_BJ_NOW", "SYS_YM", "SYS_TODAY", "ymOf", "ymdOf", "bjMonth"],
        "ranges": [("const PJ_COLS", 0, "   2. 导航与路由", -2)],
    },
    "view": {
        "file": "view.js",
        "what": "导航 · 路由 · 渲染内核 · 虚拟滚动（原 §2）",
        "why": "`render()` / `drawVirtual()` / `WIRED` 是**每页都要过**的一层；与页面代码分开，读页面时不必读它。",
        "ranges": [("   2. 导航与路由", -1, "const V={}, BIND={};", -1),
                   ("const WIRED=new Set(", 0, "   3. 看板", -2)],
    },
    "ui": {
        "file": "ui.js",
        "what": "共用 UI 件与浮层（时间面板 / 项目工具 / 项目面板 / 浮层定位）",
        "why": "「选一个项目 / 选一个时段」与浮层定位是**跨页共用**的机制（守则 §5.12 的唯一出口）⇒ 单开一件。",
        "ranges": [("   4. MOD-03 付款通知书", -1, "let fNt=", -1)],
    },
    "proj": {
        "file": "proj.js",
        "what": "通知书草稿 / 表格件与空态 / 各页表头常量 / 集采与供应商口径",
        "why": "表格外壳（`TBL`）· 空态出口 · 各页列定义 · 集采关联与供应商判定 —— 都是**跨页共用**的口径件。",
        "ranges": [("let fNt=", 0, "V.m03=()=>{", -1)],
    },
    "pages-a": {
        "file": "pages-a.js",
        "what": "`MOD-03` / `MOD-04` / `MOD-05` 的页辅助 ＋ `BIND` 注入",
        "why": "付款域三页的筛选、草稿行、台账取数是**同一批人对同一批数据**的活 ⇒ 单开一件。",
        "ranges": [("BIND.m03=()=>{", 0, "V.m05=()=>{", -1),
                   ("const PJ_TRAIL=[];", 0, "V.m01=()=>{", -1)],
    },
    "pages-b": {
        "file": "pages-b.js",
        "what": "`MOD-01`…`MOD-13` 各章的页辅助（各章里 `V.*` 之外的段）",
        "why": "其余各页的筛选 / 口径 / 取数片段集中一件 ⇒ 各页的口径改动不必再翻 4000 行。",
        "ranges": [("const IVC5=", 0, "V.m06=()=>{", -1),
                   ("const bigCands", 0, "V.m07=()=>{", -1),
                   ("let invWhs=", 0, "V.m08=()=>{", -1),
                   ("const awfPjPanel=", 0, "V.m09=()=>{", -1),
                   ("let dfNewOn=", 0, "V.m12=()=>{", -1),
                   ("let fJc=", 0, "V.m11=()=>{", -1),
                   ("let busy=", 0, "</script>", -1)],
    },
}

#: ⚠️ 同批订正（旧措辞会让人以为 `P2-a` 被禁）——`§23` 的真实口径**只管"原型切片不许搬"**。
HDR_OLD = " * ⛔ 改这里前先看 §23：`index.html` 里 258–3285 那一段（公共外壳 ＋ 原型切片 `V.*`）**不许搬**。"
HDR_NEW = (
    " * ⛔ 改这里前先看计划 §23：**原型切片 `V.*` 不许搬出 `index.html`**（`ui_parity` 的 `U1` 逐行比它）。\n"
    " *    ⚠️ **订正（2026-09-28 · `TAIL-164`）**：原文写「`index.html` 里 258–3285 那一段（公共外壳 ＋ 原型切片）\n"
    " *    不许搬」—— 那句**过宽**（`§23` 的口径只管**原型切片**）：**非切片**的公共代码已按 `P2-a` 搬进\n"
    " *    `web/shell/{base,view,ui,proj,pages-a,pages-b}.js` ⇒ ⛔ 别再照那句拦。"
)


def header(spec: dict) -> str:
    return (
        f"/* shell/{spec['file']} —— 壳的**独立件**（`P2-a` 拆件 · 2026-09-28 · 台账 `TAIL-164`）：{spec['what']}。\n"
        " *\n"
        f" * ⭐ **为什么单开一件**：{spec['why']}\n"
        " *    `index.html` 原来一件套 4000 行（CSS ＋ HTML ＋ 内联脚本混装）⇒ 改一处要翻三个区\n"
        " *    （本会话两次白屏的同一个根）。本件是「**只拆非切片**」那一批里的一件。\n"
        " * ⛔ **本件不许碰**：任何 `V.<原型页>` 切片（它们**留在 `index.html`** —— 计划 §23 的口径，\n"
        " *    `ui_parity` 的 `U1` 逐行比它）· 口径判定（判定全在后端）· 界面文案的主人。\n"
        " * ⚠️ **加载顺序**：`index.html` 的 `<script src>` 顺序即真源 —— 本件排在 `actions.js` **之前**\n"
        " *    （`actions.js` / `core.js` 里有些表**加载期就求值**到本件的常量）。⛔ 别调顺序。\n"
        " * ⚠️ 本件的代码是**原样搬出**（逐字未改，含注释）；来历与搬法见计划 §15 `TAIL-164`。 */\n"
    )


def route_block(name: str) -> str:
    safe = re.sub(r"\W", "_", name)
    return (
        "\n    # ⭐ `P2-a` 拆件（2026-09-28 · `TAIL-164`）：`shell/%s`。\n"
        "    #    ⚠️ **两处登记**：本路由 ＋ `index.html` 的 `<script src>`（缺一 ⇒ 浏览器 404 ⇒ 整支壳崩）。\n"
        '    @app.get("/static/shell/%s", include_in_schema=False)\n'
        "    def shell_%s_js() -> FileResponse:\n"
        '        return _shell_js("%s")\n' % (name, name, safe, name)
    )


def to_nl(text: str, crlf: bool) -> str:
    text = text.replace("\r\n", "\n")
    return text.replace("\n", "\r\n") if crlf else text


def v_spans(lines: list[str]) -> set[int]:
    """`V.*` 切片的行号集（口径同 `ui_parity.slices()`：含尾部注释/横幅）。"""
    out: set[int] = set()
    cur = False
    for i, ln in enumerate(lines):
        s = ln.rstrip("\r")
        if V_DECL.match(s):
            cur = True
            out.add(i)
            continue
        if cur:
            if END_RE.match(s):
                cur = False
            else:
                out.add(i)
    return out


def undo(spec: dict, name: str) -> int:
    """把**上一件**退回 `index.html`：删掉那条重复的 `<script src>` ⇒ 把件体插回 `<script>` 之后 ⇒ 删件与路由。

    ⚠️ 只在"插错标签 / 要重来"时用；`index.html` 是本会话**未提交**的改动，⛔ **不能 `git checkout`** 还原。
    """
    p = WEB / "shell" / name
    assert p.exists(), f"⛔ 找不到 {p}"
    t = p.read_text(encoding="utf-8", newline="")
    assert t.startswith(f"/* shell/{name} —— "), "⛔ 这不是本脚本生成的件（缺少头部）"
    raw = t.split("\r\n")
    k = max(i for i, ln in enumerate(raw) if "本件的代码是**原样搬出**" in ln)
    assert raw[k + 1] == "" and raw[-1] == "", "⛔ 件体边界与预期不符（头后应有空行、文件应以 CRLF 收尾）"
    body_lines = raw[k + 2:-1]                 # ⚠️ 只掐掉**末尾那一个**空元素 ⇒ 件体里的空行一个不丢

    L = INDEX.read_text(encoding="utf-8", newline="").split("\n")
    idxs = [i for i, ln in enumerate(L) if ln.rstrip("\r") == BARE]
    assert len(idxs) == 1, f"⛔ `actions.js` 的标签应恰好 1 条，实为 {len(idxs)}"
    tag = f'  <script src="/static/shell/{name}"></script>'
    ti = [i for i, ln in enumerate(L) if ln.rstrip("\r") == tag]
    assert len(ti) == 1, f"⛔ index.html 里本件的标签应恰好 1 条，实为 {len(ti)}"
    del L[ti[0]]
    s = [i for i, ln in enumerate(L) if ln.rstrip("\r") == "<script>"]
    assert len(s) == 1, f"⛔ 内联 `<script>` 起点不唯一（{len(s)} 处）"
    out = L[:s[0] + 1] + [ln if ln.endswith("\r") else ln + "\r" for ln in body_lines] + L[s[0] + 1:]
    INDEX.write_text("\n".join(out), encoding="utf-8", newline="")

    mt = MAIN.read_text(encoding="utf-8", newline="")
    block = to_nl(route_block(name), "\r\n" in mt)
    assert mt.count(block) == 1, f"⛔ main.py 里找不到本件的路由块（{name}）"
    MAIN.write_text(mt.replace(block, "", 1), encoding="utf-8", newline="")
    p.unlink()
    print(f"⇒ 已退回：index.html 复原（{len(L)} → {len(out)} 行）· 删 shell/{name} · 删 main.py 路由")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="P2-a 拆件（一次一件）")
    ap.add_argument("--file", required=True, choices=sorted(MANIFEST))
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--undo", action="store_true", help="把上一件**退回** index.html（⛔ 只动本件，别乱用）")
    a = ap.parse_args()
    spec = MANIFEST[a.file]
    name = spec["file"]

    if a.undo:
        return undo(spec, name)

    L = INDEX.read_text(encoding="utf-8", newline="").split("\n")
    picked: list[int] = []
    for s_anchor, so, e_anchor, eo in spec["ranges"]:
        hits = [i for i, ln in enumerate(L) if s_anchor in ln]
        assert len(hits) == 1, f"⛔ 起点锚点不唯一（{len(hits)} 处）：{s_anchor!r}"
        i0 = hits[0] + so
        after = [i for i, ln in enumerate(L) if e_anchor in ln and i > i0]
        assert after, f"⛔ 终点锚点找不到：{e_anchor!r}"
        picked += list(range(i0, after[0] + eo + 1))

    vs = v_spans(L)
    lo, hi = script_span(L)
    spans = seg_spans(L, lo, hi)
    keep = spec.get("keep", ())
    miss = [n for n in keep if n not in spans]
    assert not miss, f"⛔ keep 名单里有找不到的段名：{miss}"
    keep_lines = {i for n in keep for i in range(*spans[n])}
    picked_set = set(picked)
    moved = sorted(picked_set - vs - keep_lines)
    guarded = sorted(picked_set & vs)
    kept = sorted(picked_set & keep_lines)
    moved_names = {n for n, (a, _b) in spans.items() if a in picked_set and a not in keep_lines}

    # ⚠️⚠️ **加载期依赖预检**（本批第一版就栽在这）：`index.html` 里那些**顶层带调用**的声明
    #    会在**内联脚本加载时**就求值 —— 它们⛔ **不许**引到"晚加载的件"里的名字，否则内联脚本当场中断
    #    （症状：`X is not defined` ＋ 其后所有 `const` 停在 TDZ ⇒ 页面空白，而离线断言全绿）。
    late = late_names() | moved_names
    deps: list[tuple[int, str, str]] = []
    for i, ln in enumerate(L):
        if i in picked_set or i in vs:
            continue
        s = ln.rstrip("\r")
        if not s.strip() or s[0] in " \t" or s.lstrip().startswith(("//", "/*", "*", "}")):
            continue
        if s.startswith("function ") or "=>" in s or "=" not in s or "(" not in s:
            continue
        for m in re.finditer(r"\b([A-Za-z_$][\w$]*)\s*\(", s):
            if m.group(1) in late:
                deps.append((i + 1, m.group(1), s[:70]))
    assert not deps, (
        "⛔ **加载期依赖**：`index.html` 剩下的顶层声明调用了「晚加载件」里的名字 ⇒ 内联脚本会当场中断：\n  "
        + "\n  ".join(f"L{a} 调 {b} ← {c}" for a, b, c in deps[:8])
        + "\n  ⇒ 把这些名字加进该件的 `keep`（必须留在 index.html），或把那个调用点一起搬走。")

    for i in moved:
        s = L[i].rstrip("\r")
        assert not V_DECL.match(s), f"⛔ 搬运集含 `V.*` 声明行（L{i + 1}）"
        assert s not in KEEP, f"⛔ 搬运集含必须留下的行（L{i + 1}）：{s[:40]}"
        assert "<script src" not in s and "</script>" not in s, f"⛔ 搬运集含 script 标签（L{i + 1}）"

    body = [L[i] for i in moved]
    rest = [ln for i, ln in enumerate(L) if i not in set(moved)]
    tag_at = [i for i, ln in enumerate(rest) if ln.rstrip("\r") == BARE]
    assert len(tag_at) == 1, f"⛔ `actions.js` 的 `<script src>` 锚点数 = {len(tag_at)}（应为 1）"
    new_tag = f'  <script src="/static/shell/{name}"></script>' + "\r"
    out = rest[:tag_at[0]] + [new_tag] + rest[tag_at[0]:]

    print(f"件 = shell/{name} · 搬走 {len(body)} 行（原 L{moved[0] + 1}…L{moved[-1] + 1}）")
    print(f"  ⛔ 扣掉 `V.*` 切片 {len(guarded)} 行（它们留在 index.html）："
          f"{'、'.join('L%d' % (i + 1) for i in guarded[:6])}{'…' if len(guarded) > 6 else ''}")
    print(f"index.html：{len(L) - 1} → {len(out) - 1} 行")   # ⚠️ `split("\n")` 末尾会多一个空元素 ⇒ 报"真实行数"要减 1
    if a.check:
        print("（--check：未写入）")
        return 0

    (WEB / "shell" / name).write_text(
        to_nl(header(spec), True) + "\r\n" + "\n".join(body) + "\r\n", encoding="utf-8", newline="")
    INDEX.write_text("\n".join(out), encoding="utf-8", newline="")

    mt = MAIN.read_text(encoding="utf-8", newline="")
    crlf = "\r\n" in mt
    anchor = '    @app.get("/static/shell/api.js", include_in_schema=False)'
    assert mt.count(anchor) == 1, "⛔ main.py 里的 api.js 路由锚点不唯一"
    mt = mt.replace(anchor, to_nl(route_block(name), crlf) + anchor, 1)
    MAIN.write_text(mt, encoding="utf-8", newline="")

    if name == "base.js":                      # 同批订正两处过期措辞（说得太宽 ⇒ 会让人以为 P2-a 被禁）
        for f in ("actions.js", "core.js"):
            p = WEB / "shell" / f
            t = p.read_text(encoding="utf-8", newline="")
            if t.count(HDR_OLD) == 0:          # ⚠️ 幂等：已经订正过就跳过（⛔ 别 assert ⇒ 重跑会把整批中断）
                print(f"  （shell/{f} 的 §23 措辞已订正过，跳过）")
                continue
            assert t.count(HDR_OLD) == 1, f"⛔ {f} 的 §23 旧措辞锚点数 = {t.count(HDR_OLD)}"
            p.write_text(t.replace(HDR_OLD, to_nl(HDR_NEW, "\r\n" in t), 1), encoding="utf-8", newline="")
            print(f"  同批订正：shell/{f} 的 §23 措辞（过宽 ⇒ 收窄成「只管原型切片」）")

    print(f"⇒ 已写 shell/{name} ＋ index.html 加 `<script src>` ＋ main.py 加路由")
    return 0


if __name__ == "__main__":
    sys.exit(main())
