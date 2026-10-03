"""壳的**语义口径**（唯一出口）—— ⭐ `TAIL-219` 批 1＋2b（2026-10-03）。

## 为什么有它
壳是一坨**纯文本**（`shell_source.SHELL` = `index.html` ＋ `shell/*.js` 拼起来的全文）⇒
问它"语义"（某页 / 某函数 / 某条动作 / 某张常量表长什么样）本来**没有窗口**可问 ⇒
各件自写"从字符串里按字面剪一段"的剪刀（实测 **48 把 / 33 件** ＋ 就地取片 **103 处**）。
⇒ 本件把语义收成一扇**按名字取**的窗（⛔ 不给正则、⛔ 不给标记串）。
⚠️ 本件**不是第二套读取出口** —— 读字节仍归 `shell_source`（件清单 / 加载顺序的唯一主人）；
"认结构"（跳字符串/注释/正则、配平）归 **`tools/audit/jslex.py`**（2026-10-03 批 2b 拆出，本件只调它）。

## 对外暴露（按名字取）
`text()`（归一化全文）· `visible_text()`（剥注释后的全文）·
`slices_of_lines(lines)`（逐页切片的**唯一算法** —— `ui_parity.slices()` 也走它）·
`pages()` · `page_map()` / `page_slice(page)`（某页源码）·
`func_body(name)`（函数整段声明）· `act_entry(name)`（`ACT` 里某一条）· `const_obj(name)`（`const X = {…}`）。

## ⛔ 四条纪律（都是踩过的）
1. **只读** —— ⛔ 不写壳、⛔ 不搬 `V.*` 切片（搬了 `shell_verify` 会多出一堆无谓差异）。
2. **先在"剥注释后的文本"里定位** —— 实测踩到：注释里写着 `const ACT={…}` ⇒ 直接按字面找**看到的是注释那处**
   （配平当场收到 1 个字符）⇒ 定位一律走 `_scan_src()`（同长同换行的置空版）。
3. **认结构** —— 见 `jslex`；⛔ 别退回"找下一个 `\\n}`"。
4. **找不到 / 配不平 ⇒ 显式抛** —— ⛔ 绝不静默回空（"空输出 ≠ 通过"）。
⚠️ 另：`act_entry` 找成员**按"同层深度"找、⛔ 不按缩进** —— 实测壳里 `ACT` 的成员缩进 **1 与 2 空格混用**
   （` awfAdd:` 与 `  zipSfjc:` 并存）⇒ "钉 2 空格"会漏掉一半（批 2 换真实调用点时当场暴露）。

## ⚠️ 已知口径差异（照实记 · ⛔ 别当 bug 顺手改）
`page_slice` 用**行边界**（＝ `ui_parity.slices()` 那套 · 已验）⇒ 切片**含页尾横幅注释**；
`func_body` / `act_entry` / `const_obj` 用**结构配平** ⇒ **不含**尾部注释。
"""

from __future__ import annotations

import re
import sys
from functools import lru_cache

from jslex import blank_comments, match, scan_value, skip_string
from shell_source import read_shell, strip_comments

# ── 0 · 归一化的壳全文（＋ 定位用的"同长置空版"）────────────────────────


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


@lru_cache(maxsize=1)
def _scan_src() -> str:
    """**定位用**的壳文本（注释已置空 · 与 `text()` 同长同换行）—— ⛔ 只许内部用，
    对外给出去的是**原文**切片（别把置空版当"剥注释文本"用，那是 `visible_text()`）。"""
    return blank_comments(text(), html=True)


def _src(source: str | None) -> tuple[str, str]:
    """返回 `(取正文用的原文, 定位用的置空文本)`；`source` 只给判据喂合成文本用。"""
    if source is None:
        return text(), _scan_src()
    return source, blank_comments(source, html=True)


# ── 1 · 逐页切片（**唯一算法**）────────────────────────────────────────

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


# ── 2 · 函数体 / 动作条 / 常量表（认结构）──────────────────────────────


def func_body(name: str, *, source: str | None = None) -> str:
    """壳里 `[async] function <name>(…) {…}` 的**整段声明**（含函数名与花括号）。

    ⚠️ `source` 只给**判据**喂合成文本用（默认 = 真壳）；⛔ 别在业务代码里传它。
    """
    src, scan = _src(source)
    m = re.search(rf"(?m)^[ \t]*(?:async\s+)?function\s+{re.escape(name)}\s*\(", scan)
    if not m:
        raise LookupError(f"壳里找不到 `function {name}(`（形态变了就同批改调用方）")
    p = scan.index("(", m.end() - 1)
    j = match(scan, p, "(", ")")                # 参数表（可能是解构 `({a,b})`）
    k = j
    while k < len(scan) and scan[k] in " \t\n":
        k += 1
    if k < len(scan) and scan[k] == "{":
        return src[m.start():match(scan, k, "{", "}")]
    # 无花括号体（`function f()` 后直接表达式，罕见）⇒ 扫到同层 `;` 或换行
    e, depth = k, 0
    while e < len(scan):
        c = scan[e]
        if c in "'\"`":
            e = skip_string(scan, e)
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
    """壳里 `const ACT={ … }` 中**某一条动作**的源码（从行首到该成员结束）。

    ⚠️ 必须**只取这一条** —— 只写「壳里含 `API.m09Add(`」是**假绿**：
       同名调用在 `api.js` 的客户端定义里也有一份，把动作那处变异掉照样能通过。
    ⚠️ 找成员**按"同层深度"**（⛔ 不按缩进：壳里 ACT 缩进 1/2 空格混用；也防命中山层里的同名键）。
    """
    src, scan = _src(source)
    m = re.search(r"(?m)^const\s+ACT\s*=\s*\{", scan)
    if not m:
        raise LookupError("壳里找不到 `const ACT={`（列 0 定义）")
    b = scan.index("{", m.end() - 1)
    inner = src[b + 1:match(scan, b, "{", "}") - 1]
    key = re.compile(rf"[ \t]*{re.escape(name)}[ \t]*:")
    i, n, depth = 0, len(inner), 0
    while i < n:
        if depth == 0 and (i == 0 or inner[i - 1] == "\n"):
            km = key.match(inner, i)
            if km:
                return inner[i:scan_value(inner, km.end())]
        c = inner[i]
        if c in "'\"`":
            i = skip_string(inner, i)
            continue
        if c == "/" and i + 1 < n and inner[i + 1] == "/":
            j = inner.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and inner[i + 1] == "*":
            j = inner.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            if depth > 0:
                depth -= 1
        i += 1
    raise LookupError(f"`ACT` 里找不到动作 `{name}`")


def const_obj(name: str, *, source: str | None = None) -> str:
    """壳里 `const <name> = {…}` 的**对象字面量本体（含花括号）**。

    ⚠️ 只认**列 0 的 `{…}` 定义** —— `const X = […]` / `new Set([…])` / 模板串**不归它**（抛）。
    """
    src, scan = _src(source)
    m = re.search(rf"(?m)^const\s+{re.escape(name)}\s*=\s*\{{", scan)
    if not m:
        raise LookupError(f"壳里找不到列 0 的 `const {name} = {{`（只认对象字面量）")
    b = scan.index("{", m.end() - 1)
    return src[b:match(scan, b, "{", "}")]


# ── 3 · 人看一眼（**不是判据**）──────────────────────────────────────


def main() -> int:
    """`python tools/audit/shell_api.py` —— 人看一眼当前语义面（**不是判据**）。"""
    print(f"壳的语义面：{len(pages())} 页 ⇒ {', '.join(pages())}")
    for fn in ("boot", "render", "reloadM09"):
        print(f"  func_body({fn!r}) = {len(func_body(fn)):>6} 字符")
    for act in ("awfAdd", "zipSfjc", "expPivot"):       # ⚠️ 前一个 2 空格、后两个 1 空格（缩进混用）
        print(f"  act_entry({act!r}) = {len(act_entry(act)):>6} 字符")
    print(f"  const_obj('EXP_ROUTES') = {len(const_obj('EXP_ROUTES'))} 字符"
          f" · 全文 {len(text())} ⇒ 剥注释 {len(visible_text())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
