"""JS 文本的**小扫描器**（壳那点"认结构"的公共基础设施）—— ⭐ `TAIL-219` 批 2b（2026-10-03）。

## 为什么单独立件

壳的语义口径（`tools/audit/shell_api.py`）要做"配平"就必须能**跳过字符串 / 模板串 / 注释 / 正则**；
那段扫描器本身有 ~110 行，把 `shell_api` 顶到了 `T5` 的 400 行档（实测 398 → 加一件就超）
⇒ 照本仓"超预算先登记拆分"的口径，把它拆成**独立一件**：本件只干"在字符串上认结构"，⛔ 不读壳、⛔ 不知道壳是什么。

## ⛔ 三条纪律（都是踩过的）

1. **⛔ 别退回"数 `{` 与 `}`"** —— 壳里字符串/模板串/注释/正则里都有花括号：
   真例：`view.js` 的 `splitRows` 有 `/<(\\/?)(tr|tbody)\\b[^>]*>/gi`；`vsTableHits` 的正则里还夹着引号 `data-vs="[^"]*"`。
2. **⛔ 别把注释当空气** —— 注释里**写着** `const ACT={…}` 这种东西 ⇒ 定位前必须先 `blank_comments`
   （它把注释**逐字符换成空格、保留换行** ⇒ 长度与行号都不动，可拿偏移回原文取正文）。
3. **配不平 / 字面量没闭合 ⇒ 显式抛** —— ⛔ 不静默回空（"空输出 ≠ 通过"）。

⚠️ 本件**只认结构、不认语义**：它不知道"这是什么页 / 什么函数"。语义归 `shell_api.py`。
"""

from __future__ import annotations

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


def regex_ok(s: str, i: int) -> bool:
    """`s[i] == '/'` ⇒ 判它是"正则字面量"还是"除号"（标准启发式）。"""
    j = i - 1
    while j >= 0 and s[j] in " \t\n":
        j -= 1
    if j < 0:
        return True
    if s[j] in _REGEX_PREV:
        return True
    return _prev_word(s, i) in _REGEX_PREV_WORD


def skip_string(s: str, i: int) -> int:
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
            i = match(s, i + 1, "{", "}")      # `${ … }` 里又是 JS ⇒ 递归配平
            continue
        if c == q:
            return i + 1
        i += 1
    raise ValueError(f"字符串没闭合：[…{s[max(0, i - 40):i]!r}]")


def skip_regex(s: str, i: int) -> int:
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


def _skip_trivia(s: str, i: int) -> int:
    """跳过字符串 / 注释 / 正则；跳过 ⇒ 返回新下标；**不是**这些 ⇒ 返回原值（调用方自己处理）。"""
    c = s[i]
    if c in _QUOTES:
        return skip_string(s, i)
    n = len(s)
    if c == "/" and i + 1 < n and s[i + 1] == "/":
        j = s.find("\n", i)
        return n if j < 0 else j
    if c == "/" and i + 1 < n and s[i + 1] == "*":
        j = s.find("*/", i + 2)
        return n if j < 0 else j + 2
    if c == "/" and regex_ok(s, i):
        return skip_regex(s, i)
    return i


def match(s: str, i: int, open_ch: str, close_ch: str) -> int:
    """`s[i] == open_ch` ⇒ 返回与之配平的 `close_ch` **之后**的下标。

    ⚠️ **跳过**字符串 / 模板串 / 注释 / 正则 —— ⛔ 别改成"数 `{` 与 `}`"（那正是要治的脆剪刀）。
    """
    if i >= len(s) or s[i] != open_ch:
        raise ValueError(f"`match` 期望 {open_ch!r}，实到 {(s[i] if i < len(s) else '<EOF>')!r}")
    depth = 0
    n = len(s)
    while i < n:
        j = _skip_trivia(s, i)
        if j != i:
            i = j
            continue
        if s[i] == open_ch:
            depth += 1
        elif s[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError(f"`{open_ch}{close_ch}` 没配平：[…{s[max(0, i - 60):i]!r}]")


def scan_value(s: str, i: int) -> int:
    """从 `i` 起扫一个**对象成员的值**；返回它在**同一层**遇到 `,` 时的下标（或到末尾）。

    跳过字符串 / 注释 / 正则；`([{` 与 `)]}` **同层计数**。
    """
    depth = 0
    n = len(s)
    while i < n:
        j = _skip_trivia(s, i)
        if j != i:
            i = j
            continue
        c = s[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth > 0:
                depth -= 1
        elif c == "," and depth == 0:
            return i
        i += 1
    return n


def scan_stmt(s: str, i: int) -> int:
    """从 `i` 起扫**一条语句**；返回同层遇到 `;` **之后**的下标。

    ⚠️ 只在 `;` 停（⛔ 不在换行停）—— 壳里有**跨行的模板串拼接**（`` const X=`…` + `…`; ``）
       与跨行的数组/对象字面量；停在换行会当场截半。
    """
    depth = 0
    n = len(s)
    while i < n:
        j = _skip_trivia(s, i)
        if j != i:
            i = j
            continue
        c = s[i]
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth > 0:
                depth -= 1
        elif c == ";" and depth == 0:
            return i + 1
        i += 1
    raise ValueError(f"扫不到语句结束（`;`）：[…{s[max(0, i - 60):i]!r}]")


def blank_comments(src: str, *, html: bool = False) -> str:
    """把注释**逐字符换成空格**（⛔ 保留换行）⇒ 长度与行号都和原文对齐，可拿偏移回原文取正文。

    ⚠️ 与 `shell_source.strip_comments` 用途不同：那条**保留换行但删字符**（适合"人看"），
       本条**同长**（适合"定位后回原文切片"）—— ⇒ ⛔ 别当成两份"剥注释口径"。
    """
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c in _QUOTES:
            i = skip_string(src, i)
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            j = n if j < 0 else j
            _erase(out, i, j)
            i = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            end = n if j < 0 else j + 2
            _erase(out, i, end)
            i = end
            continue
        if html and src.startswith("<!--", i):         # `index.html` 里的 HTML 注释
            j = src.find("-->", i + 4)
            end = n if j < 0 else j + 3
            _erase(out, i, end)
            i = end
            continue
        if c == "/" and regex_ok(src, i):
            i = skip_regex(src, i)
            continue
        i += 1
    return "".join(out)


def _erase(out: list[str], a: int, b: int) -> None:
    """把 `out[a:b]` 抹成空格（**换行保留**）。"""
    for k in range(a, b):
        if out[k] != "\n":
            out[k] = " "
