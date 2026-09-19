"""反向灵敏度自检 —— `tests/test_wired_m04.py` 那批断言**到底有没有区分力**。

把实现故意改坏（4 处），确认**对应的**断言真的变红；随后**逐字节复原**（MD5 校验）。
⚠️ 只信"改坏后变红"这一件事：只跑一遍全绿证明不了判据有效。

跑法：`backend/.venv/Scripts/python.exe tools/_mut_m04wired.py`（rc=0 = 全部按预期变红且已复原）
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
from shell_source import SHELL_PATH as SHELL  # noqa: F401  ← `P4`① 读取点收敛
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")

MUTATIONS: list[tuple[str, str, str, str]] = [
    (
        "M1 适配层不再取后端的审查判定（result 恒空）",
        "    result: x.audit_result || '',",
        "    result: '',",
        "test_付款计划字段在适配层完成转形",
    ),
    (
        "M2 审查结果又回到「前端自算」（第二份口径）",
        "const plRev=(p)=>String((p&&p.result)||'').trim()||'—';",
        "const plRev=(p,all)=>{ const code=String(p.docNo||'').trim();\n"
        "  if(!code) return '无单据号';\n"
        "  if(Number(p.monthAmt)>Number(n.approve)-paidOf(n.id)) return '超过未付';\n"
        "  return '完全匹配'; };",
        "test_审查结果不再由前端自算",
    ),
    (
        "M3 行内改列又变成「只改内存」",
        "    plAct(()=>API.plCell(p.id, PL_COL_API[f], v),",
        "    p[f]=String(t.value==null?'':t.value).trim(); render(); plAct(()=>API.plCell(p.id, PL_COL_API[f], v),",
        "test_写动作不許用本地赋值冒充落库",
    ),
    (
        "M4 已接线的 m04 又把演示数组放回来",
        "let PLs=[];",
        "const PL = [];\nlet PLs=[];",
        "test_已接线页的演示数组必须已删",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(test_name: str) -> tuple[bool, str]:
    r = subprocess.run(
        [PY, "-m", "pytest", "-q", f"tests/test_wired_m04.py::{test_name}"],
        cwd=str(BACKEND), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.returncode == 0, (r.stdout or "")[-300:]


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
