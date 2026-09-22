"""反向灵敏度自检 —— `tests/test_wired_m01.py` 那批断言**到底有没有区分力**。

做法：把实现故意改坏（4 处），确认**对应的**断言真的变红；随后**逐字节复原**（MD5 校验）。
⚠️ 只信"改坏后变红"这一件事 —— 只跑一遍全绿证明不了判据有效（假绿温床）。

跑法：`backend/.venv/Scripts/python.exe tools/_mut_m01wired.py`（rc=0 = 全部按预期变红且文件已复原）
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH as SHELL, pick  # noqa: F401  ← `P4`① 读取点收敛
ROUTER = BACKEND / "app" / "mod01_projects" / "router.py"
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")

MUTATIONS: list[tuple[str, Path, str, str, str]] = [
    (
        "M1 状态不再做「内部值 ⇄ 显示值」转换（列表会恒空）",
        SHELL,
        "    status: PJ_STATUS_LABEL[p.status] || p.status || '',",
        "    status: p.status || '',",
        "test_项目状态在适配层完成内部值与显示值的互转",
    ),
    (
        "M2 父壳 id 不转字符串（壳与小微永远对不上）",
        SHELL,
        "    parent: (p.parent_shell_id == null ? null : String(p.parent_shell_id)),",
        "    parent: p.parent_shell_id,",
        "test_项目id与父壳id一律转字符串",
    ),
    (
        "M3 前端又自己算状态不变式（第二份规则）",
        SHELL,
        "  editStatus:t=>{ const p=PJs.find(x=>x.id===t.dataset.id), v=t.value; if(!p||v===p.status) return;",
        "  editStatus:t=>{ const p=PJs.find(x=>x.id===t.dataset.id), v=t.value; if(!p||v===p.status) return;\n    if(v==='归档'&&p.type==='shell'){ toast('不能归档'); return; }",
        "test_前端不再自己算状态不变式",
    ),
    (
        "M4 trails 的 limit 去掉上下界（越界不再 422）",
        ROUTER,
        'def trails(limit: int = Query(20, ge=1, le=200)) -> list[TrailOut]:',
        'def trails(limit: int = Query(20)) -> list[TrailOut]:',
        "test_trails端点存在且limit有边界",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(test_name: str) -> tuple[bool, str]:
    """跑单条测试 ⇒ (是否通过, 输出尾巴)。"""
    r = subprocess.run(
        [PY, "-m", "pytest", "-q", f"tests/test_wired_m01.py::{test_name}"],
        cwd=str(BACKEND), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.returncode == 0, (r.stdout or "")[-400:]


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTATIONS}}
    hits = 0
    for name, path, old, new, test_name in MUTATIONS:
        # ⚠️ 2026-09-19（性能 `P4`② 三刀真拆）：壳已拆成多件（`web/shell/*.js`）⇒ 锚点在哪件就改哪件。
        path = pick(path, old, new)
        before.setdefault(path, (path.read_bytes(), hashlib.md5(path.read_bytes()).hexdigest()))
        text = path.read_text(encoding="utf-8")
        if old not in text:
            print(f"⛔ {name}：**变异串没找到**（实现已改？）—— 本项作废")
            continue
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        try:
            passed, tail = run_one(test_name)
        finally:
            pass
        # 复原（每条改完立刻还原，避免互相污染）
        path.write_bytes(before[path][0])
        if passed:
            print(f"❌ {name}：改坏了却**仍然全绿** ⇒ 该断言是假绿\n{tail}")
        else:
            print(f"✅ {name}：对应断言**变红**（有区分力）")
            hits += 1

    print("\n  复原校验（MD5 逐字节）：", end="")
    ok = all(md5(p) == before[p][1] for p in before)
    print("✅ 全部复原" if ok else "❌ 有文件没复原！")
    print(f"\n结论：{hits}/{len(MUTATIONS)} 命中" + ("（rc=0）" if (ok and hits == len(MUTATIONS)) else "（需处理）"))
    return 0 if (ok and hits == len(MUTATIONS)) else 1


if __name__ == "__main__":
    sys.exit(main())
