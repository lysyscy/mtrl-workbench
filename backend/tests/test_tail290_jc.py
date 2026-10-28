"""290 项目内序号、合同编号及所见导出；测试库回滚和隔离浏览器。"""
from pathlib import Path
from io import BytesIO
import openpyxl
from app.core.db import session_scope
from app.mod11_jc import repository as R, service as S, domain as D
from tests.test_acc_jc_pay_link import _project


def dataset():
    with session_scope() as s:
        a=_project(s,'__自检仓_290_A__'); b=_project(s,'__自检仓_290_B__')
        aa=[R.insert_contract(s,project_id=a.id,contract_date=dt,material_name='材料'+str(i),supplier='供应商'+str(i),contract_amt=10+i) for i,dt in enumerate(['2026-01-01','2026-01-01','2026-03-01',''])]
        bb=[R.insert_contract(s,project_id=b.id,contract_date='2026-01-01',material_name='乙材料') for _ in range(2)]
        aa[2].contract_no='00CGHT前导';s.flush()
        def read(): return {r['id']:r for r in S.build_list(s)['rows']}
        rows=read()
        assert [rows[c.id]['project_seq'] for c in aa]==[1,2,3,4]
        assert [rows[c.id]['project_seq'] for c in bb]==[1,2]
        assert S.build_list(s,supplier='供应商2',project_key=a.warehouse_name)['rows'][0]['project_seq']==3
        R.set_tag(s,aa[1].id,'不纳入');rows=read()
        assert [rows[c.id]['project_seq'] for c in aa]==[1,None,2,3]
        R.set_tag(s,aa[1].id,'纳入台账');rows=read()
        assert [rows[c.id]['project_seq'] for c in aa]==[1,2,3,4]
        ws=openpyxl.load_workbook(BytesIO(S.export_xlsx(s,ids=[aa[2].id,aa[0].id]))).active
        assert [c.value for c in ws[1]][:7]==['序号','合同日期','材料名','合同编号','供应商','合同金额','发票金额']
        assert ws['A2'].value==3 and ws['D2'].value=='00CGHT前导' and ws['A3'].value==1
        assert ws['D3'].value=='—'
        assert ws['F2'].value==12 and ws['F3'].value==10 and ws['F4'].value==22
        assert ws['F2'].number_format=='General' and ws['F2'].data_type=='n'
        assert ws.max_column==len(D.JC_COLUMNS)-len(D.PAGE_ONLY_KEYS)
        filtered=S.build_list(s,supplier='供应商2',project_key=a.warehouse_name)['rows']
        data=[{k:(str(v) if k in D.SUM_KEYS else v) for k,v in rows[c.id].items()} for c in aa+bb]
        print('DB/xlsx PASS: A=1,2,3,4 B=1,2; excluded=None; filter=3; cells/order/derived-columns/format/total=22')
        s.rollback()
        return data


def test_project_sequence_and_xlsx():
    dataset()
