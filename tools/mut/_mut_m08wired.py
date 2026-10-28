"""**反向灵敏度**：证明 `test_wired_m08.py` 的断言**真有区分力**。

做法：逐条把实现**改坏** → 确认**对应的那条断言变红** → 全部复原（**MD5 逐字节校验**）。

⚠️ 若某条变异**没能让断言变红** ⇒ 那条断言是**假绿**（它没钉住它声称钉的东西）⇒ 脚本报错退出。
"""
from __future__ import annotations
import hashlib
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'audit'))
PY = ROOT / 'backend' / '.venv' / 'Scripts' / 'python.exe'
TEST = 'tests/test_wired_m08.py'
MUTS: list[tuple[str, Path, str, str, str]] = [('M8 抓取端点不再要 `confirm`（静默抓取 ⇒ 会顶号）', ROOT / 'backend' / 'app' / 'mod08_inv' / 'router.py', 'confirmed=req.confirm', 'confirmed=True', 'test_抓取端点必须显式确认')]

def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()

def run_one(case: str) -> bool:
    """跑单条断言 ⇒ True = 通过，False = 变红。"""
    r = subprocess.run([str(PY), '-m', 'pytest', '-q', f'{TEST}::{case}'], cwd=str(ROOT / 'backend'), capture_output=True, text=True, encoding='utf-8')
    return r.returncode == 0

def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old, new, case in MUTS:
        path = path
        before.setdefault(path, (path.read_bytes(), hashlib.md5(path.read_bytes()).hexdigest()))
        t = path.read_text(encoding='utf-8')
        if t.count(old) != 1:
            print(f'  ⛔ {desc} —— 锚点命中 {t.count(old)} 次（期望 1）⇒ **未验证**')
            continue
        path.write_text(t.replace(old, new), encoding='utf-8', newline='\n')
        red = not run_one(case)
        path.write_text(before[path][0].decode('utf-8'), encoding='utf-8', newline='\n')
        print(('  ✅ ' if red else '  ⛔ 未命中 ') + desc + f'  → `{case}` ' + ('变红' if red else '**仍是绿的**'))
        hit += red
    print()
    ok = all((md5(p) == h for p, (_, h) in before.items()))
    print(f'  命中 {hit}/{len(MUTS)}')
    print(f"  复原校验（MD5 逐字节）：{('✅ 全部复原' if ok else '❌ 有文件没复原')}")
    return 0 if hit == len(MUTS) and ok else 1
if __name__ == '__main__':
    sys.exit(main())
