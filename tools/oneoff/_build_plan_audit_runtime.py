"""Bundle canonical pure rules for LAN clients without a backend installation."""
import ast
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED, ZipInfo

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT/'skills/payment-plan-audit'
TARGET = SKILL/'resources/audit-runtime.zip'
PACKAGE = ROOT/'artifacts/payment-plan-audit.skill'
PACKAGE_FILES = (
    'SKILL.md', 'references/payment-methods.md', 'resources/audit-runtime.zip',
    'scripts/annotate.py', 'scripts/audit.py', 'scripts/methods.py',
    'scripts/projects.py', 'scripts/remote.py', 'scripts/snapshot.py',
)


def constants(path, names):
    found = {}
    for node in ast.parse(path.read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id in names:
                found[target.id] = ast.literal_eval(value)
    if set(found) != set(names):
        raise ValueError('规则常量已变化，请检查打包接线')
    return '\n'.join(f'{name} = {value!r}' for name,value in found.items()).encode('utf-8')


def build():
    direct = ['app/core/errors.py', 'app/core/money.py', 'app/mod04_plan/domain.py']
    sources = direct+['app/mod04_plan/models.py','app/mod05_flow/models.py']
    files = {name:(ROOT/'backend'/name).read_bytes() for name in direct}
    files['app/mod04_plan/models.py'] = constants(ROOT/'backend/app/mod04_plan/models.py',
        ['MATCH_MATCHED','MATCH_UNMATCHED','MATCH_AMBIGUOUS','EDITABLE_COLUMNS'])
    files['app/mod05_flow/models.py'] = constants(ROOT/'backend/app/mod05_flow/models.py',['PAY_METHODS'])
    for pkg in ('app','app/core','app/mod04_plan','app/mod05_flow'):
        files[pkg+'/__init__.py'] = b''
    files['manifest.json'] = json.dumps({p:sha256((ROOT/'backend'/p).read_bytes()).hexdigest()
                                         for p in sources},sort_keys=True,indent=2).encode('utf-8')
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    with ZipFile(TARGET,'w') as out:
        for name,content in sorted(files.items()):
            entry=ZipInfo(name,date_time=(2026,1,1,0,0,0))
            entry.compress_type=ZIP_DEFLATED
            out.writestr(entry,content)
    print(TARGET)


def build_package():
    # 只发布运行必需文件，避免测试、会话和临时业务数据混入交付包。
    files = {name:(SKILL/name).read_bytes() for name in PACKAGE_FILES}
    PACKAGE.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(PACKAGE, 'w') as out:
        for name, content in sorted(files.items()):
            entry = ZipInfo(f'{SKILL.name}/{name}', date_time=(2026, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            out.writestr(entry, content)
    print(PACKAGE)
    return PACKAGE


if __name__=='__main__':
    build()
    build_package()
