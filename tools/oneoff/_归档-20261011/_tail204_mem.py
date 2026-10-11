"""`TAIL-204` **第 2 步（记忆归一）** —— 把 `.workbuddy/memory/` 整个并进 `.codebuddy/memory/`。

做两件事（都先干跑）：
  **A. 搬家**（`git mv`）：
     · `.workbuddy/memory/MEMORY-细则.md` ⇒ `.codebuddy/memory/细则.md`（改名：去掉 `MEMORY-` 前缀，与它"分册"的身份一致）
     · `.workbuddy/memory/journal/`（**2026-09-28 停用**的 12 件）⇒ `.codebuddy/plans/archive/归档-逐日日志-至20260927/`
       （⛔ 是**留痕**，别并进现役日志 —— 两代流水混一起 = 同一件事两处写）
     · **现役**逐日日志（`2026-09-24 … 2026-10-01`）⇒ `.codebuddy/memory/journal/`
       （⭐ 为什么进 `journal/`：`T12` 的规矩是「memory 根只放**注入档与分册**，日志去 `journal/`」——
        它们此前在根上**没被任何尺子看见**（`T12` 当时只扫 `.workbuddy/memory`）⇒ 一并进 `journal/` 才不新增黄）
     · `.workbuddy/memory/MEMORY.md` ⇒ **内容并入** `.codebuddy/memory/MEMORY.md`（⛔ 不是 `git mv`：会撞名）
  **B. 改引用**：全库活件里 `.workbuddy<sep>memory` ⇒ `.codebuddy<sep>memory`、`MEMORY-细则` ⇒ `细则`
     （⚠️ 两种写法都覆盖：字面量 `.workbuddy/memory` ＋ 引号拼接 `ROOT / ".workbuddy" / "memory"` —— 第 1 步在这上面栽过 10 处）

⛔ **有意不动**：`tools/oneoff/**`（历史留痕）· `归档-*` / `archive/` / `journal/`（留痕档，改了才是失真）。

用法：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail204_mem.py            # 干跑
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail204_mem.py --moves    # 只做搬家
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail204_mem.py --refs     # 只改引用
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: 搬家清单（相对路径 → 相对路径）
MOVES: tuple[tuple[str, str], ...] = (
    (".workbuddy/memory/MEMORY-细则.md", ".codebuddy/memory/细则.md"),
    (".workbuddy/memory/journal", ".codebuddy/plans/archive/归档-逐日日志-至20260927"),
)
#: 现役逐日日志（搬到 `journal/` 下）—— 其后的日志也按此约定写
LIVE_LOGS: tuple[str, ...] = tuple(
    [f".codebuddy/memory/2026-09-{d}.md" for d in ("24", "25", "26", "27", "28", "29", "30")]
    + [".codebuddy/memory/2026-10-01.md"]
)
LOG_DIR = ".codebuddy/memory/journal"

#: 改引用的两条规则（**两种写法都要** —— `[/\\]` 字面量 ＋ `['"] * / * ['"]` 引号拼接）
REFS: tuple[tuple[bytes, bytes], ...] = (
    (rb"\.workbuddy([/\\]|['\"]\s*/\s*['\"])memory", rb".codebuddy\1memory"),
    # ⚠️ `bytes` 字面量**不能放非 ASCII** ⇒ 中文一律走 `.encode("utf-8")`
    ("MEMORY-细则".encode("utf-8"), "细则".encode("utf-8")),
)

EXCLUDE_MARKS = ("/归档-", "/archive/", "/journal/")
EXCLUDE_PREFIX = ("tools/oneoff/",)
#: ⛔ 这个件**现在就删**（内容已并进 `.codebuddy/memory/`）⇒ 别再当活件处理
DYING = ".workbuddy/memory/MEMORY.md"
#: ⭐ 不进 git、但每会话都要读的件
EXTRA = (".codebuddy/memory/MEMORY.md", ".codebuddy/memory/IDE-细节.md")


def _tracked() -> list[str]:
    r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True)
    return [p for p in r.stdout.decode("utf-8").split("\0") if p]


def _skip(rel: str) -> bool:
    return rel.startswith(EXCLUDE_PREFIX) or any(m in f"/{rel}" for m in EXCLUDE_MARKS)


def do_moves(write: bool) -> int:
    print("── A. 搬家")
    plan: list[tuple[str, str]] = []
    for src, dst in MOVES:
        if (ROOT / src).exists():
            plan.append((src, dst))
        else:
            print(f"   （跳过，已不在：{src}）")
    for src in LIVE_LOGS:
        if (ROOT / src).exists():
            plan.append((src, f"{LOG_DIR}/{Path(src).name}"))
    for src, dst in plan:
        print(f"   {'搬' if write else '[干跑]'} {src}  ->  {dst}")
        if not write:
            continue
        (ROOT / Path(dst).parent).mkdir(parents=True, exist_ok=True)
        r = subprocess.run(["git", "-C", str(ROOT), "mv", src, dst], capture_output=True)
        if r.returncode != 0:                       # 非 git 跟踪件 ⇒ 兜底用文件系统搬
            print(f"      （git mv 没成功，改用文件系统搬：{r.stderr.decode('utf-8', 'replace').strip()[:120]}）")
            (ROOT / dst).parent.mkdir(parents=True, exist_ok=True)
            (ROOT / src).rename(ROOT / dst)
    print(f"   共 {len(plan)} 项\n")
    return 0


def do_refs(write: bool) -> int:
    print("── B. 改引用（`.workbuddy…memory` ⇒ `.codebuddy…memory` · `MEMORY-细则` ⇒ `细则`）")
    total, files = 0, []
    for rel in _tracked():
        if _skip(rel) or rel == DYING:
            continue
        p = ROOT / rel
        try:
            data = p.read_bytes()
        except OSError:
            continue
        new, n = _sub(data)
        if n:
            files.append((rel, n))
            total += n
            if write:
                assert len(new.splitlines()) == len(data.splitlines()), f"{rel} 行数变了"
                p.write_bytes(new)
    for rel in EXTRA:
        p = ROOT / rel
        if not p.is_file():
            continue
        new, n = _sub(p.read_bytes())
        if n:
            files.append((f"{rel}（不在 git）", n))
            total += n
            if write:
                p.write_bytes(new)
    for rel, n in files:
        print(f"   {n:3d}  {rel}")
    print(f"   {'已改' if write else '将改'} {len(files)} 件 · 共 {total} 处\n")
    return 0


def _sub(data: bytes) -> tuple[bytes, int]:
    n = 0
    out = []
    for line in data.splitlines(keepends=True):
        if b"Administrator" in line:
            out.append(line)
            continue
        cur = line
        for pat, rep in REFS:
            cur, k = re.subn(pat, rep, cur)
            n += k
        out.append(cur)
    return b"".join(out), n


MERGE_SRC = ".workbuddy/memory/MEMORY.md"
MERGE_DST = ".codebuddy/memory/细则.md"
#: ⚠️ 拼进去的抬头 —— **全文原样保留**（⛔ 一字不删），只说明"为什么它在附录里"
MERGE_HEAD = (
    "\n---\n\n"
    "## 附：原 `.workbuddy/memory/MEMORY.md` 全文（**2026-10-01 `TAIL-204` 第 2 步归并**）\n\n"
    "> ⚠️ **它为什么在附录里**：该件长期**自称「唯一注入档（每会话必读）」**，而实测它 **24.7 KB** ——\n"
    ">   **远超注入上限**（本仓记录：>14.4 KB 会被截断）⇒ ⭐ **它其实从未被注入**（下个会话根本不会自动读到它；\n"
    ">   而真正被注入的一直是 `.codebuddy/memory/MEMORY.md` —— 2026-10-01 会话开头的注入内容可逐字对上）。\n"
    ">   ⇒ 第 2 步按**实际地位**归位：**「每轮都要用」的少数几条**折进真正的注入档\n"
    ">   `.codebuddy/memory/MEMORY.md` §〇（闸门 / 状态只信三处 / 铁律）；**其余全文原样留在本附录**（⛔ 一字未删）。\n"
    "> ⚠️ 因此本节**不再与上面的分册逐节对齐**（原「两册节号对齐」的前提，随这次归并消失）。\n\n"
)


def do_merge(write: bool) -> int:
    """把原项目侧 `MEMORY.md` 的**全文**拼进分册 `细则.md`（幂等：已在里面就跳过）。"""
    src, dst = ROOT / MERGE_SRC, ROOT / MERGE_DST
    if not src.is_file():
        print(f"── C. 合并：（源已不在：{MERGE_SRC}）\n")
        return 0
    body = src.read_bytes()
    old = dst.read_bytes()
    if body[:200] in old:
        print("── C. 合并：分册里**已经在**（幂等跳过）\n")
        return 0
    print(f"── C. 合并：{MERGE_SRC}（{len(body)} B）→ 追加到 {MERGE_DST}（追加 {len(MERGE_HEAD.encode('utf-8'))} B 抬头）")
    if write:
        dst.write_bytes(old + MERGE_HEAD.encode("utf-8") + body)
        print("   已写\n")
    else:
        print("   [干跑]（加 `--write` 才落盘）\n")
    return 0


def main(argv: list[str]) -> int:
    write = "--write" in argv
    if "--refs" in argv:
        return do_refs(write)
    if "--moves" in argv:
        return do_moves(write)
    if "--merge" in argv:
        return do_merge(write)
    print("（干跑：不改盘）—— 用 `--moves` / `--refs` 分别执行；两者都要落盘时加 `--write`\n")
    do_moves(False)
    do_refs(False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
