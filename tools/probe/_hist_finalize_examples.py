"""Freeze explicitly approved examples; no database access, no implicit approvals."""
from collections import defaultdict
from decimal import Decimal
import hashlib
import json

from _hist_extract import BILL, OUT, csv_out, dump, money
from _hist_match import PayRow, PayDraft, confirm_batch, normalize


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    decisions=json.loads((OUT/'plan/样例用户裁定.json').read_text(encoding='utf-8'))
    base_files=[OUT/'plan/拟写入清单.json',OUT/'plan/增补冻结清单.json']
    protected={str(p.relative_to(OUT)):sha(p) for p in base_files}
    existing=[]
    for p in base_files:
        existing.extend(json.loads(p.read_text(encoding='utf-8'))['rows'])
    snapshot=json.loads((OUT/'match/剩余匹配只读快照.json').read_text(encoding='utf-8'))
    report=json.loads((OUT/'report/剩余匹配深入核查.json').read_text(encoding='utf-8'))
    by_source={(c['source']['sheet'],c['source']['line']):c for c in report['rows']}
    by_bill=defaultdict(list)
    for n in snapshot['notices']:
        by_bill[n['bill_no']].append(n)
    linked={l['notice_id'] for l in snapshot['links']}
    paid=defaultdict(lambda:Decimal(0))
    seen=set()
    for f in snapshot['flows']:
        if f['status']=='effective':
            paid[f['notice_id']]+=money(f['amount'])
            seen.add((f['notice_id'],str(f['pay_date']),money(f['amount'])))
    for r in existing:
        paid[r['notice_id']]+=money(r['amount'])
        seen.add((r['notice_id'],r['pay_date'],money(r['amount'])))
    assert len(existing)==238
    newly_approved=[]
    consumed=set()
    for approval in decisions['payment_approvals']:
        refs=[(r['sheet'],r['line']) for r in approval['sources']]
        sources=[by_source[k]['source'] for k in refs]
        assert len(by_bill[approval['bill_no']])==1
        n=by_bill[approval['bill_no']][0]
        amount=money(approval['amount'])
        assert sum((money(r['amount']) for r in sources),Decimal(0))==amount
        assert all(r['pay_date']==approval['pay_date'] and r['pay_method']==approval['pay_method'] for r in sources)
        assert sum((money(r['E']) for r in sources),Decimal(0))==money(n['amount_approved'])
        assert not n['excluded'] and not n['i8_revoked'] and not n['revoked_joint']
        fingerprint=n['id'],approval['pay_date'],amount
        assert fingerprint not in seen
        checked=confirm_batch([PayRow(n['id'],n['approve_status'],money(n['amount_approved'])-paid[n['id']],n['category'],n['id'] in linked)],
                              {n['id']:PayDraft(approval['pay_method'],amount)},pay_date=approval['pay_date'],remark='用户已确认来源与付款事件')
        assert not checked.errors, checked.errors
        row=dict(seq=len(existing)+len(newly_approved)+1,sheet=sources[0]['sheet'],line=sources[0]['line'],
                 bill_no=n['bill_no'],notice_id=n['id'],pay_date=approval['pay_date'],amount=str(amount),
                 pay_method=approval['pay_method'],remark='来源：'+','.join(f"{r['sheet']}!{r['line']}「{r['annotation']}」" for r in sources)+'；用户确认对应与付款事件',
                 flags=dict(blank_method=False,overpay_approved=False,no_bill_no=any(not BILL.match(r['bill_no']) for r in sources)),
                 依据=dict(source_refs=approval['sources'],source_rows=sources,approval=approval,
                           notice_summary={k:n.get(k) for k in ('id','bill_no','project_name','payee','jc_supplier','amount_approved','doc_date')},
                           amount_basis='用户确认一笔合付，源分项相加' if len(sources)>1 else '用户确认原拟用金额与对应',
                           preflight_errors=checked.errors,paid_before=str(paid[n['id']]),paid_after=str(paid[n['id']]+amount)))
        newly_approved.append(row)
        consumed.update(refs)
        seen.add(fingerprint)
        paid[n['id']]+=amount
    assert len(consumed)==sum(len(a['sources']) for a in decisions['payment_approvals'])
    freeze_path=OUT/'plan/样例确认冻结清单.json'
    frozen=dict(schema='hist-supplement/1',batch='IMP-HIST-20261011',approved=True,approval_date=decisions['date'],
                source_approved_plans=protected,exceptions=[],rows=newly_approved)
    dump(freeze_path,frozen)
    total=sum((money(r['amount']) for r in existing+newly_approved),Decimal(0))
    dump(OUT/'plan/样例批准回执.json',dict(approved=True,decision_ref='样例用户裁定.json',decision_sha256=sha(OUT/'plan/样例用户裁定.json'),
        frozen_sha256=sha(freeze_path),new_event_count=len(newly_approved),source_row_count=len(consumed),
        new_amount=str(sum((money(r['amount']) for r in newly_approved),Decimal(0))),cumulative_count=len(existing)+len(newly_approved),cumulative_amount=str(total),
        scope='仅冻结批准的付款事件；全程零写库'))
    remaining=[c for c in report['rows'] if (c['source']['sheet'],c['source']['line']) not in consumed]
    equivalence=decisions['receiver_equivalence']
    alias_key=(equivalence['source']['sheet'],equivalence['source']['line'])
    alias_case=by_source[alias_key]
    names=set(equivalence['names'])
    assert alias_case['source']['payee'] in names and alias_case['current_notice']['payee'] in names
    alias_case['remaining_issues']=[i for i in alias_case['remaining_issues'] if i!='收款单位/已维护集采供应商不一致']
    alias_case['receiver_equivalence_evidence']=equivalence
    alias_case['requires_user_mapping_confirmation']=False
    alias_case['identity_resolved']=True
    alias_case['payment_approved']=False
    corrections=json.loads((OUT/'plan/格式归一增补候选_待批准.json').read_text(encoding='utf-8'))['rows']
    if not alias_case['remaining_issues'] and not alias_case['current_notice']['preflight_errors']:
        alias_row=dict(alias_case['source'],issues=[],receiver_correction_basis=equivalence,
                       remaining_cap=alias_case['current_notice']['remaining_cap'],payment_approved=False)
        corrections.append(alias_row)
    dump(OUT/'plan/格式与单位归一增补候选_待批准.json',dict(approved=False,count=len(corrections),
         amount=str(sum((money(r['amount']) for r in corrections),Decimal(0))),rows=corrections))
    old_proposals=json.loads((OUT/'plan/唯一线索拟对应_待确认.json').read_text(encoding='utf-8'))['rows']
    proposals=[p for p in old_proposals if (p['source']['sheet'],p['source']['line']) not in consumed]
    dump(OUT/'plan/待确认对应更新.json',dict(approved=False,count=len(proposals),amount=str(sum((money(p['source']['amount']) for p in proposals),Decimal(0))),rows=proposals))
    pending_view=[]
    for p in proposals:
        r=p['source']; c=p['candidate']
        pending_view.append(dict(source=r,candidate_bill=c['bill_no'],notice_id=c['notice_id'],notice_title=c['bill_title'],
                                 notice_payee=c['payee'],jc_supplier=c['jc_supplier'],approval=c['approval_amount'],
                                 confirmation_needed='费用日缺失/不同；对应及付款信息须确认'))
    for r in corrections:
        n=by_bill[r['matched_bill_no']][0]
        pending_view.append(dict(source=r,candidate_bill=n['bill_no'],notice_id=n['id'],notice_title=n['fields'].get('BillName',''),
                                 notice_payee=n['payee'],jc_supplier=n.get('jc_supplier',''),approval=str(n['amount_approved']),
                                 confirmation_needed='单位身份已补齐；付款日期/金额尚待批准'))
    pending_paid=defaultdict(lambda:Decimal(0),paid)
    for i,p in enumerate(pending_view,1):
        r=p['source']; nid=p['notice_id']; n=by_bill[p['candidate_bill']][0]
        fingerprint=nid,r['pay_date'],money(r['amount'])
        assert fingerprint not in seen
        seen.add(fingerprint)
        cap=money(n['amount_approved'])-pending_paid[nid]
        p['preflight_errors']=confirm_batch([PayRow(nid,n['approve_status'],cap,n['category'],nid in linked)],
                            {nid:PayDraft(r['pay_method'],money(r['amount']))},pay_date=r['pay_date'],remark=r['remark']).errors
        assert not p['preflight_errors'] and not n['excluded'] and not n['i8_revoked'] and not n['revoked_joint']
        p['review_seq']=i
        pending_paid[nid]+=money(r['amount'])
        p['balance_after']=str(money(n['amount_approved'])-pending_paid[nid])
        p['approved']=False
    dump(OUT/'plan/下一批28笔候选_待批准.json',dict(approved=False,count=len(pending_view),
         amount=str(sum((money(p['source']['amount']) for p in pending_view),Decimal(0))),rows=pending_view))
    def cell(v):
        return str(v).replace('|','／').replace('\n',' ')
    lines=['# 下一批候选完整审阅 · 尚未批准','',
           f"{len(pending_view)}笔，{sum((money(p['source']['amount']) for p in pending_view),Decimal(0))}元。已批准242笔不变。",
           '前25笔为拟对应，费用日期缺失或与单据日期不同；后3笔为单位身份已解除疑点，付款本身仍待批准。金额取批注明示金额优先，否则G拟用金额；不用F。',
           '准入、防重、含已批准242笔的累计额度已核验；批准仅针对清单，仍不写库。','',
           '|候选序号|Excel来源|项目|源收款|通知书|库内收款／集采供应商|源流程＝审批|拟付款|付款日|方式|依据|拟补后余额|',
           '|---|---|---|---|---|---|---:|---:|---|---|---|---:|']
    for p in pending_view:
        r=p['source']
        values=[p['review_seq'],f"{r['sheet']}!{r['line']}",r['project'],r['payee'],p['candidate_bill'],
                p['notice_payee']+'／'+p['jc_supplier'],p['approval'],r['amount'],r['pay_date'],r['pay_method'],
                r['amount_evidence_strength'],p['balance_after']]
        lines.append('|'+ '|'.join(cell(v) for v in values)+'|')
    (OUT/'report/下一批候选完整审阅.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    dump(OUT/'report/剩余问题更新.json',dict(original_source_count=len(report['rows']),approved_source_rows=len(consumed),
         new_approved_events=len(newly_approved),remaining_source_rows=len(remaining),remaining_mapping_proposals=len(proposals),
         identity_resolved_pending_payment=len(corrections),receiver_equivalence=equivalence,rows=remaining))
    csv_out(OUT/'report/剩余问题更新.csv',[dict(sheet=c['source']['sheet'],line=c['source']['line'],project=c['source']['project'],
        payee=c['source']['payee'],bill_no=c['source']['bill_no'],amount=c['source']['amount'],pay_date=c['source']['pay_date'],
        issues=c['remaining_issues'],candidate=c['current_notice'],mapping_candidates=c['matching_candidates']) for c in remaining],
        ['sheet','line','project','payee','bill_no','amount','pay_date','issues','candidate','mapping_candidates'])
    dump(OUT/'plan/已批准清单总览.json',dict(count=len(existing)+len(newly_approved),amount=str(total),zero_database_writes=True,
         files=[dict(path=str(p.relative_to(OUT)),sha256=sha(p)) for p in base_files+[freeze_path]]))
    assert all(sha(OUT/path)==digest for path,digest in protected.items())
    print(json.dumps(dict(new_approved_events=len(newly_approved),new_approved_amount=str(sum((money(r['amount']) for r in newly_approved),Decimal(0))),
         count=len(existing)+len(newly_approved),amount=str(total),remaining_source_rows=len(remaining),remaining_mapping_proposals=len(proposals),
         new_payment_candidates=len(corrections),frozen_sha256=sha(freeze_path)),ensure_ascii=False))


if __name__=='__main__':
    main()
