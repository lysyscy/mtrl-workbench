"""**反向灵敏度**：证明「未登录 ⇒ 无身份」那条断言（`ACC-USR-MGMT-001/001-01`）**真有区分力**。

用法：`backend/.venv/Scripts/python.exe tools/_mut_auth.py`
"""
from __future__ import annotations
from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir, finish_run as _finish_run
import hashlib
import os
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
BE = ROOT / 'backend'
sys.path.insert(0, str(ROOT / 'tools'))
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'audit'))
PY = BE / '.venv' / 'Scripts' / 'python.exe'
API_PY = ROOT / 'backend' / 'app' / 'mod15_user' / 'api.py'
CASE = 'tests/test_acc_usr_login.py::test_当前登录用户是管理员且管理员恒一个'

def _b(s: str) -> bytes:
    return s.replace('\r\n', '\n').encode('utf-8')

def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b'\r\n' in sample:
        return fragment.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    return fragment.replace(b'\r\n', b'\n')

def _locate(src: bytes, frag_lf: bytes):
    for cand in (frag_lf, _fit(frag_lf, src)):
        if src.count(cand) >= 1:
            return (src.count(cand), cand)
    return (0, None)
MUTS = [('M1 ⭐ 把「回落到首个在用管理员」加回去（= 未登录的人自动变管理员）', API_PY, _b('    who = current_name()  # 保留账号/旧标签类型；直接strip会丢掉新票的账号语义。\n    if not who:\n        return None\n'), _b('    who = current_name()  # 保留账号/旧标签类型；直接strip会丢掉新票的账号语义。\n    if not who:\n        return D.active_admins(R.all_users(s))[0]\n'), '⓪ 没有会话 ⇒ `_me` 必须是 None')]

def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()

def run_one(case: str) -> bool:
    env = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1', 'PLAYWRIGHT_BROWSERS_PATH': 'C:\\ProgramData\\ms-playwright'}
    r = subprocess.run([str(PY), '-m', 'pytest', '-q', case], cwd=str(BE), capture_output=True, text=True, encoding='utf-8', errors='replace', env=env)
    return r.returncode == 0

def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old_lf, new_lf, which in MUTS:
        first = old_lf.decode('utf-8').strip().split('\n')[0].strip()
        path = path
        src = path.read_bytes()
        n, cand = _locate(src, old_lf)
        if n != 1:
            print(f'  ⛔ {desc} —— 锚点命中 {n} 次（期望 1）⇒ **未验证**')
            continue
        new = new_lf if cand == old_lf else _fit(new_lf, src)
        path.write_bytes(src.replace(cand, new, 1))
        red = not run_one(CASE)
        path.write_bytes(src)
        print(('  ✅ ' if red else '  ⛔ 未命中 ') + desc + f'  → {which} ' + ('变红' if red else '**仍是绿的**'))
        hit += red
    print()
    ok = all((md5(p) == h for p, (_, h) in before.items()))
    print(f'  命中 {hit}/{len(MUTS)}')
    print(f"  复原校验（MD5 逐字节）：{('✅ 全部复原' if ok else '❌ 有文件没复原')}")
    return 0 if hit == len(MUTS) and ok else 1
if __name__ == '__main__':
    sys.exit(_finish_run(main()))
