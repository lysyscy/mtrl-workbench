"""TAIL-285 user-directed recheck: never use F or neighboring balances as admission."""
from collections import Counter, defaultdict
from decimal import Decimal
import hashlib
import json
import re

from _hist_extract import OUT, csv_out, dump, explicit_amount, money, payment_date, project_key
from _hist_match import PayRow, PayDraft, confirm_batch, normalize, session_scope, text, variant


def main():
    frozen_path = OUT/'plan/拟写入清单.json'
    original_sha = hashlib.sha256(frozen_path.read_bytes()).hexdigest()
    frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
    records = [json.loads(s) for s in (OUT/'extract/抽取明细.jsonl').read_text(encoding='utf-8').splitlines()]
    approved_classes = json.loads((OUT/'plan/排除与待确认.json').read_text(encoding='utf-8'))['i6_classes']
    # Keep the established i6/alternative exclusions, including every original occurrence.
    excluded_bills = {item['bill_no'] for name in ('i6','另类SBJS/FYBXSQ')
                      for item in approved_classes[name]}
    assert len(excluded_bills) == 129
    with session_scope() as session:
        session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
        readonly = session.execute(text('SHOW transaction_read_only')).scalar()
        notices = [dict(r) for r in session.execute(text('SELECT * FROM payment_notice ORDER BY id')).mappings()]
        flows = [dict(r) for r in session.execute(text('SELECT * FROM payment_flow ORDER BY id')).mappings()]
        links = [dict(r) for r in session.execute(text('SELECT * FROM jc_payment ORDER BY id')).mappings()]
        projects = [dict(r) for r in session.execute(text('SELECT id, name_full, warehouse_name, disp FROM project ORDER BY id')).mappings()]
        session.rollback()
    assert readonly == 'on'
    assert len(notices) == 1146 and sum(n['bill_no'].startswith('FKTZS') for n in notices) == 1143, '库基线变化，停止'
    dump(OUT/'match/新口径只读库快照.json', dict(transaction_read_only=readonly, notices=notices, flows=flows, links=links, projects=projects))
    bill_groups = defaultdict(list)
    for n in notices:
        bill_groups[n['bill_no']].append(n)
    duplicate_database_bills = {b: [n['id'] for n in rows] for b, rows in bill_groups.items() if len(rows) > 1}
    bybill = {b: rows[0] for b, rows in bill_groups.items() if len(rows) == 1}
    project_by_id = {p['id']:p for p in projects}
    linked = {l['notice_id'] for l in links}
    paid = defaultdict(lambda: Decimal(0))
    for flow in flows:
        if flow['status'] == 'effective':
            paid[flow['notice_id']] += money(flow['amount'])
    old_sources = {(r['sheet'],r['line']):r for r in frozen['rows']}
    old_amounts = defaultdict(lambda:Decimal(0))
    for row in frozen['rows']:
        old_amounts[row['notice_id']] += money(row['amount'])
    findings = []
    for r in records:
        raw = r['raw']
        original_reason = '；'.join(r['依据'])
        if r['classification'] == '排除' and original_reason != '负数/退回':
            continue
        if r['bill_no'] in excluded_bills or not r['annotation']:
            continue
        n = bybill.get(r['bill_no']) or bybill.get(variant(r['bill_no']))
        e, g = money(raw.get('E')), money(raw.get('G'))
        explicit = explicit_amount(r['annotation'])
        amount = explicit if explicit is not None else g
        day, date_basis = payment_date(r['annotation'],r['month'],r['annotation_col'])
        if not day and r['pay_date']:
            day, date_basis = r['pay_date'], r['date_basis']
        # A concrete day followed by 已付 is the same payment statement as 付.
        if not day and re.fullmatch(r'\d{1,2}[./月]\d{1,2}日?已付',r['annotation']):
            day, date_basis = payment_date(r['annotation'].replace('已付','付'),r['month'],r['annotation_col'])
        issues = []
        if '退回' in ' '.join(raw.values()) or (e is not None and e < 0) or (g is not None and g < 0):
            issues.append('负数/退回，不进入增补')
        if not day:
            issues.append('付款日未确证')
        if amount is None or amount <= 0:
            issues.append('实付金额无明确批注且G无正数')
        inferred_project = []
        if not n:
            issues.append('通知书未匹配；原第二轮唯一候选为0')
        else:
            project = project_by_id.get(n['ownership_id'],{})
            project_keys = {project_key(n['project_name']),project_key(project.get('disp','')),project_key(project.get('warehouse_name') or '')}
            if '无标题区间' in r['project']:
                inferred_project = [dict(sheet=x['sheet'],line=x['line'],project=x['project']) for x in records
                                    if x['bill_no'] == r['bill_no'] and project_key(x['project']) in project_keys]
                if not inferred_project:
                    issues.append('无标题区间项目缺少独立对应证据')
            elif project_key(r['project']) not in project_keys:
                issues.append('项目不一致，疑似错号/区块归属问题')
            payee_ok = normalize(r['payee']) == normalize(n['payee'])
            if n['category'] == 'jc' and n.get('jc_supplier'):
                payee_ok |= normalize(r['payee']) == normalize(n['jc_supplier'])
                supplier = re.fullmatch(r'集采[（(](.*)[）)]',r['payee'])
                payee_ok |= bool(supplier and normalize(supplier.group(1)) == normalize(n['jc_supplier']))
            if not payee_ok:
                issues.append('收款单位/已维护集采供应商不一致')
            if e != money(n['amount_approved']):
                issues.append('源流程金额与审批金额不等；分项或错号需核实')
            if n['approve_status'] != '已批' or n['excluded'] or n['i8_revoked'] or n['revoked_joint']:
                issues.append('未批/撤单/剔除')
            if n['category'] == 'jc' and n['id'] not in linked:
                issues.append('集采缺关联')
        method = {'银行承兑':'承兑','电汇':'现汇','现汇付款':'现汇'}.get(normalize(raw.get('J')), normalize(raw.get('J')))
        if method and method not in ('现汇','承兑','供应链','其他'):
            method = '其他'
        if not method:
            issues.append('空付款方式，须例外批准')
        existing = [f for f in flows if n and f['notice_id'] == n['id'] and f['status']=='effective'
                    and f['pay_date'] == day and money(f['amount']) == amount]
        if existing:
            issues.append('库内已有同日同金额生效流水')
        remark = f"来源：{r['sheet']}!{r['annotation_col']}{r['line']}「{r['annotation']}」；原方式：{raw.get('J','')}"
        if n and amount and day and not issues:
            check = confirm_batch([PayRow(n['id'],n['approve_status'],money(n['amount_approved'])-paid[n['id']],n['category'],n['id'] in linked)],
                                  {n['id']:PayDraft(method,amount)},pay_date=day,remark=remark)
            issues.extend(check.errors)
        findings.append(dict(sheet=r['sheet'],line=r['line'],project=r['project'],payee=r['payee'],bill_no=r['bill_no'],
                             matched_bill_no=n['bill_no'] if n else '',notice_id=n['id'] if n else None,
                             approval_amount=str(n['amount_approved']) if n else '',database_paid=str(paid[n['id']]) if n else '',
                             notice_project=n['project_name'] if n else '',notice_payee=n['payee'] if n else '',
                             jc_supplier=n.get('jc_supplier','') if n else '',project_evidence=inferred_project,
                             E=str(e),G=str(g),F_raw_only=raw.get('F',''),pay_date=day,date_basis=date_basis,
                             expense_date=r['expense_date'],approval_status=n['approve_status'] if n else '',
                             jc_linked=bool(n and n['id'] in linked),
                             amount=str(amount) if amount is not None else '',pay_method=method,remark=remark,
                             amount_basis='批注显式金额' if explicit is not None else 'G拟用金额＋综合身份/审批核验；需用户逐笔批准',
                             amount_evidence_strength='批注明示' if explicit is not None else 'G为计划列，未作为已付事实确证',
                             original_reason=original_reason,annotation=r['annotation'],raw=raw,issues=issues,
                             previously_approved=(r['sheet'],r['line']) in old_sources,existing_flows=existing))
    # Do not choose between different months when cumulative events exceed approval.
    groups = defaultdict(list)
    for row in findings:
        if not row['issues']:
            groups[row['notice_id']].append(row)
    for nid, rows in groups.items():
        total = sum((money(r['amount']) for r in rows),Decimal(0))
        if paid[nid] + total > money(rows[0]['approval_amount']):
            for row in rows:
                row['issues'].append(f'多来源累计超审批；本组拟付{total}，不得自动选择付款事件')
    additional = [r for r in findings if not r['issues'] and not r['previously_approved']]
    old_review = [r for r in findings if r['previously_approved']]
    assert len(old_review) == 34
    simulated = defaultdict(lambda:Decimal(0),old_amounts)
    for seq,row in enumerate(additional,35):
        nid = row['notice_id']
        simulated[nid] += money(row['amount'])
        row.update(seq=seq,paid_after_original_and_supplement=str(paid[nid]+simulated[nid]),
                   balance_after=str(money(row['approval_amount'])-paid[nid]-simulated[nid]),
                   flags=dict(blank_method=False,overpay_approved=False,no_bill_no=False))
        assert money(row['balance_after']) >= 0
    unresolved = [r for r in findings if r['issues']]
    for row in unresolved:
        suggestions=[]
        if row['notice_id'] is None and row['payee'] and money(row['E']) is not None:
            for n in notices:
                p=project_by_id.get(n['ownership_id'],{})
                keys={project_key(n['project_name']),project_key(p.get('disp','')),project_key(p.get('warehouse_name') or '')}
                if (project_key(row['project']) in keys and money(row['E'])==money(n['amount_approved'])
                    and normalize(row['payee']) in (normalize(n['payee']),normalize(n.get('jc_supplier','')))):
                    suggestions.append(dict(bill_no=n['bill_no'],notice_id=n['id'],doc_date=str(n['doc_date']),
                                            expense_date_matches=str(n['doc_date'])==row['expense_date'],
                                            basis='项目/收款/流程金额三要素仅供查错号；缺费用日一致不得自动采用'))
        row['wrong_bill_hints']=suggestions
    report = dict(rule='用户2026-10-11：抛弃邻月佐证与E−F＝G判据；F仅原文，金额按批注优先/G拟用，综合身份核验与准入',
                  user_quote='这玩意根本不靠谱，已付金额不一定是对的；抛弃这个判据，继续核验',
                  original_plan_sha256=original_sha,total_payment_annotation_rows=len(findings),
                  duplicate_database_bills=duplicate_database_bills,
                  additional_count=len(additional),additional_amount=str(sum((money(r['amount']) for r in additional),Decimal(0))),
                  old_approved_review=old_review,issue_counts=dict(Counter(i for r in findings for i in r['issues'])),rows=findings)
    dump(OUT/'report/新口径综合核验.json',report)
    csv_out(OUT/'report/新口径综合核验.csv',findings,list(findings[0]))
    dump(OUT/'plan/增补候选_待逐笔批准.json',dict(approved=False,original_plan_sha256=original_sha,
        count=len(additional),amount=report['additional_amount'],rule=report['rule'],rows=additional))
    csv_out(OUT/'plan/增补候选_待逐笔批准.csv',additional,list(findings[0])+['seq','paid_after_original_and_supplement','balance_after','flags'])
    dump(OUT/'report/新口径剩余问题.json',dict(count=len(unresolved),primary_counts=dict(Counter(r['issues'][0] for r in unresolved)),rows=unresolved))
    csv_out(OUT/'report/新口径剩余问题.csv',unresolved,list(findings[0])+['wrong_bill_hints'])
    def cell(value):
        return str(value).replace('|','／').replace('\n',' ')
    lines=['# 历史付款增补候选 · 待逐笔批准','',
           f"新增{len(additional)}笔，{report['additional_amount']}元；原34笔哈希未改。零写库。",
           'F与邻月金额均不参与准入。审批金额用于核对流程身份及限额，不代表实际付款。金额来源标为G的行仍是拟用金额，需逐条批准。',
           '补后余额含原34笔批准额及本次同通知书候选的累计额；库内已付只取生效流水。','',
           '|序号|来源|项目|收款单位（源）|库内收款／集采供应商|通知书|源流程＝审批|库内已付|拟补金额|付款日|方式|金额依据|补后余额|',
           '|---|---|---|---|---|---|---:|---:|---:|---|---|---|---:|']
    for row in additional:
        vals=[row['seq'],f"{row['sheet']}!{row['line']}",row['project'],row['payee'],
              row['notice_payee']+'／'+row['jc_supplier'],row['matched_bill_no'],row['approval_amount'],
              row['database_paid'],row['amount'],row['pay_date'],row['pay_method'],
              '批注明示' if row['amount_evidence_strength']=='批注明示' else '付款日期批注＋G拟用金额',row['balance_after']]
        lines.append('|'+ '|'.join(cell(v) for v in vals)+'|')
    (OUT/'report/新增候选完整审阅.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    assert hashlib.sha256(frozen_path.read_bytes()).hexdigest() == original_sha
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','old_approved_review')},ensure_ascii=False))
    print('原34笔复核问题数',sum(bool(r['issues']) for r in old_review))


if __name__ == '__main__':
    main()
