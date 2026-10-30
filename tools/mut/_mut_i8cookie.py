"""反向灵敏度（变异测试）—— `§7.8 i8 凭据` 这一片（**cookie 磁盘缓存复用** ＋ **未绑即拒**）的断言
**是否真有区分力**。

⚠️ 2026-09-30 扩了一次（`TAIL-202`）：本件从"只盯 cookie 缓存"扩成"盯**整片 i8 凭据口径**"——
   新增两靶 = **有身份却没绑 ⇒ 拒绝**（`core/identity.py`）＋ **壳上那两处"未绑定"的说法**
   （`shell/actions.js`）。⛔ 别因为文件名还叫 `i8cookie` 就以为它只管缓存。

做法：把实现**故意改坏**若干处，确认**对应断言确实变红**；每次立刻按 bytes 复原，最后核对 MD5。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_i8cookie.py`

⚠️ 本仓纪律（memory §十七）：bytes 写入 / 行尾按目标文件归一 / 变异点必须唯一命中 /
   跑完必须再跑一次全套 `pytest`。
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
PY = ROOT / 'backend' / '.venv' / 'Scripts' / 'python.exe'
FILES = {'client': ROOT / 'backend' / 'app' / 'mod02_i8' / 'client.py', 'cookie': ROOT / 'backend' / 'app' / 'mod02_i8' / 'cookie_store.py', 'gitignore': ROOT / '.gitignore', 'identity': ROOT / 'backend' / 'app' / 'core' / 'identity.py'}
T_HIT = 'test_缓存命中则不登录'
T_SAVE = 'test_无缓存则登录一次且写进缓存'
T_LEGACY = 'test_旧纯文本格式兼容'
T_GIT = 'test_缓存文件不进git'
T_UNBOUND = 'test_i8凭据取当前登录用户绑定且未绑拒抓取'
MUTATIONS: list[tuple[str, str, str, str, str]] = [('去掉「优先读缓存」（缓存命中仍去登录）', 'client', '        if cached:', '        if False:', T_HIT), ('登录成功后不落盘（下次还得再登一次）', 'client', '        cookie_store.save(result.cookie, source="http_login", user=user)', '        _ = result.cookie', T_SAVE), ('旧纯文本格式不再兼容（整文件就是一行 cookie）', 'cookie', '        return raw, "", "legacy"', '        return None, "", ""', T_LEGACY), ('缓存规则从 .gitignore 挪走（凭证会进 git）', 'gitignore', 'var/state/i8_cookie/', 'var/state/__i8cookie_off__/', T_GIT), ('有身份却没绑 i8 时**不再拒绝**（悄悄回落用共享账号 ⇒ 顶掉同事的在线会话）', 'identity', '            raise MustReportError(', '            if False: raise MustReportError(', T_UNBOUND)]

def _child_env() -> dict:
    """给子进程（`pytest`）的环境：**显式 UTF-8** ＋ 四态写回**局部档**（⛔ 不冲权威档）。"""
    return {**os.environ, 'PYTHONIOENCODING': 'utf-8'}

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
        try:
            r = subprocess.run([str(PY), '-m', 'pytest', '-q', '-k', test_name, 'tests/'], cwd=ROOT / 'backend', capture_output=True, encoding='utf-8', errors='replace', env=_child_env())
            bad = r.returncode != 0
        finally:
            FILES[fkey].write_bytes(target)
        print(f"  {i:2d}. {('✅ 变红' if bad else '⛔ 仍绿（假绿！）')} —— [{fkey}] {label}  [{test_name}]")
        if bad:
            hit += 1
    md5_after = {k: hashlib.md5(p.read_bytes()).hexdigest() for k, p in FILES.items()}
    ok_md5 = all((md5_after[k] == md5_before[k] for k in FILES))
    print(f"\n命中 {hit}/{len(MUTATIONS) - miss} · SKIP {miss} · MD5 {('逐字节复原 ✅' if ok_md5 else '⛔ 不一致')}")
    print('重跑全套 pytest（复原态）…')
    full = subprocess.run([str(PY), '-m', 'pytest', '-q', 'tests/'], cwd=ROOT / 'backend', capture_output=True, encoding='utf-8', errors='replace', env=_child_env())
    print('  全套 pytest 退出码 =', full.returncode)
    return 0 if ok_md5 and miss == 0 and (hit == len(MUTATIONS)) and (full.returncode == 0) else 1
if __name__ == '__main__':
    sys.exit(_finish_run(main()))
