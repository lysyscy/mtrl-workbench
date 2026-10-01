"""只读：`TAIL-210` 第 3 批**逐条清单**的取材件 —— 把候选词**逐处**连上下文打出来。

⭐ 与 `_text_audit9.py` 的分工：那件回答"**有多少行**"（按词分好、每词只给前 14 行），
   本件回答"**这一处到底写在什么句子里**"（每一处都给 ±70 字窗口 ＋ 标出**在不在字符串字面量里**）。
⛔ 只读、不判、不改。判"删/留/怎么改"按 `D29` ＋ 守则 §2.5 / §3.3。
⚠️ 剥注释走共用件 `tools/audit/shell_source.py::strip_comments`（保留换行 ⇒ 行号不错位）。
⚠️ "在引号里"＝**粗判**（逐字符跟 `'` / `"` / `` ` `` 的开关状态）—— 它只是帮人一把，
   命中一律要人眼复核（JS 里模板串、正则、转义都可能骗过它）。
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.audit.shell_source import parts_text, strip_comments  # noqa: E402

TERMS = ("后端", "接口", "落库", "落不了库", "写库", "解析", "phid", "幂等", "管线", "缓存", "字段名")
WIN = 70


def quote_spans(line: str) -> list[tuple[int, int]]:
    """粗判：返回本行里处在字符串字面量内的 [起, 止) 区间。"""
    spans: list[tuple[int, int]] = []
    q: str | None = None
    start = 0
    i = 0
    while i < len(line):
        c = line[i]
        if q is None:
            if c in "'\"`":
                q = c
                start = i
        else:
            if c == "\\":
                i += 2
                continue
            if c == q:
                spans.append((start, i + 1))
                q = None
        i += 1
    if q is not None:                      # 行尾仍未闭合（模板串跨行等）⇒ 到行尾为止
        spans.append((start, len(line)))
    return spans


def in_str(spans: list[tuple[int, int]], pos: int) -> bool:
    return any(a <= pos < b for a, b in spans)


def _docstring_nodes(tree: "ast.AST") -> set[int]:
    """收集**"文档字符串"式**节点的 id —— ⛔ 它们不是上屏文字（值无处可去，只是留痕）。

    = 所有**裸字符串语句**（`ast.Expr`，value 是 str 常量或 f-string）里的**字符串片段**。
    ⚠️ 不只 module/class/function 的 `body[0]`：**属性 docstring**（`x: T = v` 后面紧跟的那句）
    与"拿字符串当注释"的老写法都在此列 —— 实测（`TAIL-211`）不这么收会**假阳性**
    （`mod03_notice/service.py` 那个 `files:` 字段的文档就是被误报的那一处）。
    """
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, (ast.Constant, ast.JoinedStr)):
            for sub in ast.walk(node.value):
                if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                    out.add(id(sub))
    return out


def py_strings() -> None:
    """后端那一半：扫 `backend/app/**/*.py` 里**含候选词的字符串常量**（⛔ 不含文档字符串、⛔ 注释 AST 根本看不见）。"""
    print("══ ③ 后端**字符串常量**里含候选词的（ast 取 · ⛔ 不含文档字符串）")
    hits = 0
    for p in sorted((ROOT / "backend" / "app").rglob("*.py")):
        src = p.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            print(f"   ⚠️ {p}: 解析失败 {e}")
            continue
        skip = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in skip or not any(t in node.value for t in TERMS):
                continue
            hits += 1
            rel = p.relative_to(ROOT).as_posix()
            v = re.sub(r"\s+", " ", node.value)[:150]
            print(f"   {rel}:{node.lineno}  {v}")
    print(f"   合计 {hits} 处")


FACE = pathlib.Path("D:/工作/AI/PRD编写夹 - Workbuddy专用")
FACE_SKIP = (".bak", "_backup", "副本", "备份")


def face_dump() -> None:
    """交付面那一半（**只读**）：`--face <词>` ⇒ 只报含该词的活文件（⛔ 跳过 `.bak` / `_backup` / 副本）。

    ⚠️ 不给词 ⇒ 报**每个文件的命中行数**（先看分布，再看细节）。
    """
    want = sys.argv[sys.argv.index("--face") + 1] if sys.argv.index("--face") + 1 < len(sys.argv) else ""
    print(f"══ ④ 交付面活文件（⛔ 只读；跳过 .bak / _backup / 副本）  {FACE}"
          f"   词 = {want or '（不给词 ⇒ 只报分布）'}")
    total = 0
    for p in sorted(FACE.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in (".md", ".json", ".js", ".txt"):
            continue
        if any(s in p.name for s in FACE_SKIP):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel = p.relative_to(FACE).as_posix()
        lines = [(i, raw) for i, raw in enumerate(text.splitlines(), 1) if want and want in raw]
        if not want:
            c = text.count("落库") + text.count("后端") + text.count("phid")
            if c:
                print(f"   {c:4d} 次  {rel}")
            continue
        for i, raw in lines:
            total += 1
            print(f"   {rel}:{i}  {raw}")
    if want:
        print(f"   合计 {total} 行")


def codes_scan() -> None:
    """`TAIL-211` 取材件：按**形态**扫后端**字符串常量**里的「工程代号 / 工程侧文件名」。

    ⚠️ 只报、不判（先量假阳性 —— 「要判语义」的扫查会把判据逼关掉，本仓的既定教训）。
    ⛔ 文档字符串**跳过**（`DEV-J-01` 这种代号写在 docstring / 注释里是对的）。
    """
    import ast as _ast
    code_shapes = (r"（R\d+）", r"（D\d+）", r"（决策\s?[A-Z]?\d+", r"DEV-[A-Z]-\d+",
                   r"（ENT-\d+）", r"（API-0\d）", r"链路\s?[ABC]")
    doc_shapes = (r"ops[/\\]", r"见\s*ops", r"\.codebuddy", r"artifacts[/\\]", r"tools[/\\]", r"\.md\b")
    print("══ ⑤ 后端字符串常量 × 「工程代号 / 工程侧文件名」（ast 取 · ⛔ 跳过文档字符串）")
    n = 0
    for p in sorted((ROOT / "backend" / "app").rglob("*.py")):
        src = p.read_text(encoding="utf-8")
        try:
            tree = _ast.parse(src)
        except SyntaxError as e:
            print(f"   ⚠️ {p}: {e}")
            continue
        skip = _docstring_nodes(tree)
        for node in _ast.walk(tree):
            if not (isinstance(node, _ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in skip:
                continue
            v = node.value
            # ⚠️ 边界：**反引号包住的记号不算** —— 本仓「工程侧笔记」一律用反引号包标识符
            #    （真例：守卫表 `FORBIDDEN_TEXTS` 的墓碑值「（业务上无此数据，`DEV-R-03`）」）；
            #    而用户面上写代号**从不加反引号**（实测 9 处真缺陷无一例外）。
            v = re.sub(r"`[^`]*`", "", v)
            hit = [pat for pat in code_shapes + doc_shapes if re.search(pat, v)]
            if not hit:
                continue
            n += 1
            rel = p.relative_to(ROOT).as_posix()
            print(f"   {rel}:{node.lineno}  [{'|'.join(hit)}]  {re.sub(chr(92) + 's+', ' ', v)[:120]}")
    print(f"   合计 {n} 处")


def main() -> int:
    if "--codes" in sys.argv:
        codes_scan()
        return 0
    if "--py" in sys.argv:
        py_strings()
        return 0
    if "--face" in sys.argv:
        face_dump()
        return 0
    pages = [(n, strip_comments(t, html=n.endswith(".html"))) for n, t in parts_text()]
    total = 0
    for term in TERMS:
        hits: list[str] = []
        for name, text in pages:
            for i, raw in enumerate(text.splitlines(), 1):
                for m in re.finditer(re.escape(term), raw):
                    p = m.start()
                    lo, hi = max(0, p - WIN), min(len(raw), p + len(term) + WIN)
                    seg = raw[lo:p] + "【" + term + "】" + raw[p + len(term):hi]
                    seg = re.sub(r"\s+", " ", seg).replace("\\n", "⏎").replace("`", "′")
                    tag = "串" if in_str(quote_spans(raw), p) else "码"
                    hits.append(f"   [{tag}] {name}:{i}  …{seg}…")
        if hits:
            print(f"\n━━ 「{term}」共 {len(hits)} 处")
            for h in hits:
                print(h)
            total += len(hits)
    print(f"\n合计 {total} 处")
    return 0


if __name__ == "__main__":
    sys.exit(main())
