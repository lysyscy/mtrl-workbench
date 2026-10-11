"""Apply the user's project scope to pending evidence only; no database access."""
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json

from _hist_extract import OUT, dump, money
from _hist_match import PayRow, PayDraft, confirm_batch


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    decision_path = OUT/'plan/三峡项目范围用户裁定.json'
    decision = json.loads(decision_path.read_text(encoding='utf-8'))
    overview = json.loads((OUT/'plan/核验基线_270笔.json').read_text(encoding='utf-8'))
    assert overview['count'] == 270
    protected = {f['path']: f['sha256'] for f in overview['files']}
    assert all(sha(OUT/p) == digest for p, digest in protected.items())
    snapshot = json.loads((OUT/'match/剩余匹配只读快照.json').read_text(encoding='utf-8'))
    notices = {n['id']: n for n in snapshot['notices']}
    linked = {l['notice_id'] for l in snapshot['links']}
    paid = defaultdict(lambda: Decimal(0))
    seen = set()
    for f in snapshot['flows']:
        if f['status'] == 'effective':
            paid[f['notice_id']] += money(f['amount'])
            seen.add((f['notice_id'], str(f['pay_date']), money(f['amount'])))
    for entry in overview['files']:
        for r in json.loads((OUT/entry['path']).read_text(encoding='utf-8'))['rows']:
            paid[r['notice_id']] += money(r['amount'])
            seen.add((r['notice_id'], r['pay_date'], money(r['amount'])))
    report = json.loads((OUT/'report/剩余136行核查.json').read_text(encoding='utf-8'))
    resolved, candidates = [], []
    project_issue = '项目不一致，疑似错号/区块归属问题'
    for case in report['rows']:
        s, n = case['source'], case['current_notice']
        if not n or s['project'] != decision['source_project'] or n['project'] != decision['notice_project']:
            continue
        assert project_issue in case['remaining_issues']
        case['remaining_issues'].remove(project_issue)
        case['project_scope_evidence'] = dict(decision=decision, sha256=sha(decision_path))
        resolved.append(case)
        notice = notices[n['notice_id']]
        if any('未批/撤单/剔除' in i or '付款日未确证' in i or '源流程金额' in i for i in case['remaining_issues']):
            continue
        assert money(s['E']) == money(notice['amount_approved'])
        assert not notice['excluded'] and not notice['i8_revoked'] and not notice['revoked_joint']
        cap = money(notice['amount_approved']) - paid[notice['id']]
        fingerprint = notice['id'], s['pay_date'], money(s['amount'])
        assert fingerprint not in seen
        checked = confirm_batch([PayRow(notice['id'], notice['approve_status'], cap, notice['category'], notice['id'] in linked)],
                                {notice['id']: PayDraft(s['pay_method'], money(s['amount']))},
                                pay_date=s['pay_date'], remark=s['remark'])
        assert not checked.errors
        candidates.append(dict(review_seq=len(candidates)+1, source=s, notice=n, approved=False,
            project_evidence=case['project_scope_evidence'], remaining_issues=case['remaining_issues'],
            preflight_errors=checked.errors, balance_after=str(cap-money(s['amount'])),
            method_conflict=('现汇' in s['annotation'] and s['raw'].get('J') == '现金')))
    assert len(resolved) == 12 and len(candidates) == 8
    assert len(report['rows']) == 136
    report['issue_counts_nonexclusive'] = dict(Counter(i for c in report['rows'] for i in c['remaining_issues']))
    report['project_resolved_source_rows'] = len(resolved)
    report['new_payment_approvals'] = 0
    dump(OUT/'report/三峡范围确认后剩余核查.json', report)
    amount = sum((money(c['source']['amount']) for c in candidates), Decimal(0))
    dump(OUT/'plan/三峡项目8笔候选_待批准.json', dict(approved=False, count=8, amount=str(amount),
         decision_sha256=sha(decision_path), protected_approved_plans=protected, rows=candidates))
    lines = ['# 三峡范围确认后的付款核查', '',
        '用户已确认“三峡包括乌兰察布 鄂旗 离网制氢”。解除12行项目差异；原13行项目差异中另1行为宜化单号误指新疆普康，仍保留项目问题。',
        f'8笔金额及准入可继续审阅，合计{amount}元，尚未批准；原270笔冻结不变。其余4行：2行撤单/剔除、1行流程52369.03与审批16863.38不等、1行付款日期未确认。', '',
        '|序号|来源|编号|源收款|库内收款／供应商|流程＝审批|拟付|批注／付款日|原方式／拟方式|补后余额|仍需确认|',
        '|---|---|---|---|---|---:|---:|---|---|---:|---|']
    for c in candidates:
        s, n = c['source'], c['notice']
        vals = [c['review_seq'], f"{s['sheet']}!{s['line']}", n['bill_no'], s['payee'],
                n['payee']+'／'+n['jc_supplier'], s['E'], s['amount'], s['annotation']+'／'+s['pay_date'],
                s['raw'].get('J','')+'／'+s['pay_method'], c['balance_after'],
                '；'.join(c['remaining_issues']+(['批注现汇与J现金冲突，实际方式待确认'] if c['method_conflict'] else [])+['付款事件待批准'])]
        lines.append('|'+ '|'.join(str(v).replace('|','／').replace('\n',' ') for v in vals)+'|')
    (OUT/'report/三峡项目8笔完整审阅.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    assert all(sha(OUT/p) == digest for p, digest in protected.items())
    print(json.dumps(dict(project_resolved=12, remaining_source_rows=136, candidates=8,
                         candidate_amount=str(amount), new_approvals=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
