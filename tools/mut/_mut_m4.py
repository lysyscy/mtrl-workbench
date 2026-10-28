"""M4 · `ACC-RPT-EXP-001`（过程资料导出）的反向灵敏度。

做法与 `_mut_m9.py` 同款：**bytes ＋ `_fit()` 行尾归一**，逐条施加 → 跑断言 → 逐字节还原 → 复核 MD5。
⚠️ 片段**一律按 LF 写**；含中文的片段用 `str` 再 `.encode()`（bytes 字面量只允许 ASCII）。
"""
from __future__ import annotations
import hashlib
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
BE = ROOT / 'backend'
PY = str(BE / '.venv/Scripts/python.exe')
TEST = 'tests/test_acc_proc_exp.py tests/test_acc_proc_001.py tests/test_wired_m06.py'

def _b(s: str) -> bytes:
    return s.replace('\r\n', '\n').encode('utf-8')

def _fit(fragment: bytes, sample: bytes) -> bytes:
    """把 LF 片段转成与目标文件一致的行尾。"""
    if b'\r\n' in sample:
        return fragment.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
    return fragment.replace(b'\r\n', b'\n')
MUTATIONS: list[tuple[str, str, str, str]] = [('① 展开区不再默认选中当前项目（连「清空」也退回默认）', 'app/mod06_proc/domain.py', '    if not touched:\n        return [current] if current else []', '    if True:\n        return [current] if current else []'), ('② 多项目不再打成 zip', 'app/mod06_proc/domain.py', '        "zip": len(files) > 1,', '        "zip": False,'), ('③ 单个项目也给 zip 名（形态判断错）', 'app/mod06_proc/domain.py', '        "zip_name": f"{EXPORT_DOMAIN}_{ym}.zip" if len(files) > 1 else "",', '        "zip_name": f"{EXPORT_DOMAIN}_{ym}.zip" if len(files) >= 1 else "",'), ('④ 提示不再跟随当前表（恒取默认表）', 'app/mod06_proc/domain.py', '    cur = tab_of(tab)\n    return next(label for num, label in TABS if num == cur)', '    cur = DEFAULT_TAB\n    return next(label for num, label in TABS if num == cur)'), ('⑤ 文件名不再含表名（取数同源断掉）', 'app/mod06_proc/domain.py', '    return f"{project}_{EXPORT_DOMAIN}_{tab_name(tab)}_{ym}.xlsx"', '    return f"{project}_{EXPORT_DOMAIN}_{ym}.xlsx"')]

def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()

def run_test() -> int:
    return subprocess.run([PY, '-m', 'pytest', *TEST.split(), '-qq', '--no-header', '-p', 'no:cacheprovider'], cwd=BE, capture_output=True).returncode

def main() -> int:
    rels = {rel for _d, rel, _o, _n in MUTATIONS}
    for rel in sorted((r for r in rels if not (BE / r).exists())):
        print(f'[SKIP] ⚠️ 靶文件已不存在：{rel}（该条的 claim 已搬家或已撤 —— 见 `MUTATIONS` 注释）')
    before = {rel: md5(BE / rel) for rel in rels if (BE / rel).exists()}
    ok, miss, still_green = (0, [], [])
    for desc, rel, old_s, new_s in MUTATIONS:
        p = BE / rel
        if not p.exists():
            miss.append(f'{desc}（靶文件已删：{rel}）')
            continue
        src = p.read_bytes()
        old, new = (_fit(_b(old_s), src), _fit(_b(new_s), src))
        hit = src.count(old)
        if hit != 1:
            miss.append(f'{desc}（命中 {hit} 次）')
            print(f'[MISS] ❌ 变异点应唯一命中，实得 {hit} —— {desc}')
            continue
        p.write_bytes(src.replace(old, new, 1))
        rc = run_test()
        p.write_bytes(src)
        if rc != 0:
            ok += 1
            print(f'[RED ] ✅ {desc}')
        else:
            still_green.append(desc)
            print(f'[GREEN] ❌ 变异了却还是绿 —— {desc}')
    print('\n--- 还原复核 ---')
    bad = []
    for rel, h in before.items():
        now = md5(BE / rel)
        if now != h:
            bad.append(rel)
        print(f"  {('OK ' if now == h else 'BAD')} {rel}  {now}")
    print(f'\n命中 {ok}/{len(MUTATIONS)} · 变异点找不到 {len(miss)} · 变异后仍绿 {len(still_green)}')
    for x in miss + still_green:
        print('   !', x)
    return 0 if not bad and (not miss) and (not still_green) else 1
if __name__ == '__main__':
    sys.exit(main())
