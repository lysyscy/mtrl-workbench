"""独立核验回执：输入、运行环境和检查实现一致才复用。

失败清除整体证明与失败项，独立成功项保留。坏档禁用复用，影响选择仍归入口；
是否全验由用户明确要求或实际广泛依赖决定。回执可删，不构成权威四态。
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
VERSION = 2
# 不是执行清单：未在此证明输入范围的登记项始终重跑，新增项不会静默漏掉。
CODE_ONLY = frozenset({
    'tools/audit/syntax_audit.py', 'tools/audit/wiring_audit.py',
    'tools/audit/prg_form_audit.py', 'tools/audit/ui_parity.py',
    'tools/probe/_audit_face.py', 'tools/oneoff/_gatescope.py',
    'tools/mut/_mut_shellapi.py', 'tools/mut/_mut_segments.py',
    'tools/mut/_mut_syntax.py',
    'tools/mut/_mut_gatescope.py',
})
EXCLUDED = frozenset({'.git', '.venv', '__pycache__', 'node_modules', 'logs'})


def commands(root: Path = ROOT, registry: str = 'CMDS') -> list[tuple[str, list[str]]]:
    """从唯一 CMDS 定义读字面量；空扫、重复、动态清单和越界路径均失败。"""
    tree = ast.parse((root/'tools/oneoff/_run_rulers.py').read_text(encoding='utf-8'))
    definitions = [n.value for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
                   and any(isinstance(t, ast.Name) and t.id == registry
                           for t in (n.targets if isinstance(n, ast.Assign) else [n.target]))]
    if len(definitions) != 1:
        raise ValueError('CMDS 清单缺失或重复 ⇒ 空扫')
    items = ast.literal_eval(definitions[0])
    if not isinstance(items, list) or not items:
        raise ValueError('CMDS 清单为空 ⇒ 空扫')
    seen = set()
    for item in items:
        if not isinstance(item, tuple) or len(item) != 2:
            raise ValueError('CMDS 登记形状不合法')
        rel, args = item
        if (not isinstance(rel, str) or not rel.startswith('tools/') or
                '\\' in rel or '..' in Path(rel).parts or rel in seen or
                not isinstance(args, list) or not all(isinstance(a, str) for a in args)):
            raise ValueError('CMDS 路径/参数不合法或重复')
        seen.add(rel)
    return items


def digest(value: bytes) -> str:
    """内容摘要；相同大小或时间戳不等于相同内容。"""
    return hashlib.sha256(value).hexdigest()


def inventory(root: Path, faces: tuple[Path, ...] = ()) -> dict[str, str]:
    """实存输入及名字空间；输出/缓存/临时靶不进入回执的输入集合。"""
    files = {}
    for label, base in [('repo', root), *[(f'face{i}', p) for i, p in enumerate(faces)]]:
        if not base.is_dir():
            raise OSError(f'输入根不存在：{label}')
        files[label+'/@root'] = digest(str(base.resolve()).encode('utf-8'))
        for folder, dirs, names in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED)
            parent = Path(folder)
            if any((parent/d).is_symlink() for d in dirs):
                raise OSError('符号链接目录输入范围无法证明')
            relative = parent.relative_to(base).as_posix()
            if label == 'repo' and (relative == '.codebuddy/work/00-scratch' or
                                    relative.startswith('.codebuddy/backups/')):
                dirs[:] = []
                continue
            for name in sorted(names):
                path = parent/name
                rel = path.relative_to(base).as_posix()
                if label == 'repo' and rel.startswith('artifacts/') and rel not in (
                        'artifacts/acc_results.json', 'artifacts/变异覆盖台账.md'):
                    continue
                if path.is_symlink():
                    raise OSError('符号链接输入范围无法证明')
                files[label+'/'+rel] = digest(path.read_bytes())
    # 壳章在备份目录，其他备份由常驻 T20 读取，不能用回执跳过。
    for path in sorted((root/'.codebuddy/backups').glob('*_壳单文件基线.html')):
        files['repo/'+path.relative_to(root).as_posix()] = digest(path.read_bytes())
    return files


def environment() -> str:
    """运行时文件、可执行文件与环境只留摘要，避免同版本代码变化仍复用。"""
    material = [sys.version, json.dumps(dict(os.environ), sort_keys=True)]
    paths = {Path(sys.executable)}
    node = shutil.which('node')
    if node:
        paths.add(Path(node))
    for base in {Path(sys.base_prefix)/'Lib', Path(sys.prefix)/'Lib',
                 ROOT/'backend/.venv/Lib'}:
        if base.is_dir():
            for folder, dirs, names in os.walk(base):
                dirs[:] = [d for d in dirs if d != '__pycache__']
                paths.update(Path(folder)/n for n in names
                             if Path(n).suffix.lower() in {'.py', '.pyd', '.dll'} or
                             n in {'METADATA', 'RECORD'})
    for path in sorted(paths):
        material.append(str(path)+':'+digest(path.read_bytes()))
    return digest('\n'.join(material).encode('utf-8'))


def input_signature(rel: str, args: list[str], files: dict, context: str) -> str | None:
    """已证输入包含整个代码/配置/交付面；未证输入返回 None，必须运行。"""
    if rel in CODE_ONLY:
        selected = {n: h for n, h in files.items() if n.startswith((
            'repo/tools/', 'repo/backend/', 'repo/ops/', 'face')) or
            n in {'repo/.env', 'repo/.env.example', 'repo/.gitignore', 'repo/.gitattributes'}}
    elif rel == 'tools/audit/shell_verify.py':
        selected = {n: h for n, h in files.items() if n.startswith((
            'repo/tools/', 'repo/backend/', 'repo/.codebuddy/backups/'))}
    elif rel == 'tools/audit/mut_cover.py':
        selected = {n: h for n, h in files.items() if n.startswith('repo/tools/') or
                    n == 'repo/artifacts/变异覆盖台账.md'}
        selected['namespace'] = digest('\n'.join(sorted(files)).encode())
    elif rel == 'tools/probe/_shell_smoke.py':
        # ⭐ 2026-10-11（`/retro` 候选 1 · 省不必要的检查）：真机自检的**证明输入 = 壳字节 ＋ 环境**
        #    （`context` 已折进末尾那道 digest）—— 范围与 `_impactscope.smoke_evidence()` 写在证据头里的
        #    那两个 sha256 **同一份**（`backend/app/web/**` ＋ 全环境）⇒ ⛔ 不另造指纹。
        #    ⚠️ 此前它落到下面那句「未证输入 ⇒ 返回 None ⇒ 必跑」：实测**同一壳字节连跑三次**
        #    （02:28 / 02:46 / 03:23，`shell_sha256` 与 `environment_sha256` 逐字相同）⇒ 白跑 ~3 分钟
        #    ＋ 三份重复证据。
        #    ⚠️ **盖章**（`tools/audit/shell_verify.py --snapshot`）**不走这条**：那是"本轮壳就是这个样"
        #    的记录（0.1 s），留着比省掉值。
        #    ⚠️ **探针自己也算了进去**（`tools/probe/**` ＝ `_shell_smoke` ＋ 段注册表 `_shell_segments`
        #    ＋ 各段）：⛔ 漏掉它就会把"**没跑过的探针版本**"记成绿 —— 加一段、改判词的下一轮直接复用旧结果。
        selected = {n: h for n, h in files.items()
                    if n.startswith(('repo/backend/app/web/', 'repo/tools/probe/'))}
    elif rel == 'pytest':
        selected = {n: h for n, h in files.items() if not n.startswith(('repo/artifacts/', 'repo/backend/.codebuddy/'))}
    else:
        return None
    return digest(json.dumps([VERSION, rel, args, context, selected],
                             sort_keys=True, ensure_ascii=False).encode('utf-8'))


def validate_selection(selected: set, available: set, required: set) -> None:
    """两向机器眼：漏跑必要项、选到清单外都报错。"""
    if not required <= selected or not selected <= available:
        raise ValueError('选集漏跑或包含清单外项目')


def read_receipt(path: Path, root: Path, context: str) -> dict:
    """坏档统一归零；构造与父子合并遵守同一份字段校验。"""
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if (not isinstance(data, dict) or data.get('version') != VERSION or
                data.get('root') != str(root.resolve()) or data.get('context') != context):
            return {}
        files, records = data.get('files'), data.get('records')
        if type(data.get('passed', True)) is not bool:
            return {}
        verified = data.get('verified', {})
        if (not isinstance(verified, dict) or
                not all(isinstance(k, str) and isinstance(v, str) for k, v in verified.items()) or
                not isinstance(data.get('verified_shell', ''), str) or
                not isinstance(data.get('pytest_inputs', ''), str)):
            return {}
        if (not isinstance(files, dict) or not isinstance(records, dict) or
                not all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()) or
                not all(isinstance(k, str) and isinstance(v, dict) and
                        set(v) == {'signature', 'rc'} and isinstance(v['signature'], str) and
                        type(v['rc']) is int and v['rc'] == 0 for k, v in records.items())):
            return {}
        return data
    except (OSError, ValueError, TypeError):
        return {}


class Receipts:
    """一次串行核验的回执；失败立即失效，完整成功后才推进输入基点。"""

    def __init__(self, root=ROOT, *, related=False, faces=(), context=None, git_ok=True):
        self.root = Path(root)
        self.faces = tuple(faces)
        self.path = self.root/'artifacts/_gate_receipts.json'
        self.related = related
        self.failed = False
        self.records = {}
        self.dirty = set()
        self.context = environment() if context is None else context
        self.files = inventory(self.root, self.faces)
        old = read_receipt(self.path, self.root, self.context)
        valid = bool(old)
        previous = old.get('files', {})
        changed = {p for p in set(previous)|set(self.files) if previous.get(p) != self.files.get(p)}
        self.external_changed = valid and any(not n.startswith('repo/') for n in changed)
        self.full = not related or not valid or not git_ok
        self.reason = ('显式完整入口' if not related else '环境或回执不可复用'
                       if self.full else '输入基点可信；只复用已有通过证明')
        self.invalid = (self.path.exists() and not valid) or old.get('passed') is False or not git_ok
        self.verified = old.get('verified', {}) if valid else {}
        shell = old.get('verified_shell', '') if valid else ''
        self.verified_shell = shell.encode('utf-8') if shell else None
        self.pytest_inputs = old.get('pytest_inputs', '') if valid else ''
        if valid:
            self.records = dict(old['records'])

    def required(self, rel, args):
        """登记项没有可用证明即必跑；只凭 rc=0 不生成证明。"""
        sign = input_signature(rel, args, self.files, self.context)
        key = json.dumps([rel, args], ensure_ascii=False)
        record = self.records.get(key)
        return self.full or sign is None or record != {'signature': sign, 'rc': 0}

    def record(self, rel, args, rc):
        """输入变化或执行失败不记绿；下一轮不能吃到失败前的旧回执。"""
        key = json.dumps([rel, args], ensure_ascii=False)
        self.dirty.add(key)
        self.records.pop(key, None)
        if rc != 0:
            self.failed = True
            return
        if input_signature(rel, args, self.files, self.context) is None:
            return
        after = inventory(self.root, self.faces)
        before_sign = input_signature(rel, args, self.files, self.context)
        after_sign = input_signature(rel, args, after, self.context)
        if before_sign is not None and before_sign == after_sign:
            self.records[key] = {'signature': before_sign, 'rc': 0}
        self.files = after

    def save(self, rc=0, *, complete=False):
        """局部/失败核验不刷新权威四态；原子替换可丢弃回执。"""
        if rc:
            self.failed = True
        # 父入口与串行变异子入口共用回执，合并各自确实更新的键，避免覆盖对方证据。
        current = read_receipt(self.path, self.root, self.context)
        merged = dict(self.records)
        merged.update(current.get('records', {}))
        for key in self.dirty:
            merged.pop(key, None)
            if key in self.records:
                merged[key] = self.records[key]
        files = inventory(self.root, self.faces)
        verified = files if complete and not self.failed else current.get('verified', self.verified)
        shell = current.get('verified_shell', '') or (self.verified_shell or b'').decode('utf-8')
        if complete and not self.failed:
            shell = (self.root/'backend/app/web/index.html').read_bytes().decode('utf-8')
        inputs = current.get('pytest_inputs', self.pytest_inputs)
        inputs_path = self.root/'artifacts/_pytest_inputs.json'
        if complete and not self.failed:
            inputs = digest(inputs_path.read_bytes()) if inputs_path.is_file() else ''
        data = {'version': VERSION, 'root': str(self.root.resolve()), 'context': self.context,
                'files': files, 'records': merged,
                'passed': not self.failed,
                'verified': {} if self.failed else verified,
                'verified_shell': '' if self.failed else shell,
                'pytest_inputs': '' if self.failed else inputs}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix('.json.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding='utf-8', newline='\n')
        temp.replace(self.path)


def open_receipts(*, related=False, git_ok=True):
    """打不开真实输入/运行时即禁用复用；选定检查仍继续，避免坏档成为免检。"""
    try:
        sys.path.insert(0, str(ROOT/'tools/audit'))
        from audit_common import delivery_root
        from ui_parity import PROTO
        faces = tuple(dict.fromkeys([delivery_root(), PROTO.parent.parent]))
        return Receipts(related=related, faces=faces, git_ok=git_ok)
    except (OSError, ValueError, TypeError) as exc:
        print('相关核验：输入无法确定，禁用复用、按影响重验（'+type(exc).__name__+'）')
        return None


def selftest() -> None:
    """见证同一未提交批次中的相关/无关变化，以及坏档、失败和漏跑的后果。"""
    rel, args = 'tools/audit/syntax_audit.py', []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root/'tools/audit/syntax_audit.py'
        source.parent.mkdir(parents=True)
        source.write_text('original', encoding='utf-8')
        ticket = root/'ticket.md'
        ticket.write_text('old', encoding='utf-8')
        authority = root/'artifacts/acc_results.json'
        authority.parent.mkdir()
        authority.write_text('authority', encoding='utf-8')
        def session(**kw):
            return Receipts(root, related=True, context='fixture', **kw)
        shell = root/'backend/app/web/index.html'
        shell.parent.mkdir(parents=True)
        shell.write_text('shell', encoding='utf-8')
        first = session()
        assert first.required(rel, args), '没有证明不能跳'
        first.record(rel, args, 0)
        first.save()
        assert not session().required(rel, args), '同输入可复用'
        full = session()
        full.save(complete=True)
        assert session().verified, '完整成功才有影响基点'
        full.save(1)
        assert not session().verified, '失败必须清除完整基点'
        first.save()
        ticket.write_text('new', encoding='utf-8')
        assert not session().required(rel, args), '已证明够不着票面'
        assert session().required('unknown.py', []), '未知输入必须跑'
        assert session(git_ok=False).required(rel, args), 'git 失败兜底'
        assert Receipts(root, context='fixture').required(rel, args), '完整入口不吃回执'
        assert Receipts(root, related=True, context='changed').required(rel, args), '环境变化兜底'
        source.write_text('changed!', encoding='utf-8')
        assert session().required(rel, args), '检查自身变化必跑'
        stable = session()
        stable.record(rel, args, 0)
        stable.save()
        new = root/'new.md'
        new.write_text('new', encoding='utf-8')
        assert not session().required(rel, args), '新增说明不使未变化的检查证明失效'
        new.unlink()
        ticket.unlink()
        assert not session().required(rel, args), '删除说明不使未变化的检查证明失效'
        ticket.write_text('new', encoding='utf-8')
        independent = session()
        independent.record(rel, args, 0)
        independent.record('unknown.py', [], 1)
        independent.save(1)
        assert not session().required(rel, args), '独立失败不使成功项失效'
        assert session().required('unknown.py', []), '失败项不能复用'
        assert not session().verified, '局部成功不能伪造整体证明'
        failed = session()
        failed.record(rel, args, 1)
        failed.save()
        assert session().required(rel, args), '失败清掉旧绿'
        moving = session()
        source.write_text('moving!!', encoding='utf-8')
        moving.record(rel, args, 0)
        moving.save()
        assert session().required(rel, args), '运行中输入变了不能记绿'
        moving.path.write_text('{broken', encoding='utf-8')
        assert session().full, '坏档全跑'
        for bad in [[], None, {'files': []}, {'files': None}, {'files': {'x': []}},
                    {'records': []}, {'records': {'x': {'signature': [], 'rc': 0}}}]:
            data = {'version': VERSION, 'root': str(root.resolve()), 'context': 'fixture',
                    'files': inventory(root), 'records': {}}
            if isinstance(bad, dict):
                data.update(bad)
            else:
                data = bad
            moving.path.write_text(json.dumps(data), encoding='utf-8')
            damaged = session()
            assert damaged.full, '可解析但字段损坏必须完整重验'
            damaged.save()
            assert not read_receipt(moving.path, root, 'fixture')['records'], '坏档合并不能留绿'
        assert authority.read_text(encoding='utf-8') == 'authority', '子集不能改权威档'
        # pytest 产物不能触发自身；真实输入、环境与参数仍让旧回执失效。
        pytest_args = ['-q', 'tests/']
        proven = session()
        proven.record('pytest', pytest_args, 0)
        proven.save()
        assert not session().required('pytest', pytest_args), 'pytest 同输入可复用'
        for name in ('artifacts/acc_results.json',
                     'backend/.codebuddy/results.json',
                     '.codebuddy/work/00-scratch/result.json'):
            product = root/name
            product.parent.mkdir(parents=True, exist_ok=True)
            product.write_text('product changed', encoding='utf-8')
            assert not session().required('pytest', pytest_args), '产物变化不能让 pytest 重跑'
        assert not any(n.startswith('repo/.codebuddy/work/00-scratch/')
                       for n in inventory(root)), 'scratch 已由 inventory 排除'
        for name in ('backend/app/web/index.html', 'backend/tests/test_theme.py',
                     'tools/audit/syntax_audit.py'):
            real = root/name
            real.parent.mkdir(parents=True, exist_ok=True)
            before = real.read_bytes() if real.exists() else None
            real.write_text('real input changed', encoding='utf-8')
            assert session().required('pytest', pytest_args), '代码、测试或工具变化必须重跑 pytest'
            if before is None:
                real.unlink()
            else:
                real.write_bytes(before)
        assert Receipts(root, related=True, context='other-env').required('pytest', pytest_args), '环境变化必须重跑 pytest'
        assert session().required('pytest', ['-q', '-x', 'tests/']), '参数变化必须重跑 pytest'
        registry = root/'tools/oneoff/_run_rulers.py'
        registry.parent.mkdir(parents=True)
        registry.write_text("CMDS = [('tools/a.py', [])]", encoding='utf-8')
        assert commands(root) == [('tools/a.py', [])]
        for invalid in ["CMDS = []", "CMDS = [('tools/a.py', []), ('tools/a.py', [])]",
                        "CMDS = [('tools/../outside.py', [])]", "OTHER = []",
                        "CMDS = make_commands()"]:
            registry.write_text(invalid, encoding='utf-8')
            try:
                commands(root)
            except (ValueError, TypeError):
                pass
            else:
                raise AssertionError('空扫、重复、动态或越界 CMDS 必须失败')
        validate_selection({'a'}, {'a', 'b'}, {'a'})
        for selected, available, required in [(set(), {'a'}, {'a'}), ({'b'}, {'a'}, set())]:
            try:
                validate_selection(selected, available, required)
            except ValueError:
                pass
            else:
                raise AssertionError('漏跑/清单外必须报错')
    import _impactscope
    _impactscope.selftest()
    import _pytestscope
    _pytestscope.input_selftest()
    # ⭐ 2026-10-11（`/retro` 候选 1）：**真机自检的复用边界** —— 改壳必重跑，改别处（含改测试、
    #    改工具、改文档）可复用上轮 rc=0；环境变了也必重跑。三向各断言一次。
    #    ⚠️ 夹具里的件名用**真实存在**的（`test_wiring_guards` 会拦"引用了不存在的测试件"）。
    smoke_files = {'repo/backend/app/web/shell/base.js': 'h1',
                   'repo/backend/tests/test_theme.py': 'h2', 'face/f.md': 'h3'}
    smoke_sig = input_signature('tools/probe/_shell_smoke.py', [], smoke_files, 'ctx')
    assert smoke_sig is not None, '真机自检没有已证输入 ⇒ 又会变成每轮必跑'
    assert input_signature('tools/probe/_shell_smoke.py', [],
                           {**smoke_files, 'repo/backend/tests/test_theme.py': 'CHANGED'}, 'ctx') == smoke_sig, \
        '与壳无关的改动（测试/工具/文档）不该让真机自检重跑'
    assert input_signature('tools/probe/_shell_smoke.py', [],
                           {**smoke_files, 'repo/backend/app/web/shell/base.js': 'CHANGED'}, 'ctx') != smoke_sig, \
        '壳字节变了必须重跑真机自检'
    assert input_signature('tools/probe/_shell_smoke.py', [], smoke_files, 'other-env') != smoke_sig, \
        '环境变了必须重跑真机自检'
    assert input_signature('tools/probe/_shell_smoke.py', [],
                           {**smoke_files, 'repo/tools/probe/_shell_segments.py': 'CHANGED'}, 'ctx') != smoke_sig, \
        '探针或段注册表变了必须重跑（否则会把没跑过的探针版本记成绿）'
    print('自测 相关核验回执、输入变化、失败、兜底、双向选集、真机自检复用边界与权威档隔离全部通过')


def main() -> int:
    if '--selftest' in sys.argv:
        selftest()
        from _run_muts import KEY
        registered = {rel for rel, _ in commands() + commands(ROOT, 'SELFTESTS')} | {'tools/mut/'+n for n, _ in KEY}
        assert CODE_ONLY <= registered, '输入元数据不得指向登记外项目'
    else:
        from _run_muts import KEY
        for rel, args in [*commands(), *[('tools/mut/'+n, []) for n, _ in KEY]]:
            proven = input_signature(rel, args, {}, 'explain') is not None
            print(rel, args, '已证代码/配置/交付面或壳章/名字空间输入' if proven else '保守重验：全仓/时间/运行态输入未收窄')
    return 0


if __name__ == '__main__':
    sys.exit(main())
