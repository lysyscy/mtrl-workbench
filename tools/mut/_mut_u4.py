"""反向灵敏度（`ui_parity` 的 `U4`：「`WIRED` 标了已接后端 ⇒ 壳里必须真有 `/api/mNN`」）—— 证明 `U4` **真有牙**。

做法：把**某一页的全部接线点**改名（`/api/m09` ⇒ `/api/xm09`）⇒ `ui_parity` 必须变红（`rc=1`）
⇒ 立刻**逐字节复原**（按件记原字节 ＋ MD5 校验）⇒ 复原后必须回 `rc=0`。

⚠️ 为什么必须**全件全替换**：`U4` 只要求"壳里**出现**该串" —— 只要还剩**一处**（哪怕在注释里）它就算过
   ⇒ 只改一处 = **假绿**。⇒ 靶 = 该串在壳里出现的**所有件、所有处**。
⚠️ 为什么新名不能含旧名：`/api/m09x` **仍然含** `/api/m09` 这个子串 ⇒ 断言照样通过 ⇒ 又是假绿
   （所以用 `xm09` 这种**不含旧串**的新名）。

用法：python tools/mut/_mut_u4.py
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = str(ROOT / "backend" / ".venv" / "Scripts" / "python.exe")
TOOL = str(ROOT / "tools" / "audit" / "ui_parity.py")

sys.path.insert(0, str(ROOT / "tools" / "audit"))
from shell_source import SHELL_PARTS  # noqa: E402

#: `(旧接线点, 新接线点)` —— 新串**不含**旧串（否则 `U4` 的 `in` 断言照样过）
CASES = [
    ("m09 的接线点整体改名", "/api/m09", "/api/xm09"),
    ("m15 的接线点整体改名", "/api/m15", "/api/xm15"),
]


def run_tool() -> int:
    p = subprocess.run([PY, TOOL, "--json"], capture_output=True, text=True, encoding="utf-8")
    return p.returncode


def main() -> int:
    before = {p: p.read_bytes() for p in SHELL_PARTS}
    rc0 = run_tool()
    print(f"  基线：ui_parity rc={rc0}（期望 0）")
    if rc0 != 0:
        print("  ⛔ 基线不是 0 ⇒ 壳现在就有未登记漂移 ⇒ 停手")
        return 1

    hits = 0
    for name, old, new in CASES:
        touched: list[pathlib.Path] = []
        for p in SHELL_PARTS:
            text = p.read_text(encoding="utf-8")
            if old not in text:
                continue
            p.write_text(text.replace(old, new), encoding="utf-8", newline="")
            touched.append(p)
        if not touched:
            print(f"  ❌ {name} —— 锚点 `{old}` 在壳里一处都没命中（壳变了？）")
            continue
        leftover = sum(p.read_text(encoding="utf-8").count(old) for p in SHELL_PARTS)
        rc = run_tool()
        for p in touched:                                  # ⭐ 立刻按原字节复原
            p.write_bytes(before[p])
        ok = rc == 1 and leftover == 0
        hits += 1 if ok else 0
        print(f"  {'✅' if ok else '❌'} {name}（改了 {len(touched)} 件）⇒ ui_parity rc={rc}（期望 1）"
              f" · 残留旧串 {leftover} 处（期望 0）{'' if ok else ' —— ⛔ 没抓到，U4 可能是假的'}")

    bad = [str(p.relative_to(ROOT)) for p in SHELL_PARTS
           if hashlib.md5(p.read_bytes()).hexdigest() != hashlib.md5(before[p]).hexdigest()]
    rc_end = run_tool()
    print(f"\n  复原校验（MD5 逐字节）：{'✅ 全部一致' if not bad else '❌ 未复原：' + '、'.join(bad)}")
    print(f"  复原后 ui_parity rc={rc_end}（期望 0）")
    print(f"  反向灵敏度：**{hits}/{len(CASES)} 命中**")
    return 0 if (hits == len(CASES) and not bad and rc_end == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
