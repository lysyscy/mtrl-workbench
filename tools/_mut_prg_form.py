"""反向灵敏度（PRG 形态尺子 `tools/prg_form_audit.py`）—— 证明这把尺子**真的有区分力**。

做法：逐个把实现故意改坏 ⇒ 断言**对应的那条报告确实出现** ⇒ 逐字节复原（MD5）。
    python tools/_mut_prg_form.py
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
ROUTER = ROOT / "backend" / "app" / "mod04_plan" / "router.py"
AUDIT = "tools/prg_form_audit.py"

DRAFT_SIG = (
    '    year_month: str = Form(""), project: list[str] = Form(default=[]),\n'
    '    review: str = Form(BUCKET_ALL), sort: str = Form(""), dir: int = Form(SORT_NONE),\n'
    ") -> RedirectResponse:\n"
    '    """开草稿行'
)

CASES = [
    # name, old, new, 期望在输出里出现, 是否期望非零退出
    ("M1 草稿端点的筛选参数退回 Query（回跳丢筛选）",
     DRAFT_SIG,
     DRAFT_SIG.replace('year_month: str = Form("")', 'year_month: str = Query("")', 1),
     "act_row_draft", False),
    ("M2 强制通过的备注退回 Query",
     '    row_id: int = Form(...),\n    remark: str = Form(""),\n',
     '    row_id: int = Form(...),\n    remark: str = Query(""),\n',
     "act_force", False),
    ("M3 强制通过的必填参数退回 Query（变成 422 ⇒ 硬档）",
     '    row_id: int = Form(...),\n    remark: str = Form(""),',
     '    row_id: int = Query(...),\n    remark: str = Form(""),',
     "act_force", True),
]


def run() -> tuple[int, str]:
    p = subprocess.run([str(PY), AUDIT], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def main() -> int:
    base = ROUTER.read_bytes()
    h0 = md5(ROUTER)
    rc0, out0 = run()
    print(f"  基线：rc={rc0} · 输出 {'干净' if 'act_row_draft' not in out0 else '已含 act_row_draft'}")
    if rc0 != 0 or "act_row_draft" in out0:
        print("  ⛔ 基线不干净 ⇒ 停手")
        return 1

    hits = 0
    for name, old, new, needle, want_fail in CASES:
        text = ROUTER.read_text(encoding="utf-8")
        if old not in text:
            print(f"  ❌ {name} —— 变异串没找到")
            continue
        ROUTER.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")
        rc, out = run()
        ROUTER.write_bytes(base)                      # 立刻复原
        found = needle in out and (rc != 0) == want_fail
        print(f"  {'✅' if found else '❌'} {name} —— 期望「{needle}」出现在报告里"
              f"（rc={rc}，{'应为非零' if want_fail else '应为 0'}）⇒ {'命中' if found else '未命中'}")
        hits += 1 if found else 0

    ok = md5(ROUTER) == h0
    print(f"\n  复原校验（MD5 逐字节）：{'✅ 1/1' if ok else '❌ 未复原'}")
    print(f"  反向灵敏度：**{hits}/{len(CASES)} 命中**")
    return 0 if (hits == len(CASES) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
