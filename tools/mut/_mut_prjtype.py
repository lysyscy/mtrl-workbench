"""反向灵敏度（变异测试）—— `TAIL-42`「人工覆盖三类判定」的断言。

做法：把实现**故意改坏**，确认对应断言**确实变红**；每处跑完**逐字节复原**并核 MD5。
⚠️ 变异点**不是"无害变异"**（改了行为不变 ⇒ 断言当然不红），也**不动断言自身的锚字符串**。
⚠️ 跑 pytest 时结果**另写**一份（⛔ 别把全套的 `var/state/verification/acc_results.json` 冲掉）。

跑法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\_mut_prjtype.py`
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
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'audit'))
ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / 'backend' / '.venv' / 'Scripts' / 'python.exe'
BE = ROOT / 'backend'
MUT_RESULTS = str(ROOT / _run_dir() / '_mut_acc_results.json')
MUTATIONS: list[dict] = [{'id': 'M2', 'file': 'backend/app/mod01_projects/repository.py', 'old': '    if new_type not in (TYPE_NORMAL, TYPE_SHELL):', 'new': '    if new_type not in (TYPE_NORMAL, TYPE_SHELL, TYPE_SMALL):   # 变异：连具体小微也收', 'test': 'tests/test_acc_prj_type.py', 'k': '具体小微不由人工指定', 'why': '人工能造出「挂不上壳、没仓库名」的具体小微 ⇒ 归属判定与归档不变式全乱'}, {'id': 'M3', 'file': 'backend/app/mod01_projects/archive.py', 'old': '        manual_override = TYPE_SHELL if name in shells_in_archive else None', 'new': '        manual_override = None                    # 变异：人工覆盖不粘（下次同步又按关键字判）', 'test': 'tests/test_acc_prj_type.py', 'k': '同族仓库在建行时按壳处理', 'why': '纠正过一次的行，下次同步又被建成普通项目 ⇒ 材料侧重复处理的病根没除'}]

def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()

def run(test: str, k: str) -> int:
    env = dict(os.environ)
    env.update({'PYTHONIOENCODING': 'utf-8', 'PYTHONDONTWRITEBYTECODE': '1', 'CODEBUDDY_SAFE_DELETE_ENABLED': '0'})
    r = subprocess.run([str(PY), '-m', 'pytest', '-q', test, '-k', k, '-p', 'no:cacheprovider', '--no-header'], cwd=BE, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    return r.returncode

def main() -> int:
    ok = bad = 0
    for m in MUTATIONS:
        f = ROOT / m['file']
        f = f
        before = md5(f)
        raw = f.read_bytes()
        eol = b'\r\n' if b'\r\n' in raw else b'\n'
        needle = m['old'].encode('utf-8').replace(b'\n', eol)
        newb = m['new'].encode('utf-8').replace(b'\n', eol)
        cnt = raw.count(needle)
        if cnt != 1:
            print(f"❌ {m['id']} 变异点命中 {cnt} 次（须唯一）—— 源码已变，按现码重写锚点")
            bad += 1
            continue
        f.write_bytes(raw.replace(needle, newb))
        try:
            rc = run(m['test'], m['k'])
        finally:
            f.write_bytes(raw)
        same = md5(f) == before
        good = rc != 0 and same
        ok += 1 if good else 0
        bad += 0 if good else 1
        print(f"{m['id']} [TAIL-42 类型纠正] {('✅ 变红' if rc != 0 else '❌ 仍绿（断言没抓住！）')}  rc={rc} · MD5复原={('是' if same else '否❗')}")
        print(f"    {m['file']} ← {m['why']}")
    Path(MUT_RESULTS).unlink(missing_ok=True)
    print(f"\n合计 {ok}/{len(MUTATIONS)} 中 · 源文件全部逐字节复原 = {('是' if bad == 0 else '否')}")
    return 0 if bad == 0 else 1
if __name__ == '__main__':
    sys.exit(_finish_run(main()))
