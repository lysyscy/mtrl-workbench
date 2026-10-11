"""Record the explicit 28-row approval using archived evidence; never access DB."""
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json

from _hist_extract import OUT, BILL, dump, csv_out, money
from _hist_match import PayRow, PayDraft, confirm_batch


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base = [OUT / ('plan/' + name) for name in
            ('拟写入清单.json', '增补冻结清单.json', '样例确认冻结清单.json')]
    protected = {str(p.relative_to(OUT)): sha(p) for p in base}
    original = json.loads(base[0].read_text(encoding='utf-8'))
    existing = [r for p in base for r in json.loads(p.read_text(encoding='utf-8'))['rows']]
    assert len(existing) == 242
    candidate_path = OUT / 'plan/下一批28笔候选_待批准.json'
    candidate = json.loads(candidate_path.read_text(encoding='utf-8'))
    assert candidate['count'] == 28 and money(candidate['amount']) == Decimal('2359954.58')
    snapshot = json.loads((OUT / 'match/剩余匹配只读快照.json').read_text(encoding='utf-8'))
    notices = {n['id']: n for n in snapshot['notices']}
    assert len(notices) == 1146
    linked = {r['notice_id'] for r in snapshot['links']}
    paid = defaultdict(lambda: Decimal(0))
    seen = set()
    for flow in snapshot['flows']:
        if flow['status'] == 'effective':
            paid[flow['notice_id']] += money(flow['amount'])
            seen.add((flow['notice_id'], str(flow['pay_date']), money(flow['amount'])))
    for row in existing:
        paid[row['notice_id']] += money(row['amount'])
        seen.add((row['notice_id'], row['pay_date'], money(row['amount'])))
    rows, consumed = [], set()
    quote = '确认全部28笔对应及付款信息'
    for proposal in candidate['rows']:
        source = proposal['source']
        notice = notices[proposal['notice_id']]
        amount = money(source['amount'])
        assert notice['bill_no'] == proposal['candidate_bill']
        assert money(source['E']) == money(notice['amount_approved'])
        assert not notice['excluded'] and not notice['i8_revoked'] and not notice['revoked_joint']
        fingerprint = notice['id'], source['pay_date'], amount
        assert fingerprint not in seen
        cap = money(notice['amount_approved']) - paid[notice['id']]
        checked = confirm_batch([PayRow(notice['id'], notice['approve_status'], cap,
                                notice['category'], notice['id'] in linked)],
                                {notice['id']: PayDraft(source['pay_method'], amount)},
                                pay_date=source['pay_date'], remark=source['remark'])
        assert not checked.errors, checked.errors
        rows.append(dict(seq=243+len(rows), sheet=source['sheet'], line=source['line'],
                         bill_no=notice['bill_no'], notice_id=notice['id'], pay_date=source['pay_date'],
                         amount=str(amount), pay_method=source['pay_method'], remark=source['remark'],
                         date_basis=source['date_basis'], amount_basis=source['amount_basis'],
                         flags=dict(blank_method=False, overpay_approved=False,
                                    no_bill_no=not bool(BILL.match(source['bill_no']))),
                         依据=dict(source_refs=[dict(sheet=source['sheet'], line=source['line'])],
                                  proposal=proposal, user_quote=quote, candidate_sha256=sha(candidate_path),
                                  paid_before=str(paid[notice['id']]), paid_after=str(paid[notice['id']]+amount),
                                  preflight_errors=checked.errors)))
        consumed.add((source['sheet'], source['line']))
        paid[notice['id']] += amount
        seen.add(fingerprint)
    assert len(consumed) == len(rows) == 28
    frozen = OUT / 'plan/28笔追加冻结清单.json'
    dump(frozen, dict(schema='hist-supplement/1', batch='IMP-HIST-20261011', approved=True,
                     generated_at='2026-10-11T02:39:29+08:00',
                     source_file=original['source_file'], source_sha256=original['source_sha256'],
                     excluded_ref=original['excluded_ref'], pending_ref=original['pending_ref'],
                     approval_date='2026-10-11', source_approved_plans=protected,
                     candidate_sha256=sha(candidate_path), user_quote=quote, exceptions=[], rows=rows))
    total = sum((money(r['amount']) for r in existing+rows), Decimal(0))
    assert total == Decimal('17877670.86')
    dump(OUT / 'plan/28笔追加批准回执.json', dict(approved=True, quote=quote,
         candidate_path=str(candidate_path.relative_to(OUT)), candidate_sha256=sha(candidate_path),
         frozen_path=str(frozen.relative_to(OUT)), frozen_sha256=sha(frozen),
         count=28, amount='2359954.58', cumulative_count=270, cumulative_amount=str(total),
         scope='仅批准清单；零写库', evidence_snapshot_sha256=sha(OUT / 'match/剩余匹配只读快照.json')))
    dump(OUT / 'plan/已批准清单总览.json', dict(count=270, amount=str(total), zero_database_writes=True,
         files=[dict(path=str(p.relative_to(OUT)), sha256=sha(p)) for p in base+[frozen]]))
    old = json.loads((OUT / 'report/剩余问题更新.json').read_text(encoding='utf-8'))
    remaining = [c for c in old['rows'] if (c['source']['sheet'], c['source']['line']) not in consumed]
    assert len(old['rows']) == 164 and len(remaining) == 136
    counts = Counter(i for c in remaining for i in c['remaining_issues'])
    dump(OUT / 'report/剩余136行核查.json', dict(remaining_source_rows=136,
         issue_counts_nonexclusive=dict(counts), approved_count=270, approved_amount=str(total), rows=remaining))
    csv_out(OUT / 'report/剩余136行核查.csv', [dict(sheet=c['source']['sheet'], line=c['source']['line'],
        project=c['source']['project'], payee=c['source']['payee'], bill_no=c['source']['bill_no'],
        amount=c['source']['amount'], pay_date=c['source']['pay_date'], issues=c['remaining_issues']) for c in remaining],
        ['sheet','line','project','payee','bill_no','amount','pay_date','issues'])
    assert all(sha(OUT/path) == digest for path, digest in protected.items())
    print(json.dumps(dict(count=270, amount=str(total), remaining=136, frozen_sha256=sha(frozen),
                         issues=dict(counts)), ensure_ascii=False))


if __name__ == '__main__':
    main()
