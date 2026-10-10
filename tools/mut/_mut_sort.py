"""真实排序行序的反向灵敏度：文字金额、空值前置、草稿参与排序应红。"""
from pathlib import Path
import shutil
import subprocess
import sys
from _isolated import isolated_backend


def main():
    with isolated_backend('sort-proof-') as (base,env):
        shutil.copytree(Path(__file__).resolve().parents[2]/'tools/audit',base.parent/'tools/audit',
                        ignore=shutil.ignore_patterns('__pycache__'))
        argv=[sys.executable,'-X','utf8','-m','pytest',
              'tests/test_wired_m03_list.py::test_表头排序实际行序_金额空值与合计草稿','-q','--tb=short']
        def probe():
            return subprocess.run(argv,cwd=base,env=env,capture_output=True,text=True,
                                  encoding='utf-8',timeout=30)
        normal=probe();assert normal.returncode==0,normal.stdout+normal.stderr
        target=base/'app/web/shell/base.js';raw=target.read_bytes();source=raw.decode('utf-8')
        for label,old,new in [
            ('金额按文字比较','_cmp(a.v,b.v,tp,st.d)',"_cmp(a.v,b.v,'s',st.d)"),
            ('空值排前','if(ea) return 1;','if(ea) return -1;'),
            ('草稿参与排序',r'/\bdraftrow\b/.test(openTag)||',''),
        ]:
            assert source.count(old)==1,(label,source.count(old))
            try:
                target.write_bytes(source.replace(old,new).encode('utf-8'))
                red=probe()
                assert red.returncode==1 and 'FAILED' in red.stdout and 'ERROR' not in red.stdout,red.stdout+red.stderr
                print(label+'：正常绿/缺陷红',flush=True)
            finally:
                target.write_bytes(raw)
        assert target.read_bytes()==raw
    print('3/3 排序行为反向灵敏度通过；正式壳未写靶')


if __name__=='__main__':
    main()
