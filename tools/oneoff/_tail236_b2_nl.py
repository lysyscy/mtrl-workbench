"""一次性施工件（`TAIL-236` 批 2）：把两个被 `replace_in_file` 插入的 CRLF 文件**归一行尾**。

为什么需要：`replace_in_file` 插入的新行带裸 LF ⇒ 目标文件变成**混合行尾**
（`audit_meta.py` 6 处 · `ops/阈值表.md` 2 处）⇒ 以后每次 `git diff` 都可能把整篇算成改动。

⛔ 只对"改前 100% CRLF"的文件做（下面两个都量过）⇒ 全量归一不会碰到任何**故意**的裸 LF。
⚠️ 幂等：已是 CRLF 时 replace 是 no-op（跑两遍字节相同）。

⭐ **为什么零引用还留在仓内**（`tools/README.md` 三类件口径要求"写明留档理由"）：
第 3／4 批（降档判据 ＋ 降档动作）**还会改同样的活文档** ⇒ 这个坑会再踩一次；
它是"编辑工具插行 ⇒ 混合行尾"这件事的**唯一处方**（`MEMORY.md` 记纪律、这里记做法）。
⚠️ 将来不再需要时：按 `tools/README.md` 的处置口径移进 `_归档-YYYYMMDD/`（⛔ 不删）。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
TARGETS = ("tools/audit/audit_meta.py", "ops/阈值表.md")


def main() -> int:
    for rel in TARGETS:
        p = ROOT / rel
        raw = p.read_bytes()
        before = (raw.count(b"\r\n"), raw.count(b"\n"))
        fixed = raw.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        after = (fixed.count(b"\r\n"), fixed.count(b"\n"))
        if fixed != raw:
            p.write_bytes(fixed)
        again = p.read_bytes()
        assert again == fixed, "写后逐字节不一致：" + rel
        # 幂等：再归一一次应无变化
        assert again.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n") == again, "不幂等：" + rel
        print("%-32s crlf/lf %s → %s  %s（行数 %d）"
              % (rel, before, after, "已改" if fixed != raw else "无变化",
                 len(fixed.decode("utf-8").splitlines())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
