"""反向灵敏度（变异测试）—— `MOD-09` 壳接线断言 **是否真有区分力**。

做法：把实现**故意改坏**若干处，确认**对应断言确实变红**；每次立刻按 bytes 复原，最后核对 MD5。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_m09.py`

⚠️ 本仓纪律（见 memory §十七）：
1. **一律走 bytes**（`write_text` 在 Windows 会把 `\\n` 写成 `\\r\\n` ⇒ MD5 假 BAD）；
2. 变异片段**含中文**时用 `str` ＋ `.encode()`（`b"…"` 只允许 ASCII）；
3. **行尾按目标文件归一**（本仓源码行尾不统一）；
4. 变异点**必须唯一命中**，否则重写（不得当成"已通过"）；
5. 默认重跑复原态全套 `pytest`；显式 `--no-full-suite` 跳过，本轮不刷新权威四态。

⚠️ 本次首跑抓出 **3 处假绿**（两处是**断言**不够紧、一处是**变异点**没改干净）—— 已同步收紧：
   · `awfPj = d.project` 那条断言**放错了测试**（写在「数据源」那条里，而变异号指的是「候选与默认项目」那条）
     ⇒ 断言搬进它自己该管的用例；
   · 「后端剔除页面专用列」原写成 `"D.PAGE_ONLY_KEYS" in API` —— **文档注释里的 `domain.PAGE_ONLY_KEYS`
     含该子串** ⇒ 把实现改成 `if False:` **照样绿**（同族坑：断言被前缀/子串喂饱）⇒ 改为钉 `_row()` 函数体；
   · 「awfAdd 不再走后端」的变异写成 `()=>null && API.m09Add(` —— **`API.m09Add(` 还在** ⇒ 变异根本没改掉那处调用。
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
FILES = {'api': ROOT / 'backend' / 'app' / 'mod09_fee' / 'api.py'}
MUTATIONS: list[tuple[str, str, str, str, str]] = [('后端读端点不走 _payload', 'api', 'return _payload(s, ym=str(p.get("ym") or ""), pj=str(p.get("pj") or ""))', 'return {}', 'test_后端m09端点存在且复用service出口'), ('后端 _payload 不走 build_page_data（另写一套组装）', 'api', 'data = SV.build_page_data(s, SV.parse_state({"ym": ym, "pj": pj}))', 'data = {}', 'test_后端m09端点存在且复用service出口'), ('后端写端点不走 act_delete（另写一套）', 'api', 'return _flash(SV.act_delete(s, ym=req.ym, project_key=req.project, index=req.index))', 'return _flash({"kind": "ok", "message": "已删除"})', 'test_后端m09端点存在且复用service出口'), ('后端不剔除页面专用列（ops 漏进 API）', 'api', 'if k in D.PAGE_ONLY_KEYS:', 'if False:', 'test_后端m09端点剔除页面专用列')]

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
