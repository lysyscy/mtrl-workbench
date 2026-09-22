#!/usr/bin/env python
"""`TAIL-63` **反向灵敏度**：证明 `tests/test_amount_text_parity.py` 真有区分力。

| 变异 | 怎么改 | 期望（必须变红） |
|---|---|---|
| A · 洗净件**不再去 `¥`** | `_AMOUNT_NOISE` 里删掉 `"¥"` | `test_四处对脏输入解析出同一个数`（¥ 那几条） |
| B · 把 `MOD-09` 的**判定搅成 `MOD-11`** | 空 ⇒ `ZERO` 改成 `raise ValueError(MSG_BAD_AMOUNT)` | `test_mod09_空即0且允许负数` |

⭐ 为什么 B 这条最重要：本轮抽件时**最容易犯的错**就是"顺手把 4 处判定也统一了"
   —— 而那 4 处的判定是**刻意不同**的（两边注释都写着「别把两套搅在一起」）。
   这条变异就是给"以后谁手滑统一了"准备的。

跑法：`backend/.venv/Scripts/python.exe tools/_mut_amount.py`（rc=0 = 两处都抓到且**逐字节复原**）。
"""
from __future__ import annotations

import hashlib
import pathlib
import shutil
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
BACKEND = ROOT / "backend"
BAK = ROOT / ".workbuddy" / "scratch"
BAK.mkdir(parents=True, exist_ok=True)
PY = BACKEND / ".venv" / "Scripts" / "python.exe"
TEST = "tests/test_amount_text_parity.py"

MONEY = BACKEND / "app" / "core" / "money.py"
M09 = BACKEND / "app" / "mod09_fee" / "domain.py"

MUTS = [
    ("A · 洗净件不再去 ¥", MONEY,
     '_AMOUNT_NOISE: tuple[str, ...] = (",", "，", "¥", "￥", "$", " ", "\\u3000")',
     '_AMOUNT_NOISE: tuple[str, ...] = (",", "，", "$", " ", "\\u3000")   # 变异A：¥ 不去',
     "test_四处对脏输入解析出同一个数"),
    ("B · MOD-09 判定被搅成 MOD-11", M09,
     "    if not text:\n        return ZERO",
     "    if not text:\n        raise ValueError(MSG_BAD_AMOUNT)   # 变异B：判定被统一",
     "test_mod09_空即0且允许负数"),
]


def run(node: str | None = None) -> int:
    cmd = [str(PY), "-m", "pytest", "-q", TEST if node is None else f"{TEST}::{node}",
           "-p", "no:cacheprovider", "--tb=no"]
    return subprocess.run(cmd, cwd=str(BACKEND), capture_output=True, text=True,
                          encoding="utf-8", errors="replace").returncode


def main() -> int:
    origs = {p: p.read_bytes() for p in (MONEY, M09)}
    for p in origs:
        shutil.copy2(p, BAK / (p.name + ".bak-mutamount"))
    h0 = {p: hashlib.md5(b).hexdigest() for p, b in origs.items()}
    rc = 0
    try:
        base = run()
        print(f"基线：pytest {TEST} ⇒ rc={base}（应为 0）")
        if base != 0:
            print("❌ 基线就是红的 ⇒ 先修测试再谈变异")
            return 1
        for label, path, old, new, node in MUTS:
            t = origs[path].decode("utf-8")
            if old not in t:
                print(f"❌ {label}：找不到锚点（代码改过 ⇒ 本脚本要同步改）")
                return 1
            path.write_text(t.replace(old, new, 1), encoding="utf-8", newline="")
            m = run(node)
            ok = m != 0
            print(f"{label}：{node} ⇒ rc={m} {'✅ 抓到' if ok else '❌ 没抓到（假绿！）'}")
            rc = rc if ok else 1
            path.write_bytes(origs[path])
    finally:
        for p, b in origs.items():
            p.write_bytes(b)
    same = all(hashlib.md5(p.read_bytes()).hexdigest() == h for p, h in h0.items())
    print(f"复原：MD5 {'一致 ✅' if same else '❌ 不一致'}")
    if same:
        for p in origs:
            (BAK / (p.name + ".bak-mutamount")).unlink(missing_ok=True)
    return rc if same else 1


if __name__ == "__main__":
    sys.exit(main())
