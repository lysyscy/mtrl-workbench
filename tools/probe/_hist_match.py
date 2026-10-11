"""历史补录只读匹配、月汇总核对与冻结；绝不执行业务写入。"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from datetime import datetime, timezone, timedelta

from _hist_extract import BILL, MAIN, OUT, ROOT, csv_out, dump, explicit_amount, money, payment_date, project_key, source_date

sys.path.insert(0, str(ROOT / 'backend'))
import app.models_registry  # noqa: E402,F401
from app.core.db import session_scope  # noqa: E402
from app.mod03_notice.domain import PayRow, PayDraft, confirm_batch  # noqa: E402
from sqlalchemy import text  # noqa: E402


def normalize(s):
    """仅去空白与括号字形，绝不模糊收款单位。"""
    return re.sub(r'\s+', '', str(s or '')).replace('（','(').replace('）',')')


def summaries(records):
    """按项目列汇总格，保留所有明细及非计划备注。"""
    sums = []
    configs = {'4月汇总':(4,'B',('C','D')), '汇总5':(5,'D',('E',)), '汇总6':(6,'C',('D',)), '汇总7':(7,'D',('E',)), '汇总8':(8,'E',('F',))}
    for r in records:
        if r['sheet'] not in configs:
            continue
        month, pcol, acols = configs[r['sheet']]
        project = r['raw'].get(pcol,'')
        if not project or '合计' in project:
            continue
        amounts = [(c,money(r['raw'].get(c))) for c in acols]
        vals = [(c,v) for c,v in amounts if v is not None]
        if vals:
            sums.append(dict(month=month, project=project_key(project), amount=str(sum((v for _,v in vals), Decimal(0))), sheet=r['sheet'], line=r['line'], cells=[c for c,_ in vals], raw=r['raw']))
    return sums


def summary_report(records, sums):
    """已付款批注行与汇总表对照；G只作核对金额，不凭此放行导入。"""
    report=[]
    for month in range(4,9):
        groups=defaultdict(lambda: dict(detail=[], summary=[]))
        for r in records:
            if r['month']==month and r['block']:
                groups[project_key(r['project'])]
        for r in records:
            if r['month'] != month or not r['annotation'] or not r['payee'] or '收款单位' in r['payee']:
                continue
            if any(x in r['bill_no'] for x in ('合计','小计','外租机械')) or '退回' in ' '.join(r['raw'].values()):
                continue
            value=explicit_amount(r['annotation'])
            if value is None:
                value=money(r['raw'].get('G'))
            if value is None or value < 0:
                continue
            groups[project_key(r['project'])]['detail'].append(dict(sheet=r['sheet'], line=r['line'], amount=str(value), annotation=r['annotation'], basis='批注明示金额' if explicit_amount(r['annotation']) is not None else 'G（仅核对，不等于准入）', suspected_shift=bool(r['block'] and r['block']['suspected_shift'])))
        for r in sums:
            if r['month']==month:
                groups[r['project']]['summary'].append(r)
        for project,v in groups.items():
            d=sum((money(x['amount']) for x in v['detail']),Decimal(0))
            s=sum((money(x['amount']) for x in v['summary']),Decimal(0))
            delta=s-d
            notes=' '.join(' '.join(x['raw'].values()) for x in v['summary'])
            nature='正常差异' if delta==0 else '疑似错位' if any(x['suspected_shift'] for x in v['detail']) else '待确认'
            explanation=('一致' if v['detail'] or v['summary'] else '月表无付款批注，汇总未列；未付计划不算差额') if delta==0 else '汇总备注含计划外/待付/扣减，待逐项确认：'+notes if any(t in notes for t in ('计划','待付','扣除','单独')) else '汇总与付款批注范围/金额不一致'
            # 只将可逐格解释的差额标正常，不用“大致有备注”掩盖余差。
            if month==5 and project=='龙源' and delta==money('3264.60') and '9000' in notes and '5735.4' in notes:
                nature,explanation='正常差异','汇总计划外9000−备注扣减5735.40＝3264.60；原文引用见summary'
            if month==7 and project=='龙源' and delta==money('12000') and '单独汇报' in notes:
                nature,explanation='正常差异','汇总另列闸机一事一议12000，月表不含，原文见summary'
            report.append(dict(month=month, project=project, detail_paid=str(d), summary_paid=str(s), delta=str(delta), nature=nature, explanation=explanation, **v))
    for month,left,right,amount in ((6,'内蒙储能','乌兰察布','10600'),(7,'邵武','国风','24600')):
        a=next((r for r in report if r['month']==month and r['project']==left),None)
        b=next((r for r in report if r['month']==month and r['project']==right),None)
        if a and b and money(a['delta'])==-money(amount) and money(b['delta'])==money(amount):
            for item in (a,b):
                item.update(nature='疑似错位',explanation=f'与{right if item is a else left}呈等额反向差{amount}元；项目名称/区块归属待确认，不调整原值')
    dump(OUT/'report/月度汇总核对报告.json',report)
    csv_out(OUT/'report/月度汇总核对报告.csv',report,['month','project','detail_paid','summary_paid','delta','nature','explanation','detail','summary'])
    totals=[dict(month=m,detail_paid=str(sum((money(r['detail_paid']) for r in report if r['month']==m),Decimal(0))),summary_paid=str(sum((money(r['summary_paid']) for r in report if r['month']==m),Decimal(0))),delta=str(sum((money(r['delta']) for r in report if r['month']==m),Decimal(0))),class_counts=dict(Counter(r['nature'] for r in report if r['month']==m))) for m in range(4,9)]
    dump(OUT/'report/月度汇总总览.json',totals)
    csv_out(OUT/'report/月度汇总总览.csv',totals,['month','detail_paid','summary_paid','delta','class_counts'])
    # 已知八月事实只作固定比对，不改设计稿。
    august={r['project']:r for r in report if r['month']==8}
    expected={'慧能':'1045549.63','龙源':'1322970.38','宜化':'133857.50','大唐':'19082.00','邵武':'295418.40'}
    diff=[dict(project=k, expected=v, actual=august.get(k,{}).get('detail_paid')) for k,v in expected.items() if money(august.get(k,{}).get('detail_paid')) != money(v)]
    if money(august.get('晋江',{}).get('delta')) != money('10150'):
        diff.append(dict(project='晋江差额', expected='10150.00',actual=august.get('晋江',{}).get('delta')))
    return report,diff


def variant(b):
    """按已定两种手填变体查库。"""
    if b.startswith('FKTZ') and not b.startswith('FKTZS'):
        return 'FKTZS'+b[4:]
    if b.startswith('KFTZS'):
        return 'FKTZS'+b[5:]
    return ''


def main():
    """只读快照后离线核对，所有输出均为预览。"""
    p=argparse.ArgumentParser()
    p.add_argument('--plan',type=Path,required=True)
    args=p.parse_args()
    records=[json.loads(s) for s in args.plan.read_text(encoding='utf-8').splitlines()]
    decisions_path=OUT/'plan/用户裁定.json'
    decisions=json.loads(decisions_path.read_text(encoding='utf-8')) if decisions_path.exists() else {}
    # 数据库强制只读、可重复读事务；完成取数主动回滚，session_scope 不提交业务数据。
    with session_scope() as s:
        s.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        ro=s.execute(text('SHOW transaction_read_only')).scalar()
        notices=[dict(x) for x in s.execute(text('SELECT * FROM payment_notice ORDER BY id')).mappings()]
        flows=[dict(x) for x in s.execute(text('SELECT * FROM payment_flow ORDER BY id')).mappings()]
        links=[dict(x) for x in s.execute(text('SELECT * FROM jc_payment ORDER BY id')).mappings()]
        projects=[dict(x) for x in s.execute(text('SELECT id, name_full, warehouse_name, disp FROM project ORDER BY id')).mappings()]
        s.rollback()
    snapshot=dict(transaction_read_only=ro, notices=notices, flows=flows, links=links, projects=projects)
    dump(OUT/'match/只读库快照.json',snapshot)
    bybill=defaultdict(list)
    byproject={p['id']:p for p in projects}
    for n in notices:
        bybill[str(n['bill_no']).strip()].append(n)
    bills={r['bill_no'] for r in records if r['month'] and BILL.match(r['bill_no'])}
    hit={b for b in bills if b in bybill}
    variants={b:variant(b) for b in sorted(bills-hit) if variant(b) in bybill}
    remaining=bills-hit-set(variants)
    prefixes=Counter(re.match(r'[A-Za-z]+',b).group().upper() for b in sorted(remaining))
    control=dict(excel_unique=len(bills), notices=len(notices), FKTZS=sum(str(n['bill_no']).startswith('FKTZS') for n in notices), exact=len(hit), missing=len(bills-hit), variants=len(variants), remaining_prefixes=dict(prefixes))
    # 用户2026-10-11续轮裁定：四条KFTZS按手填错i8，变体基线4→8；原设计稿不覆写。
    expected=dict(excel_unique=535,notices=1146,FKTZS=1143,exact=395,missing=140,variants=8,remaining_prefixes={'QTZC':88,'FKTZ':38,'FKTZS':3,'SBJS':2,'FYBXSQ':1})
    dump(OUT/'match/基线比对.json',dict(actual=control,expected=expected,consistent=control==expected,user_decision='2026-10-11：四条KFTZS按手填错的i8处理；变体命中基线4→8',variant_evidence=[dict(excel_bill_no=b, transformed_bill_no=v, rule='FKTZ补S' if b.startswith('FKTZ') else 'KFTZS换首字母（用户2026-10-11续轮已批准）', notices=[{k:n[k] for k in ('id','bill_no','project_name','payee','amount_approved','doc_date')} for n in bybill[v]], source_rows=[dict(sheet=r['sheet'],line=r['line'],raw=r['raw']) for r in records if r['bill_no']==b]) for b,v in sorted(variants.items())]))
    if control!=expected:
        print(json.dumps(dict(stopped='已知编号数字不一致',actual=control,expected=expected),ensure_ascii=False))
        return 2
    sums=summaries(records)
    report,differences=summary_report(records,sums)
    if differences:
        dump(OUT/'report/已知数字差异.json',differences)
        print(json.dumps(dict(stopped='8月已付汇总与已知数字不一致',differences=differences),ensure_ascii=False))
        return 2
    # 编号精确/变体，覆盖全部行，包括硬排除与无批注佐证。
    matched=[]
    used=set()
    for r in records:
        targets=bybill.get(r['bill_no']) or bybill.get(variants.get(r['bill_no'],'')) or []
        if len(targets)==1:
            n=targets[0]
            r['notice_id']=n['id']
            r['matched_bill_no']=n['bill_no']
            r['match_kind']='编号精确' if r['bill_no'] in hit else '手填错（变体命中，i8）'
            used.add(n['id'])
            matched.append(r)
    unmatched=[r for r in records if r['month'] and r['classification']!='排除' and (BILL.match(r['bill_no']) or (r['payee'] and r['payee']!='收款单位' and r['annotation'])) and not r.get('notice_id')]
    second=[]
    for r in unmatched:
        amount=money(r.get('amount'))
        # 即使未过准入，多源金额仍可作人工线索，明确标示依据而非自动放行。
        if amount is None:
            amount=explicit_amount(r['annotation']) or money(r['raw'].get('G'))
        expense_date=r['expense_date']
        if not amount or not expense_date:
            continue
        candidates=[n for n in notices if n['id'] not in used and project_key(r['project']) in {project_key(n['project_name']),project_key(byproject.get(n['ownership_id'],{}).get('disp','')),project_key(byproject.get(n['ownership_id'],{}).get('warehouse_name') or '')} and normalize(n['payee'])==normalize(r['payee']) and money(n['amount_approved'])==amount and n['doc_date']==expense_date]
        if len(candidates)==1:
            n=candidates[0]
            second.append(dict(sheet=r['sheet'],line=r['line'],bill_no=r['bill_no'],notice_id=n['id'],candidate_bill_no=n['bill_no'],project=r['project'],payee=r['payee'],amount=str(amount),date=expense_date,date_comparison='Excel B费用日期=通知书单据日期（用户2026-10-11确认）',pay_date=r['pay_date'],amount_basis=r['amount_basis'] or 'G仅人工线索，未确证',approved=False,raw=r['raw']))
    classes={'i6':[], 'KFTZS待确认':[], 'FKTZS未抓待查':[], '另类SBJS/FYBXSQ':[]}
    for b in sorted(remaining):
        key='i6' if b.startswith(('QTZC','FKTZ')) and not b.startswith('FKTZS') else 'KFTZS待确认' if b.startswith('KFTZS') else 'FKTZS未抓待查' if b.startswith('FKTZS') else '另类SBJS/FYBXSQ'
        classes[key].append(dict(bill_no=b, second_round_proposals=[x for x in second if x['bill_no']==b], evidence=[r for r in records if r['month'] and r['bill_no']==b], approved=False))
    approved_bills=set()
    for key,approval in decisions.get('class_approvals',{}).items():
        if approval.get('approved'):
            assert len(classes[key])==approval['count'], '整类确认与现行清单条数不同，必须重新确认'
            for entry in classes[key]:
                entry.update(approved=True,approval_basis=approval['quote'])
                approved_bills.add(entry['bill_no'])
    effective=[f for f in flows if f['status']=='effective']
    linked={x['notice_id'] for x in links if x['notice_id'] is not None}
    paid=defaultdict(lambda:Decimal(0))
    for f in effective:
        paid[f['notice_id']]+=money(f['amount'])
    nidmap={n['id']:n for n in notices}
    lists={k:[] for k in ('未匹配','缺关联','未批','重复嫌疑','超付候选')}
    lists['未匹配']=unmatched
    excluded=[r for r in records if r['classification']=='排除' or r['bill_no'] in approved_bills]
    pending=[r for r in records if r['classification']=='待确认' and r['bill_no'] not in approved_bills]
    for r in excluded:
        if r['bill_no'] in approved_bills:
            r.update(extract_classification=r['classification'],final_reason='用户整类批准排除，原文见i6_classes')
    planned=[]
    seen={}
    hard_check=[]
    unresolved_bills={b for event in decisions.get('event_decisions',[]) if event['decision']=='pending_both_dates' for b in event['bill_nos']}
    identity_checks=[]
    event_checks=[]
    # 综合判定不是只看编号：E对审批额、项目对既有归属、收款单位对库字段。
    for r in matched:
        n=nidmap[r['notice_id']]
        if r['classification']=='排除':
            continue
        e=money(r['raw'].get('E'))
        proj=byproject.get(n['ownership_id'],{})
        keys={project_key(n['project_name']), project_key(proj.get('disp','')),project_key(proj.get('warehouse_name') or '')}
        project_ok=project_key(r['project']) in keys
        payee_ok=normalize(r['payee'])==normalize(n['payee'])
        if n['category']=='jc' and n.get('jc_supplier') and normalize(r['payee'])==normalize(n['jc_supplier']):
            payee_ok=True
        jc_annotation=bool(n['category']=='jc' and r['payee'].startswith('集采'))
        if jc_annotation:
            supplier=re.search(r'[（(](.*)[）)]',r['payee'])
            payee_ok=not supplier or not n.get('jc_supplier') or normalize(supplier.group(1))==normalize(n['jc_supplier'])
        issues=[]
        if e is None or e!=money(n['amount_approved']):
            issues.append('Excel流程金额E与库内审批金额不一致/缺失（分笔或错号须确认）')
        if not payee_ok:
            issues.append('收款单位/集采实际供应商不一致')
        if not project_ok and '无标题区间' not in r['project']:
            issues.append('项目简称与通知书/既有归属不一致')
        evidence=dict(sheet=r['sheet'],line=r['line'],bill_no=r['bill_no'],matched_bill_no=n['bill_no'],notice_id=n['id'],excel_project=r['project'],notice_project=n['project_name'],ownership=proj,excel_payee=r['payee'],notice_payee=n['payee'],jc_supplier=n.get('jc_supplier',''),excel_E=str(e),approved_amount=str(n['amount_approved']),payment_amount=r['amount'],payment_date=r['pay_date'],expense_date=r['expense_date'],notice_doc_date=n['doc_date'],issues=issues)
        identity_checks.append(evidence)
        r['evidence']['identity_check']=evidence
        if r['classification']=='候选' and issues:
            pending.append(dict(**r,reason='编号命中但综合证据矛盾',identity_issues=issues))
            r['identity_blocked']=True
        if r['matched_bill_no'] in unresolved_bills:
            alternatives=[]
            if r['expense_date'] and e is not None:
                for other in notices:
                    if other['id']==n['id'] or other['id'] in used:
                        continue
                    op=byproject.get(other['ownership_id'],{})
                    ok_project=project_key(r['project']) in {project_key(other['project_name']),project_key(op.get('disp','')),project_key(op.get('warehouse_name') or '')}
                    ok_payee=normalize(r['payee'])==normalize(other['payee']) or bool(other['category']=='jc' and other.get('jc_supplier') and normalize(r['payee'])==normalize(other['jc_supplier']))
                    if ok_project and ok_payee and money(other['amount_approved'])==e and other['doc_date']==r['expense_date']:
                        alternatives.append({k:other[k] for k in ('id','bill_no','project_name','payee','amount_approved','doc_date')})
            evidence.update(alternative_notices=alternatives,alternative_basis='项目＋收款单位（含已维护集采供应商）＋E流程金额＋B费用日期；只查尚未匹配通知书，仍需用户确认')
            event_checks.append(evidence)
    for r in records:
        if r['依据']!=['用户指定8月已手录区块硬排除']:
            continue
        nid=r.get('notice_id')
        effective_flows=[f for f in effective if nid is not None and f['notice_id']==nid]
        amount=money(r['amount']) if r['amount'] else money(r['raw'].get('G'))
        meaningful=bool(r['payee'] and r['payee']!='收款单位' and not any(x in r['bill_no'] for x in ('合计','小计','外租机械')))
        hard_check.append(dict(sheet=r['sheet'],line=r['line'],bill_no=r['bill_no'],notice_id=nid,raw=r['raw'],source_amount_basis='显式批注或G，仅复核线索（区块错位不据此写入）',annotation=r['annotation'],pay_date=r['pay_date'],source_amount=str(amount) if amount is not None else '',effective_flows=effective_flows,has_effective_flow=bool(effective_flows),exact_event_confirmed=bool(nid is not None and r['pay_date'] and amount is not None and any(f['pay_date']==r['pay_date'] and money(f['amount'])==amount for f in effective_flows)),data_row=meaningful,status='生效流水存在' if effective_flows else '结构行/非付款行' if not meaningful else '未匹配/未见生效流水，仅报告'))
    for r in matched:
        n=nidmap[r['notice_id']]
        amount=money(r.get('amount'))
        if r['classification']!='候选':
            continue
        if r.get('identity_blocked'):
            continue
        if r['matched_bill_no'] in unresolved_bills:
            item=dict(**r,reason='同编号同金额两月日期重复，用户要求综合判定，未确证资金事件')
            lists['重复嫌疑'].append(item)
            pending.append(item)
            continue
        fingerprint=(n['id'],r['pay_date'],amount)
        existing=[f for f in effective if (f['notice_id'],f['pay_date'],money(f['amount']))==fingerprint]
        if existing or fingerprint in seen:
            item=dict(**r,reason='库内已有' if existing else '批内同指纹重复嫌疑',existing_flows=existing, prior=seen.get(fingerprint))
            lists['重复嫌疑'].append(item)
            (excluded if existing else pending).append(item)
            continue
        seen[fingerprint]=dict(sheet=r['sheet'],line=r['line'])
        if n['category']=='jc' and n['id'] not in linked:
            lists['缺关联'].append(r)
            pending.append(dict(**r,reason='集采未关联'))
            continue
        row=PayRow(n['id'], n['approve_status'],money(n['amount_approved'])-paid[n['id']],n['category'],n['id'] in linked)
        if n['approve_status']!='已批' or n['excluded'] or n['i8_revoked']:
            item=dict(**r,reason='审批/撤单/剔除准入拦截',approve_status=n['approve_status'],excluded=n['excluded'],i8_revoked=n['i8_revoked'],block=row.block())
            lists['未批'].append(item)
            pending.append(item)
            continue
        method=normalize(r['raw'].get('J'))
        method={'银行承兑':'承兑','电汇':'现汇','现汇付款':'现汇'}.get(method,method)
        if method and method not in ('现汇','承兑','供应链','其他'):
            method='其他'
        seq=len(planned)+1
        over=amount>row.payable
        remark=f"来源：付款计划 {r['sheet']}!{r['annotation_col']}{r['line']}「{r['annotation']}」；{r['raw'].get('K','')}" + (f"；原方式：{r['raw'].get('J','')}" if method=='其他' else '')
        check=confirm_batch([row],{n['id']:PayDraft(method,amount)},pay_date=r['pay_date'],remark=remark)
        item=dict(seq=seq,sheet=r['sheet'],line=r['line'],bill_no=n['bill_no'],notice_id=n['id'],pay_date=r['pay_date'],amount=str(amount),pay_method=method,remark=remark,flags=dict(overpay_approved=False,blank_method=not method,no_bill_no=False),date_basis=r['date_basis'],amount_basis=r['amount_basis'],依据=dict(original_bill_no=r['bill_no'],match_kind=r['match_kind'],raw=r['raw'],evidence=r['evidence'],preflight_errors=check.errors))
        if over:
            lists['超付候选'].append(dict(**item,approved_amount=str(n['amount_approved']),paid_before=str(paid[n['id']]),paid_after=str(paid[n['id']]+amount)))
        planned.append(item)
        paid[n['id']]+=amount
    # 未命中抽取候选均不能进冻结清单。
    pending.extend(dict(**r,reason='通知书未匹配，不能写入') for r in unmatched if r['classification']=='候选')
    pending=[r for r in pending if r['bill_no'] not in approved_bills]
    # 终态口径明确，保持抽取分类原值，便于追溯阶段转换。
    for r in excluded:
        r['final_classification']='排除'
    for r in pending:
        r['final_classification']='待确认'
    # 最终未匹配清单保留未裁定项；已批准整类原文完整留在i6_classes/排除中。
    lists['未匹配']=[r for r in unmatched if r['bill_no'] not in approved_bills]
    # 疑似重复的四组，按假设两笔都写入保留超付模拟证据，均不进入冻结rows。
    for b in sorted(unresolved_bills):
        group=[r for r in matched if r['matched_bill_no']==b and r['classification']=='候选']
        if not group:
            continue
        n=nidmap[group[0]['notice_id']]
        total=sum((money(r['amount']) for r in group),Decimal(0))
        if paid[n['id']]+total>money(n['amount_approved']):
            lists['超付候选'].append(dict(bill_no=b,notice_id=n['id'],hypothetical_only=True,in_frozen_plan=False,approved_amount=str(n['amount_approved']),db_effective_paid=str(paid[n['id']]),proposed_if_both=str(total),hypothetical_paid_after=str(paid[n['id']]+total),source_rows=[dict(sheet=r['sheet'],line=r['line'],amount=r['amount'],pay_date=r['pay_date']) for r in group],reason='疑似两月误填，禁止自动选日或当作超付批准'))
    dump(OUT/'match/核对报告.json',dict(control=control,lists=lists,second_round=second,i6_classes=classes,hard_excluded_blocks=hard_check,jc_inventory=dict(count=len(links),sources=dict(Counter(x['source'] for x in links)),zero_amount=sum(money(x['amount'])==0 for x in links),with_effective_flow=sum(x['notice_id'] in {f['notice_id'] for f in effective} for x in links)), reverse_unmatched_notices=[n for n in notices if n['id'] not in used]))
    dump(OUT/'match/综合身份核对.json',identity_checks)
    dump(OUT/'match/两月重复待确认.json',event_checks)
    csv_out(OUT/'match/综合身份核对.csv',identity_checks,['sheet','line','bill_no','notice_id','excel_project','notice_project','excel_payee','notice_payee','jc_supplier','excel_E','approved_amount','payment_amount','payment_date','expense_date','notice_doc_date','issues','ownership'])
    csv_out(OUT/'match/缺关联清单.csv',lists['缺关联'],['sheet','line','bill_no','notice_id','project','amount','pay_date','raw'])
    csv_out(OUT/'match/第二轮唯一候选.csv',second,['sheet','line','bill_no','notice_id','candidate_bill_no','project','payee','amount','date','date_comparison','pay_date','amount_basis','approved','raw'])
    (OUT/'match/已匹配明细.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in matched),encoding='utf-8')
    exceptions=[dict(seq=r['seq'],kind='blank_method',approved=False) for r in planned if r['flags']['blank_method']]+[dict(seq=r['seq'],kind='overpay',approved=False) for r in lists['超付候选'] if not r.get('hypothetical_only')]
    source_sha=json.loads((OUT/'extract/抽取统计.json').read_text(encoding='utf-8'))['source_sha256']
    assert hashlib.sha256((OUT/'source/附件1、付款计划.xlsx').read_bytes()).hexdigest()==source_sha, '归档源件变化，须重新抽取'
    assert not decisions or decisions['source_sha256']==source_sha, '源件改变，原用户裁定不可套用'
    affecting_decisions={k:v for k,v in decisions.items() if k!='frozen_plan_approval'}
    input_signature=hashlib.sha256(args.plan.read_bytes()+(OUT/'match/只读库快照.json').read_bytes()+json.dumps(affecting_decisions,ensure_ascii=False,sort_keys=True).encode('utf-8')+Path(__file__).read_bytes()+(ROOT/'tools/probe/_hist_extract.py').read_bytes()).hexdigest()
    meta_path=OUT/'plan/冻结元数据.json'
    meta=json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}
    if meta.get('input_signature')!=input_signature:
        meta=dict(input_signature=input_signature,generated_at=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'))
        dump(meta_path,meta)
    plan=dict(schema='hist-supplement/1',generated_at=meta['generated_at'],source_file='附件1、付款计划.xlsx',source_sha256=source_sha,batch='IMP-HIST-20261011',rows=planned,exceptions=exceptions,excluded_ref='排除与待确认.json',pending_ref='排除与待确认.json')
    dump(OUT/'plan/拟写入清单.json',plan)
    dump(OUT/'plan/排除与待确认.json',dict(excluded=excluded,pending=pending,i6_classes=classes,second_round=second,approvals=decisions,freeze_approval_status='冻结清单及超付例外尚待逐条批准'))
    csv_out(OUT/'plan/拟写入清单.csv',planned,['seq','sheet','line','bill_no','notice_id','pay_date','amount','pay_method','remark','flags','date_basis','amount_basis','依据'])
    csv_out(OUT/'match/8月硬排除区块流水复核.csv',hard_check,['sheet','line','bill_no','notice_id','data_row','status','has_effective_flow','exact_event_confirmed','pay_date','source_amount','source_amount_basis','raw','effective_flows'])
    sha=hashlib.sha256((OUT/'plan/拟写入清单.json').read_bytes()).hexdigest()
    final=dict(plan_sha256=sha,rows=len(planned),amount_total=str(sum((money(r['amount']) for r in planned),Decimal(0))),overpay=sum(not r.get('hypothetical_only') for r in lists['超付候选']),overpay_pending_groups=sum(bool(r.get('hypothetical_only')) for r in lists['超付候选']),blank_method=sum(r['flags']['blank_method'] for r in planned),five_lists={k:len(v) for k,v in lists.items()},second_round=len(second),i6_classes={k:len(v) for k,v in classes.items()})
    dump(OUT/'plan/冻结回执.json',final)
    print(json.dumps(final,ensure_ascii=False))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
