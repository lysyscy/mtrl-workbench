"""292 引用导航隔离自证：错行、歧义与虚拟定位退化必须被浏览器捕获。"""
from pathlib import Path
import subprocess
import sys
import shutil
from _isolated import isolated_backend


def main():
    cases=[
        ('contract-filter','app/web/shell/actions.js',"fJc={tag:'全部',arch:'全部',sup:'',projs:[j.proj],amt:''}","fJc=fJc",'test_contract_id_conflicting_filters_and_return'),
        ('inventory-first','app/web/shell/actions.js','String(x.id)===String(t.dataset.iv)','x.wh===t.dataset.wh','test_inventory_original_id_virtual_and_return'),
        ('ambiguous-first','app/web/shell/pages-a.js','hits.length===1?hits[0]:null','hits.length?hits[0]:null','test_plan_unique_ambiguous_and_orphan_flow'),
        ('virtual-no-scroll','app/web/shell/core.js','inst.tw.scrollTop=i*EH;','inst.tw.scrollTop=0;','test_notice_exact_id_in_550_virtual_rows[flow]'),
        ('trace-write-button','app/web/shell/actions.js','data-act="jcContract"','data-act="jcAdd"','readonly'),
    ]
    for name,path,old,new,test in cases:
        with isolated_backend('tail292-') as (base,env):
            root=Path(__file__).resolve().parents[2]
            shutil.copytree(root/'tools/audit',base.parent/'tools/audit',ignore=shutil.ignore_patterns('__pycache__'))
            p=base/path;text=p.read_text(encoding='utf-8');assert old in text,name
            p.write_text(text.replace(old,new),encoding='utf-8')
            env['MTRL_UI_FIXTURE_WEB']=str(base/'app/web')
            env['PYTHONPATH']=str(base)+';'+str(root)
            target='tests/test_wired_m03_action.py::test_壳里查看关联是纯只读且流水含已撤销' if test=='readonly' else f'tests/test_tail292_nav.py::{test}'
            r=subprocess.run([sys.executable,'-X','utf8','-m','pytest','-q',target],cwd=base,env=env,capture_output=True,text=True,encoding='utf-8')
            assert r.returncode==1 and ('AssertionError' in r.stdout or 'TimeoutError' in r.stdout),(name,r.stdout,r.stderr)
            print(name,'RED rc=1 exact-row/uniqueness assertion confirmed')
    print('PASS 5 isolated mutations; formal files untouched')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
