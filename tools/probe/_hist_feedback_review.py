"""Apply numbered human feedback without changing the database or historical frozen inputs."""
import argparse
from collections import defaultdict
from copy import deepcopy
from decimal import Decimal
import json

from _hist_extract import OUT, dump, money, source_date
from _hist_match import PayRow, PayDraft, confirm_batch, session_scope, text
from _hist_L_revision import assert_payment_evidence
from _hist_freeze_13 import sha


def main(refresh=False):
    policy_path=OUT/'plan/19项用户核对裁定.json'
    policy=json.loads(policy_path.read_text(encoding='utf-8'))
    base_path=OUT/policy['base_plan_ref'];assert sha(base_path)==policy['base_plan_sha256']
    assert sha(OUT/policy['review_md_ref'])==policy['review_md_sha256']
    base=json.loads(base_path.read_text(encoding='utf-8'));assert len(base['rows'])==344
    snap_path=OUT/'match/用户反馈只读快照.json'
    if refresh:
        with session_scope() as session:
            session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            readonly=session.execute(text('SHOW transaction_read_only')).scalar()
            data={name:[dict(r) for r in session.execute(text(sql)).mappings()] for name,sql in (
                ('notices','SELECT * FROM payment_notice ORDER BY id'),('flows','SELECT * FROM payment_flow ORDER BY id'),
                ('links','SELECT * FROM jc_payment ORDER BY id'))}
            session.rollback()
        assert readonly=='on';dump(snap_path,dict(transaction_read_only=readonly,**data))
    snap=json.loads(snap_path.read_text(encoding='utf-8'));ns={n['id']:n for n in snap['notices']}
    assert snap['transaction_read_only']=='on' and len(ns)==1146 and sum(n['bill_no'].startswith('FKTZS') for n in ns.values())==1143
    by_bill={n['bill_no']:n for n in ns.values()};links={x['notice_id'] for x in snap['links']}
    records=[json.loads(s) for s in (OUT/'extract/抽取明细.jsonl').read_text(encoding='utf-8').splitlines()]
    source_map={(r['sheet'],r['line']):r for r in records}
    resolution_path=OUT/'plan/付款组合与误登记金额用户裁定.json'
    resolution=json.loads(resolution_path.read_text(encoding='utf-8'))
    correction=resolution['correction']
    assert next(f for f in snap['flows'] if f['id']==correction['flow_id'])==correction['before'],'纠错前流水已变，必须重新核验'
    rows=deepcopy(base['rows'])
    for r in rows:r['L_revision_seq']=r['seq']
    previous_jan=deepcopy(next(r for r in rows if r['notice_id']==329))
    rows=[r for r in rows if r['notice_id']!=329]
    s7=policy['problem_sources']['7']['source'];assert_payment_evidence(s7['raw'])
    day_hint=source_date(s7['raw']['I'])
    candidates=[n for n in ns.values() if money(n['amount_approved'])==money(policy['problem_7_actual_amount'])
        and '大黄蜂' in (n['payee'] or '') and '大唐雷州' in n['fields'].get('BillName','') and n['doc_date']<=s7['pay_date']]
    date_matched=[n for n in candidates if n['doc_date']==day_hint]
    assert len(date_matched)==1 and date_matched[0]['bill_no']=='FKTZS2026020340','7000同额需按I流程时间唯一消歧'
    def add(s,n,amount,basis,event_amount,allocation_count,method='现汇'):
        rows.append(dict(seq=0,L_revision_seq=None,sheet=s['sheet'],line=s['line'],bill_no=n['bill_no'],notice_id=n['id'],
            pay_date=s['pay_date'],amount=str(amount),pay_method=method,remark=f"来源：{s['sheet']}!L{s['line']}「{s['raw']['L']}」；{basis}",
            flags=dict(blank_method=False,overpay_approved=False,no_bill_no=not bool(s['bill_no']),excluded_notice=n['excluded'],
                       method_defaulted=not bool(s['pay_method']),multi_notice_allocation=allocation_count>1),
            amount_basis=basis,date_basis='L实际付款批注',revision_approval_kind='用户逐项核对后确认',
            依据=dict(source_refs=[dict(sheet=s['sheet'],line=s['line'])],source_rows=[s],actual_payment_source=s['raw'],
                      current_notice_summary={k:n.get(k) for k in ('bill_no','project_name','payee','jc_supplier','doc_date','amount_approved','excluded')},
                      match_basis=basis,original_event_amount=event_amount,allocation_count=allocation_count,
                      user_policy_ref='19项用户核对裁定.json',user_policy_sha256=sha(policy_path))))
    add(s7,date_matched[0],money(policy['problem_7_actual_amount']),
        '用户确认实付7000；同项目同单位同额两个付款前候选，用源I=2026.2.4对单据日唯一消歧，I不作实付证据','7000.00',1)
    s19=policy['problem_sources']['19']['source'];assert_payment_evidence(s19['raw'])
    targets=[by_bill[b] for b in policy['problem_19_notices']]
    assert sum((money(n['amount_approved']) for n in targets),Decimal(0))==money(s19['amount'])==Decimal('5500.00')
    assert len({n['project_name'] for n in targets})==1 and all('龙源' in n['project_name'] for n in targets)
    for n in targets:add(s19,n,money(n['amount_approved']),'用户给定两单4100＋1400＝5500，同一付款分摊到两份通知书；方式缺失授权现汇','5500.00',2)
    s10=policy['problem_sources']['10']['source'];assert_payment_evidence(s10['raw'])
    add(s10,ns[328],money(s10['amount']),'用户确认二月800000对应；依赖库内流水91先由1285654纠正为200000','800000.00',1,s10['pay_method'])
    rows[-1]['flags']['depends_on_database_correction']=True
    rows[-1]['required_correction_id']=correction['correction_id']
    rows[-1]['依据']['resolution_ref']=resolution_path.name
    rows[-1]['依据']['resolution_sha256']=sha(resolution_path)
    s11=policy['problem_sources']['11']['source'];assert_payment_evidence(s11['raw'])
    assert s11['pay_date']==resolution['problem_11']['actual_pay_date']
    add(s11,ns[329],money(s11['amount']),'用户确认只付二月13日11180；一月30日同额标注排除','11180.00',1,s11['pay_method'])
    rows[-1]['L_revision_seq']=previous_jan['L_revision_seq']
    rows[-1]['依据']['superseded_source']=previous_jan
    rows[-1]['依据']['resolution_ref']=resolution_path.name
    rows[-1]['依据']['resolution_sha256']=sha(resolution_path)
    paid=defaultdict(lambda:Decimal(0));seen=set()
    for f in snap['flows']:
        if f['status']=='effective':
            effective_amount=money(correction['after_amount']) if f['id']==correction['flow_id'] else money(f['amount'])
            paid[f['notice_id']]+=effective_amount;seen.add((f['notice_id'],str(f['pay_date']),effective_amount))
    rows.sort(key=lambda r:(r['pay_date'],r['notice_id'],r['sheet'],r['line']))
    for seq,r in enumerate(rows,1):
        r['seq']=seq;n=ns[r['notice_id']];amount=money(r['amount'])
        assert_payment_evidence(source_map[r['sheet'],r['line']]['raw'])
        for ref in r['依据'].get('source_refs',[]):assert_payment_evidence(source_map[ref['sheet'],ref['line']]['raw'])
        assert not n['i8_revoked'] and not n['revoked_joint'] and n['doc_date']<=r['pay_date']
        status='已批' if r.get('approval_exception') else n['approve_status']
        check=confirm_batch([PayRow(n['id'],status,money(n['amount_approved'])-paid[n['id']],n['category'],n['id'] in links)],
            {n['id']:PayDraft(r['pay_method'],amount)},pay_date=r['pay_date'],remark=r['remark'])
        assert not check.errors and (n['id'],r['pay_date'],amount) not in seen
        r['复核']=dict(original_approve_status=n['approve_status'],effective_approve_status=status,
             approval_amount=n['amount_approved'],paid_before=str(paid[n['id']]),paid_after=str(paid[n['id']]+amount),
             L=source_map[r['sheet'],r['line']]['raw']['L'],preflight_errors=check.errors,
             ledger_basis='已获确认但尚未执行的流水金额纠正视图' if n['id']==328 else '库内原始生效流水',
             raw_database_paid=str(sum((money(f['amount']) for f in snap['flows'] if f['status']=='effective' and f['notice_id']==n['id']),Decimal(0))))
        paid[n['id']]+=amount;seen.add((n['id'],r['pay_date'],amount))
    registered=[]
    for bill in policy['registered_august_bills']:
        n=by_bill[bill];flows=[{k:f[k] for k in ('amount','pay_date','status')} for f in snap['flows'] if f['notice_id']==n['id'] and f['status']=='effective']
        assert flows
        registered.append(dict(bill_no=bill,approval_amount=n['amount_approved'],effective_flows=flows,
             database_paid=str(sum((money(f['amount']) for f in flows),Decimal(0))),planned=str(sum((money(r['amount']) for r in rows if r['notice_id']==n['id']),Decimal(0)))))
    exclusions=[dict(problem_no=i,source=policy['problem_sources'][str(i)]['source'],reason='用户确认旧系统整行排除') for i in policy['old_system_problem_numbers']]
    pending=[]
    duplicate_exclusions=[dict(source=previous_jan,reason=resolution['problem_11']['reason'])]
    frozen=OUT/'plan/拟写入清单_用户核对后冻结.json'
    dump(frozen,dict(schema=base['schema'],source_file=base['source_file'],source_sha256=base['source_sha256'],batch=base['batch'],
         revision='numbered-feedback-v2-final',supersedes=dict(path=policy['base_plan_ref'],sha256=policy['base_plan_sha256']),
         policy_ref='19项用户核对裁定.json',policy_sha256=sha(policy_path),readonly_snapshot_sha256=sha(snap_path),
         resolution_ref=resolution_path.name,resolution_sha256=sha(resolution_path),
         required_database_corrections=[correction],actual_database_preflight_blocked_notice_ids=[328],
         approved=True,write_authorization=False,execution_ready=False,execution_limit=base['execution_limit'],
         excluded_ref='用户核对后排除与待确认.json',pending_ref='用户核对后排除与待确认.json',rows=rows))
    total=sum((money(r['amount']) for r in rows),Decimal(0))
    result=dict(count=len(rows),amount=str(total),new_entries=4,new_amount='812500.00',conditional_entries=1,conditional_amount='800000.00',required_database_corrections=[correction],date_corrected_count=1,old_system_excluded_count=len(exclusions),
         remaining_problem_numbers=[],pending_count=0,registered_august_checks=registered,
         frozen_sha256=sha(frozen),empty_L_in_plan=0,overpay_count=0,blank_method_count=0,zero_database_writes=True)
    dump(OUT/'report/用户核对后核验报告.json',result)
    dump(OUT/'plan/用户核对后排除与待确认.json',dict(old_system_exclusions=exclusions,duplicate_annotation_exclusions=duplicate_exclusions,pending=pending,
         previous_unpaid_exclusions_confirmed=True,previous_unpaid_ref='L实付更正_排除与待确认.json',
         problem_1_outcome='八月200000已登记不再新增；库内错误整额须先独立纠正，二月800000条件补录'))
    five={name:[] for name in ('未匹配','缺关联','未批','重复嫌疑','超付候选')}
    dump(OUT/'match/用户核对后五张清单.json',dict(scope='19项用户核对均已收口；库内金额纠错为执行依赖，不是超付授权',lists=five,
         counts={k:len(v) for k,v in five.items()},authorized_approval_exception_ids=[1135],required_database_corrections=[correction]))
    md=['# 用户核对已收口：最新冻结348条','',f'{len(rows)}条、{total:,.2f}元，超付例外0、空方式0、L空0。SHA256 `{sha(frozen)}`。',
        '19项主要问题均已处理，没有待你再确认的项目。本轮只冻结清单，零写库。','',
        '## 扬中蓝天：库内错误金额是执行前置依赖','',
        'FKTZS2026010195，notice_id=328，流水id=91，FL202610101629473051，2026-08-14承兑，生效。库内实记1,285,654元；你确认实际200,000元，须减少1,085,654元。完整原流水及授权原文见付款组合与误登记金额用户裁定.json。',
        '八月107行200,000元已登记，本清单不重复补。二月178行800,000元、2月13日承兑已纳入一条有条件补录；按纠正后的库付200,000＋拟补800,000＝1,000,000，审批1,285,654，余285,654。',
        '**库内现在仍是错误金额。该800,000元不能直接导入；后续必须先精确纠正流水91并重新只读核验，清单内明确绑定此依赖。本轮未更正库，也未批准超付。**','',
        '## 菘旸：只有二月一笔','',
        'FKTZS2026010194，审批11,180元，库内流水0。按你确认只保留2月份182行、2月13日11,180元现汇；1月份39行1月30日同额标注转重复排除，原文完整保留，不当作第二笔付款。','',
        '## 八月另外两张已登记','',
        'FKTZS2026020330库内8月14日100,000元，二月13日拟补97,000元仍保留，合计197,000与审批一致。FKTZS2026020332库内8月14日104,081元已付满，两张八月来源均不重复补。','',
        '## 其余已处理','',
        '问题7：实付7000，匹配FKTZS2026020340，2月10日现汇；与另一同额单据以源I=2月4日对单据日唯一消歧，实付事实仍来自L及用户确认。',
        '问题19：8月26日一笔5500，分摊FKTZS2026081938=4100及FKTZS2026081094=1400，不声称有两次银行付款；方式缺失按授权现汇。',
        '14行旧系统整行排除；附录3条L空已按你认可保持未付隔离。原月度汇总核对及其差异保留，不迁就冻结金额。',
        '五张清单均0。执行仍须解决上述流水金额纠正、历史审批漏同步单笔1135的适配器支持，并在后续写库阶段重新核验；write_authorization=false，execution_ready=false。']
    (OUT/'report/用户反馈后仍需核对.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    def cell(v):return str(v or '').replace('|','／').replace('\n',' ')
    full=['# 用户核对后完整逐笔核验','',f'{len(rows)}条，{total:,.2f}元；SHA256 `{sha(frozen)}`；零写库。',
          '本表为最新范围，原344条为历史输入。19项已收口；菘旸改二月13日；扬中蓝天800000有条件，额度按已授权但尚未执行的金额纠正视图计算。','',
          '|序号|上版序号|来源|通知书|项目|收款／集采供应商|L原文|付款日|拟付|方式|审批|库有效付＋前序预留|补后累计|',
          '|---|---|---|---|---|---|---|---|---:|---|---:|---:|---:|']
    for r in rows:
        n=ns[r['notice_id']];full.append('|'+ '|'.join(map(cell,[r['seq'],r['L_revision_seq'],f"{r['sheet']}!{r['line']}",
              r['bill_no'],n['project_name'],(n['payee'] or '')+'／'+(n.get('jc_supplier') or ''),r['复核']['L'],r['pay_date'],
              r['amount'],r['pay_method'],n['amount_approved'],r['复核']['paid_before'],r['复核']['paid_after']]))+'|')
    (OUT/'report/用户核对后完整逐笔核验.md').write_text('\n'.join(full)+'\n',encoding='utf-8')
    hold=json.loads((OUT/'plan/冻结清单执行状态.json').read_text(encoding='utf-8'))
    hold.update(replacement_ref=frozen.name,replacement_sha256=sha(frozen),replacement_status='用户核对后最新清单；19项已收口；800000条件补录须先精确纠正流水91金额；1135审批例外须后续适配')
    dump(OUT/'plan/冻结清单执行状态.json',hold)
    assert sha(base_path)==policy['base_plan_sha256']
    print(json.dumps({k:v for k,v in result.items() if k!='registered_august_checks'},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--refresh',action='store_true');main(parser.parse_args().refresh)
