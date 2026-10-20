"""归档脚本：只读提取一至九月机械报表并生成原型输入。"""
from pathlib import Path
from openpyxl import load_workbook
from datetime import date,datetime
from decimal import Decimal
import json,re,hashlib

ROOT=Path('D:/工作/材料/材机报表'); OUT=Path('.artifacts/machinery-fee-workflow/prototype-20261017')
money=lambda v:None if v is None or not isinstance(v,(int,float,Decimal)) else float(Decimal(str(v))*100)
txt=lambda v:'' if v is None else v.strftime('%Y-%m-%d') if isinstance(v,(date,datetime)) else str(v)
norm=lambda v:re.sub(r'\s+','',txt(v))
canon=lambda n:{'内蒙古宜化项目':'内蒙宜化项目'}.get(norm(n),norm(n))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
source={};hashes={};names=[]
for m in range(1,10):
    path=ROOT/f'{m}月'/f'第四工程公司{m}月份外租机械费报表.xlsx';before=sha(path)
    wb=load_workbook(path,data_only=True,read_only=True)
    source[m]={s.title:list(s.values) for s in wb};wb.close();assert sha(path)==before
    hashes[str(path)]={'before':before,'after':sha(path)}
    for r in source[m]['年度汇总'][1:]:
        if norm(r[1]) in ['当月零租费','当月包月费','当月周材费','当月内租费'] and r[0]:
            n=canon(r[0])
            if n not in names:names.append(n)
    for r in source[m]['工程公司汇总表'][5:]:
        if isinstance(r[0],(int,float)) and r[1] and canon(r[1]) not in names:names.append(canon(r[1]))
live=json.loads(Path('.artifacts/machinery-fee-workflow/live-capture-20261017/i8-lists.json').read_text(encoding='utf-8'))
for k,v in live['lists'].items():assert int(v['total'])==len(v['rows']),k
mapping={'3700000000002880':'龙源纸业项目','3700000000001488':'新疆慧能项目','3700000000003163':'内蒙宜化项目','3700000000001821':'晋江污泥项目','3700000000002422':'灵宝二期项目','3700000000003176':'福建南平项目','3700000000003199':'安徽国风项目','3700000000001485':'新疆普康项目','3700000000001823':'乌兰察布储能项目','3700000000001631':'2025泗阳锅炉','3700000000001527':'沭阳项目'}
project_names={r['projectId']:r['projectName'] for v in live['lists'].values() for r in v['rows']}
for pid,n in project_names.items():
    if pid not in mapping:
        # Preserve the actual i8 project separately until its report identity is established.
        mapping[pid]='i8：'+n
        names.append(mapping[pid])
idx={n:i for i,n in enumerate(names)};months=[f'2026-{m:02}' for m in range(1,10)]
catmap={'当月零租费':'zero','当月包月费':'monthly','当月周材费':'weekly','当月内租费':'internal'}
fields=['zero','monthly','weekly','internal','company'];records={};cumAt={};metaAt={};reported={};feeBase=[None]*len(names);feeBaseSource=['']*len(names);fixed=[None]*len(names);latestCats=[{} for n in names];latestMonthly={};quality=[];rows=[];stats={}
referenceAt={};baseMonth=[None]*len(names)
def val(r,i):return r[i] if r is not None and i is not None and i<len(r) else None
def tax(v):
    if v is None:return ''
    if isinstance(v,(int,float)):
        return '专票'+str(float(v)*100).removesuffix('.0')+'%' if 0<float(v)<1 else ''
    v=txt(v)
    if '普票' in v:return '普票'
    found=re.search(r'(\d+(?:\.\d+)?)\s*%',v)
    return '专票'+found[1]+'%' if found and float(found[1]) in [1,3,6,9,13] else ''
for m,sheets in source.items():
    ym=f'2026-{m:02}';path=ROOT/f'{m}月'/f'第四工程公司{m}月份外租机械费报表.xlsx'
    ar={};totalrows={}
    for r in sheets['年度汇总'][1:]:
        n=canon(r[0]);c=norm(r[1])
        if n not in idx:continue
        if c in catmap:ar[n,catmap[c]]=r
        if c=='合计':totalrows[n]=r
    # Locate the 2026 column by its real Excel date, never by the duplicate month number.
    annual_header=sheets['年度汇总'][0];monthcols={}
    from openpyxl.utils.datetime import from_excel
    for j,v in enumerate(annual_header):
        if isinstance(v,(int,float)) and 45000<v<47000:
            d=from_excel(v)
            if d.year==2026:monthcols[d.month]=j
    assert set(range(1,10)).issubset(monthcols),m
    report={canon(r[1]):r for r in sheets['工程公司汇总表'][5:] if isinstance(r[0],(int,float)) and r[1]}
    reported[ym]=[idx[n] for n in report];hdr=[norm(v) for v in sheets['工程公司汇总表'][4]]
    monthly_cols={c:next((j for j,v in enumerate(hdr) if v==label),None) for c,label in [('zero','当月零租费'),('monthly','当月包月费'),('weekly','当月周材费')]}
    monthly_cols['internal']=next((j for j,v in enumerate(hdr) if v.startswith('当月内租费') and '工程公司' not in v),None)
    monthly_cols['company']=next((j for j,v in enumerate(hdr) if v.startswith('当月内租费') and '工程公司' in v),None)
    cat_cols={'zero':4,'monthly':5,'weekly':6,'internal':7,'company':8 if any('租工程公司' in v for v in hdr) else None}
    cumAt[ym]=[];metaAt[ym]=[];referenceAt[ym]={}
    for n in names:
        p=idx[n];t=report.get(n);rec={'reason':f'{m}月完成汇总原值','reasons':{},'zeroNet':None,'monthlyNet':None};cum={}
        for c in fields:
            annual=ar.get((n,c));raw=val(t,monthly_cols[c]) if t else val(annual,monthcols[m])
            rec[c]=money(raw);cum[c]=money(val(t,cat_cols[c]) if t else val(annual,27))
            if annual:
                for mm in range(1,10):referenceAt[ym][f'{p}|2026-{mm:02}|{c}']=money(val(annual,monthcols[mm]))
            if m==9 and c in catmap.values() and annual:
                latestCats[p][c]=money(val(annual,27))
                for month in range(1,10):latestMonthly[f'{p}|2026-{month:02}|{c}']=money(val(annual,monthcols[month]))
        records[f'{p}|{ym}']=rec;cumAt[ym].append(cum);metaAt[ym].append({'year':txt(val(t,2)),'month':txt(val(t,3)),'source':f'{path.name} / '+('工程公司汇总表' if t else '年度汇总')})
        if n in totalrows:
            # Later annual statements supersede earlier cumulative snapshots; never sum cumulative columns.
            feeBase[p]=money(val(totalrows[n],27));fixed[p]=money(val(totalrows[n],29))
            feeBaseSource[p]=f'{path.name} / 年度汇总 / {n}合计'
            baseMonth[p]=ym
        if m==9 and t:latestCats[p]['company']=money(val(t,cat_cols['company']))
    counts={};amounts={}
    for sheet,c in [('零租设备月报表','zero'),('包月外租设备月报','monthly')]:
        cells=sheets[sheet];head=[norm(v) for v in cells[3]];current=None;count=0;total=0
        lookup=lambda label:next((j for j,v in enumerate(head) if label in v),None)
        netcol=lookup('不含税');datecol=lookup('租赁日期' if c=='zero' else '入场日期');taxcol=lookup('专票税率');unitcol=lookup('单位');devicecol=1
        for rn,r in enumerate(cells,1):
            if rn<5:continue
            name=canon(val(r,1))
            if name in idx:current=idx[name];continue
            amountcol=6 if c=='zero' else 7
            if current is None or money(val(r,amountcol)) is None:continue
            if not val(r,1) or norm(val(r,1)) in ['合计','小计','总计']:
                continue
            rawtax=val(r,taxcol);parsed=tax(rawtax);tail=val(r,12) if c=='monthly' else None
            # Older column M is a remark, not a plate. The source header owns its meaning.
            is_plate=bool(re.fullmatch(r'[\u4e00-\u9fff][A-Za-z][A-Za-z0-9·.]{4,8}',txt(tail).strip()))
            plate=txt(val(r,lookup('车牌'))) if c=='zero' else txt(tail) if m>=6 and is_plate else ''
            memo=txt(val(r,lookup('备注'))) if c=='zero' else txt(tail) if not (m>=6 and is_plate) else ''
            item={'id':f'real-{ym}-{c}-{rn}','project':current,'month':ym,'cat':c,'device':txt(val(r,1)),'spec':txt(val(r,2)),'unit':txt(val(r,3)),'qty':val(r,4) if c=='zero' else 1,'plan':val(r,4) if c=='monthly' else 1,'used':val(r,5) if c=='monthly' else 1,'rate':money(val(r,5 if c=='zero' else 6)),'amount':money(val(r,amountcol)),'date':txt(val(r,datecol)),'tax':parsed,'rawTax':txt(rawtax),'originalTax':parsed,'use':txt(val(r,lookup('用途'))) if c=='zero' else '', 'team':txt(val(r,lookup('使用班组'))) if c=='zero' else '', 'reviewer':txt(val(r,lookup('审核人'))),'vendor':txt(val(r,lookup('出租单位'))),'plate':plate,'memo':memo,'oil':('不含油' if '不含油' in txt(rawtax) else '含油' if '含油' in txt(rawtax) else '') if c=='monthly' else '', 'rawNote':txt(tail) if c=='monthly' else '', 'source':f'{path.name} / {sheet} / 第{rn}行','original':money(val(r,amountcol)),'sourceNet':money(val(r,netcol)),'manual':False}
            # Hidden net caches in column O exist from June, but not in earlier templates.
            if c=='monthly' and m>=6:item['sourceNet']=money(val(r,14))
            rows.append(item);count+=1;total+=item['amount']
        counts[c]=count;amounts[c]=total/100
    stats[ym]={'rows':counts,'gross':amounts,'reported_projects':len(report)}
    for p in range(len(names)):
        for c in ['zero','monthly']:
            rr=[r for r in rows if r['project']==p and r['month']==ym and r['cat']==c]
            if rr and all(r['sourceNet'] is not None for r in rr):records[f'{p}|{ym}'][c+'Net']=sum(r['sourceNet'] for r in rr)
            if rr:
                adopted=records[f'{p}|{ym}'][c];gap=sum(r['amount'] for r in rr)-(adopted or 0)
                if adopted is None or abs(gap)>=.5:
                    quality.append({'project':p,'month':ym,'cat':c,'kind':'明细存在，月报采用值空白' if adopted is None else '明细与月报采用值不同','detail':sum(r['amount'] for r in rr),'adopted':adopted})
                    records[f'{p}|{ym}']['reasons'][c]='原月报采用值与明细不同，保留原值待确认。'
baseline=json.loads(json.dumps(records));snapshots=[{'i6':fixed[p],'usage':None,'x':None,'approval':None,'source':'未取得可靠i8对应','readAt':None,'projectId':None} for p in range(len(names))]
ledger=[];bills=[]
periods=json.loads(Path('.artifacts/machinery-fee-workflow/technical-feasibility-20261017/i8-observed-summary.json').read_text(encoding='utf-8'))['period_help']['resolved']
for pid,n in mapping.items():
    p=idx[n];sums={};ids={}
    for typ,col in [('sbsy','usage'),('xmxhd','x'),('jxxhd','approval')]:
        rr=[r for r in live['lists'][typ]['rows'] if r['projectId']==pid];ids[typ]=[r['id'] for r in rr]
        sums[col]=sum(money(r['approval'] if typ=='jxxhd' else r['amount']) or 0 for r in rr)
        for r in rr:
            period=periods.get(r['periodKey'],'未解析周期 '+str(r['periodKey']))
            ledger.append({'p':p,'field':col,'period':period,'periodKey':r['periodKey'],'amount':money(r['approval'] if typ=='jxxhd' else r['amount']),'bill':r['bill'],'id':r['id'],'title':r['title'],'status':r['status'],'updatedAt':r['updatedAt'],'version':r['version']})
            if typ=='jxxhd' and r['amount'] is not None and r['approval'] is not None and abs(r['amount']-r['approval'])>=.005:bills.append({'project':p,'bill':r['bill'],'period':period,'settlement':money(r['amount']),'approval':money(r['approval'])})
    fp={f'{typ}|{r["id"]}':json.dumps([r['amount'],r['approval'],r['version'],r['updatedAt'],r['periodKey'],r['status']],ensure_ascii=False) for typ,v in live['lists'].items() for r in v['rows'] if r['projectId']==pid}
    snapshots[p].update(sums,projectId=pid,source='本轮内置浏览器全量抓取',readAt=live['capturedAt'],billIds=ids,fingerprints=fp)
findings=[]
for pid,n in mapping.items():
    p=idx[n]
    if p not in reported['2026-09']:
        findings.append({'id':'first-'+pid,'project':p,'status':'待确认','note':'首次建立逐单基线，本轮9月月报未包含此项目；可能是历史费用，需人工确认。','firstSeen':live['capturedAt']})
issues=[{'id':1,'project':idx['安徽国风项目'],'origin':'2026-08','due':'2026-09','amount':50000,'mode':'下月补','note':'8月核实4,500，最终采用5,000；约定下月抵补500。仅记录指定费用安排，不把9月全项目总额当执行依据。','evidence':'','status':'未完成','flow':'已有约定，待验证','reply':'用户已说明约定，实际执行仍待确认。'}]
conflicts=[]
for k,v in latestMonthly.items():
    p,ym,c=k.split('|');old=records[f'{p}|{ym}'][c]
    if old is not None and v is not None and abs(old-v)>=.5:conflicts.append({'project':int(p),'month':ym,'cat':c,'original_month_report':old,'latest_annual_reference':v})
seed={'real':True,'records':records,'baseline':baseline,'cumulativeAt':cumAt,'metaAt':metaAt,'meta':metaAt['2026-09'],'opening':[{} for n in names],'feeBase':feeBase,'feeBaseSource':feeBaseSource,'latestCats':latestCats,'latestMonthly':latestMonthly,'i8':snapshots,'incomingI8':snapshots,'captureTime':live['capturedAt'],'saved':rows,'working':rows,'ledger':ledger,'billDifferences':bills,'findings':findings,'issues':issues,'dirty':[],'drafts':{},'checked':[],'snapshots':[],'audits':[],'selected':reported['2026-09'],'order':reported['2026-09']+[p for p in range(len(names)) if p not in reported['2026-09']],'reported':reported,'quality':quality,'monthConflicts':conflicts,'scanHistory':[]}
OUT.mkdir(parents=True,exist_ok=True)
seed['incomingLedger']=ledger;seed['incomingBillDifferences']=bills
seed['referenceAt']=referenceAt;seed['baseMonth']=baseMonth;seed['overrides']={}
(OUT/'jan-sep-seed.json').write_text(json.dumps({'names':names,'months':months,'data':seed},ensure_ascii=False,separators=(',',':')),encoding='utf-8')
(OUT/'jan-sep-source-verification.json').write_text(json.dumps({'hashes':hashes,'sources_unchanged':all(sha(Path(p))==v['before'] for p,v in hashes.items()),'stats':stats,'projects':len(names),'details':len(rows),'i8_rows':len(ledger),'i8_totals':{c:sum(r['amount'] or 0 for r in ledger if r['field']==c)/100 for c in ['usage','x','approval']},'detail_adoption_conflicts':quality,'historical_month_vs_latest_annual_conflicts':conflicts,'capturedAt':live['capturedAt']},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'stats':stats,'projects':len(names),'details':len(rows),'i8_rows':len(ledger),'detail_conflicts':len(quality),'historical_reference_conflicts':len(conflicts),'findings':len(findings)},ensure_ascii=False,indent=2))
