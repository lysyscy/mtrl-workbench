"""TAIL-285 unresolved evidence review, read-only snapshots; preserve approved plan."""
from collections import Counter
from decimal import Decimal
import hashlib
import json

from _hist_extract import OUT, csv_out, dump, money, project_key


def main():
    inputs = [OUT/'extract/抽取明细.jsonl', OUT/'match/只读库快照.json',
              OUT/'plan/排除与待确认.json', OUT/'plan/拟写入清单.json']
    hashes = {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    records = [json.loads(s) for s in inputs[0].read_text(encoding='utf-8').splitlines()]
    snapshot = json.loads(inputs[1].read_text(encoding='utf-8'))
    pending = json.loads(inputs[2].read_text(encoding='utf-8'))['pending']
    notices = {n['id']: n for n in snapshot['notices']}
    findings = []
    for row in pending:
        raw = row['raw']
        e, f, g = [money(raw.get(c)) for c in ('E', 'F', 'G')]
        f = f if f is not None else Decimal(0)
        reason = '；'.join(row['依据'])
        nid = row.get('notice_id')
        notice = notices.get(nid)
        same_bill = [r for r in records if row['bill_no'] and r['bill_no'] == row['bill_no']
                     and (r['sheet'], r['line']) != (row['sheet'], row['line'])]
        near = [r for r in same_bill if abs(r['month']-row['month']) == 1]
        near_identity = [r for r in near if r['payee'] == row['payee']
                         and project_key(r['project']) == project_key(row['project'])]
        refs = [dict(sheet=r['sheet'], line=r['line'], project=r['project'], payee=r['payee'],
                     expense_date=r['expense_date'], E=r['raw'].get('E'), F=r['raw'].get('F'),
                     G=r['raw'].get('G'), annotation=r['annotation'], pay_date=r['pay_date'],
                     same_expense_date=r['expense_date'] == row['expense_date']) for r in same_bill]
        active = [v for v in snapshot['flows'] if nid is not None and v['notice_id'] == nid
                  and v['status'] == 'effective']
        exact = [v for v in active if row['pay_date'] and v['pay_date'] == row['pay_date']
                 and g is not None and money(v['amount']) == g]
        local_equal = e is not None and g is not None and g > 0 and e-f == g
        if '金额无' in reason:
            if not local_equal:
                detail = '本行E−F不等G或数值缺失'
            elif not near:
                detail = '相邻月份没有同编号行'
            elif not near_identity:
                detail = '邻月同编号但收款或项目不同'
            elif not any(r['expense_date'] == row['expense_date'] for r in near_identity):
                detail = '邻月同编号同项目同收款，但费用日期不同或单侧空'
            else:
                detail = '严格邻月存在，但E/F/G演变冲突或缺值'
        elif '无可识别编号' in reason:
            detail = '无可识别编号'
        elif '错位' in reason:
            detail = '区块疑似错位'
        elif 'G多源' in reason:
            detail = '两月重复事件'
        else:
            detail = '付款日期未确证'
        findings.append(dict(sheet=row['sheet'], line=row['line'], project=row['project'],
                             bill_no=row['bill_no'], payee=row['payee'], original_reason=reason,
                             diagnosis=detail, pay_date=row['pay_date'], annotation=row['annotation'],
                             E=str(e), F=str(f), G=str(g), expense_date=row['expense_date'],
                             local_equal=local_equal, notice_id=nid,
                             notice=notice, identity=row.get('evidence', {}).get('identity_check'),
                             same_bill_refs=refs, exact_existing_G_hint=exact,
                             active_flows=active, raw=raw))
    assert len(findings) == 369
    result = dict(input_sha256=hashes, scope='仅继续取证；不变更既有分类、批准或冻结清单；库快照时点见原报告',
                  count=len(findings), diagnoses=dict(Counter(r['diagnosis'] for r in findings)),
                  exact_existing_G_hints=sum(bool(r['exact_existing_G_hint']) for r in findings), rows=findings)
    dump(OUT/'report/待确认继续核查.json', result)
    csv_out(OUT/'report/待确认继续核查.csv', findings, list(findings[0]))
    assert all(hashlib.sha256(p.read_bytes()).hexdigest() == hashes[str(p.relative_to(OUT))] for p in inputs)
    print(json.dumps({k:v for k,v in result.items() if k != 'rows'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
