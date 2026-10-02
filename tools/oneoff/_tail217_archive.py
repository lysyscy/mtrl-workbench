"""`TAIL-217` 第二步 · `.codebuddy/backups/` 的**归档移动**（可逆 · ⛔ 一个字节都不删）。

**背景**：用户 2026-10-02 选 **②**（先移不清 ＋ 口径落纸 ＋ 给 `T20` 挂机器眼）；
本件**只做移动** —— 把"已过期但还要留痕"的顶层条目搬进 `_旧快照归档-20261002/`。
搬法是 `shutil.move`（同盘 ⇒ 原子的改名）⇒ **随时能搬回来**。

**移哪几件（逐条给理由 · 都量过）**：
  1. `原型-备份-20260924-P1b前.html` · `原型-备份-20260924-TAIL64试点前.html` —— 最老一批（距今 8 天）
  2. `材料科业务全流程说明书-20260921-1450.md.bak` —— **零引用** · 09-21 的《说明书》旧版
  3. `交付面-20260929-2047/`（**整目录**）—— 其中 `用例索引.md` / `验收基线.json` 与
     `_旧快照归档-20260929/交付面-20260929-1330-收口/PRD/验收/` 里那两份**逐字节相同**（sha256）⇒ 已被覆盖
  4. `原型-备份-20260929-P4modal前.html` —— 与 `原型-备份-20260929-P4jcInv前.html` **逐字节相同** 且**零引用**

**⛔ 刻意不动的**（口径写进口径文件时同批说明）：
  · 5 份 `*_壳单文件基线.html` —— `shell_verify` 与 `ops/pack.ps1` **真依赖**（机器自管，只留最近 5）
  · `原型-备份-20260929-P2m05前.html` == `原型-备份-20260929-P2m07后.html`（另一对逐字节相同）——
    两份**各对应当时的批次**（"改前长这样"这件事本身是留痕）⇒ 本轮只**记账**、不搬（等"产包前一晚"那次清再定）

用法（**先干跑** · 与 `tools/oneoff/` 其余一次性件同口径：不达标整批不写盘）：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail217_archive.py
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail217_archive.py --apply
"""
from __future__ import annotations

import argparse
import pathlib
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
BK = REPO / ".codebuddy" / "backups"
DEST = BK / "_旧快照归档-20261002"

#: (顶层条目名, 为什么搬它) —— ⛔ 名字必须**逐字**对得上盘上的东西
MOVES: list[tuple[str, str]] = [
    ("原型-备份-20260924-P1b前.html", "最老一批（08 天）"),
    ("原型-备份-20260924-TAIL64试点前.html", "最老一批（08 天）"),
    ("材料科业务全流程说明书-20260921-1450.md.bak", "零引用 · 09-21 的《说明书》旧版"),
    ("交付面-20260929-2047", "内含两件与已归档的 09-29 收口快照**逐字节相同**（已被覆盖）"),
    ("原型-备份-20260929-P4modal前.html", "与 `P4jcInv前` **逐字节相同** 且零引用"),
]


def entries() -> list[pathlib.Path]:
    return sorted(BK.iterdir(), key=lambda p: p.name)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="TAIL-217：把过期的 backups 顶层条目搬进归档（可逆）")
    ap.add_argument("--apply", action="store_true", help="真搬（默认只干跑）")
    a = ap.parse_args(argv)

    before = entries()
    print(f"顶层条目（搬前）：{len(before)} 个")
    print(f"目标归档：{DEST.name}/（{'已存在' if DEST.is_dir() else '将要新建'}）")
    print("-" * 78)

    # ① 先全部**校验**：源必须在、目标必须不在（⛔ 不达标整批不动）
    plan: list[tuple[pathlib.Path, pathlib.Path, str]] = []
    bad: list[str] = []
    for name, why in MOVES:
        src = BK / name
        dst = DEST / name
        if not src.exists():
            bad.append(f"源不存在：{name}")
            continue
        if dst.exists():
            bad.append(f"目标已存在（会被覆盖）：_旧快照归档-20261002/{name}")
            continue
        plan.append((src, dst, why))
    if bad:
        print("⛔ 校验未过 ⇒ **一个都不搬**：")
        for b in bad:
            print(f"    {b}")
        return 1
    for src, dst, why in plan:
        n = sum(1 for f in (src.rglob("*") if src.is_dir() else [src]) if f.is_file())
        print(f"  {src.name:<46} {n} 件 —— {why}")

    if not a.apply:
        print("-" * 78)
        print("（干跑 —— 要真搬请加 --apply）")
        return 0

    # ② 搬（同盘 ⇒ 改名；目标目录先建好）
    DEST.mkdir(parents=True, exist_ok=True)
    for src, dst, _ in plan:
        shutil.move(str(src), str(dst))
        print(f"  ✓ 已搬 ⇒ {DEST.name}/{src.name}")

    after = entries()
    print("-" * 78)
    print(f"顶层条目（搬后）：{len(after)} 个（{len(before)} → {len(after)}）")
    arc = [e for e in after if e.name.startswith(("_归档-", "_旧快照归档-"))]
    n = sum(1 for x in arc for f in x.rglob("*") if f.is_file())
    print(f"归档子目录：{len(arc)} 个 · {n} 件")
    print("⚠️ 回滚 = 把 `_旧快照归档-20261002/` 里这几件 `shutil.move` 回上一层（⛔ 没有任何东西被删）")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
