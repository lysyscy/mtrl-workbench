"""291 隔离反向自证：一次性回写与恢复事件缺失，均必须变红。"""
from pathlib import Path
import subprocess
import sys
import shutil
from _isolated import isolated_backend


def main():
    cases=[('one-shot','app/mod03_notice/repository.py', 'field=F_STAT_PAID_AUTO,', 'field="stat_paid",',
            'test_tail291_revoke.py::test_restore_follows_next_payment'),
           ('missing-event','app/mod03_notice/repository.py', 'add_stat_trace(session, StatTrace(', 'return\n    add_stat_trace(session, StatTrace(',
            'test_tail291_revoke.py::test_restore_follows_next_payment'),
           ('reason-check','app/web/shell/actions.js','if(!rs) return','if(false) return',
            'test_wired_m03_action.py::test_壳里有生效流水才出撤销付款且单条就地开窗')]
    for name,path,old,new,test in cases:
        with isolated_backend('tail291-') as (base,env):
            root=Path(__file__).resolve().parents[2]
            shutil.copytree(root/'tools/audit',base.parent/'tools/audit',ignore=shutil.ignore_patterns('__pycache__'))
            p=base/path;text=p.read_text(encoding='utf-8')
            before,sep,fn=text.partition('def restore_stat_paid_auto(' if name!='reason-check' else ' revOk:async t=>{')
            assert sep and old in fn
            if name=='one-shot':
                fn=fn.replace(old,new)+'\n    notice.stat_paid = total\n    session.flush()\n'
            elif name=='missing-event':
                fn=fn.replace(old,'notice.stat_paid = total\n    session.flush()\n    '+new)
            else:
                fn=fn.replace(old,new)
            p.write_text(before+sep+fn,encoding='utf-8')
            env['PYTHONPATH']=str(base)+';'+str(root)
            r=subprocess.run([sys.executable,'-X','utf8','-m','pytest','-q',f'tests/{test}'],cwd=base,env=env,capture_output=True,text=True,encoding='utf-8')
            assert r.returncode==1 and 'AssertionError' in r.stdout,(name,r.stdout,r.stderr)
            print(name,'RED rc=1 assertion confirmed')
    print('PASS 3 isolated mutations; formal files untouched')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
