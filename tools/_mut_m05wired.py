"""反向灵敏度自检 —— `tests/test_wired_m05.py` 那批断言**到底有没有区分力**。

把实现故意改坏（5 处），确认**对应的**断言真的变红；随后**逐字节复原**（MD5 校验）。
⚠️ 只信「改坏后变红」这一件事：跑一遍全绿证明不了判据有效。

跑法：`backend/.venv/Scripts/python.exe tools/_mut_m05wired.py`（rc=0 = 全部按预期变红且已复原）
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SHELL = BACKEND / "app" / "web" / "index.html"
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")

MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "M1 欠款又回到「前端自算」",
        "  const d = M05.debt || {};",
        "  const d = {}; const 辅材=N2(NO.filter(n=>ntLive(n)&&n.cat==='辅材').reduce((a,n)=>a+(n.ss-n.sp),0));",
        "test_欠款台账统计不再由前端自算",
    ),
    (
        "M2 台账行又回前端按月拼",
        "const ledRows=(sc,proj)=>{ const side=m05Side(sc); if(!side) return [];",
        "const ledRows=(sc,proj)=>{ const side=null; const ms=NO.filter(n=>ntLive(n)&&n.cat===sc&&ntProjKey(n)===proj).map(ntYm); if(!side) return [];",
        "test_欠款台账统计不再由前端自算",
    ),
    (
        "M3 撤销又变成「只改内存」",
        "    m05Act(()=>API.flowRevoke(f.id, rs),",
        "    f.voided=true; f.reason=rs; render(); m05Act(()=>API.flowRevoke(f.id, rs),",
        "test_写动作不許用本地赋值冒充落库",
    ),
    (
        "M4 机械结算项**又退回取零出口**（接线后必须读真源）",
        ": N2(machSettleOf(k)",
        ": N2(m05MechSettle(k)",
        "test_机械结算源已接线_读真源",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(test_name: str) -> tuple[bool, str]:
    r = subprocess.run(
        [PY, "-m", "pytest", "-q", f"tests/test_wired_m05.py::{test_name}"],
        cwd=str(BACKEND), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.returncode == 0, (r.stdout or "")[-260:]


def main() -> int:
    before = SHELL.read_bytes()
    hits = 0
    for name, old, new, test_name in MUTATIONS:
        text = SHELL.read_text(encoding="utf-8")
        if old not in text:
            print(f"⛔ {name}：**变异串没找到**（实现已改？）—— 本项作废")
            SHELL.write_bytes(before)
            continue
        SHELL.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
        passed, tail = run_one(test_name)
        SHELL.write_bytes(before)                    # 每条改完立刻复原，避免互相污染
        if passed:
            print(f"❌ {name}：改坏了却**仍然全绿** ⇒ 该断言是假绿\n{tail}")
        else:
            print(f"✅ {name}：对应断言**变红**（有区分力）")
            hits += 1

    ok = md5(SHELL) == hashlib.md5(before).hexdigest()
    print("\n  复原校验（MD5 逐字节）：", "✅ 已复原" if ok else "❌ 没复原！")
    print(f"\n结论：{hits}/{len(MUTATIONS)} 命中" + ("（rc=0）" if ok and hits == len(MUTATIONS) else "（需处理）"))
    return 0 if (ok and hits == len(MUTATIONS)) else 1


if __name__ == "__main__":
    sys.exit(main())
