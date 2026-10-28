"""`TAIL-30`-③ 人工指认（链路 B）—— **反向灵敏度**（变异测试）：改坏 ⇒ 断言必须变红。

⚠️ 每条变异：改坏 → 跑**指定那条断言**（期望 FAIL / ERROR）→ **按 bytes 复原** → 核 MD5。
⚠️ 锚点一律打在**被判据真正覆盖的那一处**（打偏 = 锚点错，不是断言假绿）。
⚠️ 子进程带 `PYTHONIOENCODING=utf-8`（否则 pytest 输出里的 `✅` 撞 GBK ⇒ `UnicodeDecodeError` 噪音）
   ＋ `CODEBUDDY_SAFE_DELETE_ENABLED=0`（多轮 pytest 会撞 safe-delete 护栏 ⇒ 假红）。
⚠️ **端点层要真库**跑不起来 ⇒ 那一层的**行为**由真机 `tools/_e2e_m01_promote.py` 覆盖；
   本脚本对端点只钉「守卫还在不在」（`M9`），并在报告里写明这一层是**静态钉**。

用法： backend/.venv/Scripts/python.exe tools/_mut_promote.py
"""
from __future__ import annotations
import hashlib
import os
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'backend'
PY = BACKEND / '.venv' / 'Scripts' / 'python.exe'
REC = 'backend/app/mod01_projects/recovery.py'
PEND = 'backend/app/mod01_projects/pending.py'
RT = 'backend/app/mod01_projects/router.py'
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'audit'))
T = 'tests/test_promote_pending.py'
TW = 'tests/test_wired_m01.py'
MUTS = [('M1 判壳让位给「≥2 条」（命中里有壳也去要人指认 —— §17.2 先判壳被破）', REC, '    if any(getattr(p, "project_type", "") == TYPE_SHELL for p in rows):\n        return KIND_CREATE_SMALL\n', '    if False:\n        return KIND_CREATE_SMALL\n', [T + '::test_命中处置的类别由唯一出口判定']), ('M2 「≥2 条」的门槛被抬成 ≥3（两条同名行就被当成「1 条扶正」）', REC, '    if len(rows) > 1:\n        return KIND_MULTI\n', '    if len(rows) > 2:\n        return KIND_MULTI\n', [T + '::test_命中处置的类别由唯一出口判定', T + '::test_每条unresolved都带kind不靠中文原因串认类别']), ('M3 清单不看「仓库是否仍陌生」（已扶正完的还摆着 ⇒ 让人对旧清单白干）', PEND, '        if wh not in still_unknown:\n            continue', '        if False:\n            continue', [T + '::test_清单逐条按当前档案现算已解决的当场丢掉']), ('M4 清单不看「是否仍命中 ≥2 条」（删到只剩 1 条了还说要人指认）', PEND, '        if classify_hits(hits) != KIND_MULTI:\n            continue', '        if False:\n            continue', [T + '::test_清单逐条按当前档案现算已解决的当场丢掉']), ('M5 「材料侧记录」认成所有记录（付款侧 / 同步记录也算 ⇒ 拿别的域的清单来凑）', PEND, '    return any(t == key or t.startswith(key + " ") for key in MATERIAL_TARGETS)\n', '    return True\n', [T + '::test_待指认清单只认最近一次材料侧抓取', T + '::test_材料侧抓取链路的登记键都要被认出来']), ('M6 「最新」信了传入顺序（不按 id 取 ⇒ 离线桩/乱序查询会把旧清单当最新）', PEND, '    for r in sorted(recs, key=lambda x: getattr(x, "id", 0) or 0, reverse=True):\n', '    for r in recs:\n', [T + '::test_待指认清单只认最近一次材料侧抓取']), ('M7 没待人工就不写那个键（「最近一次」指不住 ⇒ 旧清单永远挂着）', PEND, '    return {RECORD_KEY: [dict(x) for x in (items or [])]}\n', '    return {RECORD_KEY: [dict(x) for x in (items or [])]} if items else {}\n', [T + '::test_清单条目是两个链路共用一份不会各写一份']), ('M8 「全名回查」退化成包含匹配（§17.2 说好的是**精确相等**，不猜）', REC, '    return list((by_full or {}).get(_norm(full), []))\n', '    return [p for k, rs in (by_full or {}).items()\n            if _norm(full) and _norm(full) in k for p in rs]\n', [T + '::test_归一化后精确相等才算命中', T + '::test_候选清单只含该全名且含归档行并标出占位']), ('M9 写入口的一致性守卫被删（跨全名指认 ⇒ 仓库名会挂到别人头上）', RT, '        if want_full and norm_full_name(row.name_full) != norm_full_name(want_full):\n', '        if False:\n', [T + '::test_写入口有一致性守卫且落库只走系统扶正出口'])]

def _read(rel: str) -> bytes:
    return (ROOT / rel).read_bytes()

def _fit(rel: str, text: str) -> bytes:
    """按目标文件的**行尾习惯**归一（本仓源码行尾不统一 ⇒ ⛔ 不能硬用 `\\n`）。"""
    data = _read(rel)
    return (text.replace('\n', '\r\n') if b'\r\n' in data else text).encode('utf-8')

def main() -> int:
    rels = {REC, PEND, RT}
    base = {rel: _read(rel) for rel in rels}
    before = {rel: hashlib.md5(d).hexdigest() for rel, d in base.items()}
    print('基线 MD5:')
    for rel, h in before.items():
        print('   %-46s %s' % (rel, h))
    ok = fail = 0
    env = dict(os.environ, CODEBUDDY_SAFE_DELETE_ENABLED='0', PYTHONIOENCODING='utf-8')
    for name, rel, old, new, tests in MUTS:
        rel = rel
        before.setdefault(rel, (rel.read_bytes(), hashlib.md5(rel.read_bytes()).hexdigest()))
        path = ROOT / rel
        ob, nb = (_fit(rel, old), _fit(rel, new))
        cur = path.read_bytes()
        if ob not in cur:
            print('\n✗ SKIP %s —— 锚点没命中（`%s`）' % (name, old.strip().splitlines()[0][:60]))
            fail += 1
            continue
        path.write_bytes(cur.replace(ob, nb, 1))
        r = subprocess.run([str(PY), '-m', 'pytest', '-q', *tests], cwd=str(BACKEND), capture_output=True, text=True, encoding='utf-8', env=env)
        path.write_bytes(base[rel])
        restored = hashlib.md5(path.read_bytes()).hexdigest() == before[rel]
        red = r.returncode != 0
        good = red and restored
        ok += 1 if good else 0
        fail += 0 if good else 1
        print('\n%s %s' % ('✓' if good else '✗', name))
        print('     断言变红=%s  复原 MD5 一致=%s' % (red, restored))
        if not red:
            print('     ⚠️ 变异后仍然全绿 ⇒ **这条断言是假绿**，必须改紧！')
    print('\n--- 收尾核对 ---')
    for rel in rels:
        now = hashlib.md5((ROOT / rel).read_bytes()).hexdigest()
        assert now == before[rel], '%s 未逐字节复原！%s != %s' % (rel, now, before[rel])
        print('   %-46s 复原 ✓ %s' % (rel, now))
    print('\n结果：%d/%d 通过' % (ok, ok + fail))
    return 1 if fail else 0
if __name__ == '__main__':
    sys.exit(main())
