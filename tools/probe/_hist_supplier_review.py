"""Prepare bounded supplier/date proposals from user guidance; never write DB."""
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json

from _hist_extract import OUT, dump, money
from _hist_match import PayRow, PayDraft, confirm_batch


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    decision_path=OUT/'plan/供应商参考与日期用户裁定.json'
    decision=json.loads(decision_path.read_text(encoding='utf-8'))
    report=json.loads((OUT/'report/三峡范围确认后剩余核查.json').read_text(encoding='utf-8'))
    by_source={(c['source']['sheet'],c['source']['line']):c for c in report['rows']}
    candidates=json.loads((OUT/'plan/三峡项目8笔候选_待批准.json').read_text(encoding='utf-8'))['rows']
    keys=[(r['source']['sheet'],r['source']['line']) for r in candidates]
    keys += [('3月份',97),('2026年4月份',85),('2026年4月份',122),('2026年5月份',107),('2026年6月',139)]
    overview=json.loads((OUT/'plan/核验基线_270笔.json').read_text(encoding='utf-8'))
    assert overview['count']==270
    protected={r['path']:r['sha256'] for r in overview['files']}
    snapshot=json.loads((OUT/'match/剩余匹配只读快照.json').read_text(encoding='utf-8'))
    notices={n['id']:n for n in snapshot['notices']}
    paid=defaultdict(lambda:Decimal(0))
    seen=set()
    linked={l['notice_id'] for l in snapshot['links']}
    for f in snapshot['flows']:
        if f['status']=='effective':
            paid[f['notice_id']]+=money(f['amount'])
            seen.add((f['notice_id'],str(f['pay_date']),money(f['amount'])))
    for path,digest in protected.items():
        assert sha(OUT/path)==digest
        for r in json.loads((OUT/path).read_text(encoding='utf-8'))['rows']:
            paid[r['notice_id']]+=money(r['amount'])
            seen.add((r['notice_id'],r['pay_date'],money(r['amount'])))
    rows=[]
    for key in keys:
        case=by_source[key]
        source=case['source']
        n=notices[source['notice_id']]
        issues=[i for i in case['remaining_issues'] if i!='收款单位/已维护集采供应商不一致']
        assert not issues
        assert source['bill_no']==n['bill_no'] and money(source['E'])==money(n['amount_approved'])
        assert not any(n[k] for k in ('excluded','i8_revoked','revoked_joint'))
        pay_date=source['pay_date']
        method=source['pay_method']
        basis=source['date_basis']
        if key==('3月份',97):
            pay_date=decision['date_choice']['selected_pay_date']
            basis=decision['date_choice']['basis']
        conflict='现汇' in source['annotation'] and source['raw'].get('J')=='现金'
        if conflict:
            method='现汇'
        amount=money(source['amount'])
        cap=money(n['amount_approved'])-paid[n['id']]
        fingerprint=n['id'],pay_date,amount
        assert fingerprint not in seen
        checked=confirm_batch([PayRow(n['id'],n['approve_status'],cap,n['category'],n['id'] in linked)],
                              {n['id']:PayDraft(method,amount)},pay_date=pay_date,remark=source['remark'])
        assert not checked.errors
        paid[n['id']]+=amount
        seen.add(fingerprint)
        case['remaining_issues']=issues
        case['supplier_review_evidence']=dict(decision_sha256=sha(decision_path),quote=decision['quote'],
            basis='同号同项目同流程审批额，名称简称/同义或通知书标题相符；库内名称和源名称均保留')
        rows.append(dict(review_seq=len(rows)+1,approved=False,source=source,notice_id=n['id'],bill_no=n['bill_no'],
            notice_title=n['fields'].get('BillName',''),notice_payee=n['payee'],jc_supplier=n.get('jc_supplier',''),
            pay_date=pay_date,date_basis=basis,amount=str(amount),pay_method=method,method_conflict=conflict,
            supplier_evidence=case['supplier_review_evidence'],preflight_errors=checked.errors,
            paid_before=str(paid[n['id']]-amount),balance_after=str(cap-amount)))
    assert len(rows)==13
    amount=sum((money(r['amount']) for r in rows),Decimal(0))
    assert amount==Decimal('467591.73')
    dump(OUT/'plan/综合名称核验13笔候选_待批准.json',dict(approved=False,count=13,amount=str(amount),
         decisions=['三峡项目范围用户裁定.json','供应商参考与日期用户裁定.json'],protected_approved_plans=protected,rows=rows))
    report['payment_proposals_not_approved']=13
    report['new_payment_approvals']=0
    report['issue_counts_nonexclusive']=dict(Counter(i for c in report['rows'] for i in c['remaining_issues']))
    dump(OUT/'report/供应商参考口径后剩余核查.json',report)
    lines=['# 综合名称核验13笔完整审阅','',
        '13笔、467,591.73元，均尚待付款批准。项目范围与供应商参考口径已按用户裁定核验。已批准270笔冻结不变。',
        '3月97行按用户允许择日沿用I列3月10日，仍留L列3月11日。1月3笔付款批注写现汇、J写现金，本次提出采用批注现汇；4月4笔J写现金，方式编码仍为其他并保留现金原文。',
        '每笔编号和源流程额对审批相等；审批、撤单、剔除、集采关联、库内及批内防重、含270笔的累计额度通过。G为拟用金额，由本次逐笔审阅确认付款事实。','',
        '|序号|来源|项目|源收款|编号|库内收款／供应商|标题|流程＝审批|拟付|付款日|拟方式|原批注／原方式|补后余额|',
        '|---|---|---|---|---|---|---|---:|---:|---|---|---|---:|']
    for r in rows:
        s=r['source']
        vals=[r['review_seq'],f"{s['sheet']}!{s['line']}",s['project'],s['payee'],r['bill_no'],
              r['notice_payee']+'／'+r['jc_supplier'],r['notice_title'],s['E'],r['amount'],r['pay_date'],
              r['pay_method'],s['annotation']+'／'+s['raw'].get('J',''),r['balance_after']]
        lines.append('|'+ '|'.join(str(v).replace('|','／').replace('\n',' ') for v in vals)+'|')
    (OUT/'report/综合名称核验13笔完整审阅.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    assert all(sha(OUT/p)==digest for p,digest in protected.items())
    print(json.dumps(dict(candidates=13,amount=str(amount),approved_count=270,remaining_sources=136,
                         pending_payment_approval=13),ensure_ascii=False))


if __name__=='__main__':
    main()
