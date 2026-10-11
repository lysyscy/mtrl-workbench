"""守290项目内序号：数全量、改回筛选行号必须分别被库级与浏览器断言捕获。"""
from pathlib import Path
import subprocess
import sys
import shutil
from _isolated import isolated_backend


def main():
    cases = [
        ('count-all', 'app/mod11_jc/domain.py', 'if r["tag"] == TAG_IN', 'if True', 'test_project_sequence_and_xlsx'),
        ('filtered-index', 'app/web/index.html', "${j.projectSeq == null ? '—' : j.projectSeq}", '${i+1}', 'test_browser_sequence_columns_and_export'),
        ('export-index', 'app/report_export/jc_export.py', 'width_max=28)', 'seq_key=SEQ_KEY, width_max=28)', 'test_project_sequence_and_xlsx'),
    ]
    for name, path, old, new, test in cases:
        with isolated_backend('tail290-') as (base, env):
            shutil.copytree(Path(__file__).resolve().parents[2]/'tools/audit',base.parent/'tools/audit',ignore=shutil.ignore_patterns('__pycache__'))
            p=base/path
            raw=p.read_bytes(); text=raw.decode('utf-8')
            assert old in text, name
            p.write_bytes(text.replace(old,new).encode('utf-8'))
            env['MTRL_UI_FIXTURE_WEB']=str(base/'app/web')
            env['PYTHONPATH']=str(base)+';'+str(Path(__file__).resolve().parents[2])
            result=subprocess.run([sys.executable,'-X','utf8','-m','pytest','-q',f'tests/test_tail290_jc.py::{test}'],cwd=base,env=env,capture_output=True,text=True,encoding='utf-8')
            assert result.returncode==1 and 'AssertionError' in result.stdout, (name,result.stdout,result.stderr)
            print(name, 'RED rc=1 assertion confirmed')
    print('PASS 3 isolated mutations; formal files untouched')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
