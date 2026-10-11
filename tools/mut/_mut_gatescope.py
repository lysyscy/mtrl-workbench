"""相关核验机制的隔离反向灵敏度：按被改机制调用各自真实自测。

直接运行默认保留全部反例；--paths由影响入口传实际改动，未知范围回退全部。
正常完整自测先通过，每个故意破坏必须AssertionError，靶逐字节恢复。
"""
from pathlib import Path
import argparse
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PY = Path(sys.executable)

CASES = {'gate': ('tools/oneoff/_gatescope.py',
          [('pytest 产物误入签名', "('repo/artifacts/', 'repo/backend/.codebuddy/')", "('repo/artifacts/',)"),
           ('无证明跳过', 'return self.full or sign is None or record !=', 'return False and record !='),
           ('忽略输入内容变化', 'return hashlib.sha256(value).hexdigest()', "return 'constant'"),
           ('失败仍记绿', '        if rc != 0:', '        if False:'),
           ('漏跑和清单外失牙', 'if not required <= selected or not selected <= available:', 'if False:')]),
 'impact': ('tools/oneoff/_impactscope.py',
            [('待查候选不列', "'；可配候选：'", "'；未列：'"),
             ('说明误触机制全验',
              "checks = required_checks('documents', commands) if docs else {'tools/audit/bytes_guard.py'}",
              'checks = {rel for rel, _ in commands}'),
             ('机器输入使用者漏选',
              "if Path(name).name in p.read_text(encoding='utf-8')",
              "if False and Path(name).name in p.read_text(encoding='utf-8')"),
             ('旧dirty当新增',
              '    result = {}\n    for name in names:',
              '    result = {name: (None, (root/name).read_bytes()) for name in names if '
              "(root/name).is_file() and not name.startswith('.codebuddy/work/00-scratch/')}\n"
              '    for name in names:'),
             ('必要语法检查漏选',
              "'tools/audit/syntax_audit.py', 'tools/audit/ui_parity.py',",
              "'tools/audit/ui_parity.py',"),
             ('自测依赖冒充全部消费者已证', "pending.append('共享检查模块需查明调用者：'+name)", 'pass'),
             ('工具依赖漏自测',
              'checks |= {rel for rel, deps in SELFTEST_DEPENDENCIES.items() if names & deps}',
              'checks |= set()'),
             ('完整入口固定工具自测',
              "checks = required_checks('full', commands) | (checks & set(SELFTEST_DEPENDENCIES))",
              'checks = {rel for rel, _ in commands}'),
             ('新检查无分类被跳过',
              'return {rel for rel, _ in commands} - required_checks',
              'return set() # required_checks'),
             ('相关失败仍启动完整真机',
              "        if bad:\n            print('暂缓完整壳自检：",
              "        if False:\n            print('暂缓完整壳自检："),
             ('反例入口丢失实际范围', "mutation_args = ['--paths', *sorted(mechanism_paths)]", 'mutation_args = []')]),
 'entry': ('tools/oneoff/_run_rulers.py', [('提前失败旧绿残留', '    if rc:', '    if False:')]),
 'scope': ('tools/oneoff/_pytestscope.py',
           [('真实读取观察器脱线', 'sys.addaudithook(_input_audit)', 'pass # removed input observer'),
            ('共享helper使用者漏选', 'if _reach(graph, module) & sources', 'if module in sources', 'impact')])}


def affected(paths):
    """只缩小已知机制；调用方不提供范围或反例自身变动时验证全部。"""
    owners = {rel: {part} for part, (rel, _cases) in CASES.items()}
    if not paths or any(p not in owners for p in paths):
        return set(CASES)
    return set().union(*(owners[p] for p in paths))


def probe(part=None):
    """调用真实实现；每个反例只重跑它能破坏的自测。"""
    env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    env.pop('ACC_RESULTS_PATH', None)
    snippets = {
        'gate': 'import _gatescope; _gatescope.selftest(dependencies=False)',
        'impact': 'import _impactscope; _impactscope.selftest()',
        'entry': 'import _impactscope; _impactscope.selftest()',
        'scope': 'import _pytestscope; _pytestscope.input_selftest(); _pytestscope.shell_selftest()',
    }
    argv = [str(PY), '-X', 'utf8']
    if part is None:
        argv += [str(ROOT/'tools/oneoff/_gatescope.py'), '--selftest']
    else:
        argv += ['-c', "import sys; sys.path.insert(0, 'tools/oneoff'); " + snippets[part]]
    return subprocess.run(argv, cwd=ROOT, env=env, capture_output=True,
                          text=True, encoding='utf-8', errors='replace')


def _main(paths=None):
    chosen = affected(paths)
    normal = probe()
    if normal.returncode:
        print('正常自测失败', normal.stdout, normal.stderr)
        return 1
    good = True
    count = 0
    for part, (rel, cases) in CASES.items():
        if part not in chosen:
            print('跳过', part, '未变化机制的反例')
            continue
        target = ROOT/rel
        original = target.read_bytes()
        source = original.decode('utf-8')
        eol = '\r\n' if b'\r\n' in original else '\n'
        for case in cases:
            label, old, new = case[:3]
            witness = case[3] if len(case) == 4 else part
            old, new = old.replace('\n', eol), new.replace('\n', eol)
            assert source.count(old) == 1, label+'：靶锚必须唯一'
            try:
                target.write_bytes(source.replace(old, new, 1).encode('utf-8'))
                result = probe(witness)
                hit = result.returncode != 0 and 'AssertionError' in result.stderr
                print(label, '必红', hit, flush=True)
                if not hit:
                    print('漏响应诊断', result.stdout[-1200:], result.stderr[-1200:])
                good &= hit
                count += 1
            finally:
                target.write_bytes(original)
            assert target.read_bytes() == original, '靶未恢复'
    print('反向灵敏度与逐字节复原：', '通过' if good else '失败', count, '项')
    return 0 if good else 1


def main():
    """正式文件只读；范围在隔离副本中保持不变。"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--paths', nargs='+')
    parser.add_argument('--in-copy', action='store_true')
    args = parser.parse_args()
    if args.in_copy:
        return _main(args.paths)
    import tempfile
    import shutil
    with tempfile.TemporaryDirectory(prefix='mtrl-gate-proof-') as temp:
        root = Path(temp)
        for name in ('tools', 'backend/app', 'backend/tests'):
            shutil.copytree(ROOT/name, root/name, ignore=shutil.ignore_patterns('__pycache__'))
        argv = [str(PY), '-X', 'utf8', str(root/'tools/mut/_mut_gatescope.py'), '--in-copy']
        if args.paths:
            argv += ['--paths', *args.paths]
        result = subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace',
                                env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        print(result.stdout)
        print(result.stderr)
        return result.returncode


if __name__ == '__main__':
    sys.exit(main())
