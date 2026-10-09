"""守历史值参与合计与2025早月留空；在隔离函数源码中造错，不写工作靶。

随TAIL-269回归移除时可删；本项目真实风险为报表金额遗漏或历史重复。
"""
from pathlib import Path
import sys
import inspect
from decimal import Decimal as D
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from app.mod07_setl import extract as X

source=inspect.getsource(X.extract_template_grid)
amounts={'焊材':{'甲':{'2025-01':D('900'), '2025-12':D('10')}}}
def valid(fn):
    row=fn(amounts,'焊材',warehouses=['甲'],year='2025',balances={'焊材':{'甲':D('20')}})['rows'][0]
    return row['total']==D('30') and row['cells']==[None]*11+[D('10')]
assert valid(X.extract_template_grid)
for old,new in [("[bal.get(w), *cells]", "cells"), ("m <= '2025-11'", "False")]:
    assert old in source
    namespace=dict(X.__dict__)
    exec(compile(source.replace(old,new),'<isolated-tail269>','exec'),namespace)
    assert not valid(namespace['extract_template_grid'])
    print('caught:',old)
print('normal 1/1; mutations 2/2 caught')
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/probe'))
from _shell_pops import anchored
assert anchored(dict(top=105,triggerBottom=100,panelBottom=200,triggerTop=80))
assert anchored(dict(top=20,triggerBottom=100,panelBottom=75,triggerTop=80))
assert not anchored(dict(top=20,triggerBottom=100,panelBottom=60,triggerTop=80))
print('popup normal below/above 2/2; detached red 1/1')
