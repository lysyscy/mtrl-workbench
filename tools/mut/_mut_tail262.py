"""历史材料同月优先i8的反向灵敏度；只修改隔离副本。"""

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir, finish_run as _finish_run
from pathlib import Path
import os, shutil, subprocess, sys, tempfile
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.core.config import get_settings
CASES=[
    ('i8优先','mod06_proc/domain.py','if has_inventory:','if False:','test_tail262_proc.py::test_material_i8_same_month_precedence_keeps_history_mechanical')
]
def main():
    env=os.environ.copy();env['TEST_DATABASE_URL']=get_settings().test_database_url
    with tempfile.TemporaryDirectory(prefix='tmp-tail262-mut-',dir=ROOT/_run_dir('work')) as folder:
        base=Path(folder)/'backend';base.mkdir()
        shutil.copytree(ROOT/'backend/app',base/'app',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copytree(ROOT/'backend/tests',base/'tests',ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy2(ROOT/'backend/pytest.ini',base/'pytest.ini')
        def run(target):
            return subprocess.run([str(ROOT/'backend/.venv/Scripts/python.exe'),'-X','utf8','-m','pytest','tests/'+target,'-q','--tb=short'],cwd=base,env=env,capture_output=True,text=True,encoding='utf-8',timeout=65)
        for label,file,old,new,target in CASES:
            normal=run(target)
            assert normal.returncode==0,normal.stdout+normal.stderr
            p=base/'app'/file;original=p.read_bytes();src=original.decode('utf-8').replace('\r\n','\n')
            assert src.count(old)==1,(label,src.count(old))
            p.write_bytes(src.replace(old,new).encode('utf-8'))
            try:
                result=run(target)
                assert result.returncode and 'FAILED ' in result.stdout,result.stdout+result.stderr
                print('PASS 正常绿、指定缺陷红：'+label,flush=True)
            finally:p.write_bytes(original)
    return 0
if __name__=='__main__':sys.exit(_finish_run(main()))
