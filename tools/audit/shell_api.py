"""壳的**语义口径**（唯一出口）—— ⭐ `TAIL-219` 批 1（2026-10-03）。

## 为什么有它
壳是一坨**纯文本**（`shell_source.SHELL` = `index.html` ＋ `shell/*.js` 拼起来的全文）⇒
问它"语义"（某页 / 某函数 / 某条动作 / 某张常量表长什么样）本来**没有窗口**可问 ⇒
13 件各写"从字符串里按字面剪一段"的剪刀（实测 **16 把**，剪同一件事的算法还不一样）。
⇒ 本件把语义收成一扇**按名字取**的窗（⛔ 不给正则、⛔ 不给标记串）。
⚠️ 本件**不是第二套读取出口** —— 读字节仍归 `shell_source`（件清单 / 加载顺序的唯一主人）；
本件只在它之上加"认结构"的一层。⛔ 别在这儿再写一份 `read_shell`。

## 对外暴露（按名字取）
`text()`（归一化全文）· `visible_text()`（剥注释后的全文）·
`slices_of_lines(lines)`（逐页切片的**唯一算法** —— `ui_parity.slices()` 也走它）·
`pages()` · `page_map()` / `page_slice(page)`（某页源码）·
`func_body(name)`（函数整段声明）· `act_entry(name)`（`ACT` 里某一条）· `const_obj(name)`（`const X = {…}`）。

## ⛔ 四条纪律（都是踩过的）
1. **只读** —— ⛔ 不写壳、⛔ 不搬 `V.*` 切片（搬了 `shell_verify` 会多出一堆无谓差异）。
2. **先在"剥注释后的文本"里定位** —— 2026-10-03 实测踩到：注释里写着 `const ACT={…}` ⇒
   直接按字面找**看到的是注释那处**（配平当场收到 1 个字符）⇒ 定位一律走 `_scan_src()`
   （注释**逐字符换空格、保留换行与长度** ⇒ 偏移行号对齐，取正文仍回原文）。
3. **认结构** —— 配平必须跳过字符串 / 模板串 / 注释 / 正则（壳里真有大正则还夹着引号：
   `view.js` 的 `splitRows` / `vsTableHits`）⇒ ⛔ 别退回"找下一个 `\\n}`"（那就把 16 把脆剪刀并成一把更脆的）。
4. **找不到 / 配不平 ⇒ 显式抛** —— ⛔ 绝不静默回空（"空输出 ≠ 通过"是本仓反复踩的坑）。

## ⚠️ 已知口径差异（照实记 · ⛔ 别当 bug 顺手改）
`page_slice` 用**行边界**（＝ `ui_parity.slices()` 那套 · 已验）⇒ 切片**含页尾横幅注释**；
`func_body` / `act_entry` / `const_obj` 用**结构配平** ⇒ **不含**尾部注释。
行边界遇到"页体里有列 0 的 `const `"会提前截断（现壳没有 · `U3` 一直绿）⇒ 真要治另立一件。
"""

from __future__ import annotations

import re
import sys
from functools import lru_cache

from shell_source import read_shell, strip_comments

# ── 0 · 归一化的壳全文 ────────────────────────────────────────────────


@lru_cache(maxsize=1)
def text() -> str:
    """壳全文（CRLF ⇒ LF）。

    ⚠️ 带缓存 —— 变异脚本**临时改盘上的壳字节**时，本进程里请先 `text.cache_clear()`
       （它们另起子进程跑 pytest ⇒ 正常不受影响；同进程内改字节才是坑）。
    """
    return read_shell().replace("\r\n", "\n")


def visible_text() -> str:
    """剥注释后的全文（`html=True` 连 HTML 注释一起剥）—— "上屏文本"的近似。"""
    return strip_comments(text(), html=True)


# ── 1 · JS 感知的扫描器（认 字符串 / 模板串 / 注释 / 正则）──────────────

_QUOTES = "'\"`"
#: 正则字面量的**前一个非空白字符**落在这些里 ⇒ 那个 `/` 是正则而不是除号
_REGEX_PREV = set("(=:[!&|?{};,+*%~^<>")
#: 前一个词是这些 ⇒ 后面的 `/` 也是正则（`return /re/` 那类）
_REGEX_PREV_WORD = {"return", "typeof", "case", "in", "of", "instanceof", "do", "else", "void", "delete"}


def _prev_word(s: str, i: int) -> str:
    """`s[:i]` 里紧邻的非空白**词**（用于判 `return /re/`）。"""
    j = i - 1
    while j >= 0 and s[j] in " \t":
        j -= 1
    k = j
    while k >= 0 and (s[k].isalnum() or s[k] in "_$"):
        k -= 1
    return s[k + 1:j + 1]


def _regex_ok(s: str, i: int) -> bool:
    """`s[i] == '/'` ⇒ 判它是"正则字面量"还是"除号"（标准启发式）。"""
    j = i - 1
    while j >= 0 and s[j] in " \t\n":
        j -= 1
    if j < 0:
        return True
    if s[j] in _REGEX_PREV:
        return True
    return _prev_word(s, i) in _REGEX_PREV_WORD


def _skip_string(s: str, i: int) -> int:
    """`s[i]` 是引号（`'` `"` 反引号）⇒ 返回该字面量**之后**的下标（模板串的 `${…}` 递归跳）。"""
    q = s[i]
    n = len(s)
    i += 1
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if q == "`" and c == "$" and i + 1 < n and s[i + 1] == "{":
            i = _match(s, i + 1, "{", "}")     # `${ … }` 里又是 JS ⇒ 递归配平
            continue
        if c == q:
            return i + 1
        i += 1
    raise ValueError(f"字符串没闭合：[…{s[max(0, i - 40):i]!r}]")


def _skip_regex(s: str, i: int) -> int:
    """`s[i] == '/'` 且判定为正则 ⇒ 跳到标志位之后（字符类 `[…]` 里的 `/` 不算结束）。"""
    n = len(s)
    i += 1
    in_cls = False
    while i < n:
        c = s[i]
        if c == "\\":
            i += 2
            continue
        if c == "\n":
            return i                            # 正则不许跨行 ⇒ 判错了，原样返回（保险）
        if c == "[":
            in_cls = True
        elif c == "]":
            in_cls = False
        elif c == "/" and not in_cls:
            i += 1
            while i < n and s[i].isalpha():
                i += 1
            return i
        i += 1
    return n


def _match(s: str, i: int, open_ch: str, close_ch: str) -> int:
    """`s[i] == open_ch` ⇒ 返回与之配平的 `close_ch` **之后**的下标。

    ⚠️ **跳过**字符串 / 模板串 / 注释 / 正则 —— ⛔ 别改成"数 `{` 与 `}`"（那正是要治的脆剪刀）。
    """
    if i >= len(s) or s[i] != open_ch:
        raise ValueError(f"`_match` 期望 {open_ch!r}，实到 {(s[i] if i < len(s) else '<EOF>')!r}")
    depth = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in _QUOTES:
            i = _skip_string(s, i)
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            j = s.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == "/" and _regex_ok(s, i):
            i = _skip_regex(s, i)
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError(f"`{open_ch}{close_ch}` 没配平：[…{s[max(0, i - 60):i]!r}]")


def _scan_value(s: str, i: int) -> int:
    """从 `i` 起扫一个**对象成员的值**；返回它在**同一层**遇到 `,` 时的下标（或到末尾）。

    跳过字符串 / 注释 / 正则；`([{` 与 `)]}` **同层计数**。
    """
    depth = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c in _QUOTES:
            i = _skip_string(s, i)
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "/":
            j = s.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and s[i + 1] == "*":
            j = s.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == "/" and _regex_ok(s, i):
            i = _skip_regex(s, i)
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth > 0:
                depth -= 1
        elif c == "," and depth == 0:
            return i
        i += 1
    return n


def _blank_comments(src: str) -> str:
    """把注释**逐字符换成空格**（⛔ 保留换行）⇒ 长度与行号都和原文对齐，可拿偏移回原文取正文。

    ⚠️ 为什么不用 `shell_source.strip_comments`：那条**保留换行但删字符** ⇒ 偏移全变，
       没法用它定位后再回原文切片。本函数是"同长版"（用途不同，不是第二份剥注释口径）。
    """
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in _QUOTES:
            i = _skip_string(src, i)
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            end = n if j < 0 else j + 2
            for k in range(i, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end
            continue
        if src.startswith("<!--", i):                    # `index.html` 里的 HTML 注释
            j = src.find("-->", i + 4)
            end = n if j < 0 else j + 3
            for k in range(i, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end
            continue
        if c == "/" and _regex_ok(src, i):
            i = _skip_regex(src, i)
            continue
        i += 1
    return "".join(out)


@lru_cache(maxsize=1)
def _scan_src() -> str:
    """**定位用**的壳文本（注释已置空 · 与 `text()` 同长同换行）—— ⛔ 只许内部用，
    对外给出去的是**原文**切片（别把置空版当"剥注释文本"用，那是 `visible_text()`）。"""
    return _blank_comments(text())


def _src(source: str | None) -> tuple[str, str]:
    """返回 `(取正文用的原文, 定位用的置空文本)`；`source` 只给判据喂合成文本用。"""
    if source is None:
        return text(), _scan_src()
    return source, _blank_comments(source)


# ── 2 · 逐页切片（**唯一算法**）────────────────────────────────────────

#: 切片起点：行首 `V.<名字> =`
_VIEW_RE = re.compile(r"^V\.([A-Za-z0-9_]+)\s*=")
#: 切片终点：行首的下一个顶层声明
_END_RE = re.compile(r"^(V\.[A-Za-z0-9_]+\s*=|BIND\.|const |function |let |var )")


def slices_of_lines(lines: list[str]) -> dict[str, list[str]]:
    """逐页切片（**唯一算法**）：行首 `V.<名>=` 起，到**下一个顶层声明行**止。

    ⚠️ 本函数**从 `ui_parity.slices()` 原样搬来**（2026-10-03 `TAIL-219` 批 1）——
       行为**逐字节不变**（`ui_parity.slices()` 现在只是转发它）。⛔ 别在这儿"顺手改好"：
       它已被 `U3` ＋ 判据点钉着；要改算法 = 单独立件、先出对照。
    ⚠️ 含页尾的**横幅注释**（到下一个顶层声明为止）—— 这是既有口径，照实记。
    """
    out: dict[str, list[str]] = {}
    cur: str | None = None
    for ln in lines:
        m = _VIEW_RE.match(ln)
        if m:
            cur = m.group(1)
            out[cur] = [ln]
            continue
        if cur is None:
            continue
        if _END_RE.match(ln):
            cur = None
            continue
        out[cur].append(ln)
    return out


def page_map() -> dict[str, str]:
    """`页名 → 切片源码`（页名与切片**同一算法** —— 就是 `slices_of_lines`）。"""
    return {k: "\n".join(v) for k, v in slices_of_lines(text().split("\n")).items()}


def pages() -> list[str]:
    """页名清单（文档顺序）—— ⛔ 与切片同源（别另写一条正则）。"""
    return list(page_map())


def page_slice(page: str) -> str:
    """某页的源码。⛔ 找不到 ⇒ 抛（带现有页名，便于当场分清是名字写错还是壳改了）。"""
    m = page_map()
    if page not in m:
        raise LookupError(f"壳里没有 `V.{page}=` 切片（现有：{', '.join(sorted(m))}）")
    return m[page]


# ── 3 · 函数体 / 动作条 / 常量表（认结构）──────────────────────────────


def func_body(name: str, *, source: str | None = None) -> str:
    """壳里 `[async] function <name>(…) {…}` 的**整段声明**（含函数名与花括号）。

    ⚠️ `source` 只给**判据**喂合成文本用（默认 = 真壳）；⛔ 别在业务代码里传它。
    """
    src, scan = _src(source)
    m = re.search(rf"(?m)^[ \t]*(?:async\s+)?function\s+{re.escape(name)}\s*\(", scan)
    if not m:
        raise LookupError(f"壳里找不到 `function {name}(`（形态变了就同批改调用方）")
    p = scan.index("(", m.end() - 1)
    j = _match(scan, p, "(", ")")               # 参数表（可能是解构 `({a,b})`）
    k = j
    while k < len(scan) and scan[k] in " \t\n":
        k += 1
    if k < len(scan) and scan[k] == "{":
        return src[m.start():_match(scan, k, "{", "}")]
    # 无花括号体（`function f()` 后直接表达式，罕见）⇒ 扫到同层 `;` 或换行
    e = k
    depth = 0
    while e < len(scan):
        c = scan[e]
        if c in _QUOTES:
            e = _skip_string(scan, e)
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth > 0:
                depth -= 1
        elif depth == 0 and c in ";\n":
            break
        e += 1
    return src[m.start():e]


def act_entry(name: str, *, source: str | None = None) -> str:
    """壳里 `const ACT={ … }` 中**某一条动作**的源码（从行首缩进到该成员结束）。

    ⚠️ 必须**只取这一条** —— 只写「壳里含 `API.m09Add(`」是**假绿**：
       同名调用在 `api.js` 的客户端定义里也有一份，把动作那处变异掉照样能通过。
    """
    src, scan = _src(source)
    m = re.search(r"(?m)^const\s+ACT\s*=\s*\{", scan)
    if not m:
        raise LookupError("壳里找不到 `const ACT={`（列 0 定义）")
    b = scan.index("{", m.end() - 1)
    e = _match(scan, b, "{", "}")               # `}` 之后
    inner = src[b + 1:e - 1]
    em = re.search(rf"(?m)^\s{{2}}{re.escape(name)}\s*:", inner)
    if not em:
        raise LookupError(f"`ACT` 里找不到动作 `{name}`")
    end = _scan_value(_blank_comments(inner), em.end())
    return inner[em.start():end]


def const_obj(name: str, *, source: str | None = None) -> str:
    """壳里 `const <name> = {…}` 的**对象字面量本体（含花括号）**。

    ⚠️ 只认**列 0 的 `{…}` 定义** —— `const X = […]` / `new Set([…])` / 模板串**不归它**（抛）。
    """
    src, scan = _src(source)
    m = re.search(rf"(?m)^const\s+{re.escape(name)}\s*=\s*\{{", scan)
    if not m:
        raise LookupError(f"壳里找不到列 0 的 `const {name} = {{`（只认对象字面量）")
    b = scan.index("{", m.end() - 1)
    return src[b:_match(scan, b, "{", "}")]


# ── 4 · 人看一眼（**不是判据**）──────────────────────────────────────


def main() -> int:
    """`python tools/audit/shell_api.py` —— 人看一眼当前语义面（**不是判据**）。"""
    print(f"壳的语义面：{len(pages())} 页 ⇒ {', '.join(pages())}")
    for fn in ("boot", "render", "reloadM09"):
        print(f"  func_body({fn!r}) = {len(func_body(fn)):>6} 字符")
    for act in ("awfAdd", "awfAmt", "ordMove"):
        print(f"  act_entry({act!r}) = {len(act_entry(act)):>6} 字符")
    print(f"  const_obj('EXP_ROUTES') = {len(const_obj('EXP_ROUTES'))} 字符"
          f" · 全文 {len(text())} ⇒ 剥注释 {len(visible_text())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
