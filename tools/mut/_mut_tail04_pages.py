"""反向灵敏度（变异测试）—— `TAIL-04` **最后两页 ＋ `exp` 真分发**的断言**是否真有区分力**。

做法：把实现**故意改坏**若干处，确认**对应断言确实变红**；每次立刻按 bytes 复原，最后核对 MD5。
用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_tail04_pages.py`

⚠️ 本仓纪律（memory §十七）：bytes 写入 / 中文片段用 `str+.encode()` / 行尾按目标文件归一 /
   变异点必须唯一命中 / 跑完必须再跑一次全套 `pytest`。
⚠️ 壳是多件 ⇒ 锚点在哪件就改哪件（`pick`），判断基准一律用**原始** `SHELL_PATH`（⛔ 不累积）。
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
APP = ROOT / 'backend' / 'app'
FILES = {'nt': APP / 'report_export' / 'nt_export.py', 'naive': APP / 'report_export' / 'naive_export.py', 'live': APP / 'mod03_notice' / 'list_view.py', 'nt_api': APP / 'mod03_notice' / 'notice_api_router.py'}
T_COLS = 'test_导出列就是页面表头去掉勾选与操作'
T_NT_TOTAL = 'test_付款通知书端点按传入id顺序出行且合计只算有效行'
T_NT_EMPTY = 'test_付款通知书导出的合计只算有效行'
T_LIVE = 'test_is_live两条口径方向相反且都成立'
MUTATIONS: list[tuple[str, str, str, str, str]] = [('导出少一列（页面有、导出没有 ⇒ 表与屏幕对不上）', 'nt', '    ("审批状态", "approve_status"),\n', '', T_COLS), ('导出把表头的 `✎` 洗掉了（表头不再逐字等于屏幕）', 'nt', '("付款金额 ✎", "pay_amount")', '("付款金额", "pay_amount")', T_COLS), ('同上，但看 `ACC-INV-001/001-12` 那条断言（已按形态变化重指）', 'actions', "  '付款通知书台账':   { rows: () => ntHit(fNt),  url: '/api/m03/notices/export' },", "  '付款通知书台账':   { rows: () => ntHit(fNt),  url: '/api/m03/notices/export' },\n  '库存单据明细总表': { rows: () => [], url: '/api/m08/inventory/export' },", 'test_库存单据两种导出并存互不影响且透视提示与模板形态一致'), ('合计把**剔除行**也算进去（§4.2.2）', 'live', 'return (not self.excluded) and (', 'return (True) and (', T_NT_TOTAL), ('合计漏掉「**撤单但有牵涉**」那一档（§4.2.7：静默丢账）', 'live', '            (not self.i8_revoked) or (self.amount_paid > 0 or self.has_link)', '            (not self.i8_revoked)', T_LIVE), ('撤单有牵涉时不再按「已付金额 > 0」认（判据换成永不成立）', 'live', '(self.amount_paid > 0 or self.has_link)', '(False)', T_LIVE), ('一行有效行都没有也硬写合计行（凭空一排 0）', 'naive', '        if base or total_always:', '        if True:', T_NT_EMPTY), ('付款通知书导出按**库里顺序**出行（不跟传入 id）', 'nt_api', '    pairs = [(_rec, _export_row(_rec)) for _rec in (by_id[i] for i in ids if i in by_id)]', '    pairs = [(_rec, _export_row(_rec)) for _k, _rec in sorted(by_id.items()) if _k in set(ids)]', T_NT_TOTAL)]

def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b'\r\n' in sample:
        return fragment.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    return fragment.replace(b'\r\n', b'\n')

def _fkey(key: str) -> str:
    """⚠️ 本批的锚点全在**具体件**上（`core.js` / `actions.js` / 各 `.py`）——
    `P4`② 拆件之后壳是多件，`pick(SHELL_PATH, …)` 那一套留给"锚点可能在壳任意一件"的脚本；
    本件逐条指名到件，⛔ 不用 `pick`（省得"选错件"变成新的不确定源）。"""
    assert key in FILES, f'变异点指了不存在的件：{key}'
    return key

def main() -> int:
    orig = {k: p.read_bytes() for k, p in FILES.items()}
    md5_before = {k: hashlib.md5(v).hexdigest() for k, v in orig.items()}
    for k, v in orig.items():
        print(f'{k}: {len(v)} 字节 · MD5 {md5_before[k][:12]}')
    hit = miss = 0
    for i, (label, fkey, old, new, test_name) in enumerate(MUTATIONS, 1):
        real = _fkey(fkey)
        target = orig[real]
        o = _fit(old.encode('utf-8'), target)
        n = _fit(new.encode('utf-8'), target)
        cnt = target.count(o)
        if cnt != 1:
            print(f'  {i:2d}. ⚠️ SKIP（变异点命中 {cnt} 次）—— [{real}] {label}')
            miss += 1
            continue
        FILES[real].write_bytes(target.replace(o, n))
        r = subprocess.run([str(PY), '-m', 'pytest', '-q', '-k', test_name, 'tests/'], cwd=ROOT / 'backend', capture_output=True, text=True)
        bad = r.returncode != 0
        print(f"  {i:2d}. {('✅ 变红' if bad else '⛔ 仍绿（假绿！）')} —— [{real}] {label}  [{test_name}]")
        if bad:
            hit += 1
        FILES[real].write_bytes(target)
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
