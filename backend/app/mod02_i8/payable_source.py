"""采购合同应付只读取数；2026-10-20 Edge CDP核实，金额不代表已取得发票。"""
from decimal import Decimal
import json
from app.core.errors import ExternalServiceError
from app.mod02_i8.client import serialize_fetch
from app.mod02_i8.contract_source import CLIENT_FILTER

PATH = '/PMS/PCM/Contract/ProjBal/GetCntProjBalList'


def fetch_payables(client):
    records = []
    with serialize_fetch('jc_payable'):
        for start in range(0, 20000, 200):
            data = client.post_json(PATH, params={'model': '7', 'floatmenuCondition': ''}, data={
                'page': str(start // 200), 'start': str(start), 'limit': '200', 'sortinfo': '',
                'queryfilter': '{"queryFilter":"{}"}',
                'clientfilter': json.dumps({'OrgQuery': json.loads(CLIENT_FILTER)['OrgQuery']})})
            if not isinstance(data, dict) or not data.get('Success') or not isinstance(data.get('Record'), list):
                raise ExternalServiceError('采购合同应付读取失败，未执行关联')
            total = int(data['totalRows'])
            page = data['Record']
            records.extend(page)
            if len(records) >= total:
                break
            if not page:
                raise ExternalServiceError('采购合同应付返回不完整，未执行关联')
        else:
            raise ExternalServiceError('采购合同应付超过读取上限，未执行关联')
    if len({str(r['PhId']) for r in records}) != total:
        raise ExternalServiceError('采购合同应付数量发生变化，请重新读取')
    return [{'id': str(r['PhId']), 'code': r['BillNo'], 'contract_no': r.get('PhidCnt_EXName') or '',
             'contract_phid': str(r.get('PhidCnt') or ''), 'project': r.get('PhidPc_EXName') or '',
             'supplier': r.get('PhidBalComp_EXName') or '', 'amount': Decimal(str(r.get('AppAmtVatFc') or 0))}
            for r in records if str(r.get('AsrFlag')) == '1' and str(r.get('WfFlag')) == '2'
            and r.get('PhidFcur_EXName') == '人民币' and Decimal(str(r.get('ExchRate') or 0)) == 1]
