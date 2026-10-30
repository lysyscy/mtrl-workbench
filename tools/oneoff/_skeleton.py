"""大件的**骨架表**（一次性 · 只读 · 2026-10-02 立 · 出处 = `/retro` 复盘的候选 6）。

**为什么要有它**：读取大文件前先列出结构，缩小需要阅读的范围。
想先看清它们**有什么**时，对着整份文件 grep / 整份读都很贵 ——
实测：一次结构枚举就把工具的输出缓冲撑爆（提示 `Search output exceeded internal buffer limit … results are partial`
⇒ 只回了一部分，**而它看起来像"就这些"**）。⇒ 用本件拿一张**骨架表**（行号 ＋ 种类 ＋ 名字 ＋ 首行说明），再看哪几段值得读。

**它认什么**：
  · `.py`  ⇒ **AST**：模块 docstring 首行 ＋ 顶层 `def` / `class` / 赋值（含装饰器、类方法、docstring 首行）
  · `.js`  ⇒ 顶层 `function` / `const X=` / `V.<页> =` / `BIND.<页>` / `ACT.<动作>` ＋ 段横幅注释
  · `.html`⇒ 段横幅注释（`<!-- ==== -->` / `/* ==== */`）＋ `<section` / `<script`

用法：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_skeleton.py <文件> [更多文件…]
⚠️ **只读**：不写盘、不改任何文件。
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]


def _head(text: str | None, n: int = 64) -> str:
    """取一句"这是什么"（docstring / 注释首行）—— 压平空白、截断。"""
    if not text:
        return ""
    line = " ".join(str(text).strip().splitlines()[:1]).strip()
    return ("  —— " + (line[:n] + "…" if len(line) > n else line)) if line else ""


def py_skeleton(path: pathlib.Path) -> list[str]:
    src = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(src)
    out = [f"# {path.as_posix()}（{len(src.splitlines())} 行 · Python）",
           "  模块说明" + _head(ast.get_docstring(tree), 90)]

    def walk(node: ast.AST, depth: int) -> None:
        for ch in getattr(node, "body", []):
            ind = "  " * (depth + 1)
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                deco = "".join(f"@{d.id if isinstance(d, ast.Name) else '…'} "
                               for d in ch.decorator_list)
                k = "async def" if isinstance(ch, ast.AsyncFunctionDef) else "def"
                out.append(f"{ind}{ch.lineno:>5}  {k:<9} {ch.name}{_head(ast.get_docstring(ch))}"
                           + (f"   [{deco.strip()}]" if deco else ""))
            elif isinstance(ch, ast.ClassDef):
                out.append(f"{ind}{ch.lineno:>5}  {'class':<9} {ch.name}{_head(ast.get_docstring(ch))}")
                walk(ch, depth + 1)
            elif isinstance(ch, (ast.Assign, ast.AnnAssign)):
                tg = ch.targets[0] if isinstance(ch, ast.Assign) else ch.target
                name = tg.id if isinstance(tg, ast.Name) else "…"
                out.append(f"{ind}{ch.lineno:>5}  {'常量':<9} {name}")
            elif isinstance(ch, ast.Import | ast.ImportFrom):
                continue
        return None

    walk(tree, 0)
    return out


BANNER = re.compile(r"(?:/\*\s*=+|<!--\s*=+)(.*?)(?:\*/|-->)")


def js_like_skeleton(path: pathlib.Path) -> list[str]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    kind = "HTML" if path.suffix == ".html" else "JS"
    out = [f"# {path.as_posix()}（{len(lines)} 行 · {kind}）"]
    pats = [
        ("function", re.compile(r"^function\s+([\w$]+)")),
        ("const   ", re.compile(r"^const\s+([\w$]+)\s*=")),
        ("let     ", re.compile(r"^let\s+([\w$]+)\s*=")),
        ("V.页    ", re.compile(r"^V\.([\w$]+)\s*=")),
        ("BIND.页 ", re.compile(r"^BIND\.([\w$]+)\s*=")),
        ("ACT.动作", re.compile(r"^\s{0,2}([\w$]+)\s*:\s*(?:async\s*)?\(")),
        ("section ", re.compile(r"<section[^>]*id=\"([^\"]+)\"")),
    ]
    for i, ln in enumerate(lines, 1):
        m = BANNER.search(ln)
        if m:
            out.append(f"        {'▲ 段':<8} {m.group(1).strip().strip('= ')[:70]}")
            continue
        for tag, pat in pats:
            m2 = pat.match(ln)
            if m2:
                out.append(f"{i:>6}  {tag:<9} {m2.group(1)}")
                break
    return out


def main(argv: list[str]) -> int:
    files = [a for a in argv[1:] if not a.startswith("-")]
    if not files:
        print(__doc__.split("用法：")[1].strip().splitlines()[0])
        return 2
    for rel in files:
        p = pathlib.Path(rel)
        if not p.is_absolute():
            p = (REPO / rel) if (REPO / rel).exists() else pathlib.Path.cwd() / rel
        if not p.exists():
            print(f"# ⛔ 找不到：{rel}")
            continue
        if p.suffix == ".py":
            print("\n".join(py_skeleton(p)))
        elif p.suffix in (".js", ".html"):
            print("\n".join(js_like_skeleton(p)))
        else:
            print(f"# ⚠️ 不支持的后缀：{p.suffix}（本件只认 .py / .js / .html）")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
