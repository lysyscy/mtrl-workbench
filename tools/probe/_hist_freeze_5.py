"""Freeze explicitly approved five bill/amount/chronology events, offline."""
from collections import Counter, defaultdict
from decimal import Decimal
import json

from _hist_extract import OUT, BILL, dump, csv_out, money
from _hist_match import PayRow, PayDraft, confirm_batch
from _hist_freeze_13 import sha


def main():
    candidate_path=OUT/'plan/单号金额时序5笔候选_待批准.json'
    candidate=json.loads(candidate_path.read_text(encoding='utf-8'))
    protected=candidate['protected_approved_plans']
    existing=[r for p in protected for r in json.loads((OUT/p).read_text(encoding='utf-8'))['rows']]
    assert len(existing)==283 and all(sha(OUT/p)==digest for p,digest in protected.items())
    original=json.loads((OUT/'plan/拟写入清单.json').read_text(encoding='utf-8'))
    snapshot=json.loads((OUT/'match/剩余匹配只读快照.json').read_text(encoding='utf-8'))
    notices={n['id']:n for n in snapshot['notices']}
    assert len(notices)==1146
    linked={l['notice_id'] for l in snapshot['links']}
    paid=defaultdict(lambda:Decimal(0)); seen=set()
    for f in snapshot['flows']:
        if f['status']=='effective':
            paid[f['notice_id']]+=money(f['amount'])
            seen.add((f['notice_id'],str(f['pay_date']),money(f['amount'])))
    for r in existing:
        paid[r['notice_id']]+=money(r['amount'])
        seen.add((r['notice_id'],r['pay_date'],money(r['amount'])))
    rows=[]; consumed=set()
    for p in candidate['rows']:
        s=p['source']; n=notices[p['notice_id']]; amount=money(p['amount'])
        assert s['bill_no']==n['bill_no']==p['bill_no'] and amount==money(n['amount_approved'])
        assert str(n['doc_date'])<=p['pay_date'] and not any(n[k] for k in ('excluded','i8_revoked','revoked_joint'))
        fingerprint=n['id'],p['pay_date'],amount
        assert fingerprint not in seen
        remark=s['remark']+'；用户批准单号金额时序5笔，源单位/流程差异原文保留'
        if p['date_proposed']:
            remark+='；用户批准跨月批注7.3付取2026年7月3日'
        checked=confirm_batch([PayRow(n['id'],n['approve_status'],money(n['amount_approved'])-paid[n['id']],n['category'],n['id'] in linked)],
                              {n['id']:PayDraft(p['pay_method'],amount)},pay_date=p['pay_date'],remark=remark)
        assert not checked.errors
        rows.append(dict(seq=284+len(rows),sheet=s['sheet'],line=s['line'],bill_no=n['bill_no'],notice_id=n['id'],
            pay_date=p['pay_date'],amount=str(amount),pay_method=p['pay_method'],remark=remark,
            date_basis='用户批准6月表跨月批注7.3付取2026-07-03' if p['date_proposed'] else s['date_basis'],
            amount_basis=s['amount_basis'],flags=dict(blank_method=False,overpay_approved=False,no_bill_no=not bool(BILL.match(s['bill_no']))),
            依据=dict(source_refs=[dict(sheet=s['sheet'],line=s['line'])],proposal=p,user_quote='批准',
                      approval_scope='单号金额时序5笔及跨月日期取法',candidate_sha256=sha(candidate_path),
                      paid_before=str(paid[n['id']]),paid_after=str(paid[n['id']]+amount),preflight_errors=checked.errors)))
        paid[n['id']]+=amount; seen.add(fingerprint); consumed.add((s['sheet'],s['line']))
    assert len(rows)==len(consumed)==5
    total=sum((money(r['amount']) for r in existing+rows),Decimal(0))
    assert total==Decimal('18501587.75')
    frozen=OUT/'plan/单号金额时序5笔冻结清单.json'
    dump(frozen,dict(schema='hist-supplement/1',batch=original['batch'],generated_at='2026-10-11T02:55:35+08:00',
        source_file=original['source_file'],source_sha256=original['source_sha256'],excluded_ref=original['excluded_ref'],
        pending_ref=original['pending_ref'],approved=True,approval_date='2026-10-11',user_quote='批准',
        source_approved_plans=protected,candidate_sha256=sha(candidate_path),exceptions=[],rows=rows))
    dump(OUT/'plan/单号金额时序5笔批准回执.json',dict(approved=True,quote='批准',scope='5笔及跨月日期取法，仅批准清单，零写库',
         count=5,amount='156325.16',candidate_sha256=sha(candidate_path),frozen_sha256=sha(frozen),
         cumulative_count=288,cumulative_amount=str(total),evidence_snapshot_sha256=sha(OUT/'match/剩余匹配只读快照.json')))
    dump(OUT/'plan/已批准清单总览.json',dict(count=288,amount=str(total),zero_database_writes=True,
         files=[dict(path=p,sha256=digest) for p,digest in protected.items()]+[dict(path=str(frozen.relative_to(OUT)),sha256=sha(frozen))]))
    report=json.loads((OUT/'report/剩余123行核查.json').read_text(encoding='utf-8'))
    remaining=[c for c in report['rows'] if (c['source']['sheet'],c['source']['line']) not in consumed]
    assert len(remaining)==118
    dump(OUT/'report/剩余118行核查.json',dict(remaining_source_rows=118,approved_count=288,approved_amount=str(total),
         issue_counts_nonexclusive=dict(Counter(i for c in remaining for i in c['remaining_issues'])),rows=remaining))
    csv_out(OUT/'report/剩余118行核查.csv',[dict(sheet=c['source']['sheet'],line=c['source']['line'],
        project=c['source']['project'],payee=c['source']['payee'],bill_no=c['source']['bill_no'],amount=c['source']['amount'],
        pay_date=c['source']['pay_date'],issues=c['remaining_issues']) for c in remaining],
        ['sheet','line','project','payee','bill_no','amount','pay_date','issues'])
    assert all(sha(OUT/p)==digest for p,digest in protected.items())
    print(json.dumps(dict(count=288,amount=str(total),remaining=118,sha256=sha(frozen)),ensure_ascii=False))


if __name__=='__main__':
    main()
