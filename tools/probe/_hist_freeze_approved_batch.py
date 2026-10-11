"""Freeze an explicitly authorized batch from archived inputs, never access DB."""
import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import json

from _hist_extract import OUT, BILL, dump, csv_out, money
from _hist_match import PayRow, PayDraft, confirm_batch
from _hist_freeze_13 import sha


def main(approval_name):
    decision=json.loads((OUT/approval_name).read_text(encoding='utf-8'))
    candidate_path=OUT/decision['candidate']
    candidate=json.loads(candidate_path.read_text(encoding='utf-8'))
    protected=candidate['protected_approved_plans']
    existing=[r for p in protected for r in json.loads((OUT/p).read_text(encoding='utf-8'))['rows']]
    assert len(existing)==decision['base_count'] and all(sha(OUT/p)==digest for p,digest in protected.items())
    original=json.loads((OUT/'plan/拟写入清单.json').read_text(encoding='utf-8'))
    snap=json.loads((OUT/'match/剩余匹配只读快照.json').read_text(encoding='utf-8'))
    ns={n['id']:n for n in snap['notices']}
    linked={l['notice_id'] for l in snap['links']}
    paid=defaultdict(lambda:Decimal(0)); seen=set()
    for f in snap['flows']:
        if f['status']=='effective':
            paid[f['notice_id']]+=money(f['amount']); seen.add((f['notice_id'],str(f['pay_date']),money(f['amount'])))
    for r in existing:
        paid[r['notice_id']]+=money(r['amount']); seen.add((r['notice_id'],r['pay_date'],money(r['amount'])))
    rows=[]; consumed=set()
    for p in candidate['rows']:
        s=p['source']; n=ns[p['notice_id']]; amount=money(p['amount'])
        assert n['bill_no']==p['bill_no'] and money(s['E'])==money(n['amount_approved'])
        assert not any(n[k] for k in ('excluded','i8_revoked','revoked_joint'))
        fingerprint=n['id'],p['pay_date'],amount
        assert fingerprint not in seen
        remark=s['remark']+'；用户确认无编号拟对应及付款信息'
        checked=confirm_batch([PayRow(n['id'],n['approve_status'],money(n['amount_approved'])-paid[n['id']],n['category'],n['id'] in linked)],
                              {n['id']:PayDraft(p['pay_method'],amount)},pay_date=p['pay_date'],remark=remark)
        assert not checked.errors
        rows.append(dict(seq=len(existing)+len(rows)+1,sheet=s['sheet'],line=s['line'],bill_no=n['bill_no'],notice_id=n['id'],
            pay_date=p['pay_date'],amount=str(amount),pay_method=p['pay_method'],remark=remark,
            date_basis=s['date_basis'],amount_basis=s['amount_basis'],
            flags=dict(blank_method=False,overpay_approved=False,no_bill_no=not bool(BILL.match(s['bill_no']))),
            依据=dict(source_refs=[dict(sheet=s['sheet'],line=s['line'])],proposal=p,user_quote=decision['quote'],
                      approval_scope=decision['scope'],candidate_sha256=sha(candidate_path),
                      paid_before=str(paid[n['id']]),paid_after=str(paid[n['id']]+amount),preflight_errors=checked.errors)))
        consumed.add((s['sheet'],s['line'])); paid[n['id']]+=amount; seen.add(fingerprint)
    assert len(rows)==len(consumed)==decision['new_count']
    assert sum((money(r['amount']) for r in rows),Decimal(0))==money(decision['new_amount'])
    total=sum((money(r['amount']) for r in existing+rows),Decimal(0))
    assert total==money(decision['total_amount'])
    frozen=OUT/decision['frozen']
    dump(frozen,dict(schema='hist-supplement/1',batch=original['batch'],generated_at=decision['generated_at'],
        source_file=original['source_file'],source_sha256=original['source_sha256'],excluded_ref=original['excluded_ref'],
        pending_ref=original['pending_ref'],approved=True,approval_date=decision['date'],user_quote=decision['quote'],
        source_approved_plans=protected,candidate_sha256=sha(candidate_path),exceptions=[],rows=rows))
    dump(OUT/decision['receipt'],dict(approved=True,quote=decision['quote'],scope=decision['scope'],
         count=len(rows),amount=decision['new_amount'],candidate_sha256=sha(candidate_path),frozen_sha256=sha(frozen),
         cumulative_count=len(existing)+len(rows),cumulative_amount=str(total)))
    dump(OUT/'plan/已批准清单总览.json',dict(count=len(existing)+len(rows),amount=str(total),zero_database_writes=True,
         files=[dict(path=p,sha256=digest) for p,digest in protected.items()]+[dict(path=str(frozen.relative_to(OUT)),sha256=sha(frozen))]))
    old=json.loads((OUT/decision['pending_input']).read_text(encoding='utf-8'))
    remaining=[c for c in old['rows'] if (c['source']['sheet'],c['source']['line']) not in consumed]
    assert len(remaining)==len(old['rows'])-len(rows)
    output=OUT/decision['pending_output']
    dump(output,dict(remaining_source_rows=len(remaining),approved_count=len(existing)+len(rows),approved_amount=str(total),
         issue_counts_nonexclusive=dict(Counter(i for c in remaining for i in c['remaining_issues'])),rows=remaining))
    csv_out(output.with_suffix('.csv'),[dict(sheet=c['source']['sheet'],line=c['source']['line'],project=c['source']['project'],
        payee=c['source']['payee'],bill_no=c['source']['bill_no'],amount=c['source']['amount'],pay_date=c['source']['pay_date'],
        issues=c['remaining_issues']) for c in remaining],['sheet','line','project','payee','bill_no','amount','pay_date','issues'])
    assert all(sha(OUT/p)==digest for p,digest in protected.items())
    print(json.dumps(dict(count=len(existing)+len(rows),amount=str(total),remaining=len(remaining),sha256=sha(frozen)),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--approval',required=True)
    main(parser.parse_args().approval)
