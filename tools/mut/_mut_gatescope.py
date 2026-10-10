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
PY = Path(sys.executable)


def probe():
    """运行真实自测，不把测试断言本身当作被测实现替换。"""
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    env.pop('ACC_RESULTS_PATH', None)
    return subprocess.run([str(PY), '-X', 'utf8', str(TARGET), '--selftest'],
                          cwd=ROOT, env=env, capture_output=True,
                          text=True, encoding='utf-8', errors='replace')


def _main():
    original = TARGET.read_bytes()
    source = original.decode('utf-8')
    cases = [
        ('无证明跳过', 'return self.full or sign is None or record !=', 'return False and record !='),
        ('忽略输入内容变化', 'return hashlib.sha256(value).hexdigest()', "return 'constant'"),
        ('失败仍记绿', '        if rc != 0:', '        if False:'),
        ('漏跑和清单外失牙', 'if not required <= selected or not selected <= available:', 'if False:'),
    ]
    normal = probe()
    good = normal.returncode == 0
    if not good: print('正常自测失败', normal.stdout, normal.stderr)
    for label, old, new in cases:
        assert source.count(old) == 1, label+'：靶锚必须唯一'
        try:
            TARGET.write_bytes(source.replace(old, new, 1).encode('utf-8'))
            result = probe()
            hit = result.returncode != 0 and 'AssertionError' in result.stderr
            print(label, '必红', hit)
            if not hit: print('漏响应诊断', label, result.stdout[-1200:], result.stderr[-1200:])
            good &= hit
        finally:
            TARGET.write_bytes(original)
    assert TARGET.read_bytes() == original, '靶未恢复'
    impact = ROOT/'tools/oneoff/_impactscope.py'
    raw = impact.read_bytes()
    src = raw.decode('utf-8').replace('\r\n', '\n')
    for label, old, new in [
        ('说明误触机制全验', "checks = required_checks('documents', commands) if docs else {'tools/audit/bytes_guard.py'}", "checks = {rel for rel, _ in commands}"),
        ('机器输入使用者漏选', "if Path(name).name in p.read_text(encoding='utf-8')", "if False and Path(name).name in p.read_text(encoding='utf-8')"),
        ('旧dirty当新增', '    result = {}\n    for name in names:', "    result = {name: (None, (root/name).read_bytes()) for name in names if (root/name).is_file() and not name.startswith('.codebuddy/work/00-scratch/')}\n    for name in names:"),
        ('必要语法检查漏选', "'tools/audit/syntax_audit.py', 'tools/audit/ui_parity.py',", "'tools/audit/ui_parity.py',"),
        ('自测依赖冒充全部消费者已证', "pending.append('共享检查模块需查明调用者：'+name)", 'pass'),
        ('工具依赖漏自测', 'checks |= {rel for rel, deps in SELFTEST_DEPENDENCIES.items() if names & deps}', 'checks |= set()'),
        ('完整入口固定工具自测', "checks = required_checks('full', commands) | (checks & set(SELFTEST_DEPENDENCIES))", 'checks = {rel for rel, _ in commands}'),
        ('新检查无分类被跳过', 'return {rel for rel, _ in commands} - required_checks', 'return set() # required_checks'),
        ('相关失败仍启动完整真机', '        if bad:\n            print(\'暂缓完整壳自检：', '        if False:\n            print(\'暂缓完整壳自检：'),
    ]:
        assert src.count(old) == 1, label+'：靶锚必须唯一'
        try:
            impact.write_bytes(src.replace(old, new, 1).encode('utf-8'))
            result = probe()
            hit = result.returncode != 0 and 'AssertionError' in result.stderr
            print(label, '必红', hit)
            if not hit: print('漏响应诊断', label, result.stdout[-1200:], result.stderr[-1200:])
            good &= hit
        finally:
            impact.write_bytes(raw)
    assert impact.read_bytes() == raw
    entry = ROOT/'tools/oneoff/_run_rulers.py'
    saved = entry.read_bytes()
    text = saved.decode('utf-8')
    eol = '\r\n' if b'\r\n' in saved else '\n'
    anchor = "    if rc:"
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
    anchor = 'if _reach(graph, module) & sources'
    assert text.count(anchor) == 1
    try:
        scoped.write_bytes(text.replace(anchor, 'if module in sources', 1).encode('utf-8'))
        result = probe()
        hit = result.returncode != 0 and 'AssertionError' in result.stderr
        print('共享helper使用者漏选', '必红', hit)
        good &= hit
    finally:
        scoped.write_bytes(saved)
    good &= probe().returncode == 0
    print('反向灵敏度与逐字节复原：'  , '通过' if good else '失败')
    return 0 if good else 1


def main():
    """正式工作文件不作变异靶；同一实现与反例在隔离副本里执行。"""
    if '--in-copy' in sys.argv:
        return _main()
    import tempfile
    import shutil
    with tempfile.TemporaryDirectory(prefix='mtrl-gate-proof-') as temp:
        root = Path(temp)
        for name in ('tools', 'backend/app', 'backend/tests'):
            shutil.copytree(ROOT/name, root/name, ignore=shutil.ignore_patterns('__pycache__'))
        result = subprocess.run([str(PY), '-X', 'utf8', str(root/'tools/mut/_mut_gatescope.py'), '--in-copy'],
                                cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace',
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        print(result.stdout)
        print(result.stderr)
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())
