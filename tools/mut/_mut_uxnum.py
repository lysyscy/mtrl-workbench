"""守什么：**金额大数一律带单位**（守则 §2.3 / §5.7）—— `tests/test_ux_numbers.py` 那几条断言
到底有没有区分力；顺带证明**「不可得的金额不许冒充 0」**（`MONEY` 的 `null` 分支）不是摆设
（⭐ 2026-09-30 `P4-c` 前哨又给该件加了一条「口径说明 · N 条」的守卫 ⇒ 同批补 `M4`）。

**为什么单开一件**：那一批判据（`TAIL-117` 批次 4 · 2026-09-27）**从来没有反向灵敏度** ——
`tools/mut/` 里没有任何一件打它；而本仓纪律是「新增/收紧判据 ⇒ 同批证明它**改坏了会红**」
（2026-09-29 `A2` 逐页时补的账：那条判据的 `'<div class="v">${M('` 形态还漏掉了**勾选汇总条**）。

四靶（一次只碰一处、改完**立刻按 bytes 复原** ＋ 收尾 MD5）：
- `M1` 勾选条退回裸 `M(`（`MONEY(pkA)` → `M(pkA)`）⇒ `test_金额大数一律带单位` 必红。
- `M2` 卡片 KPI 退回裸 `M(`（`<div class="v">${MONEY(` → `<div class="v">${M(`）⇒ 同一条必红
  （证明**原断言**也有牙齿，不只是新加那两条）。
- `M3` `MONEY` 丢掉 `null` 分支（写成 `M(v)+'元'`）⇒ `test_不可得的金额不许冒充_0` 必红
  （它会把「—」变成「— 元」= 把"没取到"说成 0）。
- ⭐ `M4`（2026-09-30 · `TAIL-64` **P4-c 前哨**）：把某块「口径说明 · **13** 条」的条数改错
  ⇒ `test_口径说明的条数必须与实际的条数一致` 必红（**屏幕上写假条数**那一类的守卫）。

跑法：`backend\\.venv\\Scripts\\python.exe tools\\mut\\_mut_uxnum.py`（rc=0 = 全部按预期变红且已复原）
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(ROOT / "tools" / "audit"))
from shell_source import SHELL_PATH as SHELL, pick  # noqa: E402

PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")

MONEY_DEF = "const MONEY=v=>v==null?'—':M(v)+'<span class=\"u\">元</span>';"

MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "M1 勾选汇总条退回裸 `M(`（用户按它判断「这一批要付多少」，却看不到单位）",
        "${MONEY(pkA)}",
        "${M(pkA)}",
        "test_ux_numbers.py::test_金额大数一律带单位",
    ),
    (
        "M2 `m05` 台账标题行的「本项目当前欠款」退回裸 `M(`（同页最显眼的那个数没有单位）",
        '<b class="fc">${MONEY(cur)}</b>',
        '<b class="fc">${M(cur)}</b>',
        "test_ux_numbers.py::test_金额大数一律带单位",
    ),
    (
        "M3 `MONEY` 丢掉 null 分支（「—」会变成「— 元」= 把「没取到」说成 0）",
        MONEY_DEF,
        "const MONEY=v=>M(v)+'元';",
        "test_ux_numbers.py::test_不可得的金额不许冒充_0",
    ),
    (
        "M4 「口径说明 · 13 条」的条数改错（用户在屏幕上读到**假的条数**）",
        "口径说明 · 13 条",
        "口径说明 · 12 条",
        "test_ux_numbers.py::test_口径说明的条数必须与实际的条数一致",
    ),
]


def run_one(node: str) -> bool:
    """跑一条判据 ⇒ True = **通过**（⛔ 把"没跑起来"也当通过 —— 那正是"假绿"的一种）。"""
    r = subprocess.run(
        [PY, "-m", "pytest", "-q", f"tests/{node}"],
        cwd=str(BACKEND), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    assert "no tests ran" not in out, f"判据节点没跑起来（名字写错了？）：{node}"
    return r.returncode == 0


def main() -> int:
    before = SHELL.read_bytes()
    hits = 0
    for name, old, new, node in MUTATIONS:
        sh = pick(SHELL, old, new)
        sh0 = sh.read_bytes()
        text = sh.read_text(encoding="utf-8")
        if old not in text:
            print(f"⛔ {name}：**变异串没找到**（实现已改？）—— 本项作废")
            continue
        sh.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
        passed = run_one(node)
        sh.write_bytes(sh0)                                   # ⭐ 每条改完立刻复原
        if passed:
            print(f"❌ {name}：改坏了却**仍然全绿** ⇒ 该断言是假绿")
        else:
            print(f"✅ {name}：对应断言**变红**（有区分力）")
            hits += 1
    ok = hashlib.md5(SHELL.read_bytes()).hexdigest() == hashlib.md5(before).hexdigest()
    print("\n  复原校验（MD5 逐字节）：", "✅ 已复原" if ok else "❌ 没复原！")
    print(f"\n结论：{hits}/{len(MUTATIONS)} 命中" + ("（rc=0）" if ok and hits == len(MUTATIONS) else "（需处理）"))
    return 0 if (ok and hits == len(MUTATIONS)) else 1


if __name__ == "__main__":
    sys.exit(main())
