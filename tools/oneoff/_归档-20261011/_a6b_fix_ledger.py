#!/usr/bin/env python
"""`A6b` 台账**修正** · 一次性（2026-09-29）。

**修什么**：`_a6b_docs.py` 里我把三步行手术写成"先插 §一、再按**旧下标**删 §三" ⇒
插入让后面所有下标 +1 ⇒ `pop` 删掉的是 §三 的 **`|---|` 分隔行**（而不是 `TAIL-177` 那行），
于是 ① `TAIL-177` 在 §三 与 §四 **各一条**（`T6` 报"编号重复"）；② 计数 `C 类` 写成 0、实际 1。
⇒ 本件把 §三 那条 `TAIL-177` 行**原位换回分隔行**（表结构复原 → 段内 0 条）。

⚠️ 教训（同族第二次）：**行手术必须先做**，且**每步都要在改动后重新定位下标**；
⛔ 别拿"改动前算出的下标"去改"改动后的数组"。

用法：`… _a6b_fix_ledger.py --check` / `--write`
"""

from __future__ import annotations

import argparse
import pathlib
import sys

PLAN = pathlib.Path(__file__).resolve().parents[2] / ".workbuddy" / "plans" / "开发计划-主文档.md"
SEP = "|---|---|---|---|---|---|"        # §三 那张表是 6 栏


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    raw = PLAN.read_text(encoding="utf-8", newline="")
    nl = "\r\n" if "\r\n" in raw else "\n"
    lines = raw.replace("\r\n", "\n").split("\n")

    hC = [i for i, ln in enumerate(lines)
          if ln.strip() == "| # | 事项 | 现状 | 你只需说 | 阶段 / 时机 | 状态 |"]
    assert len(hC) == 1, f"§三 表头命中 {len(hC)} 行"
    i = hC[0] + 1
    row = lines[i]
    if row.strip() == SEP:
        print("⏭ 已修（§三 表头下面是分隔行）⇒ 无事可做")
        return 0
    assert row.startswith("| `TAIL-177` |"), f"§三 表头下面那行不是 `TAIL-177`（是 {row[:40]!r}）⇒ 先核再改"
    print(f"  ✅ 命中：§三 第 {i + 1} 行 = `TAIL-177`（本该是分隔行）")

    if not args.write:
        print("\n（`--check`：⛔ 未写）")
        return 0
    lines[i] = SEP
    PLAN.write_text(nl.join(lines), encoding="utf-8", newline="")
    back = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n").split("\n")
    assert back[i].strip() == SEP and "待你裁定" not in back[i], "写回自校验不过"
    print("✅ 已修：§三 那条 `TAIL-177` 行 ⇒ 换回分隔行（段内 0 条；编号不再重复）")
    print("   接着：`audit_meta`（`T6` 期望 0）⇒ 12 把尺子")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
