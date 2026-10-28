"""反向灵敏度（变异测试）—— `MOD-07` 壳接线断言 **是否真有区分力**。

做法：把实现**故意改坏**若干处，确认**对应断言确实变红**；每次立刻按 bytes 复原，最后核对 MD5。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_m7w.py`

⚠️ 本仓纪律（见 memory §十七）：
1. **一律走 bytes**（`write_text` 在 Windows 会把 `
` 写成 `\r
` ⇒ MD5 假 BAD）；
2. 变异片段**含中文**时用 `str` ＋ `.encode()`（`b"…"` 只允许 ASCII）；
3. **行尾按目标文件归一**（本仓源码行尾不统一）；
4. 变异点**必须唯一命中**，否则重写（不得当成"已通过"）；
5. 默认重跑复原态全套 `pytest`；显式 `--no-full-suite` 跳过，本轮不刷新权威四态。

⚠️ 本次首跑就抓出 **2 处假绿**（断言写得不够紧）—— 已同步改紧：
   · `in: N0(` 这条正则缺前缀边界 ⇒ 被 `begin:` 里的子串 `in:` 喂饱；
   · `boot()` 断言用 `body.index("reloadMech")` ⇒ 被**注释里**的同名字串喂饱。
"""
from __future__ import annotations
import hashlib
import subprocess
import sys
from pathlib import Path
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'audit'))
ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / 'backend' / '.venv' / 'Scripts' / 'python.exe'
FILES = {'api': ROOT / 'backend' / 'app' / 'mod07_setl' / 'api.py', 'm06r': ROOT / 'backend' / 'app' / 'mod06_proc' / 'router.py'}
MUTATIONS: list[tuple[str, str, str, str, str]] = [('抓取端点不要求二次确认（D9 形同虚设）', 'api', 'confirmed=req.confirm', 'confirmed=True', 'test_抓取端点必须显式确认'), ('机械写端点不复用 mech_ui 判据（另写一套）', 'm06r', 'mech_ui.parse_mech_values(req.values).items()', '{}.items()', 'test_后端机械写端点存在')]

def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b'\r\n' in sample:
        return fragment.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    return fragment.replace(b'\r\n', b'\n')

def main() -> int:
    orig = {k: p.read_bytes() for k, p in FILES.items()}
    md5_before = {k: hashlib.md5(v).hexdigest() for k, v in orig.items()}
    for k, v in orig.items():
        print(f'{k}: {len(v)} 字节 · MD5 {md5_before[k][:12]}')
    hit = miss = 0
    for i, (label, fkey, old, new, test_name) in enumerate(MUTATIONS, 1):
        target = orig[fkey]
        o = _fit(old.encode('utf-8'), target)
        n = _fit(new.encode('utf-8'), target)
        cnt = target.count(o)
        if cnt != 1:
            print(f'  {i:2d}. ⚠️ SKIP（变异点命中 {cnt} 次）—— [{fkey}] {label}')
            miss += 1
            continue
        FILES[fkey].write_bytes(target.replace(o, n))
        r = subprocess.run([str(PY), '-m', 'pytest', '-q', '-k', test_name, 'tests/'], cwd=ROOT / 'backend', capture_output=True, text=True)
        bad = r.returncode != 0
        print(f"  {i:2d}. {('✅ 变红' if bad else '⛔ 仍绿（假绿！）')} —— [{fkey}] {label}  [{test_name}]")
        if bad:
            hit += 1
        FILES[fkey].write_bytes(target)
    md5_after = {k: hashlib.md5(p.read_bytes()).hexdigest() for k, p in FILES.items()}
    ok_md5 = all((md5_after[k] == md5_before[k] for k in FILES))
    print(f"\n命中 {hit}/{len(MUTATIONS) - miss} · SKIP {miss} · MD5 {('逐字节复原 ✅' if ok_md5 else '⛔ 不一致')}")
    if '--no-full-suite' in sys.argv:
        print('跳过全套 pytest（--no-full-suite）：本轮不刷新权威四态')
        full_rc = 0
    else:
        print('重跑全套 pytest（复原态）…')
        full = subprocess.run([str(PY), '-m', 'pytest', '-q', 'tests/'], cwd=ROOT / 'backend', capture_output=True, text=True)
        print('  全套 pytest 退出码 =', full.returncode)
        full_rc = full.returncode
    return 0 if ok_md5 and miss == 0 and (hit == len(MUTATIONS)) and (full_rc == 0) else 1
if __name__ == '__main__':
    sys.exit(main())
