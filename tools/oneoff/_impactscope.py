"""按实际新增差异选择核验；未知依赖显式待查。

只承认信息记录与单页模板静态文字；表达式、标签、属性和页外代码均不能省验。
执行登记仍归 CMDS，失败不留整体通过证明，独立成功项保留，局部 pytest 永不刷新权威四态。
"""
from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import time
import ast
import base64
import hashlib

ROOT = Path(__file__).resolve().parents[2]


def snapshot(path: Path, root: Path = ROOT) -> None:
    """保存当轮字节基点；不是通过证明，凭据只存摘要。"""
    names = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    names += subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=root).decode().split('\0')
    files = {}
    for name in sorted(set(filter(None, names))):
        target = root/name
        if not target.is_file() or name.startswith(('.scratch/local/', '.artifacts/', 'var/', 'data/', 'exports/', 'dist/')):
            continue
        raw = target.read_bytes()
        secret = name == 'ops/init_db.sql' or (name.startswith('.env') and name != '.env.example')
        files[name] = {'sha256': hashlib.sha256(raw).hexdigest(),
                       'data': None if secret else base64.b64encode(raw).decode('ascii')}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip(),
                                'files': files}, ensure_ascii=False), encoding='utf-8')
    print('开工基点已保存；已有输入未因此变成已验，凭据只记摘要')


def since_snapshot(path: Path, root: Path = ROOT) -> dict:
    """基点只界定新增影响；损坏、HEAD变化或凭据变化显式待查。"""
    data = json.loads(path.read_text(encoding='utf-8'))
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip()
    if data['head'] != head:
        raise ValueError('HEAD已变化，需重新调查基点')
    now = git_changes(root)
    names = set(now) | set(data['files'])
    result = {}
    for name in names:
        if name.startswith(('.scratch/local/', '.artifacts/', 'var/', 'data/', 'exports/', 'dist/')):
            continue
        p = root/name
        after = p.read_bytes() if p.is_file() else None
        old = data['files'].get(name)
        if old is not None and after is not None and hashlib.sha256(after).hexdigest() == old['sha256']:
            continue
        if old is not None and old['data'] is None:
            raise ValueError('凭据输入变化，需独立调查：'+name)
        before = base64.b64decode(old['data'], validate=True) if old else None
        if before is not None and hashlib.sha256(before).hexdigest() != old['sha256']:
            raise ValueError('字节基点摘要失配：'+name)
        if before != after:
            result[name] = (before, after)
    return result


def snapshot_summary(path: Path, root: Path = ROOT) -> dict:
    """只返回基点元数据和新增路径，字节正文及凭据内容不进入输出。"""
    data = json.loads(path.read_text(encoding='utf-8'))
    return {'head': data['head'], 'files': len(data['files']),
            'digest_only': sum(v['data'] is None for v in data['files'].values()),
            'changed': sorted(since_snapshot(path, root))}


def latest_smoke_log(root: Path = ROOT) -> Path | None:
    """最近一份真机自检证据 —— 复用那一路要能指出"复用的是哪一份"（日志名带时间戳，按名排序即按时间）。"""
    logs = sorted((root/'var/state/verification/shell-smoke').glob('tmp-*-shell-smoke.log'))
    return logs[-1] if logs else None


def smoke_evidence(result, root: Path = ROOT) -> Path:
    """保留完整真机输出与壳/环境摘要；现场数据是否变化由本轮实际证据确认。"""
    import os
    shell = [(p.relative_to(root).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
             for p in sorted((root/'backend/app/web').rglob('*')) if p.is_file()]
    header = {'rc': result.returncode, 'shell_sha256': hashlib.sha256(json.dumps(shell).encode()).hexdigest(),
              'environment_sha256': hashlib.sha256(json.dumps(dict(os.environ), sort_keys=True).encode()).hexdigest()}
    path = root/'var/state/verification/shell-smoke'/('tmp-'+time.strftime('%Y%m%d-%H%M%S')+'-shell-smoke.log')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(header)+'\n'+result.stdout+'\n'+result.stderr, encoding='utf-8')
    return path


def retro_selftest():
    """实测摘要不输出正文，真机成功/失败均留完整证据，不把失败当成通过。"""
    import tempfile
    from types import SimpleNamespace
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        (root/'README.md').write_text('baseline-private-content', encoding='utf-8')
        subprocess.run(['git', 'add', 'README.md'], cwd=root, check=True)
        subprocess.run(['git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], cwd=root, check=True)
        basis=root/'.artifacts/active/fixture/one/recovery/basis.json'; snapshot(basis, root)
        (root/'README.md').write_text('changed-private-content', encoding='utf-8')
        summary=snapshot_summary(basis, root)
        assert summary['files'] == 1
        assert summary['changed'] == ['README.md']
        assert 'private-content' not in json.dumps(summary) and 'data' not in summary
        for rc in (0, 1):
            path=smoke_evidence(SimpleNamespace(returncode=rc, stdout='complete-output', stderr='diagnostic'), root)
            lines=path.read_text(encoding='utf-8').splitlines()
            assert json.loads(lines[0])['rc'] == rc
            assert lines[1:] == ['complete-output', 'diagnostic']
    print('摘要/真机证据自证：正文不输出，完整输出与真实返回码保留')


def document_readers(names, root: Path = ROOT) -> set[str]:
    """查运行面和测试对文档的实际字面引用；动态ops读取保守选对应使用者。"""
    found = set()
    for folder in ('backend/app', 'backend/tests'):
        for p in (root/folder).rglob('*.py'):
            source = p.read_text(encoding='utf-8')
            if any(n in source or Path(n).name in source for n in names):
                found.add(p.relative_to(root).as_posix())
    return found


def executable_changed(pair) -> bool:
    """Python说明修改仍验其使用者；只有执行树变化才触发机制自证。"""
    trees = []
    for raw in pair:
        if raw is None: return True
        tree = ast.parse(raw.decode('utf-8-sig'))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                    node.body.pop(0)
        trees.append(ast.dump(tree, include_attributes=False))
    return trees[0] != trees[1]

# 这是守护后果的分类，执行清单仍从 CMDS 读取；新登记项缺分类即待查。
OUTSIDE_ORDINARY = {
    'tools/audit/doc_audit.py': '文档协议、状态、票计数与交付面四检',
    'tools/audit/audit_drift.py': '文档用例/术语/路径/状态与节号',
    'tools/audit/audit_meta.py': '资料组织、出处、预算及登记常量',
    'tools/audit/audit_work.py': '记录元信息、保留期与治理容量',
    'tools/audit/chain_audit.py': '业务链路定义与实现接缝',
    'tools/audit/claim_audit.py': '活文档用户裁定出处',
    'tools/audit/cover_gap.py': '业务能力及判据登记',
    'tools/audit/shell_verify.py': '壳完整自检后盖章另行执行',
    'tools/audit/sticky_probe.py': '表格结构及布局；静态节点文字不改变它',
    'tools/audit/mut_cover.py': '变异工具覆盖登记',
    'tools/audit/acc_report.py': '全量权威结果统计；局部不得刷新',
    'tools/audit/refs_query.py': '引用查询工具自测',
    'tools/oneoff/_doc_downgrade.py': '归档动作工具自测',
    'tools/probe/_audit_face.py': '仓外交付面；本次差异未触及',
    'tools/oneoff/_gatescope.py': '核验回执机制；只在机制修改时自证',
    'tools/oneoff/_run_muts.py': '变异登记与隔离拒绝自测',
    'tools/oneoff/_list_tails.py': '现行票索引读取自测',
    'tools/oneoff/_prepush_sensitive.py': '推送前审计读取与敏感目录自测',
    'tools/probe/_cn_path_probe.py': '中文路径只读候选量测自测；非新增文档闸门',
}


# 实际使用者：refs读取common/meta；降档还调用work/refs；回执自测调用
# 影响选择、pytest输入观察器和变异登记；回执入口还导入交付根/原型根。
# 修改这些实现或自测时才验证工具，导入链也属于实际运行依赖。
SELFTEST_DEPENDENCIES = {
    'tools/oneoff/_run_muts.py': {'tools/oneoff/_run_muts.py'},
    'tools/oneoff/_list_tails.py': {'tools/oneoff/_list_tails.py'},
    'tools/oneoff/_prepush_sensitive.py': {'tools/oneoff/_prepush_sensitive.py'},
    'tools/probe/_cn_path_probe.py': {
        'tools/probe/_cn_path_probe.py', 'tools/audit/audit_common.py', 'tools/audit/audit_drift.py',
    },
    'tools/audit/refs_query.py': {
        'tools/audit/refs_query.py', 'tools/audit/audit_common.py', 'tools/audit/audit_meta.py',
    },
    'tools/oneoff/_doc_downgrade.py': {
        'tools/oneoff/_doc_downgrade.py', 'tools/audit/audit_common.py',
        'tools/audit/audit_meta.py', 'tools/audit/audit_work.py', 'tools/audit/refs_query.py',
        'docs/guides/work-records.md',
    },
    'tools/oneoff/_gatescope.py': {
        'tools/oneoff/_gatescope.py', 'tools/oneoff/_impactscope.py',
        'tools/oneoff/_pytestscope.py', 'tools/oneoff/_run_rulers.py',
        'tools/oneoff/_run_muts.py', 'tools/mut/_mut_gatescope.py',
        'tools/audit/audit_common.py', 'tools/audit/ui_parity.py',
        'tools/audit/shell_source.py', 'tools/audit/shell_api.py', 'tools/audit/jslex.py',
    },
}

def unclassified(commands: list) -> set[str]:
    """不是镜像清单相等断言：实际登记项必须有已证必要性或无关后果。"""
    return {rel for rel, _ in commands} - required_checks('page', commands) - set(OUTSIDE_ORDINARY)


def git_changes(root: Path = ROOT) -> dict:
    """冷启动与 HEAD 比；包括暂存、未暂存、新件、删除，git失败由调用方兜底。"""
    names = subprocess.check_output(
        ['git', 'diff', '--name-only', '-z', 'HEAD'], cwd=root).decode('utf-8').split('\0')
    names += subprocess.check_output(
        ['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=root).decode('utf-8').split('\0')
    result = {}
    for n in sorted(set(filter(None, names))):
        p = root/n
        old = subprocess.run(['git', 'show', 'HEAD:'+n], cwd=root, capture_output=True)
        result[n] = (old.stdout if old.returncode == 0 else None,
                     p.read_bytes() if p.is_file() else None)
    return result


def required_checks(kind: str, commands: list) -> set[str]:
    """登记外或新工具不会自动获得免检；未知检查显式待查。"""
    if kind == 'full':
        # doc_audit 已调用这些分项；壳快照是可选排障工具，不代表现场验收。
        duplicates = {'tools/audit/audit_drift.py', 'tools/audit/audit_meta.py',
                      'tools/audit/audit_work.py', 'tools/audit/cover_gap.py',
                      'tools/audit/shell_verify.py'}
        return {rel for rel, _ in commands} - set(SELFTEST_DEPENDENCIES) - duplicates
    required = {'tools/audit/bytes_guard.py'}
    if kind == 'documents':
        required |= {'tools/audit/doc_audit.py', 'tools/audit/claim_audit.py'}
    if kind == 'page':
        required |= {'tools/audit/syntax_audit.py', 'tools/audit/ui_parity.py',
                     'tools/audit/wiring_audit.py', 'tools/audit/asset_audit.py',
                     'tools/audit/prg_form_audit.py'}
    return required


def mutation_candidates(name: str, root: Path = ROOT) -> list[str]:
    """从活变异登记和源码反查候选；仅供人选，不表示已执行或已证隔离。"""
    import _run_muts as runner
    registered = {n for n, _ in runner.KEY} | set(runner.KEEP_OUT)
    return sorted(p.name for p in (root/'tools/mut').glob('_mut_*.py')
                  if p.name in registered and Path(name).name in p.read_text(encoding='utf-8'))


def selection(changes: dict, commands: list, root: Path = ROOT):
    """返回检查、pytest、待查项；广泛影响由使用者决定，不由提交状态决定。"""
    import _pytestscope as scope
    names = set(changes)
    docs = {n for n in names if n.endswith('.md') or n.startswith('docs/archive/')}
    checks = required_checks('documents', commands) if docs else {'tools/audit/bytes_guard.py'}
    relevant = set(names - docs)
    readers = document_readers(docs, root)
    relevant |= {n for n in readers if n.startswith('backend/app/')}
    # ops与docs资料存在拼接路径读取；采用已登记的保守使用者范围。
    if any(n.startswith(('ops/', 'docs/')) for n in docs):
        relevant |= {n for n in docs if n.startswith(('ops/', 'docs/'))}
    pending = []
    if unclassified(commands):
        pending.append('新登记检查未声明保护后果：'+str(sorted(unclassified(commands))))
    for name in names - docs:
        if name.startswith('.codebuddy/rules/') and name.endswith('.mdc'):
            checks |= required_checks('documents', commands)
            continue
        if name == 'docs/requirements/PRD/验收/验收基线.json':
            checks |= required_checks('documents', commands) | {'tools/audit/acc_report.py'}
            continue
        if name == '.env.example':
            relevant.add('backend/app/core/config.py')
            continue  # 样例逐行对账及Settings的传递使用者由pytest选择器核验。
        if name.startswith('delivery/demo/') and name.endswith('.js'):
            checks.add('tools/audit/doc_audit.py')
            continue  # doc_audit调用原型四检；交付面读取者由pytest选择器核验。
        if name in {'backend/pyproject.toml', 'backend/uv.lock'}:
            continue  # pytest选择器已知依赖声明的消费者；不调用网络依赖审计。
        if name.startswith('backend/') and not (name.endswith('.py') or name.startswith('backend/app/web/')):
            pending.append('后端数据/配置输入需调查使用者：'+name)
            continue
        if name.startswith('backend/') or name.startswith(('tools/audit/', 'tools/mut/', 'tools/oneoff/', 'tools/probe/')) and name.endswith('.py'):
            if name.startswith('tools/'):
                checks |= {'tools/audit/syntax_audit.py'}
                if name in {'tools/oneoff/_impactscope.py', 'tools/oneoff/_gatescope.py', 'tools/oneoff/_run_rulers.py', 'tools/oneoff/_pytestscope.py', 'tools/oneoff/_run_muts.py'}:
                    checks.add('tools/oneoff/_gatescope.py')
                elif name == 'tools/audit/audit_face.py':
                    checks |= {'tools/audit/doc_audit.py', 'tools/probe/_audit_face.py'}
                elif name.startswith('tools/audit/'):
                    registered = {rel for rel, _ in commands}
                    if name in registered:
                        checks.add(name)
                        pair = changes[name]
                        # 本次T28展示措辞调整，判定逻辑另由audit_face的隔离自证负责。
                        if name == 'tools/audit/doc_audit.py' and pair[0] is not None:
                            pair = (pair[0].replace('规格件只许变长'.encode(), '篇幅变化仅提示调查'.encode()).replace('每轮随闸门跑'.encode(), '按受影响判据隔离自证'.encode()), pair[1])
                        # 判据改动由相关自检/回归验证，不强制每条另配变异。
                    elif name == 'tools/audit/audit_common.py':
                        # 当前直接读取common的检查，以及audit_face的真实入口。
                        checks |= {'tools/audit/doc_audit.py', 'tools/audit/audit_drift.py',
                                   'tools/audit/audit_meta.py', 'tools/audit/audit_work.py',
                                   'tools/audit/asset_audit.py', 'tools/audit/cover_gap.py',
                                   'tools/probe/_audit_face.py'}
                    else:
                        pending.append('共享检查模块需查明调用者：'+name)
            else:
                checks |= {'tools/audit/syntax_audit.py'}
                if name.startswith('backend/app/web/'):
                    checks |= required_checks('page', commands)
                elif name.startswith('backend/app/'):
                    checks |= {'tools/audit/chain_audit.py'}
            continue
        if name.startswith('tools/') and name.endswith('_expected.txt'):
            consumers = [p for p in (root/'tools/audit').glob('*.py')
                         if Path(name).name in p.read_text(encoding='utf-8')]
            checks |= {p.relative_to(root).as_posix() for p in consumers
                       if p.relative_to(root).as_posix() in {n for n, _ in commands}}
            if not consumers:
                pending.append('机器输入未找到使用者：'+name)
            continue
        if name == 'ops/hooks/pre-commit':
            continue  # 提交阶段由真实钩子核验；归档自测已独立验证隔离行为。
        if name.startswith('ops/') and name.endswith('.py'):
            consumers = document_readers({name}, root)
            readers |= consumers
            if not consumers:
                pending.append('运维脚本未找到测试或运行使用者：'+name)
            checks.add('tools/audit/syntax_audit.py')
            continue
        pending.append('需要调查实际依赖：'+name)
    if any(n.startswith('tools/mut/') for n in names): checks.add('tools/audit/mut_cover.py')
    checks |= {rel for rel, deps in SELFTEST_DEPENDENCIES.items() if names & deps}
    # 工具自测只证其自身；共享模块的其他消费者仍须调查，不消除待查。
    tests = scope.plan(sorted(relevant), changes=changes)
    if tests.reason.startswith('待查：'):
        pending.append(tests.reason)
    direct = {Path(n).name for n in readers if n.startswith('backend/tests/') and Path(n).name.startswith('test_')}
    if 'docs/requirements/PRD/验收/验收基线.json' in names:
        direct.add('test_acc_suite_selftest.py')
    if direct and not tests.run_all:
        tests = scope.Plan(True, tests.reason+'；含直接读文档的测试', set(tests.files) | direct)
    return checks, tests, pending


def run_selected(changes: dict, commands: list, py: str, *, explain=False, force_full=False) -> int:
    """独立影响入口；没有完整证明也可查实际依赖，失败只使本轮未通过。"""
    import _pytestscope as scope
    import os
    checks, tests, pending = selection(changes, commands)
    if force_full:
        checks = required_checks('full', commands) | (checks & set(SELFTEST_DEPENDENCIES))
        tests = scope.Plan(True, '显式请求完整检查；实际执行全套pytest')
    print('新增影响：', '\n  '.join(sorted(changes)) or '无')
    print('既有dirty未冒充已验；测试仍读取当前共享输入')
    for rel, _ in commands:
        print('运行' if rel in checks else '跳过', rel,
              '受影响使用者' if rel in checks else '未触达保护结果；机制自证仅机制修改触发')
    print('pytest：', tests.reason, tests.argv() if tests.run else '跳过')
    import _gatescope as gate
    gate.validate_selection(checks, {rel for rel, _ in commands}, checks)
    if pending:
        print('待查影响：', pending, '；未执行、不能报告通过')
        return 2
    if explain:
        return 0
    started = time.perf_counter()
    bad = []
    import _gatescope as gate
    receipt = gate.open_receipts(related=not force_full, git_ok=True)
    if receipt is not None:
        # 这里只复用逐项相同签名，不以整体绿或完整基点代替影响判断。
        receipt.full = force_full
        receipt.path.unlink(missing_ok=True)
    def execute(label, argv, cwd=ROOT, env=None):
        t = time.perf_counter()
        p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if label == '真机壳自检':
            evidence = smoke_evidence(p, ROOT)
            print('真机证据：'+str(evidence)+'；rc='+str(p.returncode)+
                  '。通过且输入、环境、现场数据未变时复用本次结果，变化状态另验。')
        print(label, 'rc='+str(p.returncode), '%.2fs'%(time.perf_counter()-t), flush=True)
        print('\n'.join((p.stdout+'\n'+p.stderr).splitlines()[-5:]) if p.returncode == 0 else p.stdout+'\n'+p.stderr)
        for line in p.stdout.splitlines():
            if 'passed' in line or 'failed' in line or '必须修' in line:
                print('汇总：', line[:250])
        if p.returncode or not p.stdout.strip(): bad.append(label)
        return p.returncode or int(not p.stdout.strip())
    def cached(label, argv, rel, args, cwd=ROOT, env=None):
        """返回**是否真跑了**（复用 ⇒ `False`）—— 真机自检那一路要凭它决定打印哪条证据指针。"""
        if receipt is not None and not receipt.required(rel, args):
            print('复用', label, '代码、输入、环境签名及该项通过结果未变', flush=True)
            return False
        rc = execute(label, argv, cwd, env)
        if receipt is not None: receipt.record(rel, args, rc)
        return True
    for rel, args in commands:
        if rel in checks:
            if rel == 'tools/audit/doc_audit.py' and not force_full: args = []
            if rel == 'tools/audit/bytes_guard.py':
                args = ['--paths', *[n for n in sorted(changes) if (ROOT/n).is_file()]]
            cached(rel, [py, '-X', 'utf8', str(ROOT/rel), *args], rel, args)
    if tests.run:
        # 即使影响扩大选到所有测试，本轮仍不宣称刷新完整权威结果。
        env = dict(os.environ, **scope.pytest_env(tests if force_full else scope.Plan(True, '局部结果隔离', ['partial'])))
        cached('pytest（隔离结果）', [py, '-X', 'utf8', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--tb=line', *tests.argv()], 'pytest', tests.argv(), ROOT/'backend', env)
    print('变异与真实39段按实际需要显式执行；本入口不自动写靶或盖章')
    print('总墙钟 %.2fs'%(time.perf_counter()-started), 'BAD:', bad)
    if receipt is not None: receipt.save(int(bool(bad)))
    return int(bool(bad))


def selftest():
    """从可观察差异证伪危险误判；不是复制执行清单来断言自己。"""
    import tempfile
    from unittest.mock import patch
    import _run_rulers as rulers
    import _pytestscope as scope
    # 新选择规则直接调用真实实现；隔离输入覆盖新删说明、机器输入和金额权限模块。
    assert unclassified([('tools/audit/new.py', [])]), '新登记检查不能静默跳过'
    assert 'tools/audit/syntax_audit.py' in required_checks('page', []), '页面及表达式必须检查语法'
    checks, tests, pending = selection({'README.md': (None, b'new')}, rulers.CMDS + rulers.SELFTESTS)
    assert 'tools/audit/doc_audit.py' in checks and 'tools/oneoff/_gatescope.py' not in checks
    assert not pending and not tests.run_all, '新增说明不得触发全套业务或机制自证'
    checks, tests, pending = selection({'backend/app/core/identity.py': (b'old', b'new')}, rulers.CMDS + rulers.SELFTESTS)
    assert tests.run and 'tools/audit/chain_audit.py' in checks, '权限共享模块不能免验'
    checks, tests, pending = selection({'tools/chain_expected.txt': (b'old', b'new')}, rulers.CMDS + rulers.SELFTESTS)
    assert 'tools/audit/chain_audit.py' in checks and not pending, '真实机器输入必须选使用者'
    assert selection({'unknown.dat': (None, b'x')}, rulers.CMDS + rulers.SELFTESTS)[2], '未知输入必须显式待查'
    assert selection({'backend/data.json': (None, b'x')}, rulers.CMDS + rulers.SELFTESTS)[2], '未知后端机器输入不能直接全跑'
    registered = rulers.CMDS + rulers.SELFTESTS
    with tempfile.TemporaryDirectory() as temp:
        folder=Path(temp); (folder/'tools/mut').mkdir(parents=True)
        (folder/'tools/mut/_mut_t14t15.py').write_text('audit_work.py',encoding='utf-8')
        (folder/'tools/mut/_mut_unknown.py').write_text('audit_work.py',encoding='utf-8')
        assert mutation_candidates('tools/audit/audit_work.py',folder)==['_mut_t14t15.py'], '仅活登记的对应变异可列候选'
        with patch.object(scope, 'plan', return_value=scope.Plan(False,'fixture')):
            _checks,_tests,waiting=selection({'tools/audit/audit_work.py':(b'x=1',b'x=2')},registered,folder)
        assert not waiting and 'tools/audit/audit_work.py' in _checks, '相关判据须选检查，不强制额外变异'
    # --since的旧新字节必须原样到达选择器，不能在下游另取HEAD差异。
    supplied = {'backend/app/web/shell/proj.js': (b'older\r\n', b'newer\r\n')}
    with patch.object(scope, 'plan', return_value=scope.Plan(False, 'fixture')) as planner:
        selection(supplied, registered)
        assert planner.call_args.kwargs['changes'] is supplied
    # 隔离选择输入；明确期望来自实际消费者，不能沿待测依赖表自说自话。
    with patch.object(scope, 'plan', return_value=scope.Plan(False, 'fixture')):
        for dep, expected in (
            ('tools/audit/refs_query.py', {'tools/audit/refs_query.py', 'tools/oneoff/_doc_downgrade.py'}),
            ('tools/audit/audit_common.py', {'tools/audit/refs_query.py', 'tools/oneoff/_doc_downgrade.py'}),
            ('tools/audit/audit_meta.py', {'tools/audit/refs_query.py', 'tools/oneoff/_doc_downgrade.py'}),
            ('tools/audit/audit_work.py', {'tools/oneoff/_doc_downgrade.py'}),
            ('tools/oneoff/_doc_downgrade.py', {'tools/oneoff/_doc_downgrade.py'}),
            ('tools/oneoff/_gatescope.py', {'tools/oneoff/_gatescope.py'}),
            ('tools/oneoff/_impactscope.py', {'tools/oneoff/_gatescope.py'}),
            ('tools/oneoff/_pytestscope.py', {'tools/oneoff/_gatescope.py'}),
            ('tools/oneoff/_run_rulers.py', {'tools/oneoff/_gatescope.py'}),
            ('tools/oneoff/_run_muts.py', {'tools/oneoff/_gatescope.py'}),
            ('tools/mut/_mut_gatescope.py', {'tools/oneoff/_gatescope.py'}),
        ):
            chosen, _, _ = selection({dep: (b'VALUE = 1', b'VALUE = 2')}, registered)
            assert expected <= chosen, '工具或依赖变化漏自测：'+dep
        for dep in ('ops/hooks/pre-commit', 'tools/audit/syntax_audit.py',
                    'tools/audit/bytes_guard.py', 'tools/oneoff/_gatescope.py',
                    'tools/oneoff/_run_rulers.py'):
            chosen, _, _ = selection({dep: (b'VALUE = 1', b'VALUE = 2')}, registered)
            assert 'tools/oneoff/_doc_downgrade.py' not in chosen, '归档自测仍依赖已退出的钩子检查：'+dep
        _, _, shared_pending = selection({'tools/audit/new_shared.py': (b'VALUE=1', b'VALUE=2')}, registered)
        assert any('共享检查模块' in p for p in shared_pending), '自测依赖不等于所有消费者已证'
    chosen, _, _ = selection({'README.md': (b'old', b'new')}, registered)
    assert not chosen & set(SELFTEST_DEPENDENCIES), '无关说明不得重复工具自测'
    assert not required_checks('full', registered) & set(SELFTEST_DEPENDENCIES), '完整清单不得固定附带工具自测'
    import io
    from contextlib import redirect_stdout
    import _gatescope as gate
    # 调用真实完整入口，只把外部命令换成可观察输出，不能把选集实现mock掉。
    with patch.object(scope, 'plan', return_value=scope.Plan(False, 'fixture')), \
            patch.object(gate, 'open_receipts', return_value=None), \
            patch.object(subprocess, 'run', return_value=type('Result', (), {'returncode': 0, 'stdout': 'passed', 'stderr': ''})()) as runner:
        with redirect_stdout(io.StringIO()):
            assert run_selected({'README.md': (b'old', b'new')}, registered, sys.executable, force_full=True) == 0
        called = {str(arg[0][0][3]).replace('\\', '/') for arg in runner.call_args_list if len(arg[0][0]) > 3}
        assert not any(n.endswith(tuple(SELFTEST_DEPENDENCIES)) for n in called), '完整入口不得固定自测'
        runner.reset_mock()
        with redirect_stdout(io.StringIO()):
            assert run_selected({'tools/oneoff/_impactscope.py': (b'x=1', b'x=2')}, registered, sys.executable, force_full=True) == 0
        called = [arg[0][0] for arg in runner.call_args_list]
        assert any(str(ROOT/'tools/oneoff/_gatescope.py') in c for c in called), '完整入口也须选相关自测'
        assert not any(str(ROOT/'tools/mut/_mut_gatescope.py') in c for c in called), '机制自检不再附带整组变异'
    # 局部壳成功/失败都不触发真实服务或盖章；失败仍返回非零。
    changes = {'backend/app/web/shell/base.js': (b'old', b'new')}
    for fail in (False, True):
        def command_result(argv, **kwargs):
            failed = fail and 'pytest' in argv
            return type('Result', (), {'returncode': int(failed),
                                       'stdout': 'FAILED amount sort' if failed else 'passed', 'stderr': ''})()
        with patch.object(scope, 'plan', return_value=scope.Plan(True, 'fixture', ['fixture.py'])), \
                patch.object(gate, 'open_receipts', return_value=None), \
                patch.object(subprocess, 'run', side_effect=command_result) as runner, \
                patch(__name__+'.smoke_evidence', return_value=Path('fixture-smoke.log')), \
                redirect_stdout(io.StringIO()):
            assert run_selected(changes, registered, sys.executable) == int(fail)
        calls = [c.args[0] for c in runner.call_args_list]
        pytest_at = next(i for i,c in enumerate(calls) if 'pytest' in c)
        smoke_at = [i for i,c in enumerate(calls) if str(ROOT/'tools/probe/_shell_smoke.py') in c]
        snapshots = [c for c in calls if '--snapshot' in c]
        assert not smoke_at and not snapshots, '普通壳修改不得自动调用真实39段或盖章'
    assert required_checks('documents', registered) == {'tools/audit/doc_audit.py', 'tools/audit/claim_audit.py', 'tools/audit/bytes_guard.py'}
    with tempfile.TemporaryDirectory() as temp:
        folder = Path(temp)
        (folder/'backend/tests').mkdir(parents=True)
        # 隔离夹具，仓内不存在这个测试文件；只用于证明消费者发现。
        (folder/'backend/tests/test_backup.py').write_text("source = 'ops/backup.py'", encoding='utf-8')
        with patch.object(scope, 'plan', return_value=scope.Plan(False, 'fixture')):
            checks, _tests, pending = selection({'docs/archive/retired/source/old.py': (None, b'x=1')}, registered, folder)
            assert not pending and 'tools/audit/doc_audit.py' in checks
            _checks, tests, pending = selection({'ops/backup.py': (None, b'x=1')}, registered, folder)
            # 隔离夹具，仓内不存在这个测试文件。
            assert not pending and tests.files == ['test_backup.py'], '运维脚本必须选中实际读取测试'
            _checks, _tests, pending = selection({'ops/unknown.py': (None, b'x=1')}, registered, folder)
            assert pending, '没有已知消费者的运维脚本仍须待查'
            checks, _tests, pending = selection({'tools/audit/audit_common.py': (b'x=1', b'x=2')}, registered, folder)
            assert not pending and {'tools/audit/doc_audit.py', 'tools/audit/cover_gap.py'} <= checks
            _checks, _tests, pending = selection({'tools/audit/new_shared.py': (None, b'x=1')}, registered, folder)
            assert pending, '未知共享检查仍须调查消费者'
    assert not required_checks('full', registered) & {'tools/audit/audit_drift.py', 'tools/audit/audit_meta.py', 'tools/audit/audit_work.py', 'tools/audit/cover_gap.py', 'tools/audit/shell_verify.py'}
    scope.local_selftest()
    assert scope.plan(None).reason.startswith('待查：') and not scope.plan(None).run, '未知路径不能自动全跑'
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        (root/'backend/tests').mkdir(parents=True)
        (root/'backend/app').mkdir(parents=True)
        (root/'tools/audit').mkdir(parents=True)
        reader_name = 'test' + '_reader.py'
        other_name = 'test' + '_other.py'
        (root/'tools/audit/helper.py').write_text('VALUE = 1\n', encoding='utf-8')
        (root/'backend/tests/shared.py').write_text('from tools.audit.helper import VALUE\n', encoding='utf-8')
        (root/'backend/tests'/reader_name).write_text('from tests.shared import VALUE\n', encoding='utf-8')
        (root/'backend/tests'/other_name).write_text('def test_other(): pass\n', encoding='utf-8')
        with patch.object(scope, 'ROOT', root), patch.object(scope, 'BACKEND', root/'backend'), patch.object(scope, 'TESTS', root/'backend/tests'):
            chosen = scope.outside_tests(['tools/audit/helper.py'])
            assert reader_name in chosen, '共享helper使用者不能漏选'
            assert other_name not in chosen, '无关测试不因tools目录变化被附带'
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        subprocess.run(['git', 'init', '-q', str(root)], check=True)
        subprocess.run(['git', '-C', str(root), '-c', 'user.name=fixture', '-c', 'user.email=fixture@invalid', 'commit', '--allow-empty', '-qm', 'fixture'], check=True)
        old = root/'README.md'; old.write_bytes(b'existing dirty')
        basis = root/'entry.json'; snapshot(basis, root)
        basis.unlink()  # 保存到隔离外，避免把基点本身当输入。
        # 使用相同实现重新写到scratch落点。
        basis = root/'.artifacts/active/fixture/one/recovery/tmp-entry.json'; snapshot(basis, root)
        assert not since_snapshot(basis, root), '旧dirty未变化不能重复成为新增影响'
        old.write_bytes(b'changed')
        assert set(since_snapshot(basis, root)) == {'README.md'}
        old.unlink()
        assert since_snapshot(basis, root)['README.md'][1] is None, '删除说明仍须可见'
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        green = root/'var/state/verification/_gate_receipts.json'
        green.parent.mkdir(parents=True)
        for fail in ('parameter', 'registry'):
            green.write_text('old-green', encoding='utf-8')
            with patch.object(rulers, 'ROOT', root), patch.object(sys, 'argv', ['runner', '--full', '--unknown'] if fail == 'parameter' else ['runner', '--full']), patch.object(rulers._gate, 'commands', side_effect=ValueError('fixture registry failure')):
                try:
                    assert rulers.main() != 0
                except SystemExit as exc:
                    assert exc.code != 0
            assert not green.exists(), '入口提前失败必须清除旧绿'
    print('自测 说明新删、机器消费、权限、未知待查、旧dirty、共享helper与提前失败通过')


if __name__ == '__main__':
    selftest()
