"""Read-only investigation of remaining historic payment clues; no automatic remapping."""
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
import re

from _hist_extract import OUT, csv_out, dump, money, project_key
from _hist_match import PayRow, PayDraft, confirm_batch, normalize, session_scope, text


def receiver_match(source, notice):
    if not normalize(source):
        return ''
    actual = {normalize(notice['payee'])}
    if notice.get('jc_supplier'):
        actual.add(normalize(notice['jc_supplier']))
    if normalize(source) in actual:
        return '精确全名'
    bracket = re.fullmatch(r'(.*?)[（(](.*)[）)]',source)
    if (bracket and normalize(bracket.group(1)) == normalize(notice['payee'])
            and notice.get('jc_supplier') and normalize(bracket.group(2)) == normalize(notice['jc_supplier'])):
        return '括号前收款账户＋括号内已维护集采供应商均精确'
    if source.endswith(('（临建）','(临建)')) and normalize(re.sub(r'[（(]临建[）)]$','',source)) in actual:
        return '去源行临建用途说明后全名精确'
    return ''


def main():
    source_path=OUT/'report/新口径剩余问题.json'
    sources=json.loads(source_path.read_text(encoding='utf-8'))['rows']
    protected=[OUT/'plan/拟写入清单.json',OUT/'plan/增补冻结清单.json',OUT/'plan/增补候选_待逐笔批准.json']
    hashes={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    approved=[]
    for p in protected[:2]:
        approved.extend(json.loads(p.read_text(encoding='utf-8'))['rows'])
    assert len(approved)==238
    with session_scope() as session:
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        readonly=session.execute(text('SHOW transaction_read_only')).scalar()
        notices=[dict(r) for r in session.execute(text('SELECT * FROM payment_notice ORDER BY id')).mappings()]
        flows=[dict(r) for r in session.execute(text('SELECT * FROM payment_flow ORDER BY id')).mappings()]
        links=[dict(r) for r in session.execute(text('SELECT * FROM jc_payment ORDER BY id')).mappings()]
        projects=[dict(r) for r in session.execute(text('SELECT id, name_full, warehouse_name, disp FROM project ORDER BY id')).mappings()]
        session.rollback()
    assert readonly=='on'
    assert len(notices)==1146 and sum(n['bill_no'].startswith('FKTZS') for n in notices)==1143,'库内基线变化，停止'
    dump(OUT/'match/剩余匹配只读快照.json',dict(transaction_read_only=readonly,notices=notices,flows=flows,links=links,projects=projects))
    byid={n['id']:n for n in notices}
    ownership={p['id']:p for p in projects}
    linked={r['notice_id'] for r in links}
    paid=defaultdict(lambda:Decimal(0))
    for f in flows:
        if f['status']=='effective':
            paid[f['notice_id']]+=money(f['amount'])
    committed=defaultdict(lambda:Decimal(0))
    for r in approved:
        committed[r['notice_id']]+=money(r['amount'])
    records=[json.loads(s) for s in (OUT/'extract/抽取明细.jsonl').read_text(encoding='utf-8').splitlines()]
    def project_ok(row,n):
        p=ownership.get(n['ownership_id'],{})
        return project_key(row['project']) in {project_key(n['project_name']),project_key(p.get('disp','')),project_key(p.get('warehouse_name') or '')}
    def summary(n,row):
        amount=money(row['amount'])
        cap=money(n['amount_approved'])-paid[n['id']]-committed[n['id']]
        errors=[]
        if n['excluded'] or n['i8_revoked'] or n['revoked_joint']:
            errors.append('撤单/剔除')
        if amount is None or not row['pay_date'] or not row['pay_method']:
            errors.append('金额/付款日/方式尚不齐')
        else:
            errors.extend(confirm_batch([PayRow(n['id'],n['approve_status'],cap,n['category'],n['id'] in linked)],
                         {n['id']:PayDraft(row['pay_method'],amount)},pay_date=row['pay_date'],remark=row['remark']).errors)
        earlier=bool(row['pay_date'] and str(n['doc_date'])<=row['pay_date'])
        return dict(notice_id=n['id'],bill_no=n['bill_no'],project=n['project_name'],payee=n['payee'],
                    jc_supplier=n.get('jc_supplier',''),approval_amount=str(n['amount_approved']),
                    bill_title=n['fields'].get('BillName',''),doc_date=str(n['doc_date']),
                    source_expense_date=row['expense_date'],expense_date_equal=bool(row['expense_date'] and str(n['doc_date'])==row['expense_date']),
                    document_not_after_payment=earlier,receiver_basis=receiver_match(row['payee'],n),
                    database_paid=str(paid[n['id']]),approved_238_reserved=str(committed[n['id']]),
                    remaining_cap=str(cap),preflight_errors=errors,
                    excel_same_bill_refs=[dict(sheet=r['sheet'],line=r['line'],annotation=r['annotation']) for r in records if r['bill_no']==n['bill_no']])
    cases=[]
    corrected=[]
    for r in sources:
        n=byid.get(r['notice_id'])
        candidates=[]
        for alternative in notices:
            if (money(r['E']) is not None and money(r['E'])==money(alternative['amount_approved'])
                    and project_ok(r,alternative) and receiver_match(r['payee'],alternative)):
                candidates.append(summary(alternative,r))
        current=summary(n,r) if n else None
        issues=list(r['issues'])
        if n and receiver_match(r['payee'],n) and project_ok(r,n) and money(r['E'])==money(n['amount_approved']):
            issues=[i for i in issues if i!='收款单位/已维护集采供应商不一致']
        if n and not issues and not current['preflight_errors']:
            corrected.append(dict(r,issues=[],receiver_correction_basis=receiver_match(r['payee'],n),
                                  remaining_cap=current['remaining_cap'],balance_after=str(money(current['remaining_cap'])-money(r['amount']))))
        # Source line splits of one notice are kept as evidence, not merged into bank events.
        split=[]
        if n and any('源流程金额' in i for i in r['issues']):
            same=[x for x in sources if x['notice_id']==r['notice_id'] and x['pay_date']==r['pay_date']
                  and x['payee']==r['payee'] and x['project']==r['project']]
            if len(same)>1 and all(money(x['E']) is not None for x in same):
                amount=sum((money(x['E']) for x in same),Decimal(0))
                if amount==money(n['amount_approved']):
                    split=dict(source_refs=[dict(sheet=x['sheet'],line=x['line'],E=x['E'],amount=x['amount']) for x in same],
                               sum_E=str(amount),approval_amount=str(n['amount_approved']),
                               proposal='流程金额似按费用分项拆列；需确认实际是一笔合付还是两笔，不自动合并')
        plausible=[c for c in candidates if c['document_not_after_payment'] and not c['preflight_errors']]
        cases.append(dict(source=r,current_notice=current,matching_candidates=candidates,
                          three_factor_unique=len(candidates)==1,chronology_and_preflight_candidates=plausible,
                          chronology_and_preflight_unique=len(plausible)==1,source_split_evidence=split,
                          remaining_issues=issues,requires_user_mapping_confirmation=True))
    report=dict(count=len(cases),protected_sha256=hashes,approved_count=238,approved_amount=str(sum((money(r['amount']) for r in approved),Decimal(0))),
                rule='继续查项目/收款/流程金额＋通知书标题及时间顺序；费用日一致仍单列；未确认映射绝不自动采用；不使用F',
                three_factor_unique=sum(c['three_factor_unique'] for c in cases),
                unmapped_unique=sum(c['three_factor_unique'] for c in cases if c['source']['notice_id'] is None),
                formatting_corrections=len(corrected),formatting_correction_amount=str(sum((money(r['amount']) for r in corrected),Decimal(0))),rows=cases)
    mapping_proposals=[]
    allocated=defaultdict(lambda:Decimal(0))
    for case in cases:
        if case['source']['notice_id'] is not None or not case['chronology_and_preflight_unique']:
            continue
        candidate=case['chronology_and_preflight_candidates'][0]
        row=case['source']
        fingerprint=(candidate['notice_id'],row['pay_date'],row['amount'])
        duplicate=any((p['candidate']['notice_id'],p['source']['pay_date'],p['source']['amount'])==fingerprint for p in mapping_proposals)
        allocated[candidate['notice_id']]+=money(row['amount'])
        cap=money(candidate['remaining_cap'])
        pending_issues=[]
        if allocated[candidate['notice_id']]>cap:
            pending_issues.append('本轮拟对应清单累计超付，仍需裁定')
        if duplicate:
            pending_issues.append('本轮拟对应清单同日同金额重复，仍需裁定')
        mapping_proposals.append(dict(source=row,candidate=candidate,mapping_confirmed=False,payment_approved=False,
                                      cumulative_proposed=str(allocated[candidate['notice_id']]),
                                      balance_after_238_and_proposals=str(cap-allocated[candidate['notice_id']]),pending_issues=pending_issues))
    dump(OUT/'plan/唯一线索拟对应_待确认.json',dict(count=len(mapping_proposals),
         amount=str(sum((money(p['source']['amount']) for p in mapping_proposals),Decimal(0))),
         rule='仅为拟对应；费用日不同/缺失需用户确认；238笔批准不延伸',rows=mapping_proposals))
    csv_out(OUT/'report/唯一线索拟对应_待确认.csv',[
        dict(sheet=p['source']['sheet'],line=p['source']['line'],project=p['source']['project'],payee=p['source']['payee'],
             original_bill=p['source']['bill_no'],candidate_bill=p['candidate']['bill_no'],bill_title=p['candidate']['bill_title'],
             source_E=p['source']['E'],approval=p['candidate']['approval_amount'],amount=p['source']['amount'],
             pay_date=p['source']['pay_date'],method=p['source']['pay_method'],doc_date=p['candidate']['doc_date'],
             source_expense_date=p['source']['expense_date'],database_paid=p['candidate']['database_paid'],
             approved_reserved=p['candidate']['approved_238_reserved'],balance_after=p['balance_after_238_and_proposals'],
             evidence=p['candidate'],issues=p['pending_issues']) for p in mapping_proposals],
        ['sheet','line','project','payee','original_bill','candidate_bill','bill_title','source_E','approval','amount',
         'pay_date','method','doc_date','source_expense_date','database_paid','approved_reserved','balance_after','evidence','issues'])
    report['mapping_proposal_count']=len(mapping_proposals)
    report['mapping_proposal_amount']=str(sum((money(p['source']['amount']) for p in mapping_proposals),Decimal(0)))
    dump(OUT/'report/剩余匹配深入核查.json',report)
    dump(OUT/'plan/格式归一增补候选_待批准.json',dict(approved=False,count=len(corrected),amount=report['formatting_correction_amount'],rows=corrected))
    csv_out(OUT/'report/剩余匹配深入核查.csv',[
        dict(sheet=c['source']['sheet'],line=c['source']['line'],project=c['source']['project'],payee=c['source']['payee'],
             bill_no=c['source']['bill_no'],E=c['source']['E'],amount=c['source']['amount'],pay_date=c['source']['pay_date'],
             issues=c['remaining_issues'],current_notice=c['current_notice'],candidates=c['matching_candidates'],
             plausible_candidates=c['chronology_and_preflight_candidates'],split=c['source_split_evidence']) for c in cases],
        ['sheet','line','project','payee','bill_no','E','amount','pay_date','issues','current_notice','candidates','plausible_candidates','split'])
    assert len(cases)==169
    assert all(hashlib.sha256((OUT/k).read_bytes()).hexdigest()==v for k,v in hashes.items())
    print(json.dumps({k:v for k,v in report.items() if k!='rows'},ensure_ascii=False))


if __name__=='__main__':
    main()
