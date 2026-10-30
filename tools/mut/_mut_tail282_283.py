"""**反向灵敏度** —— `TAIL-282` / `TAIL-283` 本批**新增或改形**的判据**到底有没有区分力**。

## 为什么有这个件

2026-10-11 的双轴 `/code-review`（基点 `14d53aa`）**Standards 轴当场判红**：本批新增的 11 条用例
在 `tools/mut/` 里 **grep 0 命中** —— 违反 `docs/agents/workflow.md`「自证」与
`docs/guides/frontend-design.md` §0「**新增／修改判据时按仓内流程补隔离反向灵敏度**」。
（本件就是那条硬违规的补件：⛔ 不是"为了绿而补"，而是"这些断言到底拦不拦得住退化"此前无人证明。）

## 做法（同 `_mut_m03pay.py`）

逐条把实现**改坏** → 跑**点名的那一条判据** → 必须变红 → 按**原 bytes**复原 → 末尾 MD5 逐字节校验。
⚠️ 锚点命中 0 次 ⇒ 报「**未验证**」并计入失败（⛔ 不许静默跳过 —— 静默失效是这套东西最大的坑）。"""
from __future__ import annotations
from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir, finish_run as _finish_run
import hashlib
import os
import pathlib
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
BE = ROOT / 'backend'
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'audit'))
PY = BE / '.venv' / 'Scripts' / 'python.exe'
APP = BE / 'app'
T282_DRAFT = 'tests/test_tail282_pay_draft.py::test_手改拟付后重拉列表草稿不丢且按通知书记'
T282_FACT = 'tests/test_tail282_pay_draft.py::test_审批额或已付额变化后旧草稿作废'
T282_PAYOK = 'tests/test_tail282_pay_draft.py::test_付款成功后即使列表刷新失败也作废草稿'
T282_REVOKE = 'tests/test_tail282_pay_draft.py::test_撤销成功后即使刷新失败也作废草稿且回执仍在'
T283_FIVE = 'tests/test_tail283_flow.py::test_装配补五项且失联流水照常出行'
T283_EXPORT = 'tests/test_tail283_flow.py::test_导出全量装配并逐格对上页面列'
T283_ZERO = 'tests/test_tail283_flow.py::test_只有已撤销时导出仍写零合计且无伪数据行'
T283_COLS = 'tests/test_shell_ui_workflow.py::test_付款流水补通知书五列并改对操作人与流水号'
T283_SUM = 'tests/test_shell_ui_workflow.py::test_付款流水合计只加实付且导出按屏幕行序'
T283_SORT = 'tests/test_shell_ui_workflow.py::test_通知书名含合计词的行不被排序钉到表尾'

def _b(s: str) -> bytes:
    """把源码片段编成 **LF** bytes（匹配前按目标文件行尾归一）。"""
    return s.replace('\r\n', '\n').encode('utf-8')

def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b'\r\n' in sample:
        return fragment.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    return fragment.replace(b'\r\n', b'\n')
MUTS: list[tuple[str, Path, bytes, bytes, str]] = [('M5 失联流水的审批额伪 0（「没有这个数」装成「是 0」）', APP / 'mod05_flow' / 'service.py', _b('"amount_approved": f"{to_money(n.amount_approved):.2f}" if n else None,'), _b('"amount_approved": f"{to_money(n.amount_approved):.2f}" if n else "0.00",'), T283_FIVE), ('M6 导出不再要全量（回到后端默认当月 ⇒ 历史月份导不出来）', APP / 'mod05_flow' / 'router.py', _b('load(year_month="")'), _b('load()'), T283_EXPORT), ('M7 合计又把「审批金额」并进去（每笔重复的对照数被加总）', APP / 'report_export' / 'fl_export.py', _b('TOTAL_KEYS: frozenset[str] = frozenset({"amount"})'), _b('TOTAL_KEYS: frozenset[str] = frozenset({"amount", "amount_approved"})'), T283_EXPORT), ('M8 全已撤销时不再写零合计行（与屏幕对不上号）', APP / 'mod05_flow' / 'router.py', _b('FLOW_EFFECTIVE],\n                        total_always=True)'), _b('FLOW_EFFECTIVE],\n                        total_always=False)'), T283_ZERO)]

def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()

def run_one(case: str) -> bool:
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    r = subprocess.run([str(PY), '-m', 'pytest', '-q', case], cwd=str(BE), capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
    return r.returncode == 0

def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old_lf, new_lf, case in MUTS:
        path = path
        before.setdefault(path, (path.read_bytes(), md5(path)))
        src = path.read_bytes()
        old, new = (_fit(old_lf, src), _fit(new_lf, src))
        n = src.count(old)
        if n != 1:
            print(f'  ⛔ {desc} —— 锚点命中 {n} 次（期望 1）⇒ **未验证**')
            continue
        path.write_bytes(src.replace(old, new, 1))
        red = not run_one(case)
        path.write_bytes(src)
        print(('  ✅ ' if red else '  ⛔ 未命中 ') + desc + f"  → `{case.rsplit('::', 1)[-1]}` " + ('变红' if red else '**仍是绿的**'))
        hit += red
    print()
    ok = all((md5(p) == h for p, (_, h) in before.items()))
    print(f'  命中 {hit}/{len(MUTS)}')
    print(f"  复原校验（MD5 逐字节）：{('✅ 全部复原' if ok else '❌ 有文件没复原')}")
    return 0 if hit == len(MUTS) and ok else 1
if __name__ == '__main__':
    sys.exit(_finish_run(main()))
