"""Rebuild a historical plan with nonempty L as a mandatory payment-evidence gate."""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
import re

from _hist_extract import OUT, dump, csv_out, money, payment_date
from _hist_match import PayRow, PayDraft, confirm_batch, session_scope, text
from _hist_freeze_13 import sha


OLD_SHA = '538f2155ea8cd09b22a049716972fbf8f8d294dc9acf834b48e38c193c2221bc'


def assert_payment_evidence(raw):
    annotation=raw.get('L','').strip()
    assert annotation,'L空不得生成付款分录；I/单号/金额均不替代'
    assert not any(t in annotation for t in ('货到','验收合格','回款后','进度款到','（删除）','退回','未收到')),'条件/退回不是成功付款'


def selftest():
    for raw in ({'I':'2026.3.11','L':''},{'I':'2026.3.11','L':'  '},
                {'I':'2026.3.11','L':'验收合格后付款'},{'L':'承兑退回未收到'}):
        try:assert_payment_evidence(raw)
        except AssertionError:pass
        else:raise AssertionError('反例未拒：'+str(raw))
    for raw in ({'I':'2026.3.11','L':'4.15付款'},{'L':'√'},{'L':'已付款'}):assert_payment_evidence(raw)
    for status in ('未批','已批'):
        check=confirm_batch([PayRow(99999,status,Decimal('10'),'material',False)],
              {99999:PayDraft('现汇',Decimal('10'))},pay_date='2026-01-30',remark='隔离纯函数例子')
        assert bool(check.errors)==(status=='未批'),'普通未批审批闸不得变化'
    print('L空/I有日期、付款条件、退回反例拒绝；L实付正例通过；普通未批仍拒')


def main(refresh=False):
    old_path=OUT/'plan/拟写入清单_全部核验冻结.json'
    assert sha(old_path)==OLD_SHA
    old=json.loads(old_path.read_text(encoding='utf-8'))
    policy=json.loads((OUT/'plan/L列实付证据用户裁定.json').read_text(encoding='utf-8'))
    assert policy['all_months'] and policy['missing_L_exception_requires_user_verification']
    approval=json.loads((OUT/'plan/历史审批漏同步单笔裁定.json').read_text(encoding='utf-8'))
    snapshot_path=OUT/'match/L实付更正只读快照.json'
    if refresh:
        with session_scope() as session:
            session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            readonly=session.execute(text('SHOW transaction_read_only')).scalar()
            data={name:[dict(r) for r in session.execute(text(sql)).mappings()] for name,sql in (
                 ('notices','SELECT * FROM payment_notice ORDER BY id'),
                 ('flows','SELECT * FROM payment_flow ORDER BY id'),('links','SELECT * FROM jc_payment ORDER BY id'))}
            session.rollback()
        assert readonly=='on'
        dump(snapshot_path,dict(transaction_read_only=readonly,**data))
    snap=json.loads(snapshot_path.read_text(encoding='utf-8'))
    assert snap['transaction_read_only']=='on' and len(snap['notices'])==1146
    ns={n['id']:n for n in snap['notices']};links={x['notice_id'] for x in snap['links']}
    records=[json.loads(x) for x in (OUT/'extract/抽取明细.jsonl').read_text(encoding='utf-8').splitlines()]
    sources={(r['sheet'],r['line']):r for r in records}
    outcomes=json.loads((OUT/'plan/自主核验排除与待确认.json').read_text(encoding='utf-8'))['rows']
    cases={(x['source']['sheet'],x['source']['line']):x['source'] for x in outcomes}
    def l_date(s):
        month=int(re.search(r'(\d+)月',s['sheet']).group(1))
        annotation=s['raw'].get('L','')
        parsed=payment_date(annotation,month,'L')[0]
        if parsed:return parsed
        found=re.search(r'(\d{1,2})[./月](\d{1,2})(?:日)?\s*付',annotation)
        if found:return date(2026,*map(int,found.groups())).isoformat()
        bare=re.fullmatch(r'(\d{1,2})[./月](\d{1,2})(?:日|号)?',annotation.strip())
        if bare:return date(2026,*map(int,bare.groups())).isoformat()
        # L still proves actual payment; M can supply its explicitly stated date.
        if annotation.strip() and '付款' in s['raw'].get('M',''):
            found=re.search(r'(\d{1,2})[./月](\d{1,2})(?:日)?\s*付款',s['raw']['M'])
            if found:return date(2026,*map(int,found.groups())).isoformat()
        return ''
    revised=[];changes=[];unpaid=[]
    for prior in old['rows']:
        row=deepcopy(prior); primary=sources[row['sheet'],row['line']]
        if not primary['raw'].get('L','').strip():
            ev=row.get('依据',{})
            paid_refs=[s for s in ev.get('source_rows',[]) if s['raw'].get('L','').strip()]
            if not paid_refs:
                unpaid.append(dict(previous_seq=row['seq'],sheet=row['sheet'],line=row['line'],bill_no=row['bill_no'],
                                   amount=row['amount'],I=primary['raw'].get('I',''),L='',reason='L空未付；无已核准其他实付来源'))
                changes.append(dict(previous_seq=row['seq'],action='隔离未付',old_date=row['pay_date'],amount=row['amount']))
                continue
            assert len(paid_refs)==1 and len(ev['source_rows'])==2,'另一实付来源不唯一，停止'
            actual=paid_refs[0]; day=l_date(actual); assert day
            changes.append(dict(previous_seq=row['seq'],action='改用四月实付来源',old_date=row['pay_date'],
                                new_date=day,old_source=f"{row['sheet']}!{row['line']}",new_source=f"{actual['sheet']}!{actual['line']}",amount=row['amount']))
            row.update(sheet=actual['sheet'],line=actual['line'],pay_date=day,date_basis='L实际付款批注：'+actual['raw']['L'],
                       raw=actual['raw'],annotation=actual['raw']['L'],
                       remark=f"来源：{actual['sheet']}!L{actual['line']}「{actual['raw']['L']}」；三月L空未付，原择早判断撤销")
            ev['unpaid_source_refs']=[s for s in ev['source_refs'] if s not in [dict(sheet=actual['sheet'],line=actual['line'])]]
            ev['source_refs']=[dict(sheet=actual['sheet'],line=actual['line'])];ev['source_rows']=[actual]
            ev['match_basis']='单号同额唯一，四月L实付；三月I日期不作实付依据'
            row['flags']['date_chosen']=False
        elif row['sheet']=='3月份':
            day=l_date(primary);assert day,'三月L实付日期不能解析，停止'
            if day!=row['pay_date']:
                changes.append(dict(previous_seq=row['seq'],action='付款日期改取L',source=f"{row['sheet']}!{row['line']}",
                                    old_date=row['pay_date'],new_date=day,amount=row['amount'],L=primary['raw']['L']))
                row.update(pay_date=day,date_basis='L实际付款批注；I仅时间线索',
                           remark=f"来源：{row['sheet']}!L{row['line']}「{primary['raw']['L']}」；原I日期判断撤销")
        row['revision_approval_kind']='用户授权按L实付证据更正' if any(c['previous_seq']==prior['seq'] for c in changes) else (
            '原逐项批准' if prior['seq']<297 else '用户授权自主核定')
        row['previous_seq']=prior['seq'];revised.append(row)
    # Removing the unpaid March line resolves the former March+April overpayment.
    additions=((('2026年4月份',6),'用户授权自主核定'),(('1月份',44),'用户单笔历史审批漏同步特批'),
               (('2026年4月份',129),'用户授权自主核定'),(('2026年4月份',130),'用户授权自主核定'))
    for key,approval_kind in additions:
        s=deepcopy(cases[key]);assert s['raw'].get('L','').strip()
        if key==('2026年4月份',130):
            used={r['notice_id'] for r in revised}
            options=[n for n in ns.values() if n['id'] not in used and n['approve_status']=='已批'
                     and money(n['amount_approved'])==money(s['amount']) and '晋江' in n['project_name']
                     and '万马' in (n['payee'] or '')+(n.get('jc_supplier') or '')+n['fields'].get('BillName','')
                     and not n['i8_revoked'] and not n['revoked_joint'] and str(n['doc_date'])<=l_date(s)]
            assert len(options)==1 and options[0]['id']==571,'万马同额项目候选不唯一，停止'
            s['notice_id']=options[0]['id']
        n=ns[s['notice_id']];day=l_date(s);assert day and money(s['amount'])>0
        row={k:deepcopy(s[k]) for k in ('sheet','line','bill_no','notice_id','amount','pay_method','remark','raw','project','payee')}
        row.update(bill_no=n['bill_no'],pay_date=day,date_basis='L明确实付金额＋本行M明确付款日期' if key[1] in (129,130) else 'L实际付款批注',amount_basis=s['amount_basis'],previous_seq=None,
                   revision_approval_kind=approval_kind,flags=dict(blank_method=False,overpay_approved=False,
                    no_bill_no=not bool(s['bill_no']),excluded_notice=bool(n['excluded']),historical_approval_exception=n['id']==1135),
                   依据=dict(source_refs=[dict(sheet=s['sheet'],line=s['line'])],source_rows=[s],
                             match_basis='同号同金额；三月未付剔除后额度通过' if n['id']==1123 else (
                                 '用户明确单笔审批漏同步特批' if n['id']==1135 else 'L金额＋M付款日，单号/同额项目供应商唯一匹配')))
        if n['id']==1135:
            assert n['bill_no']==approval['bill_no'] and row['amount']==approval['amount'] and day==approval['pay_date']
            row['approval_exception']=dict(original_status=n['approve_status'],effective_status='已批',
                 policy_ref='历史审批漏同步单笔裁定.json',policy_sha256=sha(OUT/'plan/历史审批漏同步单笔裁定.json'),
                 adapter_support_required=True,database_status_unchanged=True)
        revised.append(row)
        changes.append(dict(previous_seq=None,action='新增单笔审批特批' if n['id']==1135 else (
                            '三月未付后解除四月超付嫌疑' if n['id']==1123 else 'L金额与本行M实际付款日确证'),
                            source=f"{s['sheet']}!{s['line']}",bill_no=n['bill_no'],amount=row['amount'],new_date=day))
    paid=defaultdict(lambda:Decimal(0));seen=set()
    for f in snap['flows']:
        if f['status']=='effective':
            paid[f['notice_id']]+=money(f['amount']);seen.add((f['notice_id'],str(f['pay_date']),money(f['amount'])))
    rows=sorted(revised,key=lambda r:(r['pay_date'],r['notice_id'],r['sheet'],r['line']))
    for seq,row in enumerate(rows,1):
        row['seq']=seq;n=ns[row['notice_id']];amount=money(row['amount'])
        assert_payment_evidence(sources[row['sheet'],row['line']]['raw'])
        assert not n['i8_revoked'] and not n['revoked_joint'] and str(n['doc_date'])<=row['pay_date']
        effective_status='已批' if row.get('approval_exception') else n['approve_status']
        checked=confirm_batch([PayRow(n['id'],effective_status,money(n['amount_approved'])-paid[n['id']],n['category'],n['id'] in links)],
                              {n['id']:PayDraft(row['pay_method'],amount)},pay_date=row['pay_date'],remark=row['remark'])
        assert not checked.errors and (n['id'],row['pay_date'],amount) not in seen
        row['复核']=dict(original_approve_status=n['approve_status'],effective_approve_status=effective_status,
                         paid_before=str(paid[n['id']]),paid_after=str(paid[n['id']]+amount),approval_amount=n['amount_approved'],
                         jc_linked=n['id'] in links,preflight_errors=checked.errors,L=sources[row['sheet'],row['line']]['raw']['L'])
        row.setdefault('依据',dict(source_refs=[dict(sheet=row['sheet'],line=row['line'])],
             match_basis='沿用原逐项批准对应，按L重新验证实际付款证据'))
        row['依据']['actual_payment_source']=sources[row['sheet'],row['line']]['raw']
        row['依据']['current_notice_summary']={k:n.get(k) for k in ('bill_no','project_name','payee','jc_supplier','doc_date','amount_approved','excluded')}
        for ref in row['依据'].get('source_refs',[]):assert_payment_evidence(sources[ref['sheet'],ref['line']]['raw'])
        paid[n['id']]+=amount;seen.add((n['id'],row['pay_date'],amount))
    pending=[x for x in outcomes if x['outcome']=='待确认' and x['source']['raw'].get('L','').strip()
             and (x['source']['sheet'],x['source']['line']) not in {key for key,_ in additions}]
    # Refresh reasons using revised reservations, instead of the invalid I-based ledger.
    for x in pending:
        s=x['source'];n=ns.get(s['notice_id'])
        s['pay_date']=l_date(s)
        if n and money(s['amount']) and paid[n['id']]+money(s['amount'])>money(n['amount_approved']):
            x['current_ledger']=dict(notice_id=n['id'],bill_no=n['bill_no'],approval=n['amount_approved'],
                                    paid_and_planned=str(paid[n['id']]),source_proposed_amount=s['amount'])
    total=sum((money(r['amount']) for r in rows),Decimal(0));frozen=OUT/'plan/拟写入清单_L实付更正版.json'
    dump(frozen,dict(schema=old['schema'],source_file=old['source_file'],source_sha256=old['source_sha256'],batch=old['batch'],
         revision='L-payment-evidence-v1',supersedes=dict(path=str(old_path.relative_to(OUT)),sha256=OLD_SHA),
         policy_ref='L列实付证据用户裁定.json',policy_sha256=sha(OUT/'plan/L列实付证据用户裁定.json'),
         readonly_snapshot_sha256=sha(snapshot_path),approved=True,write_authorization=False,
         execution_ready=False,execution_limit='仅清单核验已完成；历史审批单笔特批须TAIL-286适配器显式支持，禁止直接写库',
         pending_ref='L实付更正_排除与待确认.json',excluded_ref='L实付更正_排除与待确认.json',rows=rows))
    result=dict(count=len(rows),amount=str(total),old_count=343,old_amount='38247845.87',changes=changes,
         empty_L_quarantined_count=len(unpaid),empty_L_quarantined_amount=str(sum((money(x['amount']) for x in unpaid),Decimal(0))),
         pending_count=len(pending),history_approval_exception_count=1,overpay_count=0,blank_method_count=0,
         empty_L_in_plan_count=0,frozen_sha256=sha(frozen),zero_database_writes=True)
    lists={k:[] for k in ('未匹配','缺关联','未批','重复嫌疑','超付候选')}
    for x in pending:
        s=x['source'];n=ns.get(s['notice_id']);entry=dict(sheet=s['sheet'],line=s['line'],bill_no=s['bill_no'],
                                                      amount=s['amount'],reason=x['reason'])
        if n is None:lists['未匹配'].append(entry)
        if n and n['category']=='jc' and n['id'] not in links:lists['缺关联'].append(entry)
        if n and n['approve_status']!='已批':lists['未批'].append(entry)
        if x.get('blocked_identity_candidates') or x.get('current_ledger'):lists['重复嫌疑'].append(entry)
        if n and money(s['amount']) and paid[n['id']]+money(s['amount'])>money(n['amount_approved']):lists['超付候选'].append(entry)
    result['five_list_counts']={k:len(v) for k,v in lists.items()}
    dump(OUT/'match/L实付更正五张清单.json',dict(scope='L有实付批注但未解除的21行；多标签，不可相加',lists=lists,
         counts=result['five_list_counts'],authorized_original_unapproved_exception_ids=[1135]))
    dump(OUT/'report/L实付更正核验报告.json',result)
    unpaid_sources=[dict(source=x['source'],reason='L空，用户确认未付款') for x in outcomes if not x['source']['raw'].get('L','').strip()]
    dump(OUT/'plan/L实付更正_排除与待确认.json',dict(pending=pending,unpaid_frozen_entries=unpaid,
         unpaid_previous_110_sources=unpaid_sources,retained_other_outcomes=[x for x in outcomes if x['outcome'] in
         ('排除/退回','库内已有/已含批准','佐证/付款条件')],i6_alternative_ref='排除与待确认.json'))
    csv_out(OUT/'report/L实付更正版逐笔核验.csv',[dict(seq=r['seq'],previous_seq=r['previous_seq'],sheet=r['sheet'],line=r['line'],
         bill_no=r['bill_no'],amount=r['amount'],pay_date=r['pay_date'],L=r['复核']['L'],pay_method=r['pay_method'],
         approval_exception=bool(r.get('approval_exception')),paid_after=r['复核']['paid_after']) for r in rows],
         ['seq','previous_seq','sheet','line','bill_no','amount','pay_date','L','pay_method','approval_exception','paid_after'])
    def cell(v):return str(v or '').replace('|','／').replace('\n',' ')
    md=['# 历史付款补录：请核对的剩余事项','',
        f'最新更正版：{len(rows)}条通知书付款分录，{total:,.2f}元；每条主来源L均有付款批注，零写库。',
        f'清单SHA256：`{sha(frozen)}`。原343条暂停，不再作为执行清单。',
        '三月I日期已撤销为实付证据；11条改选四月L付款来源，三月有L行的日期取L；原三条L空记录已隔离。',
        '1月44行29000元单笔审批特批已列清单，保留原未批状态。当前适配器尚需实现例外支持，本轮没有写库。','',
        '## 一、需要你处理的事项','',f'共{len(pending)}行。可按问题编号回复，给正确通知书编号、实际付款日期/金额，或确认属于重复标注/不需补录即可。',
        '供应商名称差异不作为单独问题；下列问题是现有材料不足以定位通知书、确认日期/金额或排除超额。']
    for i,x in enumerate(pending,1):
        s=x['source']; key=s['sheet'],s['line'];n=ns.get(s['notice_id'])
        if not money(s['amount']):question='请确认实际支付金额。E流程额不能单独当成实付额；如没有实际付款，请说明。'
        elif not s['pay_date']:question='已付批注没有日期，请给实际付款日。'
        elif n and paid[n['id']]+money(s['amount'])>money(n['amount_approved']):
            question='这笔是否已包含在库内流水/已批准付款中，还是对应另一个通知书？请给正确对应或说明额外实付。'
        elif x.get('blocked_identity_candidates'):question='同额通知书已被另一付款来源占满。请确认是否同一笔重复标注，还是应对应另一单据。'
        else:question='请提供正确通知书编号或能定位流程的线索；若属于老系统/其他业务单据，请明确类别。'
        md.extend(['',f"### 问题{i} · {s['sheet']}!{s['line']}",'',
             f"项目：{s['project']}；收款：{s['payee']}；源编号：{s['bill_no'] or '无'}。",
             f"E流程额：{s['E']}；G：{s['G']}；拟实付：{s['amount'] or '缺失'}；L原文：「{s['raw']['L']}」；当前拟日期：{s['pay_date'] or '缺失'}。",
             f"核查结果：{x['reason']}。",f'**请你核对：{question}**'])
        if n:md.append(f"对应库内单据：{n['bill_no']}；审批{n['amount_approved']}；库内已付＋更正版预留{paid[n['id']]}。")
        if '扬中蓝天' in s['payee']:
            known=ns[328]
            md.append(f"同项目同供应商线索：{known['bill_no']}；审批{known['amount_approved']}。源2月800000与8月200000是否被库内整额流水一并包含，需要你核对，不能重复加付。")
            flows=[{k:f[k] for k in ('amount','pay_date','status')} for f in snap['flows'] if f['notice_id']==328]
            md.append('对应库内流水：`'+json.dumps(flows,ensure_ascii=False)+'`')
        if x.get('blocked_identity_candidates'):md.append('同额线索：`'+json.dumps(x['blocked_identity_candidates'],ensure_ascii=False)+'`')
        md.append('源行全文：`'+json.dumps(s['raw'],ensure_ascii=False)+'`')
    md.extend(['','## 二、L空已按未付隔离：供你核实是否有漏标','',
               '这三条曾误进冻结清单。当前按你的口径排除，不认定已付。如你查到确已付款，请提供实付日期/金额或凭证线索，再恢复核验。',
               '|原序号|来源|通知书|金额|I计划时间|L|','|---|---|---|---:|---|---|'])
    for x in unpaid:md.append('|'+ '|'.join(map(cell,[x['previous_seq'],f"{x['sheet']}!{x['line']}",x['bill_no'],x['amount'],x['I'],'空，按未付']))+'|')
    md.extend(['','## 三、已自行解决，不需要再逐项确认','',
        '11条三月L空、四月L写4.15付款：只计四月。灵宝4月6行397726.50元：三月未付不参与累计，准入与额度通过。',
        '三月已有L的日期改动及旧新来源映射见下面更正明细；单号、金额保持，唯独实际日期以L为准。',
        '|原序号|处理|原来源|新来源|旧日期|新日期|金额|','|---|---|---|---|---|---|---:|'])
    for c in changes:md.append('|'+ '|'.join(map(cell,[c['previous_seq'],c['action'],c.get('old_source',c.get('source','')),
                    c.get('new_source',''),c.get('old_date',''),c.get('new_date',''),c['amount']]))+'|')
    md.extend(['','## 四、已核定但有推定日期的记录（可选复核）','',
        '这4条L确有已付批注，日期沿用此前授权自主判断，取同项目当月唯一已付款汇总日期；不等同银行日期已另证。如日期不符请指出。'])
    for r in rows:
        ev=r.get('依据',{})
        if ev.get('date_evidence'):md.append(f"- 更正版序号{r['seq']}，{r['sheet']}!{r['line']}，{r['bill_no']}，{r['amount']}元，拟{r['pay_date']}，L「{r['复核']['L']}」。")
    (OUT/'report/需要用户核对_L实付更正版.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    complete_md=['# L实付更正版完整逐笔核验','',f'{len(rows)}条，{total:,.2f}元；SHA256 `{sha(frozen)}`；零写库。',
        '原343条为旧版本暂停件。旧序号仅供追溯，不再用于新清单批准定位。当前付款来源均有L批注；原未批特批按有效核验视图已批预检，尚需适配器支持。','',
        '|新序号|旧序号|实付来源|通知书|项目|库内收款／集采供应商|源E／G|L付款批注|付款日期|金额|方式|审批额|库内及前序预留|补后累计|审批例外|',
        '|---|---|---|---|---|---|---|---|---|---:|---|---:|---:|---:|---|']
    for r in rows:
        s=sources[r['sheet'],r['line']];n=ns[r['notice_id']]
        complete_md.append('|'+ '|'.join(map(cell,[r['seq'],r['previous_seq'],f"{r['sheet']}!{r['line']}",r['bill_no'],n['project_name'],
              (n['payee'] or '')+'／'+(n.get('jc_supplier') or ''),s['raw'].get('E','')+'／'+s['raw'].get('G',''),r['复核']['L'],
              r['pay_date'],r['amount'],r['pay_method'],n['amount_approved'],r['复核']['paid_before'],r['复核']['paid_after'],
              '原未批，用户单笔特批' if r.get('approval_exception') else '无']))+'|')
    (OUT/'report/L实付更正版完整逐笔核验.md').write_text('\n'.join(complete_md)+'\n',encoding='utf-8')
    hold=json.loads((OUT/'plan/冻结清单执行状态.json').read_text(encoding='utf-8'))
    hold.update(replacement_ref='拟写入清单_L实付更正版.json',replacement_sha256=sha(frozen),
                replacement_status='只读核验完成；需历史审批特批适配支持，不是直接写入授权')
    dump(OUT/'plan/冻结清单执行状态.json',hold)
    assert sha(old_path)==OLD_SHA
    print(json.dumps({k:v for k,v in result.items() if k!='changes'},ensure_ascii=False))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');parser.add_argument('--selftest',action='store_true')
    args=parser.parse_args()
    selftest() if args.selftest else main(args.refresh)
