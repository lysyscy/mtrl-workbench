#!/usr/bin/env python
"""把 `tools/oneoff/` 里**零引用**的件**移进** `_归档-20260930/`（可逆 · ⛔ 不删）。

**口径出处** = `tools/README.md` 的「`oneoff/` 的保留与处置口径」那一段（**唯一主人**）：
  ① **常驻小工具** ⇒ 长期保留；② **被引用的留痕件**（台账/设计件/判据/记忆提到文件名）⇒ 长期保留（删了就断链）；
  ③ **零引用的** ⇒ **候选** ⇒ **移进** `tools/oneoff/_归档-YYYYMMDD/`（可逆、⛔ 不盲删）。

⚠️ **名单只有一个来源**：直接**跑** `_oneoff_measure.py` 并解析它打印的"零引用清单"
（⛔ 不在这里另写一套"哪些算被引用"的判据 —— 两套口径必然漂）。
⚠️ 它列出的**常驻工具**（`_run_rulers.py` 那 7 件）**不在**零引用清单里（它单列）⇒ 天然不会被移。

用法：`python tools/oneoff/_归档_20260930.py`（干跑）· `… --write`（真移 · 并在归档目录写一份清单）
"""

from __future__ import annotations

import argparse
import pathlib
import re
import shutil
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ONEOFF = ROOT / "tools" / "oneoff"
DEST = ONEOFF / "_归档-20260930"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"


def zero_ref() -> list[pathlib.Path]:
    """跑量测件（**它才是口径的主人**）⇒ 解析"零引用清单"那一段。"""
    r = subprocess.run([str(PY), "-X", "utf8", str(ONEOFF / "_oneoff_measure.py")],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    assert "零引用清单" in out, "⛔ 量测件没跑出「零引用清单」—— 先看它的输出"
    seg = out.split("零引用清单", 1)[1].split("被引用最多的", 1)[0]
    hits = re.findall(r"·\s+(tools/oneoff/[^\s]+)", seg)
    assert hits, "⛔ 清单解析为空（量测件格式变了？）"
    return [ROOT / h for h in hits]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    files = zero_ref()
    me = pathlib.Path(__file__).resolve()
    files = [f for f in files if f.resolve() != me]          # 本件不归档自己
    print(f"零引用 **{len(files)}** 件 ⇒ 拟移进 `{DEST.relative_to(ROOT)}/`")
    for f in files[:8]:
        print(f"   · {f.relative_to(ROOT)}")
    if len(files) > 8:
        print(f"   …还有 {len(files) - 8} 件")
    if not args.write:
        print("\n（干跑：⛔ 未移）")
        return 0

    DEST.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []
    for f in files:
        assert f.exists(), f"⛔ 找不到 {f}"
        tgt = DEST / f.name
        assert not tgt.exists(), f"⛔ 归档目录里已有同名件：{tgt.name}"
        shutil.move(str(f), str(tgt))
        moved.append(f.name)
    print(f"\n✅ 已移 {len(moved)} 件 ⇒ `{DEST.relative_to(ROOT)}/`（可逆 · ⛔ 没删任何一个字节）")

    #: 归档目录留一份清单 —— 67 个文件堆在那儿，后人得知道"它们是什么、为什么在这儿、谁移的"
    man = DEST / "清单.md"
    man.write_text(
        "# `tools/oneoff/` 归档 · 2026-09-30\n\n"
        "> **为什么在这儿**：`tools/oneoff/` 长期只增不减（`TAIL-194` 立了 `T20` 机器眼）⇒ 按 `tools/README.md`\n"
        "> 那一段的处置口径，把**零引用**的件**移进**本目录（**可逆 · ⛔ 不删**）。\n"
        "> **判据的出处**（唯一主人）= **跑** `tools/oneoff/_oneoff_measure.py` 解析它的「零引用清单」\n"
        "> （⛔ 不必也不许另写一套「哪些算被引用」的口径）。移入脚本 = `tools/oneoff/_归档_20260930.py`。\n"
        "> ⚠️ **要取回某一件**：直接从本目录移回上一级即可（它们**一字未改**）。\n\n"
        f"共 **{len(moved)}** 件：\n\n"
        + "\n".join(f"- `{n}`" for n in sorted(moved)) + "\n",
        encoding="utf-8")
    print(f"  ✅ 清单 ⇒ {(man).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
