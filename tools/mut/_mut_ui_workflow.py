"""守供应商确认、即时搜索、集中导入流程、范围保留与空态判据；仅在临时副本改坏，不碰正式工作文件。

对应 backend/tests/test_shell_ui_workflow.py；另对改指后的看板删项及导入行内提示断言做内存自证。
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
WEB=ROOT/'backend/app/web'
PY=ROOT/'backend/.venv/Scripts/python.exe'
TEST='backend/tests/test_shell_ui_workflow.py'
CASES=[
 ('设置删项','shell/legacy.js','<h4>外观主题</h4>','<h4>外观主题</h4><p>变更留痕</p>','系统设置精简主题无障碍与尺寸切换'),
 ('设置主题名称','shell/legacy.js','aria-label="${esc(p.name)}"','aria-label="匿名"','系统设置精简主题无障碍与尺寸切换'),
 ('默认页说明复活','index.html','<h4>审查结果<span class="sp">','<h4>审查结果<span class="sp"><div class="tip">旧说明</div>','默认页删说明保留操作与反馈'),
 ('撤页复活','shell/view.js',"['imp','数据导入','通用']","['m13','导出与删除','MOD-13'],['imp','数据导入','通用']",'默认页删说明保留操作与反馈'),
 ('真实导出保留','index.html','data-act="bigExport"','data-act="disabledBigExport"','默认页删说明保留操作与反馈'),
 ('建档读取错误保留','shell/core.js','ARCP.length || ARCP_ERR','ARCP.length','项目页实际待办与错误保留'),

 ('过程资料矩阵接线','shell/core.js','PROC_MATRIX = d.matrices || {};','PROC_MATRIX = {};','过程资料历史候选月份金额与后端一致'),
 ('截止修改清预览','shell/legacy.js','IMP.cutoff=t.value;IMP.preview=null;','IMP.cutoff=t.value;','截止月返回修改使旧预览无法确认'),
 ('首项直接确定','shell/actions.js','String(selected?selected.value:(supSel||\'\'))','String(supSel||\'\')','供应商首项直接确定与人工回车'),
 ('人工回车','shell/actions.js',"e.key==='Enter'&&!e.isComposing&&field", "e.key==='DisabledEnter'&&!e.isComposing&&field",'供应商首项直接确定与人工回车'),
 ('搜索过滤','shell/proj.js','&&ntSearchMatch(n,f.q)','&&true','搜索各展示列并重置'),
 ('隐藏控件保留年月','shell/legacy.js',"IMP.ym || bjMonth()","bjMonth()",'导入只显示当前步骤并保留范围'),
 ('当前步显示','shell/legacy.js','IMP.cols.length && IMP.step === 1','IMP.cols.length','导入只显示当前步骤并保留范围'),
 ('映射失效','shell/legacy.js',"IMP.mapping[t.dataset.src]=t.value||''; IMP.preview=null;","IMP.mapping[t.dataset.src]=t.value||'';",'修改范围或列对应使旧预览失效'),
 ('合同金额','shell/actions.js','合同金额 ${M(j.contractAmt)}','合同金额缺失','合同候选显示日期金额且仍按编号排序'),
 ('审查颜色','shell/base.js',"'plan-notfound'","'plan-missing'",'审查颜色与看板删减'),
 ('看板删项','index.html','<h4>待办<span class="sp">','<h4>待办 状态一览<span class="sp">','审查颜色与看板删减'),
 ('空库正常合计','index.html','sum:list.length?sumRowOf(PL_THEAD','sum:false?sumRowOf(PL_THEAD','空库也能验证空态和正常合计且样本恢复'),
]

def run(web, name=None):
    env=os.environ.copy();env['MTRL_UI_FIXTURE_WEB']=str(web)
    env['ACC_RESULTS_PATH']=str(ROOT/'artifacts/_mut_ui_acc_results.json')
    cmd=[str(PY),'-X','utf8','-m','pytest',TEST+('::test_'+name if name else ''),'-q','--tb=short']
    return subprocess.run(cmd,cwd=ROOT,env=env,text=True,encoding='utf-8',capture_output=True,timeout=65)

def static_checks():
    sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'tools/audit')]
    from tests import test_imp_shell, test_acc_home_todo
    from tools.audit import shell_api
    original=shell_api.text()
    checks=[
      (test_imp_shell.test_不会落库的行要在行上直接标,'处理说明','隐藏说明'),
      (test_imp_shell.test_截止核算月要说清它是什么_不是只给一个名字,'留空取本批最大核算月','隐藏默认解释'),
      (test_acc_home_todo.test_看板只保留待办,'<h4>待办<span class="sp">','<h4>待办 状态一览<span class="sp">'),
    ]
    for fn,old,new in checks:
        fn()
        assert old in original,old
        mutant=original.replace(old,new)
        with patch.object(shell_api,'text',lambda:mutant),patch.object(test_imp_shell,'SHELL',mutant):
            shell_api._scan_src.cache_clear()
            try:fn()
            except AssertionError:print('PASS 静态反向:',fn.__name__)
            else:raise RuntimeError('改坏后仍绿：'+fn.__name__)
        shell_api._scan_src.cache_clear()

def main():
    with tempfile.TemporaryDirectory(prefix='tmp-ui-mut-',dir=ROOT/'.scratch/local') as folder:
        web=Path(folder)/'web';shutil.copytree(WEB,web)
        normal=run(web)
        if normal.returncode:print(normal.stdout+normal.stderr);return 1
        print('PASS 正常基线',flush=True)
        for label,file,old,new,test in CASES:
            path=web/file;original=path.read_bytes();src=original.decode('utf-8')
            if old not in src:raise RuntimeError('靶未命中：'+label)
            path.write_bytes(src.replace(old,new).encode('utf-8'))
            try:
                result=run(web,test)
                if result.returncode==0 or ('FAILED '+TEST+'::test_'+test) not in result.stdout.replace('\\','/'):
                    print(result.stdout+result.stderr);raise RuntimeError('未证明指定断言报红：'+label)
                print('PASS 反向:',label,flush=True)
            finally:path.write_bytes(original)
    static_checks()
    return 0

if __name__=='__main__':sys.exit(main())
