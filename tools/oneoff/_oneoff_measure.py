"""`TAIL-194` 量测：**`tools/oneoff/` 的件数 / 容量 / 被引用情况**（只读 · ⛔ 不改任何文件）。

**为什么必须"先查引用"**：口径写着「盲删 ⇒ 造**断链**」（`T3` 幽灵路径 / 交付面 `_links` 都会报）——
而 `tools/oneoff/` 里恰恰有很多件**被留痕 md、台账、设计件引用**（如 `_a175_measure.py` / `_tail189_*`）。
⇒ 处置前先分清「**被引用的**（留着）」与「**零引用的**（候选）」。

另外一件必须分清的：**它里面有一批"其实不是一次性"的** —— `_run_rulers.py`（收工闸门一把跑）·
`_ps_bom.py` / `_ps_parse_check.ps1`（PS 两条闸）· `_list_tails.py`（盘点）· `_page_measure.py`（逐页量测）
这些是**反复要跑的常驻工具** ⇒ ⛔ 别按"一次性"盲清（本件会把它们标出来）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_oneoff_measure.py`
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
ONEOFF = ROOT / "tools" / "oneoff"

#: ⭐ **常驻工具**（不是"一次性"）—— 收工闸门/口径会反复引用它们 ⇒ ⛔ 别按一次性处置
STANDING = (
    "_run_rulers.py", "_run_muts.py", "_ps_bom.py", "_ps_parse_check.ps1", "_list_tails.py",
    "_page_measure.py", "_prepush_sensitive.py", "_oneoff_measure.py",
)

_TEXT_EXT = {".md", ".py", ".ps1", ".txt", ".js", ".html", ".json", ".toml", ".ini", ".sql", ".mdc"}


def _tracked_text() -> dict[str, str]:
    """语料 = **跟踪件** ∪ **仓内的文书**（⚠️ 后者必须包含 —— `.codebuddy/memory/` 与
    `.workbuddy/backups/` **不入 git**，但恰恰引用了一批 oneoff 件；漏了它们 ⇒ 会把"其实有出处"
    的件误判成**零引用**（第一版就是这么错的，本仓的"假阴性"同族）。"""
    #: ⚠️⚠️ 必须带 `-c core.quotepath=false`：git 默认给**非 ASCII 路径加双引号并转义**
    #:   —— 实测 2026-10-01（`TAIL-204` 第 7 步真要跑本件时才发现）：`"tools\oneoff\_归档-20260930\清单.md"`
    #:   被当成字面路径 ⇒ `Path(...)` 直接 `OSError [WinError 123]` **把整支脚本打挂**。
    #:   ⇒ 本件此前**一直是坏的**（同族：本仓"量测件自己烂掉、而它不在任何闸门清单里"）。
    out = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files"],
                         cwd=str(ROOT), capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout
    rels = {r for r in out.splitlines() if r.strip()}
    skip_dirs = {".git", ".venv", "__pycache__", "node_modules"}
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in _TEXT_EXT:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if any(part in skip_dirs for part in p.relative_to(ROOT).parts):
            continue
        rels.add(rel)
    files: dict[str, str] = {}
    for rel in sorted(rels):
        if Path(rel).suffix.lower() not in _TEXT_EXT:
            continue
        try:
            files[rel] = (ROOT / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            pass
    return files


def main() -> int:
    corpus = _tracked_text()
    #: ⭐ 口径按**跟踪件**算（`__pycache__/*.pyc` 这种是本机产物、且不在版本库里 ⇒ 不算"堆着的件"）
    #: ⚠️ 同上：**必须** `-c core.quotepath=false`（否则 `_归档-*/` 里那份中文名的件会把本步打挂）。
    listed = subprocess.run(["git", "-c", "core.quotepath=false", "ls-files", "tools/oneoff"],
                            cwd=str(ROOT), capture_output=True,
                            text=True, encoding="utf-8", errors="replace").stdout
    all_files = sorted((ROOT / r) for r in listed.splitlines() if r.strip())
    #: ⭐ 2026-10-02 **口径对齐 `T20`**（`audit_work.check_retention`）：**`_归档-YYYYMMDD/` 里的不计**
    #:   —— 那边数的是"**还堆在顶层**的件"（归档件已不在堆里，且它会**照实打出**归档件数）。
    #:   ⚠️ 本件此前**没跳归档** ⇒ 印出的"件数 / 零引用"与 `T20` 对不上 = **同一件事两个数**
    #:      （本仓最贵的病）；实测：`T20` 说 190 件、本件说 282 件，而差的就是那 92 件归档件。
    def _is_archived(f: Path) -> bool:
        return any(x.startswith("_归档-") for x in f.relative_to(ONEOFF).parts[:-1])

    files = [p for p in all_files if not _is_archived(p)]
    n_arch = len(all_files) - len(files)
    on_disk = [p for p in ONEOFF.rglob("*") if p.is_file()]
    total_bytes = sum(p.stat().st_size for p in files)

    referenced: list[tuple[str, list[str]]] = []
    orphan: list[str] = []
    for p in files:
        name = p.name
        rel = p.relative_to(ROOT).as_posix()
        hits = [r for r, txt in corpus.items() if r != rel and name in txt]
        # ⚠️ 只在**别的**件里出现才算"被引用"（自己文件里当然有自己名字）
        if hits:
            referenced.append((rel, hits))
        else:
            orphan.append(rel)

    standing = [r for r, _ in referenced if Path(r).name in STANDING] + [
        o for o in orphan if Path(o).name in STANDING
    ]
    print("=" * 78)
    print(f" `tools/oneoff/` 现状：**{len(files)} 件（在堆里 · 跟踪）** · {total_bytes / 1024:.0f} KB"
          f"   ｜ 已入档 `_归档-*` **{n_arch} 件**（⛔ 不计 —— 口径同 `T20`）"
          f"   ｜ 磁盘上另有 {len(on_disk) - len(all_files)} 件（`__pycache__` 等本机产物）")
    print(f"   · 被（其它跟踪件）引用：**{len(referenced)} 件**")
    print(f"   · **零引用**：**{len(orphan)} 件**")
    print(f"   · 其中**常驻工具**（⛔ 不是一次性）：{len(standing)} 件 —— {', '.join(sorted(Path(x).name for x in standing))}")
    print("=" * 78)
    print(" ── 零引用清单（候选：按口径处置；⛔ 先人眼复核）──")
    for rel in orphan:
        print(f"   · {rel}")
    print()
    print(" ── 被引用最多的 12 件（⇒ 动它们之前先看谁在用）──")
    for rel, hits in sorted(referenced, key=lambda x: -len(x[1]))[:12]:
        print(f"   · {rel}   ← 被 {len(hits)} 处引用（如 {', '.join(hits[:2])}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
