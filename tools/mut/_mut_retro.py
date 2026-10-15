"""选测和证据出口：只在隔离工具副本中造漏选、全量误选、正文泄漏及假绿。"""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def main():
    with tempfile.TemporaryDirectory(prefix='tmp-retro-', dir=ROOT/'.scratch/local') as folder:
        base=Path(folder)
        shutil.copytree(ROOT/'tools/oneoff', base/'tools/oneoff', ignore=shutil.ignore_patterns('__pycache__', '_归档*'))
        runner=base/'proof.py'
        runner.write_text("import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).parent/'tools/oneoff'))\nimport _pytestscope as s\nimport _impactscope as i\ns.shell_selftest()\ni.retro_selftest()\n", encoding='utf-8')
        def run():
            return subprocess.run([sys.executable,'-X','utf8',str(runner)], cwd=base,
                                  capture_output=True, text=True, encoding='utf-8', timeout=60)
        normal=run(); assert normal.returncode==0,normal.stdout+normal.stderr
        cases=[
            ('共享漏选','_pytestscope.py','if _reach(mods, m) & readers','if m in readers'),
            ('全量误选','_pytestscope.py','selected = shell_plan()',"selected = Plan(True, 'mutant')"),
            ('json误认js','_pytestscope.py',"re.search(r'\\.js\\b', v)","'.js' in v"),
            ('摘要泄漏正文','_impactscope.py',"'files': len(data['files'])","'files': data['files']"),
            ('失败证据变绿','_impactscope.py',"'rc': result.returncode","'rc': 0"),
        ]
        for label,rel,old,new in cases:
            path=base/'tools/oneoff'/rel; original=path.read_bytes(); source=original.decode('utf-8')
            assert source.count(old)==1,label
            try:
                path.write_bytes(source.replace(old,new).encode('utf-8'))
                red=run(); assert red.returncode and 'AssertionError' in red.stderr,red.stdout+red.stderr
                print('PASS 正常绿、反例红：'+label,flush=True)
            finally:
                path.write_bytes(original)
    return 0


if __name__=='__main__':
    sys.exit(main())
