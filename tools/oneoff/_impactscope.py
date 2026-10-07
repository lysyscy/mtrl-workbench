"""按实际新增差异判断普通核验；关键、结构或未知输入退回完整入口。

只承认信息记录与单页模板静态文字；表达式、标签、属性和页外代码均不能省验。
执行登记仍归 CMDS，失败不留通过证明，局部 pytest 永不刷新权威四态。
"""
from __future__ import annotations

from pathlib import Path
import re
import json
from html.parser import HTMLParser
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tools/audit'))
import jslex
import shell_api

# 这是守护后果的分类，执行清单仍从 CMDS 读取；新登记项缺分类即完整重验。
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
}


def unclassified(commands: list) -> set[str]:
    """不是镜像清单相等断言：实际登记项必须有已证必要性或无关后果。"""
    return {rel for rel, _ in commands} - required_checks('page', commands) - set(OUTSIDE_ORDINARY)


def template_shape(source: str) -> str:
    """只消去模板原文中的中文文本节点；保留全部 JS 插值及 HTML 结构。"""
    out = []
    i = 0
    while i < len(source):
        end = jslex._skip_trivia(source, i) if source.startswith(('//', '/*'), i) else i
        if end != i:
            out.append(source[i:end])
            i = end
        elif source[i] in "'\"`":
            end = jslex.skip_string(source, i)
            literal = source[i:end]
            if source[i] == '`':
                if re.search(r'<\s*(script|style)\b', literal, re.I):
                    raise ValueError('模板包含脚本或样式')
                chunks = []
                start = k = i + 1
                while k < end - 1:
                    if source[k] == '\\':
                        # 不证明转义与节点边界的关系。
                        raise ValueError('模板含转义，影响未知')
                    if source.startswith('${', k):
                        chunks.append(mask_text(source[start:k]))
                        stop = jslex.match(source, k + 1, '{', '}')
                        chunks.append(source[k:stop])
                        start = k = stop
                    else:
                        k += 1
                chunks.append(mask_text(source[start:end-1]))
                literal = '`' + ''.join(chunks) + '`'
            out.append(literal)
            i = end
        elif source[i] == '/' and jslex.regex_ok(source, i):
            end = jslex.skip_regex(source, i)
            out.append(source[i:end])
            i = end
        else:
            out.append(source[i])
            i += 1
    return ''.join(out)


def mask_text(chunk: str) -> str:
    """节点必须全是普通中文/标点；数字、实体、插值、标签不能被掩盖。"""
    edits = []
    starts = [0]
    for line in chunk.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    class Nodes(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=False)
            self.depth = 0
        def handle_starttag(self, tag, attrs):
            if tag not in {'br', 'hr', 'img', 'input', 'meta', 'link'}:
                self.depth += 1
        def handle_endtag(self, tag):
            self.depth = max(0, self.depth - 1)
        def handle_data(self, data):
            if self.depth and re.fullmatch(r'[\u4e00-\u9fff，。；：！？、（）「」· \t]+', data):
                line, column = self.getpos()
                pos = starts[line - 1] + column
                if chunk[pos:pos+len(data)] != data:
                    raise ValueError('HTML节点位置无法证明')
                edits.append((pos, pos + len(data)))
    parser = Nodes()
    parser.feed(chunk)
    parser.close()
    for a, b in reversed(edits):
        chunk = chunk[:a] + 'TEXT' + chunk[b:]
    return chunk


def classify(changes: dict[str, tuple[bytes | None, bytes | None]]) -> tuple[str, str]:
    """返回 documents/page/full；每个实际改动必须有证明，缺一个就完整重验。"""
    pages = set()
    kinds = set()
    for name, (before, after) in changes.items():
        if before is None or after is None:
            return 'full', '新增或删除文件：' + name
        if name.endswith('.md') and name.startswith((
                '.codebuddy/work/50-tickets/', '.codebuddy/memory/journal/')):
            kinds.add('documents')
            continue
        if name == 'backend/app/web/index.html':
            old = before.decode('utf-8')
            new = after.decode('utf-8')
            a = shell_api.slices_of_lines(old.splitlines(keepends=True))
            b = shell_api.slices_of_lines(new.splitlines(keepends=True))
            changed = [p for p in a if a[p] != b.get(p)]
            if set(a) != set(b) or len(changed) != 1:
                return 'full', '多个页面或页面边界改变'
            page = changed[0]
            x, y = ''.join(a[page]), ''.join(b[page])
            # 仅证明直接返回模板的页面；复杂页函数中的字符串可能参与业务比较。
            direct = re.match(r'^V\.m\d+\s*=\s*\(\)\s*=>\s*`', x)
            other = re.match(r'^V\.m\d+\s*=\s*\(\)\s*=>\s*`', y)
            if direct is None or other is None:
                return 'full', '页面模板不是直接返回值，影响未证明'
            try:
                xe = jslex.skip_string(x, direct.end() - 1)
                ye = jslex.skip_string(y, other.end() - 1)
                shape_equal = (template_shape(x[:xe]) == template_shape(y[:ye]) and x[xe:] == y[ye:])
            except (ValueError, IndexError):
                shape_equal = False
            if not shape_equal or old.replace(x, '', 1) != new.replace(y, '', 1):
                return 'full', '表达式、结构、属性或页外代码改变'
            pages.add(page)
            kinds.add('page')
            continue
        return 'full', '关键或未证明输入：' + name
    if len(pages) > 1:
        return 'full', '多个页面改变'
    return ('page', '单页静态文字：' + ','.join(pages)) if pages else (
        'documents', '仅信息记录；无业务、入口或核验机制差异')


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


def changes_since_proof(receipt) -> dict | None:
    """完整通过的内容基点才可排除既有dirty；任意失败后不能复用该基点。"""
    if receipt is None or not receipt.verified:
        return None
    previous = receipt.verified
    changed = {n for n in set(previous) | set(receipt.files)
               if previous.get(n) != receipt.files.get(n)}
    changes = {}
    for n in changed:
        if not n.startswith('repo/'):
            raise ValueError('完整基点外部输入改变')
        name = n[5:]
        path = receipt.root/name
        after = path.read_bytes() if path.is_file() else None
        # 信息记录不参与业务执行，仅需要知道它仍是既有文件。
        if name.endswith('.md') and name.startswith((
                '.codebuddy/work/50-tickets/', '.codebuddy/memory/journal/')):
            changes[name] = (b'existing' if n in previous else None, after)
        else:
            # 回执只有摘要，不能证明文字变化的形状；读完整通过时保存的壳字节。
            before = receipt.verified_shell if name == 'backend/app/web/index.html' else None
            changes[name] = (before, after)
    return changes


def required_checks(kind: str, commands: list) -> set[str]:
    """登记外或新工具不会自动获得免检；未知检查退回完整路径。"""
    if kind == 'full':
        return {rel for rel, _ in commands}
    required = {'tools/audit/bytes_guard.py', 'tools/oneoff/_gatescope.py'}
    if kind == 'page':
        required |= {'tools/audit/syntax_audit.py', 'tools/audit/ui_parity.py',
                     'tools/audit/wiring_audit.py', 'tools/audit/asset_audit.py',
                     'tools/audit/prg_form_audit.py'}
    return required


def source_tests(receipt, root=ROOT):
    """只有完整通过绑定的读入证据才可选测试；改写或缺档即全套兜底。"""
    import _gatescope as gate
    import _pytestscope as scope
    metadata = None
    path = root/'artifacts/_pytest_inputs.json'
    if receipt is not None and receipt.pytest_inputs and path.is_file():
        raw = path.read_bytes()
        if gate.digest(raw) == receipt.pytest_inputs:
            try:
                metadata = json.loads(raw)
            except (ValueError, UnicodeError):
                pass
    return scope.text_plan(metadata)


def run(kind: str, reason: str, commands: list, py: str, receipt=None, changed=()) -> int:
    """普通路径实际运行所需检查；全壳pytest与真机保留，耗时照实汇报。"""
    import _gatescope as gate
    import _pytestscope as scope
    start = time.perf_counter()
    if receipt is not None:
        receipt.path.unlink(missing_ok=True)
    required = required_checks(kind, commands)
    available = {rel for rel, _ in commands}
    selected = [(rel, args) for rel, args in commands if rel in required]
    gate.validate_selection({rel for rel, _ in selected}, available, required)
    print('影响核验：', kind, reason, flush=True)
    for rel, _ in commands:
        if rel not in required:
            print('  跳过', rel, OUTSIDE_ORDINARY.get(rel, '代码/壳结构检查：信息记录未触及运行面'))
    bad = []
    authority = ROOT/'artifacts/acc_results.json'
    authority_before = authority.read_bytes()
    def execute(label, argv, cwd=ROOT, env=None):
        t = time.perf_counter()
        p = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                           text=True, encoding='utf-8', errors='replace')
        print(label, 'rc='+str(p.returncode), '%.2fs' % (time.perf_counter()-t), flush=True)
        print('\n'.join(((p.stdout or '')+'\n'+(p.stderr or '')).splitlines()[-4:]))
        if p.returncode or not p.stdout.strip():
            bad.append(label)
        return p.returncode
    for rel, args in selected:
        if rel == 'tools/audit/bytes_guard.py':
            args = ['--paths', *sorted(changed)]
        execute(rel, [py, '-X', 'utf8', str(ROOT/rel), *args])
    print('变异：未改检查/判据，无必要写靶；跳过变异执行（共用靶保持串行）')
    if kind == 'page':
        import os
        pl = source_tests(receipt)
        print('pytest范围：', pl.reason, '跑全套' if pl.run_all else str(len(pl.files))+'件', flush=True)
        print('  跑了：', '全部' if pl.run_all else ' '.join(sorted(pl.files)))
        print('  跳过：', '无' if pl.run_all else ' '.join(sorted({p.name for p in scope.TESTS.glob('test_*.py')} - set(pl.files))))
        env = dict(os.environ, **scope.pytest_env(scope.Plan(True, '局部隔离', ['placeholder'])))
        execute('pytest（隔离结果）', [py, '-m', 'pytest', '-q',
                '-p', 'no:cacheprovider', '--tb=line', *pl.argv()], ROOT/'backend', env)
        execute('真机壳完整自检', [py, '-X', 'utf8', str(ROOT/'tools/probe/_shell_smoke.py')])
        # 盖章是原有改壳收尾条件；仅在前面的全部检查成功后执行。
        if not bad:
            execute('壳基线盖章', [py, '-X', 'utf8', str(ROOT/'tools/audit/shell_verify.py'), '--snapshot'])
    else:
        print('pytest/真机/壳章：信息记录没有触达运行面，跳过')
    if authority.read_bytes() != authority_before:
        bad.append('局部核验改写权威档')
    if receipt is not None:
        receipt.save(int(bool(bad)))
    print('BAD:', bad)
    print('影响核验内部耗时 %.2fs；约一分钟目标以外层总墙钟为准' % (time.perf_counter()-start))
    return int(bool(bad))


def selftest():
    """从可观察差异证伪危险误判；不是复制执行清单来断言自己。"""
    doc = '.codebuddy/work/50-tickets/TAIL-1-example.md'
    assert classify({doc: (b'old', b'new')})[0] == 'documents'
    assert classify({doc: (None, b'new')})[0] == 'full'
    for name in ['backend/app/x.py', 'ops/agents/issue-tracker.md', 'unknown.txt',
                 'tools/oneoff/_run_rulers.py', 'backend/alembic/x.py']:
        assert classify({name: (b'old', b'new')})[0] == 'full', '关键/未知输入必须完整'
    html = 'V.m01=()=>`<p>原文字</p>${amount}`;\nconst x=1;\n'
    def case(new):
        return classify({'backend/app/web/index.html': (html.encode(), new.encode())})[0]
    assert case(html.replace('原文字', '新文字')) == 'page'
    attribute = 'V.m01=()=>`<p title=">原文字<">显示</p>`;\n'
    assert classify({'backend/app/web/index.html': (attribute.encode(), attribute.replace('原文字', '新文字').encode())})[0] == 'full', '属性不能误判静态节点文字'
    indirect = 'V.m01=()=>{let a=`<p>原文字</p>`;return a;};\n'
    assert classify({'backend/app/web/index.html': (indirect.encode(), indirect.replace('原文字', '新文字').encode())})[0] == 'full', '复杂页函数影响无法证明' 
    for new in [html.replace('amount', 'other'), html.replace('<p>', '<p id="x">'),
                html.replace('x=1', 'x=2'), html.replace('</p>', '</div>')]:
        assert case(new) == 'full', '结构、表达式及页外变化必须完整'
    assert template_shape('`<p>${a > "原文字" < b}</p>`') != template_shape('`<p>${a > "新文字" < b}</p>`')
    assert template_shape('`<p>${"<b>原文字</b>"}</p>`') != template_shape('`<p>${"<b>新文字</b>"}</p>`'), '插值内部HTML字符串不得省验'
    assert 'tools/audit/syntax_audit.py' in required_checks('page', []), '静态文字也必须实际验证JS语法'
    assert unclassified([('tools/audit/new.py', [])]), '新登记检查必须可观察兜底'
    from types import SimpleNamespace
    external = SimpleNamespace(verified={'face0/x': 'old'}, files={'face0/x': 'new'})
    try:
        changes_since_proof(external)
    except ValueError:
        pass
    else:
        raise AssertionError('仓外输入变化必须完整，不能退回HEAD局部')
    import tempfile
    from unittest.mock import patch
    import _run_rulers as rulers
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        green = root/'artifacts/_gate_receipts.json'
        green.parent.mkdir()
        for fail in ('parameter', 'registry'):
            green.write_text('old-green', encoding='utf-8')
            with patch.object(rulers, 'ROOT', root), patch.object(sys, 'argv', ['runner', '--unknown'] if fail == 'parameter' else ['runner']), patch.object(rulers._gate, 'commands', side_effect=ValueError('fixture registry failure')):
                assert rulers.main() == 1
            assert not green.exists(), '入口提前失败必须清除旧绿'
    import _pytestscope as scope
    import _gatescope as gate
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        path = root/'artifacts/_pytest_inputs.json'
        path.parent.mkdir()
        names = sorted(p.name for p in scope.TESTS.glob('test_*.py'))
        data = {'version': 1, 'files': [names[0]], 'shared': [], 'tests': names}
        path.write_text(json.dumps(data), encoding='utf-8')
        proof = SimpleNamespace(pytest_inputs=gate.digest(path.read_bytes()))
        assert names[0] in source_tests(proof, root).files
        data['files'] = [names[1]]
        path.write_text(json.dumps(data), encoding='utf-8')
        assert source_tests(proof, root).run_all, '读入证据改变不能复用'
    print('自测 影响分类、属性/插值、关键/未知、提前失败及读入证明隔离通过')


if __name__ == '__main__':
    selftest()
