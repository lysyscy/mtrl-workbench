"""Delegate-authorized historical review; SELECT-only refresh, offline deterministic plan."""
import argparse
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from itertools import combinations
import json
import re

from _hist_extract import OUT, BILL, dump, csv_out, money, project_key, source_date
from _hist_match import PayRow, PayDraft, confirm_batch, session_scope, text, normalize
from _hist_freeze_13 import sha


def pkey(value):
    if any(t in value for t in ('三峡','离网制氢','乌兰察布','鄂旗','压缩空气')):
        return '内蒙储能'
    for token in ('焦作','佰利','方城','南靖'):
        if token in value:
            return '焦作佰利' if token in ('焦作','佰利') else token
    return project_key(value)


def refresh():
    with session_scope() as session:
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        readonly=session.execute(text('SHOW transaction_read_only')).scalar()
        data={k:[dict(r) for r in session.execute(text(sql)).mappings()] for k,sql in (
            ('notices','SELECT * FROM payment_notice ORDER BY id'),
            ('flows','SELECT * FROM payment_flow ORDER BY id'),
            ('links','SELECT * FROM jc_payment ORDER BY id'),
            ('projects','SELECT id, name_full, warehouse_name, disp FROM project ORDER BY id'))}
        session.rollback()
    assert readonly=='on'
    assert len(data['notices'])==1146 and sum(n['bill_no'].startswith('FKTZS') for n in data['notices'])==1143,'库内基线变化，停止'
    dump(OUT/'match/自主核验只读快照.json',dict(transaction_read_only=readonly,**data))


def main(do_refresh=False):
    hold=OUT/'plan/冻结清单执行状态.json'
    if hold.exists() and json.loads(hold.read_text(encoding='utf-8')).get('status')=='hold':
        raise SystemExit('冻结清单暂停：用户确认L空代表未付；先修订三月付款证据口径，禁止重生旧343条清单')
    if do_refresh:
        refresh()
    config=json.loads((OUT/'plan/自主核验执行口径.json').read_text(encoding='utf-8'))
    checkpoint=json.loads((OUT/'report/核验接续状态.json').read_text(encoding='utf-8'))
    # The initial 296-row checkpoint is a fixed input; the result is saved separately.
    assert checkpoint['count']==296
    protected={f['path']:f['sha256'] for f in checkpoint['approved_files']}
    assert all(sha(OUT/p)==digest for p,digest in protected.items())
    approved=[r for p in protected for r in json.loads((OUT/p).read_text(encoding='utf-8'))['rows']]
    assert len(approved)==296
    snap_path=OUT/'match/自主核验只读快照.json'
    snap=json.loads(snap_path.read_text(encoding='utf-8'))
    ns={n['id']:n for n in snap['notices']}; linked={l['notice_id'] for l in snap['links']}
    assert len(ns)==1146 and snap['transaction_read_only']=='on'
    ownership={p['id']:p for p in snap['projects']}
    by_bill=defaultdict(list)
    for n in ns.values():by_bill[n['bill_no']].append(n)
    paid=defaultdict(lambda:Decimal(0)); seen=set(); assigned=set()
    for f in snap['flows']:
        if f['status']=='effective':
            paid[f['notice_id']]+=money(f['amount']); seen.add((f['notice_id'],str(f['pay_date']),money(f['amount'])))
    for r in approved:
        fingerprint=r['notice_id'],r['pay_date'],money(r['amount'])
        assert fingerprint not in seen,'批准清单已在当前库出现同日同额，停止并报告'
        seen.add(fingerprint); paid[r['notice_id']]+=money(r['amount']); assigned.add(r['notice_id'])
        assert paid[r['notice_id']]<=money(ns[r['notice_id']]['amount_approved']),'原批准清单在当前库累计超额，停止并报告'
    records=[json.loads(s) for s in (OUT/'extract/抽取明细.jsonl').read_text(encoding='utf-8').splitlines()]
    summary_dates=defaultdict(list)
    columns={'4月汇总':(4,'B','D'),'汇总5':(5,'D','C'),'汇总6':(6,'C','B'),'汇总7':(7,'D','C'),'汇总8':(8,'E','D')}
    for r in records:
        if r['sheet'] not in columns:continue
        month,pc,dc=columns[r['sheet']]; day=source_date(r['raw'].get(dc))
        if day:summary_dates[(month,pkey(r['raw'].get(pc,'')))].append(dict(sheet=r['sheet'],line=r['line'],date=day,raw=r['raw']))
    cases=json.loads((OUT/'report/剩余110行核查.json').read_text(encoding='utf-8'))['rows']
    assert len(cases)==110
    def project_ok(s,n):
        hint=s['project']
        raw_hint=s['raw'].get('C','')
        if not BILL.match(raw_hint) and raw_hint in ('安徽国风','国风'):
            hint=raw_hint
        p=ownership.get(n['ownership_id'],{})
        values=[n['project_name'],n['fields'].get('BillName',''),p.get('disp',''),p.get('warehouse_name') or '']
        return any(pkey(hint)==pkey(v) or (hint and hint in v) for v in values)
    def vendor_score(s,n):
        def meaningful(value):
            value=normalize(value or '')
            for token in ('有限责任公司','有限公司','商贸','科技','设备','工程','集采'):
                value=value.replace(token,'')
            return value
        source=meaningful(s['payee'])
        values=[meaningful(n['payee']),meaningful(n.get('jc_supplier','')),meaningful(n['fields'].get('BillName',''))]
        if source and any(source in v or (v and v in source) for v in values):return 100
        return max((len(source[i:j]) for i in range(len(source)) for j in range(i+3,len(source)+1)
                    if any(source[i:j] in v for v in values)),default=0)
    def day_for(s):
        if s['pay_date']:return s['pay_date'],s['date_basis'],[]
        a=s['annotation'].strip()
        m=re.fullmatch(r'(\d{1,2})[./月](\d{1,2})(?:日|号)?(?:付(?:款)?)?',a)
        if m:
            try:return date(2026,*map(int,m.groups())).isoformat(),'用户允许裸月日/跨月付款批注',[]
            except ValueError:return '', '非法日期',[]
        if a=='√' or re.fullmatch(r'付\s*\d+(?:\.\d+)?\s*万',a) or '已付款' in a:
            month=int(re.search(r'(\d+)月',s['sheet']).group(1))
            evidence=summary_dates.get((month,pkey(s['project'])),[])
            unique={x['date'] for x in evidence}
            if len(unique)==1:return next(iter(unique)),'自主择用同项目当月唯一已付款汇总日期',evidence
        return '', '无实际付款日',[]
    def method_for(s):
        for value in ('现汇','承兑','供应链'):
            if value in s['annotation']:return value,'付款批注明示'
        raw=s['raw'].get('J','')
        if any(t in raw for t in ('承兑','银承')):return '承兑','源J承兑/银承'
        if raw in ('现汇','电汇'):return '现汇','源J'
        if raw in ('现金','其他'):return '其他','源J现金/其他，原文入备注'
        if s['pay_method'] in ('现汇','承兑','供应链'):
            return s['pay_method'],'此前可识别方式'
        return '现汇','用户授权无法识别/缺失方式兜底'
    def eligible(n,day):
        return (n['approve_status']=='已批' and not n['i8_revoked'] and not n['revoked_joint']
                and bool(n['doc_date']) and str(n['doc_date'])<=day
                and (n['category']!='jc' or n['id'] in linked)
                and money(n['amount_approved'])>paid[n['id']])
    groups=defaultdict(list)
    for c in cases:
        s=c['source']; day,_,_=day_for(s)
        if c['current_notice'] and day and money(s['amount']) is not None:
            groups[s['notice_id']].append(c)
    duplicate_refs={}; blocked_groups=set()
    for nid,group in groups.items():
        if len(group)<2 or not any('多来源累计超审批' in i for c in group for i in c['remaining_issues']):continue
        amounts={money(c['source']['amount']) for c in group}
        if len(amounts)==1 and next(iter(amounts))==money(ns[nid]['amount_approved']):
            ordered=sorted(group,key=lambda c:(day_for(c['source'])[0],c['source']['sheet'],c['source']['line']))
            first=ordered[0]['source']; duplicate_refs[(first['sheet'],first['line'])]=ordered
        else:blocked_groups.add(nid)
    rows=[]; outcomes={}; exceptions=[]
    def finish(group,kind,reason,**extra):
        for c in group:
            s=c['source']; key=s['sheet'],s['line']
            assert key not in outcomes
            outcomes[key]=dict(source=s,outcome=kind,reason=reason,**extra)
    def add(group,allocations,day,basis,evidence,match_basis,aggregate=False):
        s=group[0]['source']; method,method_basis=method_for(s)
        event_amount=sum((amount for _,amount in allocations),Decimal(0))
        assert event_amount==(sum((money(c['source']['amount']) for c in group),Decimal(0)) if aggregate else money(s['amount']))
        refs=[dict(sheet=c['source']['sheet'],line=c['source']['line']) for c in group]
        for n,amount in allocations:
            remark=s['remark']+'；自主核定；方式依据：'+method_basis
            if len(group)>1:remark+=('；同日费用分项按唯一审批总額合并，银行实际笔数未另证' if aggregate else '；跨月重复列示择最早日期，全部来源保留')
            if len(allocations)>1:remark+='；同一原付款按多份通知书分摊'
            cap=money(n['amount_approved'])-paid[n['id']]
            checked=confirm_batch([PayRow(n['id'],n['approve_status'],cap,n['category'],n['id'] in linked)],
                                  {n['id']:PayDraft(method,amount)},pay_date=day,remark=remark)
            assert not checked.errors and (n['id'],day,amount) not in seen
            seq=297+len(rows)
            flags=dict(blank_method=False,overpay_approved=False,no_bill_no=not bool(BILL.match(s['bill_no'])),
                       excluded_notice=bool(n['excluded']),method_defaulted='兜底' in method_basis,
                       date_chosen=(len(group)>1 and not aggregate) or bool(evidence),multi_notice_allocation=len(allocations)>1,
                       source_item_aggregation=aggregate)
            rows.append(dict(seq=seq,sheet=s['sheet'],line=s['line'],bill_no=n['bill_no'],notice_id=n['id'],pay_date=day,
                amount=str(amount),pay_method=method,remark=remark,flags=flags,date_basis=basis,amount_basis=s['amount_basis'],
                依据=dict(source_refs=refs,source_rows=[c['source'] for c in group],match_basis=match_basis,
                    notice_summary={k:n.get(k) for k in ('id','bill_no','project_name','payee','jc_supplier','doc_date','amount_approved','excluded')},
                    original_event_amount=str(event_amount),allocation_count=len(allocations),date_evidence=evidence,
                    method_basis=method_basis,paid_before=str(paid[n['id']]),paid_after=str(paid[n['id']]+amount),
                    preflight_errors=checked.errors,approval_kind='用户授权自主核定')))
            if n['excluded']:exceptions.append(dict(seq=seq,kind='excluded_notice',approved=True,basis='用户允许其他业务口代付，保留剔除状态'))
            paid[n['id']]+=amount; seen.add((n['id'],day,amount)); assigned.add(n['id'])
        finish(group,'自主核定',match_basis,allocation_notice_ids=[n['id'] for n,_ in allocations])
    # Contiguous same-day source items are only merged when their exact sum has one
    # unused same-project/supplier approval. H totals, where present, must agree.
    item_groups=defaultdict(list)
    for c in cases:
        s=c['source']; day,_,_=day_for(s)
        if not s['bill_no'] and day and money(s['amount']) and money(s['amount'])>0:
            item_groups[(s['sheet'],s['project'],normalize(s['payee']),day)].append(c)
    for key,group in sorted(item_groups.items()):
        group=sorted(group,key=lambda c:c['source']['line'])
        if len(group)<2 or max(c['source']['line'] for c in group)-min(c['source']['line'] for c in group)!=len(group)-1:continue
        total=sum((money(c['source']['amount']) for c in group),Decimal(0))
        declared=[money(c['source']['raw'].get('H')) for c in group if money(c['source']['raw'].get('H'))]
        if declared and any(x!=total for x in declared):continue
        s=group[0]['source']; day,basis,evidence=day_for(s)
        pool=[n for n in ns.values() if eligible(n,day) and n['id'] not in assigned and project_ok(s,n)
              and vendor_score(s,n)>=3 and money(n['amount_approved'])==total and paid[n['id']]==0]
        if len(pool)==1:
            add(group,[(pool[0],total)],day,basis,evidence,'连续同单位同日费用分项合计等于唯一审批；H原文合计留证，银行笔数未另证',aggregate=True)
    ordered=sorted(cases,key=lambda c:(c['current_notice'] is None,day_for(c['source'])[0] or '9999',c['source']['sheet'],c['source']['line']))
    for c in ordered:
        s=c['source']; key=s['sheet'],s['line']
        if key in outcomes:continue
        if any('负数/退回' in i for i in c['remaining_issues']):
            finish([c],'排除/退回','源文明确退回/未收到承兑，未当作成功支付');continue
        if any(t in s['annotation'] for t in ('货到','验收合格','回款后','进度款到','（删除）')):
            finish([c],'佐证/付款条件','付款条件或删除说明不证明实际支付');continue
        amount=money(s['amount'])
        if amount is None or amount<=0:
            finish([c],'待确认','实付金额无可用依据，不能凭审批造付款');continue
        day,basis,evidence=day_for(s)
        if not day:
            finish([c],'待确认','没有可用实际付款日或同项目唯一汇总日期');continue
        if s['notice_id'] in blocked_groups:
            finish([c],'待确认','同单两月金额不同且累计超额，无法确定实际付款组合');continue
        group=duplicate_refs.get(key,[c])
        if s['notice_id'] in groups and len(groups[s['notice_id']])>1 and any(
            (x['source']['sheet'],x['source']['line']) in duplicate_refs for x in groups[s['notice_id']]) and len(group)==1:
            continue
        exact=by_bill.get(s['bill_no'],[])
        if len(exact)==1:
            n=exact[0]
            if n['approve_status']!='已批' or n['i8_revoked'] or n['revoked_joint']:
                finish(group,'待确认','未批或真正撤单，剔除代付授权不等于更改审批状态');continue
            if (n['id'],day,amount) in seen:
                finish(group,'库内已有/已含批准','同通知书同日同额已在库或批准清单');continue
            if eligible(n,day) and amount<=money(n['amount_approved'])-paid[n['id']]:
                add(group,[(n,amount)],day,basis,evidence,'编号唯一命中，付款时序及余额符合；源流程差异留原文');continue
            if eligible(n,day) and amount>money(n['amount_approved'])-paid[n['id']]:
                pool=[x for x in ns.values() if eligible(x,day) and x['id'] not in assigned and x['id']!=n['id']
                      and x['project_name']==n['project_name'] and normalize(x['payee'])==normalize(n['payee'])
                      and money(x['amount_approved'])==money(x['amount_approved'])-paid[x['id']]]
                options=[]
                for size in (1,2):
                    for rest in combinations(pool,size):
                        parts=[n,*rest]
                        if sum((money(x['amount_approved'])-paid[x['id']] for x in parts),Decimal(0))==amount:
                            options.append(parts)
                if len(options)==1:
                    add(group,[(x,money(x['amount_approved'])-paid[x['id']]) for x in options[0]],day,basis,evidence,
                        '源金额等同项目同单位的唯一未占用审批组合，同一付款按通知书分摊');continue
            # A mistyped existing bill can only be replaced by a unique full
            # amount + project + meaningful supplier + prior-date alternative.
            alternatives=[x for x in ns.values() if eligible(x,day) and x['id'] not in assigned
                          and project_ok(s,x) and vendor_score(s,x)>=3
                          and money(x['amount_approved'])==amount and paid[x['id']]==0]
            if len(alternatives)==1 and not project_ok(s,n):
                add(group,[(alternatives[0],amount)],day,basis,evidence,'原单号对应异项目且金额不符；同额同项目同单位时序唯一替代，保留原错号');continue
            finish(group,'待确认','同号但当前余额/时序/关联不足或累计超额，未裁剪金额');continue
        target=money(s['E']) or amount
        pool=[n for n in ns.values() if eligible(n,day) and n['id'] not in assigned and project_ok(s,n)
              and (money(n['amount_approved'])==target or money(n['amount_approved'])==amount)
              and amount<=money(n['amount_approved'])-paid[n['id']]]
        exact_flow=[n for n in pool if money(n['amount_approved'])==target]
        if exact_flow:pool=exact_flow
        if len(pool)>1:
            scored=[(vendor_score(s,n),n) for n in pool]; best=max(score for score,_ in scored)
            pool=[n for score,n in scored if score==best] if best>=3 else pool
        if not pool:
            pool=[n for n in ns.values() if eligible(n,day) and n['id'] not in assigned and project_ok(s,n)
                  and vendor_score(s,n)>=3 and amount<=money(n['amount_approved'])-paid[n['id']]]
        if len(pool)==1:
            add(group,[(pool[0],amount)],day,basis,evidence,'无可用编号，金额＋项目/标题匹配唯一；重复金额用单位参考消歧');continue
        blocked=[]
        if not pool:
            for n in ns.values():
                if project_ok(s,n) and vendor_score(s,n)>=3 and money(n['amount_approved']) in (target,amount):
                    reasons=[]
                    if n['id'] in assigned:reasons.append('通知书已含此前批准/本次分录')
                    if money(n['amount_approved'])-paid[n['id']]<amount:reasons.append('当前库有效流水＋冻结预留后余额不足')
                    if str(n['doc_date'] or '')>day:reasons.append('单据日期晚于付款线索')
                    if n['approve_status']!='已批':reasons.append('未批')
                    if n['i8_revoked'] or n['revoked_joint']:reasons.append('真正撤单')
                    if n['category']=='jc' and n['id'] not in linked:reasons.append('缺集采关联')
                    blocked.append(dict(notice_id=n['id'],bill_no=n['bill_no'],amount_approved=n['amount_approved'],
                                        doc_date=n['doc_date'],reserved_and_paid=str(paid[n['id']]),reasons=reasons))
        finish(group,'待确认','无唯一可用通知书；同额身份线索被余额/时序等阻断' if blocked else (
               '无唯一通知书候选' if not pool else '多个通知书候选，证据不足以唯一消歧'),
               candidate_ids=[n['id'] for n in pool],blocked_identity_candidates=blocked)
    assert len(outcomes)==110,'来源覆盖不全，停止'
    total=sum((money(r['amount']) for r in rows),Decimal(0))
    original=json.loads((OUT/'plan/拟写入清单.json').read_text(encoding='utf-8'))
    frozen=OUT/'plan/自主核定冻结增补清单.json'
    dump(frozen,dict(schema='hist-supplement/1',generated_at=config['generated_at'],source_file=original['source_file'],
         source_sha256=original['source_sha256'],batch=original['batch'],approved=True,approval_kind='用户授权自主核定',
         policy_ref='自主核验与其他口代付用户裁定.json',policy_sha256=sha(OUT/'plan/自主核验与其他口代付用户裁定.json'),
         source_approved_plans=protected,readonly_snapshot_sha256=sha(snap_path),exceptions=exceptions,
         excluded_ref='自主核验排除与待确认.json',pending_ref='自主核验排除与待确认.json',rows=rows))
    view=list(outcomes.values()); counts=dict(Counter(r['outcome'] for r in view))
    lists={name:[] for name in ('未匹配','缺关联','未批','重复嫌疑','超付候选')}
    for x in view:
        if x['outcome']=='自主核定':continue
        s=x['source']; n=ns.get(s['notice_id']); amount=money(s['amount'])
        entry=dict(sheet=s['sheet'],line=s['line'],bill_no=s['bill_no'],notice_id=s['notice_id'],
                   amount=s['amount'],pay_date=s['pay_date'],reason=x['reason'])
        if x['outcome']=='待确认' and n is None:lists['未匹配'].append(entry)
        if n and n['category']=='jc' and n['id'] not in linked:lists['缺关联'].append(entry)
        if n and (n['approve_status']!='已批' or n['i8_revoked'] or n['revoked_joint']):lists['未批'].append(entry)
        if x['outcome']=='库内已有/已含批准' or '两月金额不同' in x['reason'] or x.get('blocked_identity_candidates'):
            lists['重复嫌疑'].append(entry)
        if n and x['outcome']=='待确认' and amount and amount+paid[n['id']]>money(n['amount_approved']):
            lists['超付候选'].append({**entry,'approval_amount':n['amount_approved'],'paid_and_reserved':str(paid[n['id']]),
                                      'simulated_after':str(amount+paid[n['id']])})
    dump(OUT/'match/自主核验五张清单.json',dict(scope='本次110行；只列未解除事项，各清单非互斥，不能相加作为总行数',
         original_report_ref='核对报告.json',readonly_snapshot_sha256=sha(snap_path),counts={k:len(v) for k,v in lists.items()},lists=lists))
    dump(OUT/'plan/自主核验排除与待确认.json',dict(source_count=110,outcome_counts=counts,rows=view))
    result=dict(human_approved_count=296,human_approved_amount='18728676.85',delegated_entry_count=len(rows),
         delegated_amount=str(total),combined_entry_count=296+len(rows),combined_amount=str(Decimal('18728676.85')+total),
         outcome_counts=counts,excluded_notice_count=sum(r['flags']['excluded_notice'] for r in rows),
         default_method_count=sum(r['flags']['method_defaulted'] for r in rows),exceptions=exceptions,
         frozen_sha256=sha(frozen),zero_database_writes=True,rows=rows)
    result['five_list_counts']={k:len(v) for k,v in lists.items()}
    dump(OUT/'report/自主核验报告.json',result)
    csv_out(OUT/'report/自主核验逐行结果.csv',[dict(sheet=x['source']['sheet'],line=x['source']['line'],
         bill_no=x['source']['bill_no'],project=x['source']['project'],payee=x['source']['payee'],amount=x['source']['amount'],
         outcome=x['outcome'],reason=x['reason'],allocation_notice_ids=x.get('allocation_notice_ids',[]),candidate_ids=x.get('candidate_ids',[])) for x in view],
         ['sheet','line','bill_no','project','payee','amount','outcome','reason','allocation_notice_ids','candidate_ids'])
    complete=OUT/'plan/拟写入清单_全部核验冻结.json'
    dump(complete,dict(schema=original['schema'],generated_at=config['generated_at'],source_file=original['source_file'],
         source_sha256=original['source_sha256'],batch=original['batch'],approved=True,
         approval_scope=dict(human_individually_approved=296,delegated_review=len(rows)),
         plan_refs={**protected,'plan/自主核定冻结增补清单.json':sha(frozen)},
         readonly_snapshot_sha256=sha(snap_path),exceptions=exceptions,rows=[*approved,*rows],
         excluded_ref='自主核验排除与待确认.json',pending_ref='自主核验排除与待确认.json'))
    result['combined_frozen_sha256']=sha(complete)
    result['protected_original_plans']=protected
    result['fixed_source_coverage']=dict(previously_approved_sources=297,new_review_sources=110,
                                       combined_sources=407,new_accepted_sources=counts.get('自主核定',0))
    dump(OUT/'report/自主核验报告.json',result)
    dump(OUT/'report/自主核验接续状态.json',{k:v for k,v in result.items() if k!='rows'})
    def cell(value):return str(value or '').replace('|','／').replace('\n',' ')
    human=['# 自主核验完整审阅','',f'原逐项批准296笔：18,728,676.85元；本次授权自主核定{len(rows)}条通知书付款分录：{total:,.2f}元。',
           f'合并{296+len(rows)}条：{Decimal("18728676.85")+total:,.2f}元。全程零写库。',
           '',f'增补SHA256：`{sha(frozen)}`；合并SHA256：`{sha(complete)}`。','',
           '跨月同单同全额重复列示择最早有效批注，只计一次；这是自主判断，原文双来源保留。',
           '同日连续费用分项按唯一通知书审批合计归并，银行实际笔数未另证；一笔源付款分摊多个通知书时，分录条数不等于银行笔数。',
           '勾号/已付而无日期的行，采用同项目当月唯一已付款汇总日期，并在每条证据中注明推定；付款条件、退回、缺金额不生成付款。',
           '', '|序号|来源|通知书|项目／收款|审批额|付款日|拟付款|方式|核验依据|',
           '|---|---|---|---|---:|---|---:|---|---|']
    for r in rows:
        ev=r['依据']; n=ev['notice_summary']; refs='、'.join(f"{x['sheet']}!{x['line']}" for x in ev['source_refs'])
        human.append('|'+ '|'.join(map(cell,[r['seq'],refs,r['bill_no'],n['project_name']+'／'+(n['payee'] or ''),
                     n['amount_approved'],r['pay_date'],r['amount'],r['pay_method'],ev['match_basis']]))+'|')
    for r in rows:
        ev=r['依据'];human.extend(['',f"## 序号{r['seq']} · {r['bill_no']}",'',
            f"库内单据日：{ev['notice_summary']['doc_date']}；原剔除状态：{ev['notice_summary']['excluded']}。",
            f"累计已付＋此前冻结预留：{ev['paid_before']}；本次后累计：{ev['paid_after']}；审批：{ev['notice_summary']['amount_approved']}。准入错误：0。",
            f"日期依据：{r['date_basis']}；方式依据：{ev['method_basis']}；原付款总额：{ev['original_event_amount']}；分摊通知书数：{ev['allocation_count']}。"])
        for s in ev['source_rows']:
            human.extend(['',f"来源 {s['sheet']}!{s['line']}：原编号 {s['bill_no'] or '无'}；项目 {s['project']}；单位 {s['payee']}；E流程 {s['E']}；G计划 {s['G']}；付款批注「{s['annotation']}」。",
                          '原行：`'+json.dumps(s['raw'],ensure_ascii=False)+'`'])
        if ev['date_evidence']:human.append('汇总日期原文：`'+json.dumps(ev['date_evidence'],ensure_ascii=False)+'`')
    human.extend(['','# 剩余问题逐行证据','',f"待确认{counts.get('待确认',0)}行；退回{counts.get('排除/退回',0)}行；库内已有{counts.get('库内已有/已含批准',0)}行；付款条件等佐证{counts.get('佐证/付款条件',0)}行。",'',
                  '|来源|原单号|项目|单位|E流程|拟金额|付款批注|结论|原因／候选|',
                  '|---|---|---|---|---:|---:|---|---|---|'])
    for x in view:
        if x['outcome']=='自主核定':continue
        s=x['source']; extra=json.dumps(x.get('blocked_identity_candidates',x.get('candidate_ids',[])),ensure_ascii=False)
        human.append('|'+ '|'.join(map(cell,[f"{s['sheet']}!{s['line']}",s['bill_no'],s['project'],s['payee'],s['E'],s['amount'],s['annotation'],x['outcome'],x['reason']+'；'+extra]))+'|')
    (OUT/'report/自主核验完整审阅.md').write_text('\n'.join(human)+'\n',encoding='utf-8')
    assert all(sha(OUT/p)==digest for p,digest in protected.items())
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','exceptions')},ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--refresh',action='store_true')
    main(parser.parse_args().refresh)
