"""Find amount/chronology clues for missing bills; bounded proposals, no DB access."""
from collections import defaultdict
from decimal import Decimal
import json

from _hist_extract import OUT, dump, money
from _hist_match import PayRow, PayDraft, confirm_batch
from _hist_freeze_13 import sha


def main():
    paths=['plan/拟写入清单.json','plan/增补冻结清单.json','plan/样例确认冻结清单.json',
           'plan/28笔追加冻结清单.json','plan/综合名称核验13笔冻结清单.json','plan/单号金额时序5笔冻结清单.json']
    protected={p:sha(OUT/p) for p in paths}
    approved=[r for p in paths for r in json.loads((OUT/p).read_text(encoding='utf-8'))['rows']]
    assert len(approved)==288
    used={r['notice_id'] for r in approved}
    snap=json.loads((OUT/'match/剩余匹配只读快照.json').read_text(encoding='utf-8'))
    paid=defaultdict(lambda:Decimal(0))
    flow_ids=set()
    for f in snap['flows']:
        if f['status']=='effective':
            paid[f['notice_id']]+=money(f['amount']); flow_ids.add(f['notice_id'])
    for r in approved:
        paid[r['notice_id']]+=money(r['amount'])
    linked={l['notice_id'] for l in snap['links']}
    report=json.loads((OUT/'report/剩余118行核查.json').read_text(encoding='utf-8'))
    keys={('2月份',line) for line in (159,160,161,164,174,175,179,180)}|{('2026年5月份',108),('2026年5月份',119)}
    proposals=[]
    for c in report['rows']:
        s=c['source']; key=s['sheet'],s['line']
        if key not in keys:
            continue
        assert not s['bill_no'] and not c['current_notice']
        matches=[n for n in snap['notices'] if n['id'] not in used|flow_ids and money(n['amount_approved'])==money(s['E'])
                 and n['doc_date'] and str(n['doc_date'])<=s['pay_date'] and n['approve_status']=='已批'
                 and not any(n[k] for k in ('excluded','i8_revoked','revoked_joint'))]
        assert len(matches)==1
        n=matches[0]; title=n['fields'].get('BillName','')
        if s['project']=='大唐雷州':
            assert '大唐雷州' in title
        elif s['project']=='晋江污泥':
            assert '晋江污泥' in title and n['jc_supplier'] in s['payee']
        elif key==('2026年5月份',108):
            assert '福建南平' in title and n['payee']=='资产管理处调拨户'
        else:
            assert '太康龙源' in title and n['payee']=='资产管理处调拨户'
        amount=money(s['amount']); cap=money(n['amount_approved'])-paid[n['id']]
        way_pending=key[0]=='2026年5月份'
        checked=confirm_batch([PayRow(n['id'],n['approve_status'],cap,n['category'],n['id'] in linked)],
            {n['id']:PayDraft(s['pay_method'],amount)},pay_date=s['pay_date'],remark=s['remark'])
        if not way_pending:
            assert not checked.errors
        proposals.append(dict(review_seq=len(proposals)+1,approved=False,source=s,notice_id=n['id'],
            bill_no=n['bill_no'],notice_project=n['project_name'],notice_payee=n['payee'],jc_supplier=n.get('jc_supplier',''),
            notice_title=title,doc_date=n['doc_date'],approval=str(n['amount_approved']),amount=str(amount),
            pay_date=s['pay_date'],pay_method=s['pay_method'],payment_method_pending=way_pending,
            preflight_errors=checked.errors,balance_after=str(cap-amount),
            mapping_basis='未占用且无生效流水通知书中，审批等源E且先于付款唯一；另核标题项目及单位/业务描述'))
        used.add(n['id']); paid[n['id']]+=amount
    assert len(proposals)==10
    ready=[p for p in proposals if not p['payment_method_pending']]
    assert len(ready)==8
    total=sum((money(p['amount']) for p in ready),Decimal(0))
    assert total==Decimal('227089.10')
    dump(OUT/'plan/无编号8笔候选_待批准.json',dict(approved=False,count=8,amount=str(total),
         protected_approved_plans=protected,rows=ready))
    dump(OUT/'report/无编号10行线索核验.json',dict(approved=False,count=10,payment_ready_count=8,
         payment_method_pending_count=2,rows=proposals))
    lines=['# 无编号10行完整线索审阅','',
        '均为Excel编号空白，提出对应后仍需用户确认。审批额等源E、通知书先于付款且未占用候选唯一；另按标题核项目/材料及供应商，不仅凭金额同值匹配。',
        '前8笔共227,089.10元，方式齐、准入/关联/防重及含288笔累计额度通过，尚未批准。后2行只提出通知书对应，付款方式仍待明确；不自动把数字误读为方式。',
        '大唐雷州4行库内项目挂“第四工程公司2024小微项目”，通知书标题均明确大唐雷州；需随拟对应确认。','',
        '|序号|来源|源项目／收款|拟编号|库内收款／供应商|标题|源E＝审批|拟付|单据日|付款日|方式|补后余额|',
        '|---|---|---|---|---|---|---:|---:|---|---|---|---:|']
    for p in proposals:
        s=p['source']
        vals=[p['review_seq'],f"{s['sheet']}!{s['line']}",s['project']+'／'+s['payee'],p['bill_no'],
              p['notice_payee']+'／'+p['jc_supplier'],p['notice_title'],p['approval'],p['amount'],
              p['doc_date'],p['pay_date'],'待确认（J='+s['raw'].get('J','')+'）' if p['payment_method_pending'] else p['pay_method'],p['balance_after']]
        lines.append('|'+ '|'.join(str(v).replace('|','／').replace('\n',' ') for v in vals)+'|')
    (OUT/'report/无编号10行完整线索审阅.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    assert all(sha(OUT/p)==digest for p,digest in protected.items())
    print(json.dumps(dict(mapping_proposals=10,ready=8,ready_amount=str(total),method_pending=2,approved=288),ensure_ascii=False))


if __name__=='__main__':
    main()
