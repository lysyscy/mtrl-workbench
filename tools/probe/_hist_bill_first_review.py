"""Review pending exact bills under explicit amount/chronology guidance, offline."""
from collections import defaultdict
from decimal import Decimal
import hashlib
import json

from _hist_extract import OUT, dump, money
from _hist_match import PayRow, PayDraft, confirm_batch


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    decision_path=OUT/'plan/单号金额时序用户裁定.json'
    decision=json.loads(decision_path.read_text(encoding='utf-8'))
    paths=['plan/拟写入清单.json','plan/增补冻结清单.json','plan/样例确认冻结清单.json',
           'plan/28笔追加冻结清单.json','plan/综合名称核验13笔冻结清单.json']
    protected={p:sha(OUT/p) for p in paths}
    approved=[r for p in paths for r in json.loads((OUT/p).read_text(encoding='utf-8'))['rows']]
    assert len(approved)==283
    snapshot=json.loads((OUT/'match/剩余匹配只读快照.json').read_text(encoding='utf-8'))
    notices={n['id']:n for n in snapshot['notices']}
    paid=defaultdict(lambda:Decimal(0))
    seen=set()
    linked={l['notice_id'] for l in snapshot['links']}
    for f in snapshot['flows']:
        if f['status']=='effective':
            paid[f['notice_id']]+=money(f['amount'])
            seen.add((f['notice_id'],str(f['pay_date']),money(f['amount'])))
    for r in approved:
        paid[r['notice_id']]+=money(r['amount'])
        seen.add((r['notice_id'],r['pay_date'],money(r['amount'])))
    report=json.loads((OUT/'report/剩余123行核查.json').read_text(encoding='utf-8'))
    rows=[]
    for case in report['rows']:
        s=case['source']
        if not case['current_notice']:
            continue
        n=notices[s['notice_id']]
        if s['bill_no']!=n['bill_no'] or not s['amount']:
            continue
        amount=money(s['amount'])
        if amount<=0 or amount!=money(n['amount_approved']):
            continue
        if any('负数' in i or '多来源累计超审批' in i for i in case['remaining_issues']):
            continue
        pay_date=s['pay_date']
        date_proposed=False
        if not pay_date and s['annotation']=='7.3付' and (s['sheet'],s['line'])==('2026年6月',132):
            pay_date='2026-07-03'
            date_proposed=True
        if not pay_date or not s['pay_method'] or not n['doc_date'] or str(n['doc_date'])>pay_date:
            continue
        if any(n[k] for k in ('excluded','i8_revoked','revoked_joint')):
            continue
        fingerprint=n['id'],pay_date,amount
        if fingerprint in seen:
            continue
        cap=money(n['amount_approved'])-paid[n['id']]
        checked=confirm_batch([PayRow(n['id'],n['approve_status'],cap,n['category'],n['id'] in linked)],
                              {n['id']:PayDraft(s['pay_method'],amount)},pay_date=pay_date,remark=s['remark'])
        if checked.errors:
            continue
        rows.append(dict(review_seq=len(rows)+1,approved=False,source=s,notice_id=n['id'],bill_no=n['bill_no'],
            notice_project=n['project_name'],notice_payee=n['payee'],jc_supplier=n.get('jc_supplier',''),
            notice_title=n['fields'].get('BillName',''),doc_date=n['doc_date'],approval=str(n['amount_approved']),
            amount=str(amount),pay_date=pay_date,pay_method=s['pay_method'],date_proposed=date_proposed,
            original_issues=case['remaining_issues'],rule_evidence=decision,rule_sha256=sha(decision_path),
            preflight_errors=checked.errors,balance_after=str(cap-amount)))
        paid[n['id']]+=amount
        seen.add(fingerprint)
    assert {(r['source']['sheet'],r['source']['line']) for r in rows}=={
        ('3月份',96),('2026年4月份',66),('2026年4月份',76),('2026年6月',78),('2026年6月',132)}
    total=sum((money(r['amount']) for r in rows),Decimal(0))
    dump(OUT/'plan/单号金额时序5笔候选_待批准.json',dict(approved=False,count=5,amount=str(total),
         source_pending_count=123,protected_approved_plans=protected,rows=rows))
    lines=['# 单号金额时序5笔完整审阅','',
        f'5笔、{total}元，尚未批准。原283笔、18345262.59元冻结不变。',
        '按用户新口径：单号、拟付金额与审批一致、通知书先于付款。原单位/流程差异照实保留；所有准入、防重、含283笔的额度均通过。',
        '第5笔6月表写7.3付，提出2026年7月3日；跨月日期需随本批批准，不静默确证。第4笔源洛阳桐玺与库内集采宿迁伟民明显不同；仍展示双方，按用户单号优先口径提出。','',
        '|序号|来源|源项目／收款|编号|库内项目／收款／供应商|标题|源E|源拟付＝审批|单据日|拟付款日|方式|原问题|',
        '|---|---|---|---|---|---|---:|---:|---|---|---|---|']
    for r in rows:
        s=r['source']
        vals=[r['review_seq'],f"{s['sheet']}!{s['line']}",s['project']+'／'+s['payee'],r['bill_no'],
              r['notice_project']+'／'+r['notice_payee']+'／'+r['jc_supplier'],r['notice_title'],s['E'],
              r['amount'],r['doc_date'],r['pay_date'],r['pay_method'],'；'.join(r['original_issues'])]
        lines.append('|'+ '|'.join(str(v).replace('|','／').replace('\n',' ') for v in vals)+'|')
    (OUT/'report/单号金额时序5笔完整审阅.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    assert all(sha(OUT/p)==digest for p,digest in protected.items())
    print(json.dumps(dict(count=5,amount=str(total),approved_count=283,remaining=123),ensure_ascii=False))


if __name__=='__main__':
    main()
