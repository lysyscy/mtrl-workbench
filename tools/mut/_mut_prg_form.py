"""反向灵敏度（PRG 形态尺子 `tools/audit/prg_form_audit.py`）—— 证明这把尺子**真的有区分力**。

做法：逐个把实现故意改坏 ⇒ 断言**对应的那条报告确实出现** ⇒ 逐字节复原（MD5）。
    python tools/mut/_mut_prg_form.py

⚠️ 2026-09-24 订正（接手核验轮查出）：本件原写 `tools/prg_form_audit.py` —— ⛔ **那是搬迁前的旧路径**
   （`TAIL-58` 分目录后尺子进了 `tools/audit/`）⇒ 子进程起不来、基线 rc=2 ⇒ 本件**静默失效**
   （表现为"基线不干净 ⇒ 停手"，而不是假绿）。同类病灶当天已中过三次，故顺手一并核了它。
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
# ⚠️ 2026-09-24 订正（接手核验轮）：**靶也换了** —— 原 3 条打的是 `mod04_plan` 的旧 PRG 表单端点
#    （`act_row_draft` / `act_force`），那些端点**已随旧渲染层删除** ⇒ 修好路径后实测 **0/3**（变异串一个都找不到）。
#    全站现在只剩 **3 个真 PRG 端点**，都在 `mod05_flow/router.py`
#    （`/m05/opening` · `/m05/opening/delete` · `/m05/ledger/remark`）⇒ 改指它们，**claim 一字未改**：
#    「PRG 端点参数必须用 `Form`（输入在 body）—— 退回 `Query` ⇒ 必填则永远 422、可选则回跳筛选静默丢失」。
TARGET = ROOT / "backend" / "app" / "mod05_flow" / "router.py"
# ⚠️ 2026-09-24 订正：尺子已随 `TAIL-58` 搬进 `tools/audit/`（旧路径 ⇒ 子进程 rc=2 ⇒ 本件失效）。
AUDIT = "tools/audit/prg_form_audit.py"

OPEN_SIG = (
    "def act_opening(\n"
    '    category: str = Form(...), project_id: int = Form(...), cutoff_ym: str = Form(""),\n'
    '    settle_amount: str = Form(""), paid_amount: str = Form(""), remark: str = Form(""),\n'
    '    end_ym: str = Form(""),\n'
    ") -> RedirectResponse:\n"
)
REMARK_SIG = (
    "def act_remark(\n"
    '    category: str = Form(...), project_id: int = Form(...), ym: str = Form(""),\n'
    '    remark: str = Form(""), end_ym: str = Form(""),\n'
    ") -> RedirectResponse:\n"
)

CASES = [
    # name, old, new, 期望在输出里出现, 是否期望非零退出
    ("M1 期初录入的必填 `category` 退回 Query（表单提交即 422 ⇒ 硬档）",
     OPEN_SIG,
     OPEN_SIG.replace('category: str = Form(...)', 'category: str = Query(...)', 1),
     "act_opening", True),
    ("M2 期初录入的必填 `project_id` 退回 Query（同上 · 换一个参数位）",
     OPEN_SIG,
     OPEN_SIG.replace('project_id: int = Form(...)', 'project_id: int = Query(...)', 1),
     "act_opening", True),
    ("M3 台账备注的可选 `remark` 退回 Query（不 422，但回跳 / 筛选静默丢失 ⇒ 软档）",
     REMARK_SIG,
     REMARK_SIG.replace('remark: str = Form("")', 'remark: str = Query("")', 1),
     "act_remark", False),
]


def run() -> tuple[int, str]:
    # ⚠️ 2026-10-06（`TAIL-239`）：`-X utf8` 是**必需** —— 少了它尺子会自己崩（`UnicodeEncodeError`）
    #   ⇒ 本件误报「基线不干净」。**这一族的口径主人（含一手证据）＝ `_run_muts.py` 的题头 ⑤**。
    p = subprocess.run([str(PY), "-X", "utf8", AUDIT], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def main() -> int:
    base = TARGET.read_bytes()
    h0 = md5(TARGET)
    rc0, out0 = run()
    print(f"  基线：rc={rc0} · 输出 {'干净' if 'act_opening' not in out0 else '已含 act_opening'}")
    if rc0 != 0 or "act_opening" in out0:
        print("  ⛔ 基线不干净 ⇒ 停手")
        return 1

    hits = 0
    for name, old, new, needle, want_fail in CASES:
        text = TARGET.read_text(encoding="utf-8")
        if old not in text:
            print(f"  ❌ {name} —— 变异串没找到")
            continue
        TARGET.write_text(text.replace(old, new, 1), encoding="utf-8", newline="")
        rc, out = run()
        TARGET.write_bytes(base)                      # 立刻复原
        found = needle in out and (rc != 0) == want_fail
        print(f"  {'✅' if found else '❌'} {name} —— 期望「{needle}」出现在报告里"
              f"（rc={rc}，{'应为非零' if want_fail else '应为 0'}）⇒ {'命中' if found else '未命中'}")
        hits += 1 if found else 0

    ok = md5(TARGET) == h0
    print(f"\n  复原校验（MD5 逐字节）：{'✅ 1/1' if ok else '❌ 未复原'}")
    print(f"  反向灵敏度：**{hits}/{len(CASES)} 命中**")
    return 0 if (hits == len(CASES) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
