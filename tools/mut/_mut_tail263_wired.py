"""TAIL-263 默认页说明删项的反向自证；仅改内存副本并执行真实旧判据。"""
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'backend'),str(ROOT/'tools/audit')]
from tests import test_wired_m01 as M1, test_wired_m09 as M9, test_wired_m14 as M14
from tools.audit import shell_api
from tests import test_wired_m04 as M4, test_wired_m05 as M5, test_wired_m06 as M6, test_wired_m07 as M7, test_wired_m07_big as MB
from tests import test_ux_states as UX
CASES=[
 (M4,'test_筛不到行时必须给空态而不是一片空白',"EMPTYROW(thCount(PL_THEAD),'当前筛选条件下没有付款计划'","EMPTYROW(thCount(PL_THEAD),'空白'"),
 (M5,'test_台账的现状数_截至行与入口名都钉住','${MONEY(cur)}','${MONEY(0)}'),
 (M6,'test_过程资料页标出机械历史段的截止月','MECH_SECTIONS = d.sections || {};','MECH_SECTIONS = {};'),
 (M7,'test_壳里产出物清单按仓数加总表且真导出','data-act="zipSfjc"','data-act="disabledZipSfjc"'),
 (MB,'test_壳里出纸走按模板导出且没有打印通道','data-act="bigExport"','data-act="disabledBigExport"'),
 (M14,'test_分类规则表只读不渲染编辑入口','<h4>集采项目剔除名单','<h4>分类规则</h4><h4>集采项目剔除名单'),
 (M14,'test_关键词编辑入口在项目行本页只读','<h4>集采项目剔除名单','<h4>小微识别关键字配置</h4><h4>集采项目剔除名单'),
 (M9,'test_壳里自动项与手填项同桌','安全文明施工费</b>','自动项已丢失</b>'),
 (M9,'test_壳里本页不设导出入口且写明随台账导出','data-act="ledExpToggle"','data-act="disabledLedExpToggle"'),
 (M1,'test_待建档入口与清单同源且与指认那路各报各的','if (ARCP.length || ARCP_ERR)','if (ARCP.length)'),
 (M1,'test_待建档入口与清单同源且与指认那路各报各的','ARCP_DROP = d.dropped_items || [];','ARCP_DROP = [];'),
]
def main():
    original = shell_api.text()
    for module,name,old,new in CASES:
        shell_api.text.cache_clear();shell_api._scan_src.cache_clear()
        target=getattr(module,name)
        target()
        assert original.count(old)==1,(name,original.count(old))
        src=original.replace(old,new)
        overrides={'SHELL':src}
        shell_api.text.cache_clear();shell_api._scan_src.cache_clear()
        with patch.multiple(module,**overrides), patch.object(shell_api,'text',return_value=src):
            try:target()
            except AssertionError:print('PASS 正常绿、指定缺陷红：'+name,flush=True)
            else:raise AssertionError('缺陷未被真实判据捕获：'+name)
    UX.test_真机31号的空态判据还在()
    probe=ROOT/'tools/probe/_shell_empty.py'
    read=Path.read_text
    def altered(path,*args,**kwargs):
        value=read(path,*args,**kwargs)
        return value.replace('ok_empty','removed_empty') if path==probe else value
    with patch.object(Path,'read_text',altered):
        try:UX.test_真机31号的空态判据还在()
        except AssertionError:print('PASS 正常绿、指定缺陷红：真机空态探针注册与结果判据')
        else:raise AssertionError('空态探针缺陷未被捕获')
    shell_api.text.cache_clear();shell_api._scan_src.cache_clear()
    return 0
if __name__=='__main__':sys.exit(main())
