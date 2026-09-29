#!/usr/bin/env python
"""`TAIL-64` **P4-b** 收尾：**消号幽灵登记**（只删登记簿里那些"当前已无对应漂移"的行）。

**为什么必须单独做**：`ui_parity --write-expected` **只追加**新漂移（2026-09-25 用户裁定"登记簿可以变长"），
⛔ **不会**替你删旧行 —— 消号是**人的决定**（自动删会连带冲掉旁边的理由注释）。
⚠️ 本批（P4-b）实测：换号 **18 行** ＋ 幽灵 **18 条** —— 因为 `index.html` 里 **4 页**（`m03`/`m05`/`m06`/`m11`）
的筛选栏**本来就与原型错位**（壳比原型多几行）⇒ 那两行的"配对伙伴"换了号；`m14` 那块是**壳新增**（原型没有）。

**它怎么算幽灵**：**照抄 `ui_parity` 自己的比法**（同一份 `slices()` / `fp()`）——
先算出**当前真实的漂移指纹集**，再拿登记簿减它 ⇒ 剩下的就是"登记了、但现在已经不存在的"。
⛔ **不自己另写一套比对规则**（两套口径必然漂）。

用法：`python tools/oneoff/_p4b_ghosts.py`（干跑）· `… --write`（真删）
"""

from __future__ import annotations

import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "audit"))

from ui_parity import (  # noqa: E402
    EXPECTED,
    PROTO,
    fp,
    load_expected,
    read_lines,
    read_shell,
    slices,
)


def ghosts() -> list[tuple[str, str]]:
    p_views = slices(read_lines(PROTO))
    s_views = slices(read_shell().replace("\r\n", "\n").split("\n"))
    now: dict[str, set[str]] = {}
    for key, plines in p_views.items():
        slines = s_views.get(key)
        if slines is None:
            continue
        for i in range(max(len(plines), len(slines))):
            a = plines[i].rstrip() if i < len(plines) else "<无此行>"
            b = slines[i].rstrip() if i < len(slines) else "<无此行>"
            if a != b:
                now.setdefault(key, set()).add(fp(a + "||" + b))
    return sorted((k, f) for k, fs in load_expected().items() for f in fs if f not in now.get(k, set()))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    gh = ghosts()
    print(f"幽灵登记 **{len(gh)}** 条（登记了、但当前已无对应漂移）：")
    for k, f in gh:
        print(f"  · {k} {f}")
    if not args.write:
        print("\n（干跑：⛔ 未写）")
        return 0

    lines = read_lines(EXPECTED)
    killed: list[str] = []
    keep: list[str] = []
    wanted = {f"{k} {f}" for k, f in gh}
    for ln in lines:
        s = ln.strip()
        head = " ".join(s.split()[:2]) if s and not s.startswith("#") else ""
        if head in wanted:
            wanted.discard(head)
            killed.append(ln)
            continue
        keep.append(ln)
    assert not wanted, f"⛔ 有 {len(wanted)} 条幽灵在登记簿里**没找到对应行**：{sorted(wanted)[:3]}"
    assert len(killed) == len(gh), f"⛔ 删了 {len(killed)} 行、但幽灵是 {len(gh)} 条"
    EXPECTED.write_text("\n".join(keep).rstrip("\n") + "\n", encoding="utf-8")
    print(f"\n✅ 已删 {len(killed)} 行 ⇒ 登记簿 {len(lines)} → {len(keep)} 行")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
