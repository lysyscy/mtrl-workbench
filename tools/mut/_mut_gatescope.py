"""相关核验回执的反向灵敏度：靶为 tools/oneoff/_gatescope.py 的真实自测与选择判据。

分别制造无证跳过、忽略输入内容变化、失败仍记绿、双向选集失牙；
每次自测必须失败，正常自测通过；finally 逐字节恢复靶，不改权威四态。
"""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
TARGET = ROOT/'tools/oneoff/_gatescope.py'
PY = ROOT/'backend/.venv/Scripts/python.exe'


def probe():
    """运行真实自测，不把测试断言本身当作被测实现替换。"""
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    env.pop('ACC_RESULTS_PATH', None)
    return subprocess.run([str(PY), '-X', 'utf8', str(TARGET), '--selftest'],
                          cwd=ROOT, env=env, capture_output=True,
                          text=True, encoding='utf-8', errors='replace')


def main():
    original = TARGET.read_bytes()
    source = original.decode('utf-8')
    cases = [
        ('无证明跳过', 'return self.full or sign is None or record !=', 'return False and record !='),
        ('忽略输入内容变化', 'return hashlib.sha256(value).hexdigest()', "return 'constant'"),
        ('失败仍记绿', '        if rc != 0:', '        if False:'),
        ('漏跑和清单外失牙', 'if not required <= selected or not selected <= available:', 'if False:'),
    ]
    good = probe().returncode == 0
    for label, old, new in cases:
        assert source.count(old) == 1, label+'：靶锚必须唯一'
        try:
            TARGET.write_bytes(source.replace(old, new, 1).encode('utf-8'))
            result = probe()
            hit = result.returncode != 0 and 'AssertionError' in result.stderr
            print(label, '必红', hit)
            good &= hit
        finally:
            TARGET.write_bytes(original)
    assert TARGET.read_bytes() == original, '靶未恢复'
    impact = ROOT/'tools/oneoff/_impactscope.py'
    raw = impact.read_bytes()
    src = raw.decode('utf-8')
    for label, old, new in [
        ('读取证据摘要失牙', 'if gate.digest(raw) == receipt.pytest_inputs:', 'if True:'),
        ('仓外改变退回局部', "raise ValueError('完整基点外部输入改变')", 'return None'),
        ('属性保护失牙', 'parser.feed(chunk)', '''return re.sub(r'(?<=>)[\u4e00-\u9fff，。；：！？、（）「」· \t]+(?=<)', 'TEXT', chunk)'''),
        ('未知误判普通', "return 'full', '关键或未证明输入：' + name", "return 'documents', '错误免检'"),
        ('插值失去保护', 'chunks.append(source[k:stop])', 'chunks.append(mask_text(source[k:stop]))'),
        ('必要语法检查漏选', "'tools/audit/syntax_audit.py', 'tools/audit/ui_parity.py',", "'tools/audit/ui_parity.py',"),
        ('新检查无分类被跳过', 'return {rel for rel, _ in commands} - required_checks', 'return set() # required_checks'),
    ]:
        assert src.count(old) == 1, label+'：靶锚必须唯一'
        try:
            impact.write_bytes(src.replace(old, new, 1).encode('utf-8'))
            result = probe()
            hit = result.returncode != 0 and 'AssertionError' in result.stderr
            print(label, '必红', hit)
            good &= hit
        finally:
            impact.write_bytes(raw)
    assert impact.read_bytes() == raw
    entry = ROOT/'tools/oneoff/_run_rulers.py'
    saved = entry.read_bytes()
    text = saved.decode('utf-8')
    eol = '\r\n' if b'\r\n' in saved else '\n'
    anchor = "    if rc:" + eol + "        (ROOT/'artifacts/_gate_receipts.json').unlink(missing_ok=True)"
    assert text.count(anchor) == 1
    try:
        entry.write_bytes(text.replace(anchor, anchor.replace('if rc:', 'if False:'), 1).encode('utf-8'))
        result = probe()
        hit = result.returncode != 0 and 'AssertionError' in result.stderr
        print('提前失败旧绿残留', '必红', hit)
        good &= hit
    finally:
        entry.write_bytes(saved)
    assert entry.read_bytes() == saved
    good &= probe().returncode == 0
    scoped = ROOT/'tools/oneoff/_pytestscope.py'
    saved = scoped.read_bytes()
    text = saved.decode('utf-8')
    anchor = 'sys.addaudithook(_input_audit)'
    assert text.count(anchor) == 1
    try:
        scoped.write_bytes(text.replace(anchor, 'pass # removed input observer', 1).encode('utf-8'))
        result = probe()
        hit = result.returncode != 0 and 'AssertionError' in result.stderr
        print('真实读取观察器脱线', '必红', hit)
        good &= hit
    finally:
        scoped.write_bytes(saved)
    assert scoped.read_bytes() == saved
    good &= probe().returncode == 0
    print('反向灵敏度与逐字节复原：'  , '通过' if good else '失败')
    return 0 if good else 1


if __name__ == '__main__':
    sys.exit(main())
