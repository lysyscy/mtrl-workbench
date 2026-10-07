"""反向灵敏度（**交付面尾部两张网**：`T27` 页脚后无内容 · `T28` `PRD` 规格件只许变长）—— 证明它们**真有区分力**。

立于 2026-10-06（`TAIL-234`）。⚠️ 两张网都是**当天真事故**打出来的，所以"它能不能红"必须当场验：
  · `T27` 的病 = `MOD-14.md` 两条 `ACC-*` 验收条目**掉到页脚之后** ⇒ `T1`–`T26` 一层都看不见；
  · `T28` 的病 = WPS 云同步**把整个交付面盖回历史快照**（本机至少两次）。

**五靶**（一次只碰一个文件 · 改完**立刻按 bytes 复原** ＋ 收尾 MD5 逐字节对账 ——
用户 2026-09-24：「云同步也没那么蠢，只要别同时大量连续改文件」）：

| 靶 | 改坏什么 | 期望 |
|---|---|---|
| `M1` | 在某份 `MOD-*.md` 的**页脚之后加一行** | `T27` 必红 |
| `M2` | 删某份 `MOD-*.md` 的**最后一行** | `T28` 必红（变短） |
| `M3` | 把某份 `MOD-*.md` 编号表**最后一行的行号改小**（**行数不变**） | `T28` 必红（行号锚点那一半） |
| `M4` | ⭐ **真实坏样本**：把 `MOD-11.md` 换成**旧根**那份（被云端盖回过的快照） | `T28` 必红 |
| `M5` | **不动盘**：查"排除清单还在不在、且真的 load-bearing" | 归档那 6 处孤儿**仍在**、却**一条不报** |

⚠️ **为什么 `M3` 要单独造**（本仓真事）：24 件里只有 2 件在回退后**变短**
⇒ 只钉行数等于把"等长回退"整片放过去。`M3` 就是那一半的**造得出来的红**。
⚠️ **`M5` 钉的是另一头**：排除清单若哪天被清空，`T27` 会把归档那6 处也报红（闸门当场红）；
反过来若有人把扫描面缩窄来"消红"，本靶会发现**那 6 处已经不在扫描面里** ⇒ 两种偷懒都堵。

⚠️ **跑的是 `audit_face.py` 自己**（不是 `doc_audit`）—— 它是这两张网的**单一出口**，
判据与靶必须对着同一件东西量（`doc_audit` 只是把它并进同一份 `raw`）。
⚠️ **不在交付面新建文件**（与 `_mut_uicheck` 同款纪律）。

用法：python tools/mut/_mut_facedoc.py
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
sys.path.insert(0, str(ROOT / "tools" / "audit"))
from audit_common import FOOTER_EXCLUDE_PARTS, delivery_root  # noqa: E402
from audit_face import PRD_DOC_BASELINE, scan_footer_tails  # noqa: E402

FACE = delivery_root()
RULER = ROOT / "tools" / "audit" / "audit_face.py"
MOD14 = "PRD/02-功能规格/MOD-14.md"
MOD11 = "PRD/02-功能规格/MOD-11.md"
#: ⭐ **旧根 = 真实坏样本的来处**（被云端盖回至少两次的历史快照 · **用户裁定**：留着当坏样本、⛔ 不再处理它）
OLD_ROOT = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用")


def run_ruler() -> tuple[int, str]:
    r = subprocess.run([str(PY), "-X", "utf8", str(RULER)], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace",
                       env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def tail_after_footer(path: pathlib.Path) -> list[str]:
    """该件页脚之后的非空行 —— ⭐ **转发到尺子那一份**（`/code-review` 2026-10-06：⛔ 别在变异脚本里
    再写一遍 `rglob` ＋ `parts[:-1]` ＋ 标记字面 —— 判据一改它不跟着变）。"""
    rel = path.relative_to(FACE).as_posix()
    return next((t for r, t, _ex in scan_footer_tails() if r == rel), [])


def case(desc: str, rel: str, kind: str, a: bytes, b: bytes, needle: str) -> bool:
    """改坏 → 必须红且输出里有 `needle` → **finally 按 bytes 复原**（交付面文件，绝不留坏态）。

    `kind` 四种（⛔ 显式枚举，不靠"内容长什么样"猜 —— 猜的那版第一跑就切错分支）：
    `append`（尾部追加 `a`）· `drop_line`（删掉整行 `a`）· `swap`（`a` → `b`，各须命中 1 次）
    · `whole`（整份换成 `a`）。
    """
    path = FACE / rel
    src = path.read_bytes()
    try:
        if kind == "append":
            path.write_bytes(src + a)
        elif kind == "drop_line":
            n = src.count(a)
            assert n == 1, f"`drop_line` 锚串命中 {n} 次（要 1 次）⇒ ⛔ 未验证"
            path.write_bytes(src.replace(a, b"", 1))
        elif kind == "swap":
            n = src.count(a)
            assert n == 1, f"`swap` 锚串命中 {n} 次（要 1 次）⇒ ⛔ 未验证"
            path.write_bytes(src.replace(a, b, 1))
        elif kind == "whole":
            path.write_bytes(a)
        else:
            raise AssertionError(f"未知 kind={kind}")
        rc, out = run_ruler()
    finally:
        path.write_bytes(src)                     # ⭐ 立刻复原
    ok = rc != 0 and needle in out
    print(("  ✅ " if ok else "  ⛔ 未命中 ") + f"{desc}  → rc={rc}"
          + ("" if ok else f"（判据 `{needle}` 未出现）"))
    return ok


def main() -> int:
    assert FACE and FACE.is_dir(), f"交付面根拿不到：{FACE}"
    before = {rel: hashlib.md5((FACE / rel).read_bytes()).hexdigest()
              for rel in (MOD14, MOD11)}

    rc, out = run_ruler()
    print(f"基线（未改坏）：audit_face rc={rc}（应为 0）")
    if rc != 0:
        print("  ⛔ 基线就不对 ⇒ 先清红再来跑本件")
        return 1

    # ── `M5`（只读盘，先跑）—— 排除清单必须 **load-bearing** ──────────────────
    #⚠️ 扫描/排除**全走尺子那一份**（`scan_footer_tails`）⇒ 本靶与 `T27` 永不各写一套。
    tails = scan_footer_tails()
    arch = [(r, t) for r, t, ex in tails if ex]
    n_arch = sum(len(t) for _r, t in arch)
    m5 = n_arch > 0 and "[T27]" not in out
    print(("  ✅ " if m5 else "  ⛔ 未命中 ")
          + f"M5 排除清单 load-bearing：{'/'.join(FOOTER_EXCLUDE_PARTS)} 下 {len(arch)} 份件里"
            f"**确实还有** {n_arch} 处页脚孤儿，活件一条 T27 都不报（排除生效 ⇔ 不是把扫描面缩窄当修复）")
    if not m5 and n_arch == 0:
        print("     ⛔ `n_arch==0` ⇒ 那几处已被人删掉 ⇒ 排除清单变成空转，本靶失去意义，先核原文")

    # ── 各靶的锚（⛔ 全部先断言"基线里就是这样"，否则靶打偏了都不知道） ──────
    assert not tail_after_footer(FACE / MOD14), "基线里 MOD-14 页脚之后就有内容 ⇒ 前提不符，先核原文"
    ls14 = (FACE / MOD14).read_text(encoding="utf-8", errors="replace").splitlines()
    last = ls14[-1] if ls14[-1].strip() else ls14[-2]
    assert "本文件性质" in last, "MOD-14 末行不是页脚 ⇒ 尾部另有内容？先核原文"
    # ⭐ 行号**从基线表取**（⛔ 不写死 `11` —— 那会让"一个数两处用"；基线更新它自动跟随）
    row_no = PRD_DOC_BASELINE[MOD14][1]
    row = [ln for ln in ls14 if ln.startswith(f"| {row_no} |")]
    assert len(row) == 1, f"`| {row_no} |` 行命中 {len(row)} 处 —— ⛔ 先核原文"
    old = OLD_ROOT / MOD11
    assert old.is_file(), f"旧根那份不在：{old} —— ⛔ 先核路径"
    assert old.read_bytes() != (FACE / MOD11).read_bytes(), "旧根那份与真源逐字节相同 ⇒ 没有坏样本可用"

    hits = [
        case(f"M1 `T27`：在 {MOD14} 的**页脚之后加一行** ⇒ 必须红", MOD14, "append",
             "\n（变异靶：页脚之后的一行）\n".encode("utf-8"), b"", "T27"),
        case(f"M2 `T28`：删掉 {MOD14} 的**最后一行** ⇒ 必须红（变短）", MOD14, "drop_line",
             last.encode("utf-8") + b"\n", b"", "T28"),
        case(f"M3 `T28`：把 {MOD14} 编号表最后一行的**行号改小**（**行数不变**）⇒ 必须红（行号锚点）",
             MOD14, "swap", row[0].encode("utf-8"),
             row[0].replace(f"| {row_no} |", "| 4 |", 1).encode("utf-8"), "T28"),
        case("M4 `T28`：⭐ **真实坏样本** —— 把 MOD-11 换成**旧根**那份（云同步盖回过的快照）⇒ 必须红",
             MOD11, "whole", old.read_bytes(), b"", "T28"),
    ]
    hit = sum(hits) + int(m5)

    dirty = [rel for rel, md5 in before.items()
             if hashlib.md5((FACE / rel).read_bytes()).hexdigest() != md5]
    print()
    print(f"  命中 {hit}/{len(hits) + 1}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if not dirty else '❌ 未复原：' + '、'.join(dirty)}")
    return 0 if (hit == len(hits) + 1 and not dirty) else 1


if __name__ == "__main__":
    raise SystemExit(main())