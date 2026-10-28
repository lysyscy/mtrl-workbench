"""**反向灵敏度**：证明 `test_wired_m03_pay.py`（`§19` 批 4 · S4⑤ 搬的 9 条壳侧断言）**真有区分力**。

做法：逐条把实现**改坏** → 确认**对应的那条断言变红** → 全部复原（**MD5 逐字节校验**）。
⚠️ 若某条变异**没能让断言变红** ⇒ 那条断言是**假绿** ⇒ 脚本报错退出。"""
from __future__ import annotations
from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir
import hashlib
import os
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
BE = ROOT / 'backend'
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'audit'))
ACTIONS = BE / 'app' / 'mod03_notice' / 'notice_pay_actions.py'
PY = BE / '.venv' / 'Scripts' / 'python.exe'
TEST = 'tests/test_wired_m03_pay.py'

def _b(s: str) -> bytes:
    """把源码片段编成 **LF** bytes（脚本里一律按 LF 写片段，匹配前再按目标文件归一）。"""
    return s.replace('\r\n', '\n').encode('utf-8')

def _fit(fragment: bytes, sample: bytes) -> bytes:
    """把 LF 片段转成**与目标文件一致**的行尾（目标含 CRLF ⇒ 转 CRLF，否则原样）。"""
    if b'\r\n' in sample:
        return fragment.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    return fragment.replace(b'\r\n', b'\n')
MUTS: list[tuple[str, Path, bytes, bytes, str]] = [('M3 付款方式取不到不再兜底「现汇」', ACTIONS, _b('    return str((plan_methods or {}).get(str(bill_no or "").strip()) or "") or "现汇"'), _b('    return str((plan_methods or {}).get(str(bill_no or "").strip()) or "")'), 'test_付款方式默认取付款计划取不到兜底现汇')]

def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()

def run_one(case: str) -> bool:
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1'}
    r = subprocess.run([str(PY), '-m', 'pytest', '-q', f'{TEST}::{case}'], cwd=str(BE), capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
    return r.returncode == 0

def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old_lf, new_lf, case in MUTS:
        path = path
        before.setdefault(path, (path.read_bytes(), hashlib.md5(path.read_bytes()).hexdigest()))
        src = path.read_bytes()
        old, new = (_fit(old_lf, src), _fit(new_lf, src))
        n = src.count(old)
        if n != 1:
            print(f'  ⛔ {desc} —— 锚点命中 {n} 次（期望 1）⇒ **未验证**')
            continue
        path.write_bytes(src.replace(old, new, 1))
        red = not run_one(case)
        path.write_bytes(src)
        print(('  ✅ ' if red else '  ⛔ 未命中 ') + desc + f'  → `{case}` ' + ('变红' if red else '**仍是绿的**'))
        hit += red
    print()
    ok = all((md5(p) == h for p, (_, h) in before.items()))
    print(f'  命中 {hit}/{len(MUTS)}')
    print(f"  复原校验（MD5 逐字节）：{('✅ 全部复原' if ok else '❌ 有文件没复原')}")
    return 0 if hit == len(MUTS) and ok else 1
if __name__ == '__main__':
    sys.exit(main())
