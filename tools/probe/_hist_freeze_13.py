"""Freeze the explicitly approved 13 events from archived inputs; no DB access."""
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json

from _hist_extract import OUT, BILL, dump, csv_out, money
from _hist_match import PayRow, PayDraft, confirm_batch


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    candidate_path=OUT/'plan/综合名称核验13笔候选_待批准.json'
    candidate=json.loads(candidate_path.read_text(encoding='utf-8'))
    protected=candidate['protected_approved_plans']
    original=json.loads((OUT/'plan/拟写入清单.json').read_text(encoding='utf-8'))
    existing=[]
    for path,digest in protected.items():
        assert sha(OUT/path)==digest
        existing.extend(json.loads((OUT/path).read_text(encoding='utf-8'))['rows'])
    assert len(existing)==270
    snapshot=json.loads((OUT/'match/剩余匹配只读快照.json').read_text(encoding='utf-8'))
    notices={n['id']:n for n in snapshot['notices']}
    assert len(notices)==1146
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
    rows,consumed=[],set()
    for proposal in candidate['rows']:
        s=proposal['source']; n=notices[proposal['notice_id']]
        amount=money(proposal['amount'])
        assert n['bill_no']==proposal['bill_no'] and money(s['E'])==money(n['amount_approved'])
        assert not any(n[k] for k in ('excluded','i8_revoked','revoked_joint'))
        fingerprint=n['id'],proposal['pay_date'],amount
        assert fingerprint not in seen
        cap=money(n['amount_approved'])-paid[n['id']]
        remark=s['remark']+'；用户批准综合名称核验13笔及日期/方式取法'
        if proposal['method_conflict']:
            remark+='；付款批注现汇优先，原计划现金保留'
        if (s['sheet'],s['line'])==('3月份',97):
            remark+='；用户允许择日用I列3月10日，L列3月11日原文保留'
        checked=confirm_batch([PayRow(n['id'],n['approve_status'],cap,n['category'],n['id'] in linked)],
                              {n['id']:PayDraft(proposal['pay_method'],amount)},
                              pay_date=proposal['pay_date'],remark=remark)
        assert not checked.errors
        rows.append(dict(seq=271+len(rows),sheet=s['sheet'],line=s['line'],bill_no=n['bill_no'],
            notice_id=n['id'],pay_date=proposal['pay_date'],amount=str(amount),pay_method=proposal['pay_method'],
            remark=remark,date_basis=proposal['date_basis'],amount_basis=s['amount_basis'],
            flags=dict(blank_method=False,overpay_approved=False,no_bill_no=not bool(BILL.match(s['bill_no']))),
            依据=dict(source_refs=[dict(sheet=s['sheet'],line=s['line'])],proposal=proposal,
                      candidate_sha256=sha(candidate_path),user_quote='批准',
                      approval_scope='13笔及已展示日期/方式取法',preflight_errors=checked.errors,
                      paid_before=str(paid[n['id']]),paid_after=str(paid[n['id']]+amount))))
        consumed.add((s['sheet'],s['line']))
        paid[n['id']]+=amount
        seen.add(fingerprint)
    assert len(rows)==len(consumed)==13
    amount=sum((money(r['amount']) for r in rows),Decimal(0))
    total=sum((money(r['amount']) for r in existing+rows),Decimal(0))
    assert amount==Decimal('467591.73') and total==Decimal('18345262.59')
    frozen=OUT/'plan/综合名称核验13笔冻结清单.json'
    dump(frozen,dict(schema='hist-supplement/1',batch=original['batch'],generated_at='2026-10-11T02:48:38+08:00',
        source_file=original['source_file'],source_sha256=original['source_sha256'],
        excluded_ref=original['excluded_ref'],pending_ref=original['pending_ref'],approved=True,
        approval_date='2026-10-11',user_quote='批准',source_approved_plans=protected,
        candidate_sha256=sha(candidate_path),exceptions=[],rows=rows))
    dump(OUT/'plan/综合名称核验13笔批准回执.json',dict(approved=True,quote='批准',scope='13笔及日期/方式取法，仅批准清单，零写库',
         count=13,amount=str(amount),candidate_sha256=sha(candidate_path),frozen_sha256=sha(frozen),
         cumulative_count=283,cumulative_amount=str(total),evidence_snapshot_sha256=sha(OUT/'match/剩余匹配只读快照.json')))
    dump(OUT/'plan/已批准清单总览.json',dict(count=283,amount=str(total),zero_database_writes=True,
        files=[dict(path=p,sha256=digest) for p,digest in protected.items()]+[dict(path=str(frozen.relative_to(OUT)),sha256=sha(frozen))]))
    report=json.loads((OUT/'report/供应商参考口径后剩余核查.json').read_text(encoding='utf-8'))
    remaining=[c for c in report['rows'] if (c['source']['sheet'],c['source']['line']) not in consumed]
    assert len(report['rows'])==136 and len(remaining)==123
    counts=dict(Counter(i for c in remaining for i in c['remaining_issues']))
    dump(OUT/'report/剩余123行核查.json',dict(remaining_source_rows=123,approved_count=283,approved_amount=str(total),
         issue_counts_nonexclusive=counts,rows=remaining))
    csv_out(OUT/'report/剩余123行核查.csv',[dict(sheet=c['source']['sheet'],line=c['source']['line'],
        project=c['source']['project'],payee=c['source']['payee'],bill_no=c['source']['bill_no'],
        amount=c['source']['amount'],pay_date=c['source']['pay_date'],issues=c['remaining_issues']) for c in remaining],
        ['sheet','line','project','payee','bill_no','amount','pay_date','issues'])
    assert all(sha(OUT/p)==digest for p,digest in protected.items())
    print(json.dumps(dict(count=283,amount=str(total),remaining_source_rows=123,sha256=sha(frozen)),ensure_ascii=False))


if __name__=='__main__':
    main()
