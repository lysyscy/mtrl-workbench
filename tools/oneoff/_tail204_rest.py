"""`TAIL-204` **第 3–5 步**（合流 ＋ 归档）—— 搬家与改引用，仍**干跑优先**。

  **第 3 步 · 工程文档合流**：`docs/*.md`（5 件）⇒ `ops/`；`docs/` 取消（一类一夹：工程文档只落 `ops/`）
  **第 4 步 · 留痕归一**：`.codebuddy/plans/归档-*.md`（7 件）⇒ `.codebuddy/plans/archive/`
  **第 5 步 · 备份归一**：`artifacts/delivery-backups/*` ⇒ `.codebuddy/backups/`（两个目录都不进 git ⇒ 文件系统搬）

⚠️ 与 `_tail204_mem.py` 同一族（同一次手术）—— ⛔ **不另立口径**：排除规则、bytes 级替换、两种写法都挡，全部照抄。
⛔ **有意不动**：`tools/oneoff/**`（历史留痕；⭐ **例外见 `REFS5`**）· 归档/`archive/`/`journal/`（留痕档）。

用法（每步都先干跑）：
    python tools/oneoff/_tail204_rest.py --step 3            # 干跑
    python tools/oneoff/_tail204_rest.py --step 3 --write    # 落盘（搬家 ＋ 改引用）
    … --step 4 / --step 5 同理
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DOCS = ("architecture", "changelog", "deployment", "modules", "delivery-surface")

#: 每步 =（搬家清单, 引用规则）
STEPS: dict[str, tuple[list[tuple[str, str]], tuple[tuple[bytes, bytes], ...]]] = {
    "3": (
        [(f"docs/{n}.md", f"ops/{n}.md") for n in DOCS],
        # ⚠️ 两种分隔符都覆盖（`.md` 里写 `/`、`.ps1` 里写 `\\`）
        [(rb"docs([/\\])(" + b"|".join(n.encode() for n in DOCS) + rb")\.md", rb"ops\1\2.md")],
    ),
    "4": (
        [],   # 归档-* 的清单在运行时现取（名字带日期）
        # ⚠️ `bytes` 字面量**不能放非 ASCII** ⇒ 中文一律 `.encode()`
        # ⚠️ 负向断言：⛔ 别把**已经在 `archive/` 里**的那 4 件再套一层（`plans/archive/归档-…`）
        [
            ("(?<!archive[/\\\\])plans([/\\\\])归档-".encode(), "plans\\1archive\\1归档-".encode()),
        ],
    ),
    "5": (
        [],
        [(rb"artifacts[/\\]delivery-backups", rb".codebuddy/backups")],
    ),
}

EXCLUDE_MARKS = ("/归档-", "/archive/", "/journal/")
EXCLUDE_PREFIX = ("tools/oneoff/",)
#: ⭐ **有意例外**：第 5 步要改的两个一次性脚本（施工图 §四-5 点名；它们的 `BACKUPS` 常量是**活引用**）
EXCEPT_FILES = ("tools/oneoff/_p4a_fbar.py", "tools/oneoff/_p4b_fbar.py")
EXTRA = (".codebuddy/memory/MEMORY.md", ".codebuddy/memory/细则.md", ".codebuddy/memory/IDE-细节.md")


def _tracked() -> list[str]:
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True)
    return [p for p in r.stdout.decode("utf-8").split("\0") if p]


def _skip(rel: str) -> bool:
    if rel in EXCEPT_FILES:
        return False
    return rel.startswith(EXCLUDE_PREFIX) or any(m in f"/{rel}" for m in EXCLUDE_MARKS)


def _plan_moves(step: str) -> list[tuple[str, str]]:
    if step == "4":
        return [(r, f".codebuddy/plans/archive/{Path(r).name}")
                for r in _tracked()
                if r.startswith(".codebuddy/plans/归档-")]
    if step == "5":
        d = ROOT / "artifacts" / "delivery-backups"
        return [(f"artifacts/delivery-backups/{p.name}", f".codebuddy/backups/{p.name}")
                for p in (d.iterdir() if d.is_dir() else [])]
    return STEPS[step][0]


def main(argv: list[str]) -> int:
    step = ""
    for i, a in enumerate(argv):
        if a == "--step":
            step = argv[i + 1]
    if step not in STEPS:
        print("用法：--step 3|4|5 [--write]")
        return 2
    write = "--write" in argv
    moves = _plan_moves(step)
    print(f"── 第 {step} 步 {'落盘' if write else '干跑'}")

    for src, dst in moves:
        print(f"   {'搬' if write else '[干跑]'} {src}  ->  {dst}")
        if not write:
            continue
        (ROOT / Path(dst).parent).mkdir(parents=True, exist_ok=True)
        if subprocess.run(["git", "-C", str(ROOT), "mv", src, dst],
                          capture_output=True).returncode != 0:
            (ROOT / src).rename(ROOT / dst)

    refs = STEPS[step][1]
    total, files = 0, []
    for rel in dict.fromkeys(list(_tracked()) + list(EXTRA)):
        if _skip(rel):
            continue
        p = ROOT / rel
        try:
            data = p.read_bytes()
        except OSError:
            continue
        new, n = _sub(data, refs)
        if n:
            files.append((rel, n))
            total += n
            if write:
                assert len(new.splitlines()) == len(data.splitlines()), f"{rel} 行数变了"
                p.write_bytes(new)
    for rel, n in files:
        print(f"   {n:3d}  {rel}")
    print(f"   引用：{'已改' if write else '将改'} {len(files)} 件 · {total} 处 · 搬家 {len(moves)} 项\n")
    return 0


def _sub(data: bytes, refs) -> tuple[bytes, int]:
    n = 0
    out = []
    for line in data.splitlines(keepends=True):
        if b"Administrator" in line:
            out.append(line)
            continue
        cur = line
        for pat, rep in refs:
            cur, k = re.subn(pat, rep, cur)
            n += k
        out.append(cur)
    return b"".join(out), n


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
