"""`TAIL-204` 第 1 步（乙 主体）—— **`.workbuddy/` ⇒ `.codebuddy/` 的"全库活件改路径"那一半**。

守什么：`plans` / `work` / `backups` 三个子夹**搬走之后**，全库**还在用旧路径**的地方必须同批改掉
（⛔ 不改 = `T3` 幽灵路径红 / `T18` 常量体检红 / 产包脚本指错 ⇒ 目标机报"没有基线"）。

⛔ **有意不动的**（每一条都有理由，⛔ 别"顺手"改）：
- `tools/oneoff/**`                     —— 一次性脚本的**历史留痕**（跑过的台账都在，改了才是失真）；
- `<plans>/归档-*.md` · `<plans>/archive/**` · `<memory>/journal/**` —— 留痕档，同上
  （⚠️ 这三类**按标记**判、⛔ 不按前缀判 —— 见 `EXCLUDE_MARKS` 上方踩过的那个坑）；
- **`.workbuddy/memory/**` 的引用**      —— 记忆是**第 2 步**才搬 ⇒ 本步动了会**静默指到 IDE 侧同名件**
                                            （`.codebuddy/memory/MEMORY.md` 已存在、且是**另一份**文件）；
- **`.workbuddy/scratch`**              —— 第 7 步取消；本步它**还在原处**；
- **`<用户目录>\\.workbuddy\\binaries`**  —— 那是**宿主家目录**（Node 运行时），与仓内 `.workbuddy/` **同名不同物**；
                                            ⇒ 含 `Administrator` 的整行**一律跳过**。

用法：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail204_move.py           # 干跑（逐件打印命中数）
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail204_move.py --write   # 落盘

⚠️ 一律 **bytes 级**替换（⛔ 不走 `text` 模式）—— 保住 CRLF 与 `.ps1` 的 UTF-8 BOM。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: `.workbuddy` 后面**不是**这些的，才改（负向断言）：
#:   `memory`（第 2 步）· `binaries`（宿主家目录的 Node）· `scratch`（第 7 步取消，本步仍在原处）
#: ⚠️⚠️ 2026-10-01 **当场踩过的第二个坑**：只挡"字面量"写法（`.workbuddy/memory`）**远远不够** ——
#:    `Path` 拼接写法 `ROOT / ".workbuddy" / "memory"` 里，`.workbuddy` 后面紧跟的是**引号**
#:    ⇒ 第一版负向断言**放行**了它 ⇒ **10 处被误改**（`memory` 7 · `scratch` 3）
#:    ⇒ 症状 = `T12` 突然多报 **9 条黄**（它跑去扫了 **IDE 侧那份同名记忆** `.codebuddy/memory`）。
#:    ⇒ 两种写法**都得挡**：① 字面量 `[/\\]xxx` ② 引号拼接 `['"] * / * ['"]xxx['"]`。
RE = re.compile(
    rb"\.workbuddy"
    rb"(?![/\\](?:memory|binaries|scratch))"
    rb"(?!['\"]\s*/\s*['\"](?:memory|binaries|scratch)['\"])"
)
#: 整行含它就跳过（宿主家目录写死路径的另一处写法：`C:/Users/Administrator/.workbuddy/...`）
SKIP_LINE = b"Administrator"

#: ⛔ 整件排除（历史留痕 / 不属于本步）。
#: ⚠️⚠️ 2026-10-01 **当场踩过的坑**：最初写成**带前缀**的形式（`.workbuddy/plans/归档-` 等）——
#:    而 `git mv` 之后路径变成 `.codebuddy/plans/归档-…` ⇒ **前缀全都不匹配** ⇒
#:    干跑（搬之前）报 69 件、落盘（搬之后）却写了 **77 件**，多改的 **8 件恰好是留痕档**
#:    （归档 7 ＋ `archive/` 1，共 99 处）。⇒ 判据改成**按标记**判，⛔ 不再依赖前缀
#:    （同族教训 = `_ps_bom.py` 搬目录后 `parent.parent` 指错 ⇒ 永久打印 "no .ps1 found"）。
EXCLUDE_MARKS = ("/归档-", "/archive/", "/journal/")
EXCLUDE_PREFIX = ("tools/oneoff/",)

#: ⭐ 不在 git 里、但**我每会话都要读**的件（改了才不会被旧路径带偏）—— 第 2 步会再规整一次
EXTRA: tuple[str, ...] = (".codebuddy/memory/MEMORY.md", ".codebuddy/memory/IDE-细节.md")


def _tracked() -> list[str]:
    """→ 进 git 的件（POSIX 相对路径）。⚠️ `-z` ⇒ 中文路径**不转义**（⛔ 别用带引号的输出）。"""
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                       capture_output=True, check=True)
    return [p for p in r.stdout.decode("utf-8").split("\0") if p]


def _plan() -> tuple[list[tuple[Path, int]], int, list[str]]:
    """→ ([(件, 命中数)], 总命中, 跳过的件名)。"""
    hits: list[tuple[Path, int]] = []
    total = 0
    skipped: list[str] = []
    for rel in _tracked():
        if rel.startswith(EXCLUDE_PREFIX) or any(m in f"/{rel}" for m in EXCLUDE_MARKS):
            continue
        p = ROOT / rel
        try:
            data = p.read_bytes()
        except OSError:
            continue
        if b".workbuddy" not in data:
            continue
        n = _count(data)
        if n:
            hits.append((p, n))
            total += n
    for rel in EXTRA:
        p = ROOT / rel
        if not p.is_file():
            continue
        n = _count(p.read_bytes())
        if n:
            hits.append((p, n))
            total += n
            skipped.append(f"{rel}（不在 git —— 已一并处理）")
    return hits, total, skipped


def _count(data: bytes) -> int:
    n = 0
    for line in data.splitlines(keepends=True):
        if SKIP_LINE in line:
            continue
        n += len(RE.findall(line))
    return n


def _transform(data: bytes) -> bytes:
    out = []
    for line in data.splitlines(keepends=True):
        if SKIP_LINE in line:
            out.append(line)
            continue
        out.append(RE.sub(b".codebuddy", line))
    return b"".join(out)


def main(argv: list[str]) -> int:
    write = "--write" in argv
    hits, total, notes = _plan()
    print(f"{'落盘' if write else '干跑'} —— 命中 {len(hits)} 件 · 共 {total} 处 `.workbuddy` ⇒ `.codebuddy`")
    for p, n in hits:
        print(f"  {n:3d}  {p.relative_to(ROOT).as_posix()}")
    for s in notes:
        print(f"       ⭐ {s}")
    if not write:
        print("\n（干跑不动盘 —— 加 `--write` 才落盘）")
        return 0
    changed = 0
    for p, _ in hits:
        old = p.read_bytes()
        new = _transform(old)
        assert new != old, f"{p} 命中却无变化（正则与实际不符）"
        assert len(new.splitlines()) == len(old.splitlines()), \
            f"{p} 行数变了（⛔ 只该改路径字面量）"
        p.write_bytes(new)
        changed += 1
    print(f"\n已写 {changed} 件。")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
