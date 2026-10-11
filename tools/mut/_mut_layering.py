"""守test_layering的A/B/B2/C/D/C2：隔离直查必红，正当引用放行，防空扫/幽灵/名单增长仍承重。

复用归档件仍有效的import靶；旧入口直接改工作文件且路径失效，改为isolated_backend。
只加载副本判据并调用真实断言，不执行注入的业务源码；不写正式文件或权威四态。
"""
from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
import sys

from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
TARGETS = ("tests/test_layering.py",)

# 归档旧靶的路径/规则已逐项与现行源码比较；不再使用旧脚本的正式树写入入口。
IMPORT_CASES = (
    ("core/nav.py", "from app.mod01_projects import models as ghost", "test_A_core_不得反向依赖业务包_除放行名单", "反向依赖会成环"),
    ("core/app_settings.py", "from app.mod14_config.models import AppSetting as ghost", "test_A_core_不得反向依赖业务包_除放行名单", "反向依赖会成环"),
    ("core/projects.py", "from app.mod01_projects import repository as ghost", "test_A_core_不得反向依赖业务包_除放行名单", "反向依赖会成环"),
    ("mod09_fee/models.py", "from app.report_export import service as ghost", "test_B_业务包不得直接_import_导出层_除放行名单", "改一侧牵动另一侧"),
    ("export_registry.py", "from app.report_export import service as ghost", "test_B2_注册表必须是叶子件", "叶子件"),
    ("mod03_notice/merge.py", "from app.mod05_flow import repository as ghost", "test_C_包间不得直查对方表_只许经包间出口", "直查了对方表"),
    ("mod05_flow/domain.py", "from app.mod03_notice import repository as ghost", "test_C_包间不得直查对方表_只许经包间出口", "直查了对方表"),
    ("mod09_fee/models.py", "from app.mod07_setl import repository as ghost", "test_C_包间不得直查对方表_只许经包间出口", "直查了对方表"),
    ("report_export/ledger_export.py", "from app.mod06_proc import repository as ghost", "test_D_导出层不得直查业务包的表", "直查了业务包的表"),
)
QUERY = "test_C2_不得把别包模型当查询目标"
TABLE = "test_C2_名单逐条命中且待清只许变短"
SHAPES = ("select(X)", "select(X.id)", "session.get(X, 1)",
          "session.query(X)", "select(1).select_from(X)", "session.get(entity=X, ident=1)")
ALIASES = (
    ("from app.mod01_projects.models import Project as X", "X"),
    ("from app.mod01_projects import models as pm", "pm.Project"),
    ("import app.mod01_projects.models", "app.mod01_projects.models.Project"),
    # 数字包名不许再次被正则漏掉。
    ("from app.mod02_i8.models import RunRecord as X", "X"),
    ("from ..mod01_projects.models import Project as X", "X"),
)


def digest():
    return {str(p): hashlib.sha256(p.read_bytes()).digest()
            for base in (ROOT / "backend/app", ROOT / "backend/tests")
            for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts}


def main():
    before = digest()
    count = 0
    with isolated_backend('layering-') as (base, _env):
        sys.path.insert(0, str(base))
        spec = importlib.util.spec_from_file_location('isolated_layering', base / TARGETS[0])
        layer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(layer)

        def check(name, red=None):
            nonlocal count
            try:
                getattr(layer, name)()
            except AssertionError as exc:
                assert red is not None and red in str(exc), f'意外失败：{name}: {exc}'
            else:
                assert red is None, f'哑靶：{name} 未报 {red}'
            count += 1

        baseline = [name for name in vars(layer) if name.startswith('test_')
                    and (name.startswith(('test_A_', 'test_B_', 'test_C_', 'test_D_', 'test_C2_'))
                         or name == 'test_B2_注册表必须是叶子件')]
        for name in baseline:
            check(name)
        print(f'基线 {len(baseline)} 条真判据绿')

        def injected(path, source, name, red=None):
            p = layer.APP / path
            raw = p.read_bytes()
            nl = b'\r\n' if b'\r\n' in raw else b'\n'
            try:
                p.write_bytes(raw + nl + source.replace('\n', nl.decode()).encode())
                check(name, red)
            finally:
                p.write_bytes(raw)
            assert p.read_bytes() == raw

        for path, source, name, red in IMPORT_CASES:
            assert (layer.APP / path).is_file(), path
            injected(path, source, name, red)

        for imports, model in ALIASES:
            for shape in SHAPES:
                source = f'\ndef query_ghost(session):\n    from sqlalchemy import select\n    {imports}\n    return {shape.replace("X", model)}\n'
                print('C2靶', model, shape)
                injected('mod03_notice/sup_match.py', source, QUERY, '跨包查询目标必须走主人service')
        print('A/B/B2/C/D旧靶红；C2五形态＋get关键字×五种引用全红')

        # 与typing/domain/join条件混用，也不能误伤；本包查询正当。
        normal = '''
from sqlalchemy import select
from app.mod01_projects.models import Project as Other
from app.mod01_projects import domain as PD
from app.mod03_notice.models import PaymentNotice as Own
def normal_query(session, p: Other) -> Other:
    PD.ordered([p])
    by_type = {Other: p}
    by_type.get(Other)
    PD.CACHE.get(Other)
    return select(Own).join(Other, Own.ownership_id == Other.id).where(Other.id == 1)
'''
        injected('mod03_notice/sup_match.py', normal, QUERY)
        print('typing/domain/本包查询/join与where条件放行')

        # Session注解和显式session别名也必须识别，不靠固定变量拼写。
        injected('mod03_notice/sup_match.py', '''
from sqlalchemy.orm import Session
from app.mod01_projects.models import Project
def typed_query(db: Session):
    return db.get(entity=Project, ident=1)
''', QUERY, '跨包查询目标必须走主人service')
        injected('mod03_notice/sup_match.py', '''
from app.mod01_projects.models import Project
def alias_query(session):
    db = session
    return db.query(Project)
''', QUERY, '跨包查询目标必须走主人service')

        # 真的把已收口的一处改回原来直查，规则必须红（不只喂合成查询）。
        p = layer.APP / 'mod04_plan/project_views.py'
        raw = p.read_bytes()
        old = b'for p in PS.all_projects(session)'
        assert raw.count(old) == 2
        try:
            p.write_bytes(raw.replace(old, b'for p in session.execute(select(Project)).scalars().all()', 1)
                          + b'\nfrom sqlalchemy import select\nfrom app.mod01_projects.models import Project\n')
            check(QUERY, '跨包查询目标必须走主人service')
        finally:
            p.write_bytes(raw)

        # 名单漏扫、同处多一次查询、幽灵和增长分别验证。
        key = next(iter(layer._ALLOW_C2_PENDING))
        path, fn, model = key
        injected(path, f'\nfrom {model.rsplit(".",1)[0]} import {model.rsplit(".",1)[1]} as Ghost\n'
                       f'def {fn}(session):\n    session.get(Ghost, 1)\n', QUERY,
                 '跨包查询目标必须走主人service')
        ghost = ('mod03_notice/missing.py', 'ghost', 'app.mod01_projects.models.Project')
        layer._ALLOW_C2_BY_DESIGN[ghost] = '隔离幽灵'
        try:
            check(TABLE, 'C2 名单未被扫出')
        finally:
            del layer._ALLOW_C2_BY_DESIGN[ghost]
        layer._ALLOW_C2_PENDING[ghost] = '隔离增长'
        try:
            check(TABLE, 'C2 待清名单不许变长')
        finally:
            del layer._ALLOW_C2_PENDING[ghost]
        original = layer._query_targets
        layer._query_targets = lambda *args: []
        try:
            check(TABLE, 'C2 名单未被扫出')
        finally:
            layer._query_targets = original
        original_files = layer._py_files
        layer._py_files = lambda *args: []
        try:
            check(QUERY, '规则 C2 件数不足')
        finally:
            layer._py_files = original_files
        original_app = layer.APP
        empty = base / 'empty'; empty.mkdir()
        layer.APP = empty
        try:
            check(QUERY, '规则 C2 包数不足')
        finally:
            layer.APP = original_app
        print('同处新增/名单幽灵/增长/漏扫/件数与包数防空扫均红')

    assert digest() == before, '正式源码被改写'
    print(f'全部命中 {count} 次；正式文件与权威四态未写靶')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
