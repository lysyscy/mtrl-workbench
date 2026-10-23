"""Read-only name-based W2 hints; inspect actual callers before acting."""
from __future__ import annotations
import argparse
import ast
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/'backend/app'
EXPECTED=ROOT/'tools/wiring_expected.txt'
FRAMEWORK_DECORATOR_HINTS=('router.','app.','page_router.','actions_router.','api_router.',
                           'staticmethod','classmethod','property','abstractmethod','pytest.')
HTTP_METHODS=frozenset({'get','post','put','delete','patch','head','options'})

def rel(p: Path) -> str:
    return str(p).replace("\\", "/").split("mtrl-workbench/")[-1]

@dataclass
class Def:
    name: str
    kind: str                      # func / async / class
    file: str
    line: int
    end_line: int
    doc: str = ""
    decorators: tuple[str, ...] = ()

    @property
    def public(self) -> bool:
        return not self.name.startswith("_")

    @property
    def framework_wired(self) -> bool:
        for d in self.decorators:
            if d.startswith(FRAMEWORK_DECORATOR_HINTS):
                return True
            # ⭐ 局部 router 的 HTTP 方法装饰器（`r.get` / `rr.post` …）—— 同属框架装配
            if "." in d and d.rsplit(".", 1)[1] in HTTP_METHODS:
                return True
        return False

def decorator_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        return decorator_name(node.func)
    if isinstance(node, ast.Attribute):
        return f"{decorator_name(node.value)}.{node.attr}"
    if isinstance(node, ast.Name):
        return node.id
    return ""

def scan(paths: list[Path]) -> tuple[list[Def], dict[str, list[tuple[str, int]]]]:
    """扫生产代码 → `(定义列表, 引用位置表)`。

    ⚠️ **只收表达式里的 `Name`/`Attribute`** —— `import` 语句**不算装配**
       （`alias` 节点不是 `Name`）；这正是要抓的形态：**导入了却没调用**。
    ⭐ **2026-09-28 补：别名也算引用** —— `from x import build_router as build_imp_router` 之后写
       `build_imp_router(...)`，旧版只认 `build_router` 这个裸名 ⇒ 把**在用**的函数误判成死代码
       （实测：`import_kit.api.build_router`/`domains_router` 被四个域与 `main.py` 以别名调用）。
    """
    defs: list[Def] = []
    refs: dict[str, list[tuple[str, int]]] = defaultdict(list)
    for p in paths:
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        f = rel(p)
        # ⭐ 本件内的别名表：`import x as y` / `from a.b import c as d` ⇒ `y`/`d` 指的是原名。
        alias: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for a in node.names:
                    if a.asname:
                        alias[a.asname] = a.name.split(".")[-1]
            elif isinstance(node, ast.Import):
                for a in node.names:
                    if a.asname:
                        alias[a.asname] = a.name.split(".")[-1]
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                kind = "class" if isinstance(node, ast.ClassDef) else (
                    "async" if isinstance(node, ast.AsyncFunctionDef) else "func"
                )
                defs.append(Def(
                    name=node.name, kind=kind, file=f, line=node.lineno,
                    end_line=getattr(node, "end_lineno", node.lineno) or node.lineno,
                    doc=ast.get_docstring(node) or "",
                    decorators=tuple(decorator_name(d) for d in node.decorator_list),
                ))
            elif isinstance(node, ast.Name):
                refs[alias.get(node.id, node.id)].append((f, node.lineno))
            elif isinstance(node, ast.Attribute):
                refs[node.attr].append((f, node.lineno))
    return defs, refs

def load_expected() -> set[str]:
    if not EXPECTED.exists():
        return set()
    out: set[str] = set()
    for line in EXPECTED.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            out.add(s)
    return out

def external_refs(d: Def, refs: dict[str, list[tuple[str, int]]]) -> list[tuple[str, int]]:
    """该定义**在别处**被引用的位置（排除自己函数体内的自引用）。"""
    return [
        (f, ln) for f, ln in refs.get(d.name, ())
        if not (f == d.file and d.line <= ln <= d.end_line)
    ]

def candidates(defs, refs, expected):
    """W2 is a name-based hint, not proof of a bug or permission to delete."""
    return [d for d in defs if d.public and not d.framework_wired
            and not external_refs(d, refs) and f'W2 {d.file}:{d.name}' not in expected]


def main() -> int:
    parser = argparse.ArgumentParser(description='Name-based unused public definition hints (W2)')
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    paths = sorted(APP.rglob('*.py'))
    defs, refs = scan(paths)
    expected = load_expected()
    unused = candidates(defs, refs, expected)
    keys = {f'W2 {d.file}:{d.name}' for d in defs
            if d.public and not d.framework_wired and not external_refs(d, refs)}
    stale = sorted(expected - keys)
    report = {'scanned_files': len(paths),
              'W2': [{'file': d.file, 'name': d.name, 'line': d.line} for d in unused],
              'stale_expected': stale}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f'W2: {len(unused)} unused-name candidates; inspect real callers before acting')
        for d in unused:
            print(f'{d.file}:{d.line} {d.name}')
        for key in stale:
            print(f'Stale hint exclusion: {key}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
