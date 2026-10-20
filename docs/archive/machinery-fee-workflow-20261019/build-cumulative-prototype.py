"""归档脚本：构建多项目机械费累计工作区原型。"""
from pathlib import Path
import json,re,subprocess
p=Path('.scratch/machinery-fee-workflow/interaction-prototype.html');out=Path('.artifacts/machinery-fee-workflow/prototype-20261017')
backup=out/'before-cumulative-workbench.html'
if not backup.exists():backup.write_bytes(p.read_bytes())
s=backup.read_text(encoding='utf-8');payload=json.loads((out/'jan-sep-seed.json').read_text(encoding='utf-8'))
def put(name,new):
    global s
    a=s.index('function '+name+'(');m=re.search(r'\n(?:async )?function ',s[a+1:]);b=a+1+m.start() if m else s.index('\nrender();',a)
    s=s[:a]+new+'\n'+s[b:]
a=s.index('const names=');b=s.index('const cats=',a)
s=s[:a]+'const names='+json.dumps(payload['names'],ensure_ascii=False)+';\nconst REAL_SEED='+json.dumps(payload['data'],ensure_ascii=False,separators=(',',':')).replace('</','<\\/')+';\n'+s[b:]
s=re.sub(r"const months=\[[^\n]+",'const months='+json.dumps(payload['months'])+';',s,count=1)
put('cumulative',r'''function cumulative(p){const delta=months.reduce((sum,m)=>sum+['zero','monthly','internal'].reduce((a,c)=>a+appliedDelta(p,c,m,data.baseMonth[p]||'2026-09'),0),0);const base=data.feeBase[p],fees=base===null?null:base+delta,{i6,usage,x,approval}=data.i8[p];return {fees,i6,usage,x,approval,diff:fees===null||usage===null?null:Math.round(fees-(i6||0)-usage),second:usage===null||x===null||approval===null?null:Math.round(usage-x-approval)};}
function appliedDelta(p,c,m,referenceMonth){const k=`${p}|${m}|${c}`;if(!(k in data.overrides))return 0;const reference=data.referenceAt[referenceMonth]?.[k]??data.baseline[`${p}|${m}`]?.[c]??0;return (data.overrides[k]||0)-reference;}
function captureStamp(v){return v?new Date(v).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false}):'未取数';}
''')
put('catSum',r'''function catSum(p,c,snap=null){const month=snap?.month||ui.month,base=data.cumulativeAt[month][p][c];if(base===null)return null;const overrides=snap?snap.overrides:data.overrides;return base+months.filter(m=>m<=month).reduce((a,m)=>{const k=`${p}|${m}|${c}`;return a+(k in overrides?(overrides[k]||0)-(data.referenceAt[month]?.[k]??data.baseline[`${p}|${m}`]?.[c]??0):0);},0);}
''')
s=s.replace('r[c]=parseMoney(v);r.reasons[c]=reason;', 'r[c]=parseMoney(v);data.overrides[k]=r[c];r.reasons[c]=reason;')
s=s.replace('r[c]=suggestion(p,c);r[c+', 'r[c]=suggestion(p,c);data.overrides[`${p}|${ui.month}|${c}`]=r[c];r[c+')
s=s.replace('const snapshot={history:', 'const snapshot={overrides:structuredClone(data.overrides),history:')
s=s.replace('本次仅更新勾选类别的含税及不含税月值；', '本次仅更新勾选类别的含税及不含税月值；如旧月报与最新年度记录不同，以本次确认额替换累计中的该月分量，不重复加计。')
s=s.replace("${esc(data.meta[p].year)}","${esc(data.metaAt[m][p].year)}").replace("${esc(data.meta[p].month)}","${esc(data.metaAt[m][p].month)}")
s=s.replace('<div class="fi"><label for="month">','<div class="fi" id="month-field"><label for="month">')
s=s.replace('<option>2026-09</option>', ''.join('<option>'+m+'</option>' for m in reversed(payload['months'])))
render_start=s.index('function render(){');render_end=s.index('\nfunction ',render_start+1)
r=s[render_start:render_end].replace("document.getElementById('month').value=ui.month;", "document.getElementById('month').value=ui.month;document.getElementById('month-field').hidden=ui.view==='reconcile';")
s=s[:render_start]+r+s[render_end:]
s=s.replace('<strong>公司汇总</strong>', '<strong>公司汇总</strong><button class="btn sm" onclick="showMonthProjects()">本月报表项目</button>')
s=s.replace("const c=ui.cat;const all=", "const c=ui.cat;const all=")
s=s.replace("保存明细后确认汇总；只改日期、车牌等字段可仅保存。", "保存明细后确认汇总；只改日期、车牌等字段可仅保存。${data.quality.some(q=>q.month===ui.month&&q.cat===c&&scoped().includes(q.project))?' 当前范围有原月报与明细不一致，原采用值保留。':''}${data.monthConflicts.some(q=>q.month===ui.month&&q.cat===c&&scoped().includes(q.project))?' 当时报送值与最新年度记录不同，请查看历史来源说明。':''}")
put('reconcileView',r'''function reconcileView(){const filter=ui.workFilter||'pending',pendingFinding=f=>f.status==='待确认';const found=data.findings.filter(pendingFinding),ids=filter==='findings'?[...new Set(found.map(f=>f.project))]:scoped();const active=p=>{const c=cumulative(p);return c.diff===null||c.second===null||c.diff!==0||c.second!==0||data.billDifferences.some(b=>b.project===p)||unresolved(p)||found.some(f=>f.project===p);};const shown=filter==='pending'?ids.filter(active):ids,normal=filter==='pending'?ids.filter(p=>!active(p)):[];return `<div class="bd"><div class="actionbar"><button class="btn ${filter==='pending'?'on':''}" onclick="ui.workFilter='pending';render()">待处理</button><button class="btn ${filter==='findings'?'on':''}" onclick="ui.workFilter='findings';render()">本轮发现（${found.length}）</button><button class="btn ${filter==='all'?'on':''}" onclick="ui.workFilter='all';render()">全部所选项目</button><div class="sp"><button class="btn" onclick="openIssues()">核对事项</button><button class="btn" onclick="historyEntry()">历史接续</button><button class="btn pri" onclick="prepareRefresh()">全量取数</button></div></div><p class="section-note">当前累计，不随查看月份切换。已载入2026年1—9月，累计承接最新年度汇总；取数时间：${captureStamp(data.captureTime)}。${filter==='findings'?'本轮发现覆盖全量项目，不受显示名单限制。':''}</p><div class="work-legend">两条差额均为左侧减右侧。班组消耗采用审批金额；结算／审批不同仍逐单保留。</div>${workRows(shown)}${normal.length?`<details class="normal-projects" ${ui.showNormal?'open':''} ontoggle="ui.showNormal=this.open"><summary>正常项目（${normal.length}）</summary>${workRows(normal)}</details>`:''}</div>`;}
function showMonthProjects(){data.selected=[...data.reported[ui.month]];ui.focus='all';render();notify('已显示'+ui.month+'原月报包含的项目。');}
function addShownProject(p){if(!data.selected.includes(p))data.selected.push(p);ui.focus=String(p);ui.workFilter='all';render();notify('已加入显示名单，未填入或修改报表金额。');}
''')
put('workRows',r'''function workRows(ids){return `<div class="tw work-scroll"><table class="dt work-table cumulative-table"><thead><tr><th rowspan="2" class="work-project">项目</th><th colspan="3">报表核对</th><th colspan="3">i8内部核对</th><th rowspan="2">结算／审批不同</th><th rowspan="2">项目核查进度</th><th rowspan="2">操作</th></tr><tr><th>报表费用累计</th><th>班组使用累计<br>（含历史接续）</th><th>差额＝左－右</th><th>班组使用累计</th><th>项目结算＋班组审批</th><th>差额＝左－右</th></tr></thead><tbody>${ids.map(p=>{const c=cumulative(p),items=data.issues.filter(i=>i.project===p&&i.status==='未完成'),f=data.findings.find(f=>f.project===p&&f.status==='待确认'),bs=data.billDifferences.filter(b=>b.project===p);return `<tr><td class="work-project"><b title="${esc(names[p])}">${esc(names[p])}</b><div class="table-sub">${data.i8[p].projectId?'取数 '+captureStamp(data.i8[p].readAt):'尚无可靠i8对应'}</div></td><td class="num">${fmt(c.fees)}</td><td class="num">${fmt(c.usage===null?null:c.usage+(c.i6||0))}</td><td class="num ${c.diff?'danger-text':''}">${fmt(c.diff)}</td><td class="num">${fmt(c.usage)}</td><td class="num"><button class="link" onclick="consumptionParts(${p})">${fmt(c.x===null||c.approval===null?null:c.x+c.approval)}</button></td><td class="num ${c.second?'danger-text':''}">${fmt(c.second)}</td><td>${bs.length?`<button class="link" onclick="billDetail(${p})">${bs.length}张 · 查看</button>`:'—'}</td><td>${f?`<button class="link" onclick="findingEditor(${p})">首次发现／变化待确认</button>`:items.length?esc([...new Set(items.map(i=>i.flow||'待通知项目'))].join('、')):c.diff===null?'核对数据未齐':'尚无跟进事项'}</td><td class="work-actions"><button class="link" onclick="prepareRefresh(${p})">更新i8</button><button class="link" onclick="openIssues(${p})">跟进</button><button class="link" onclick="toggleBasis(${p})">依据</button>${!data.selected.includes(p)?`<button class="link" onclick="addShownProject(${p})">加入显示</button>`:''}</td></tr>${ui.basis===p?`<tr class="basis-row"><td colspan="10"><div class="actionbar"><span>累计沿最新年度汇总接续，历史月报按当时报送版本保留。</span><div class="sp"><button class="btn sm" onclick="periodDetail(${p})">周期与来源</button><button class="btn sm" onclick="copyContact(${p})">复制核对摘要</button><button class="btn sm" onclick="reportReferences(${p})">历史来源说明</button></div></div></td></tr>`:''}`;}).join('')||'<tr><td colspan="10" class="empty">当前范围没有此类项目。</td></tr>'}</tbody></table></div>`;}
function consumptionParts(p){const c=cumulative(p);dialog('消耗累计组成 · '+names[p],`<dl class="info-grid"><dt>项目消耗结算</dt><dd>${fmt(c.x)}</dd><dt>班组消耗审批</dt><dd>${fmt(c.approval)}</dd></dl><p class="section-note">班组消耗采用本期审批金额。</p>`);}
function reportReferences(p){const qq=data.quality.filter(q=>q.project===p),cc=data.monthConflicts.filter(q=>q.project===p);dialog('历史来源说明 · '+names[p],`<p class="section-note">1—9月各月报保存当时报送值；当前费用累计沿最新年度汇总接续，累计列不重复相加。历史修订产生的不同不自动覆盖。</p><table class="dt"><tr><th>月份</th><th>事项</th><th>原月报采用值</th><th>另一来源</th></tr>${qq.map(q=>`<tr><td>${q.month}</td><td>${q.cat==='zero'?'零租':'包月'} · ${q.kind}</td><td class="num">${fmt(q.adopted)}</td><td class="num">明细 ${fmt(q.detail)}</td></tr>`).join('')}${cc.map(q=>`<tr><td>${q.month}</td><td>最新年度记录与当时报送不同</td><td class="num">${fmt(q.original_month_report)}</td><td class="num">年度记录 ${fmt(q.latest_annual_reference)}</td></tr>`).join('')}</table>${!qq.length&&!cc.length?'<p class="section-note">未发现本次已检查范围内的上述不同。</p>':''}`);}
''')
put('periodDetail',r'''function periodDetail(p){const rows=data.ledger.filter(r=>r.p===p),periods=[...new Set(rows.map(r=>r.period))].sort();dialog('周期与来源 · '+names[p],`<p class="section-note">本轮真实取数按引用周期汇总；未知周期保留原键，不用录单日期补月份。当前累计包含全部已取记录。</p><div class="tw"><table class="dt"><tr><th>核算期／统计周期</th><th class="num">班组使用</th><th class="num">项目消耗结算</th><th class="num">班组消耗审批</th><th>来源</th></tr>${periods.map(period=>`<tr><td>${esc(period)}</td>${['usage','x','approval'].map(f=>`<td class="num">${fmt(rows.filter(r=>r.period===period&&r.field===f).reduce((a,r)=>a+(r.amount||0),0))}</td>`).join('')}<td><button class="link" onclick="sourceBills(${p},'${esc(period)}')">查看单据</button></td></tr>`).join('')||'<tr><td colspan="5">本次未取得可靠的项目对应，不填0。</td></tr>'}</table></div>`);}
function sourceBills(p,period){const rs=data.ledger.filter(r=>r.p===p&&r.period===period);dialog('相关来源单据 · '+names[p],`<div class="tw"><table class="dt"><tr><th>类型</th><th>单据号</th><th>名称</th><th class="num">采用金额</th><th>状态</th></tr>${rs.map(r=>`<tr><td>${({usage:'班组使用',x:'项目结算',approval:'班组审批'})[r.field]}</td><td>${esc(r.bill)}</td><td>${esc(r.title)}</td><td class="num">${fmt(r.amount)}</td><td>${r.status===1?'已审':'未审／待核'}</td></tr>`).join('')}</table></div>`,`<button class="btn" onclick="periodDetail(${p})">返回周期</button><button class="btn" onclick="closeDialog()">关闭</button>`);}
''')
put('billDetail',r'''function billDetail(p){const bs=data.billDifferences.filter(b=>b.project===p);dialog('结算／审批不同 · '+names[p],`<table class="dt"><tr><th>单据号</th><th>周期</th><th class="num">结算额</th><th class="num">审批金额（采用）</th><th class="num">审批－结算</th></tr>${bs.map(b=>`<tr><td>${esc(b.bill)}</td><td>${esc(b.period)}</td><td class="num">${fmt(b.settlement)}</td><td class="num">${fmt(b.approval)}</td><td class="num">${fmt(b.approval-b.settlement)}</td></tr>`).join('')}</table><p class="section-note">累计对平仍保留每张两额不同单据。</p>`);}
''')
s=s.replace("${data.selected.map(p=>", "${data.order.map(p=>")
# Older monthly statements use their final column for remarks; later unnamed cells may mix plates and notes.
ds=s.index('function detailView(');de=s.index('\nfunction ',ds+1);detail=s[ds:de]
detail=detail.replace("'车牌号'];if(c==='monthly')", "ui.month<'2026-06'?'备注':'车牌／原备注'];if(c==='monthly')")
detail=detail.replace("${detailInput(r,'plate','车牌')}</td>`}", "${detailInput(r,ui.month<'2026-06'?'memo':r.plate?'plate':'memo',ui.month<'2026-06'?'原表备注':'车牌或原备注')}</td>`}")
ts=detail.index('${[',detail.index('const tax='))+2;te=detail.index('.map(t=>',ts)
taxes=['','普票','专票1%','专票3%','专票6%','专票9%','专票13%']
taxes+=sorted({r['tax'] for r in payload['data']['saved'] if r['tax']} - set(taxes))
detail=detail[:ts]+json.dumps(taxes,ensure_ascii=False)+detail[te:]
s=s[:ds]+detail+s[de:]
rs=s.index('function reportTable(');re_end=s.index('\nfunction ',rs+1);report=s[rs:re_end]
report=report.replace("r.tax+' '+r.oil,r.plate]", "r.tax+' '+r.oil,r.plate||r.memo]")
report=report.replace("' '];let rows", "snap.month<'2026-06'?'备注':' '];let rows")
s=s[:rs]+report+s[re_end:]
# Append the snapshot update/monitor interactions before the final render.
extra=r'''
function prepareRefresh(p=null){const ids=p===null?data.incomingI8.map((x,i)=>x.projectId?i:null).filter(x=>x!==null):[p];window.refreshPlan=ids.map(p=>{const old=data.i8[p],next=structuredClone(data.incomingI8[p]),before=old.fingerprints||{},after=next.fingerprints||{};const removed=Object.keys(before).filter(k=>!(k in after)),changed=Object.keys(after).filter(k=>before[k]!==after[k]);const valid=!!next.projectId&&['usage','x','approval'].every(c=>Number.isFinite(next[c]));return {p,next,removed,changed,valid,chosen:valid&&!removed.length,allowRemoval:false};});drawRefreshPlan();}
function drawRefreshPlan(){dialog(window.refreshPlan.length===1?'更新项目i8数据':'全量取数 · 本轮真实快照',`<p class="section-note">此原型使用刚通过内置浏览器抓取的真实快照演示采用过程，不从按钮再次联网。来源时间：${captureStamp(data.captureTime)}。只更新勾选项目，其他项目保持原样。</p><div class="tw"><table class="dt refresh-table"><tr><th>采用</th><th>项目</th><th>班组使用：原→新</th><th>项目结算：原→新</th><th>班组审批：原→新</th><th>单据变化</th></tr>${window.refreshPlan.map((r,i)=>`<tr><td><input type="checkbox" aria-label="更新${esc(names[r.p])}" ${r.chosen?'checked':''} ${!r.valid||(r.removed.length&&!r.allowRemoval)?'disabled':''} onchange="window.refreshPlan[${i}].chosen=this.checked"></td><td>${esc(names[r.p])}</td>${['usage','x','approval'].map(c=>`<td class="num">${fmt(data.i8[r.p][c])} → ${fmt(r.next[c])}</td>`).join('')}<td>${!r.valid?'三类数据未齐，保留旧值':r.removed.length?`原有${r.removed.length}条未返回 <button class="link" onclick="ackMissing(${i})">核实</button>`:r.changed.length?'新增／变更'+r.changed.length+'条':'无变化'}</td></tr>`).join('')}</table></div>`,`<button class="btn" onclick="closeDialog()">取消</button><button class="btn pri" onclick="applyRefresh()">确认采用勾选项目</button>`);}
function ackMissing(i){dialog('核实原有数据未返回',`<p>项目：${esc(names[window.refreshPlan[i].p])}。请先核实查询范围及原单据是否确实删除、作废或归零。</p><div class="formline"><label for="missing-reason">核实依据</label><textarea class="inp" id="missing-reason" rows="3"></textarea></div>`,`<button class="btn" onclick="drawRefreshPlan()">返回，保留旧值</button><button class="btn pri" onclick="confirmMissing(${i})">已核实，允许勾选减少后的金额</button>`);}
function confirmMissing(i){const reason=document.getElementById('missing-reason').value.trim();if(!reason){notify('请填写已核实的依据。');return;}window.refreshPlan[i].allowRemoval=true;window.refreshPlan[i].removalReason=reason;drawRefreshPlan();}
function ensureFinding(p,note,signature){const old=data.findings.find(f=>f.project===p);if(old?.status==='待确认'){old.lastSeen=data.captureTime;if(!old.note.includes(note))old.note+='\n'+note;return;}if(old&&old.signature===signature)return;if(old){(data.findingHistory||=[]).push(structuredClone(old));data.findings=data.findings.filter(f=>f!==old);}data.findings.push({id:'change-'+p+'-'+data.scanHistory.length,project:p,status:'待确认',note,signature,firstSeen:data.captureTime});}
function applyRefresh(){const applied=[];for(const r of window.refreshPlan){if(!r.chosen||!r.valid||(r.removed.length&&!r.allowRemoval))continue;const old=structuredClone(data.i8[r.p]);data.i8[r.p]=structuredClone(r.next);applied.push(r.p);if(r.changed.length||r.removed.length)ensureFinding(r.p,'i8单据或金额有变化，请确认本轮报表是否覆盖。',JSON.stringify(r.next.fingerprints));data.audits.push({kind:'i8快照采用',project:r.p,before:old,after:structuredClone(r.next),reason:r.removalReason||'本轮抓取预览确认'});}data.scanHistory.push({projects:applied,sourceAt:data.captureTime});closeDialog();render();notify('已采用'+applied.length+'个项目的本轮快照，其他项目及未处理发现保持原样。');}
function findingEditor(p){const f=data.findings.find(f=>f.project===p&&f.status==='待确认');if(!f)return;dialog('本轮发现 · '+names[p],`<p>${esc(f.note)}</p><p class="section-note">首次发现时间：${captureStamp(f.firstSeen)}。不据此直接认定漏报。</p><div class="formline"><label for="finding-note">核实／跟进说明</label><textarea id="finding-note" class="inp" rows="3">${esc(f.resolutionNote||'')}</textarea></div>`,`<button class="btn" onclick="closeDialog()">关闭</button><button class="btn" onclick="saveFinding(${p},false)">保存，继续跟进</button><button class="btn pri" onclick="saveFinding(${p},true)">已核实，本轮无需补报</button>`);}
function saveFinding(p,done){const note=document.getElementById('finding-note').value.trim();if(done&&!note){notify('请填写本轮无需补报的核实说明。');return;}const f=data.findings.find(f=>f.project===p&&f.status==='待确认');f.resolutionNote=note;if(done)f.status='已核实，本轮无需补报';closeDialog();render();notify(done?'已结束本次发现；以后有新变化仍会提示。':'跟进说明已保存；下次取数仍保留此发现。');}
'''
s=s.replace('\nrender();\n</script>',extra+'\nrender();\n</script>')
s=s.replace('已载入9月真实报表：零租282条、包月19条；修改仅在本机原型中试用。','已载入2026年1—9月真实报表，1966条设备明细；i8本轮完整抓取505条。')
s=s.replace('已载入9月真实报表与10月17日核验快照。','已载入1—9月真实月报与本轮i8取数。')
s=s.replace('i8核验快照：2026-10-17','i8本轮抓取：2026-10-17')
s=s.replace('class="dt work-table cumulative-table"><thead>', 'class="dt work-table cumulative-table"><colgroup><col style="width:175px">'+''.join('<col style="width:110px">' for _ in range(6))+'<col style="width:90px"><col style="width:130px"><col style="width:145px"></colgroup><thead>')
s=s.replace('<th>项目结算＋班组审批</th>','<th>项目结算<br>＋班组审批</th>')
s=s.replace('bills().filter(b=>b.project===p)','data.billDifferences.filter(b=>b.project===p)')
put('contactSummary',r'''function contactSummary(p){const c=cumulative(p);return `${names[p]}：请核查机械费。\n报表采用${data.baseMonth[p]||'未取得'}累计记录及后续已确认修订；i8取数${captureStamp(data.i8[p].readAt)}。\n报表核对差额${fmt(c.diff)}元；i8内部差额${fmt(c.second)}元。\n请回复原因、是否修订报表及处理安排。\n${data.billDifferences.filter(b=>b.project===p).map(b=>`单据${b.bill}，周期${b.period}，结算额${fmt(b.settlement)}，审批金额${fmt(b.approval)}，审批减结算${fmt(b.approval-b.settlement)}。`).join('\n')}`;}
''')
s=s.replace('const valid=!!next.projectId', "if(removed.length)ensureFinding(p,'原有数据本次未返回，保留旧值等待核实。',JSON.stringify(next.fingerprints));const valid=!!next.projectId")
s=s.replace('data.i8[r.p]=structuredClone(r.next);applied.push(r.p);', 'data.i8[r.p]=structuredClone(r.next);data.ledger=data.ledger.filter(x=>x.p!==r.p).concat(structuredClone(data.incomingLedger.filter(x=>x.p===r.p)));data.billDifferences=data.billDifferences.filter(x=>x.project!==r.p).concat(structuredClone(data.incomingBillDifferences.filter(x=>x.project===r.p)));applied.push(r.p);')
# Missing counts in older monthly templates must not turn a price edit into an automatic zero amount.
es=s.index('function editRow(');ee=s.index('\nfunction ',es+1);edit=s[es:ee]
edit=edit.replace('r[f]=v;if(f===', 'r[f]=v;let missingMeasure=false;if(f===')
edit=edit.replace("{r.amount=Math.round(r.rate*(r.cat==='zero'?r.qty:r.used));", "{const measure=r.cat==='zero'?r.qty:r.used;missingMeasure=typeof measure!=='number'||!Number.isFinite(measure)||typeof r.rate!=='number'||!Number.isFinite(r.rate);if(!missingMeasure)r.amount=Math.round(r.rate*measure);")
edit=edit.replace("notify('明细修改待保存，有效月值未改变。');", "notify(missingMeasure?'计量数量未填，合价未自动重算；请核对合价后保存。':'明细修改待保存，有效月值未改变。');")
s=s[:es]+edit+s[ee:]
s=s.replace('最新年度汇总接续，历史修订', '项目最新年度汇总接续，历史修订')
s=s.replace('<p class="section-note">1—9月各月报保存当时报送值；', '<p class="section-note">累计基线来源：${esc(data.feeBaseSource[p])||\'未取得\'}。</p><p class="section-note">1—9月各月报保存当时报送值；')
put('help',r'''function help(){dialog('当前试用范围',`<p>2026年1—9月九份完成汇总已载入，共1966条设备明细。表1—3按月查看，可用“本月报表项目”显示该月原报范围。</p><p>工作台始终核对当前累计，不受月份选择影响。累计接续最新年度汇总，历史月报不重复加累计。</p><p>i8已通过内置浏览器重新完整读取307条使用记录、69条项目结算、129条班组消耗。本原型的取数按钮回放这次真实快照，正式实时取数尚未接入。</p><p>试用修改只在页面内存，刷新恢复。原Excel和i8单据不修改。</p>`);}
''')
# Make original template remarks visible instead of losing them when the older column was not a plate.
s=s.replace("<dt>说明</dt><dd>${esc(r.memo)||'无'}</dd>","<dt>原票种文字</dt><dd>${esc(r.rawTax||r.tax)}</dd><dt>原备注</dt><dd>${esc(r.rawNote||r.memo)||'无'}</dd>")
css='''
#month-field[hidden]{display:none}.work-legend{font-size:12px;color:var(--tx2);margin:0 0 12px}
.cumulative-table{min-width:1200px;width:100%;table-layout:fixed}.cumulative-table thead th{text-align:center;white-space:normal;min-width:0!important}
.cumulative-table thead tr:first-child th{height:32px;top:0}.cumulative-table thead tr:nth-child(2) th{top:32px;height:42px}
.cumulative-table td{height:58px}.cumulative-table .work-project{position:sticky;left:0;min-width:180px;max-width:205px;background:var(--sf);z-index:3;white-space:normal}
.cumulative-table thead .work-project{z-index:7;background:var(--sf2)}.work-project b{display:block;max-width:205px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.work-actions{min-width:145px;white-space:normal}.work-actions button+button{margin-left:7px}.refresh-table{min-width:1000px}
.cumulative-table th:nth-child(5){min-width:125px}.cumulative-table th:last-child{min-width:155px}
'''
s=s.replace('</style>',css+'</style>',1)
from runpy import run_path
s=run_path(str(Path(__file__).with_name('refine-detail-prototype.py')))['refine'](s)
style_end=s.rfind('</style>')+len('</style>')
s=s[:style_end]+'\n<style>\n'+Path(__file__).with_name('prototype-polish.css').read_text(encoding='utf-8')+'\n</style>\n'+s[style_end:]
p.write_text(s,encoding='utf-8',newline='\r\n')
subprocess.run(['node','--check'],input=re.search(r'<script>([\s\S]*)</script>',s).group(1),text=True,encoding='utf-8',check=True)
print('Jan-Sep data and cumulative workbench built; syntax passed.')
