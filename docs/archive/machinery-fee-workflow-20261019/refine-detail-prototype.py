"""Apply the confirmed detail and reconciliation refinements to the prototype only."""
import re

def refine(s):
    def get(name):
        a=s.index('function '+name+'(')
        m=re.search(r'\n(?:async )?function ',s[a+1:])
        return s[a:a+1+m.start() if m else s.index('\nloadIgnored();',a)]
    def put(name,new):
        nonlocal s
        old=get(name);s=s.replace(old,new+'\n',1)
    s=s.replace('!r.plate.trim()',"!(r.plateNotRequired||r.plate.trim())")
    d=get('detailView')
    d=d.replace('if(!rs.length)continue;', 'if(!rs.length&&ui.onlyProblems)continue;')
    a=d.index('body+=`<tr class="detail-project">');b=d.index(';for(const r of rs)',a)
    d=d[:a]+'''const projectRows=all.filter(r=>r.project===p),grossIndex=titles.indexOf('合价（元）'),netIndex=titles.indexOf('不含税价');body+=`<tr class="detail-project"><td colspan="${grossIndex}"><b>${names[p]}</b> · ${rs.length}条</td>${titles.slice(grossIndex).map((t,j)=>{const i=j+grossIndex;return i===grossIndex?`<td class="num" data-project-gross="${p}">${fmt(projectRows.reduce((a,r)=>a+r.amount,0))}</td>`:i===netIndex?`<td class="num" data-project-net="${p}">${detailNetTotal(projectRows)}</td>`:i===titles.length-1?`<td class="row-actions"><button class="link sm" onclick="createRow(${p})">增行</button></td>`:'<td></td>';}).join('')}</tr>`'''+d[b:]
    d=d.replace("${detailInput(r,f,l)}</td>`).join('')}`", "${f==='plate'?plateField(r):detailInput(r,f,l)}</td>`).join('')}`")
    # The older monthly form's last column remains its original remarks column.
    d=d.replace("ui.month<'2026-06'?'原表备注':'车牌或原备注')}</td>", "ui.month<'2026-06'?'原表备注':'车牌或原备注')}${plateExemption(r)}</td>")
    d=re.sub(r'<button class="link sm" onclick="sourceRow\([^<]+</button>','',d)
    d=d.replace('<button class="btn" onclick="addRow()">增行</button>','')
    a=d.index('<tr class="detail-totals">');b=d.index('<tr>${titles.map',a);d=d[:a]+d[b:]
    d=d.replace('合计见对应金额列上方','合计见各项目对应金额列')
    d=re.sub(r'<span>当前\$\{c===.*?</span>', '',d)
    put('detailView',d)
    e=get('editRow');a=e.index('const projectTotal=');b=e.index('const net=',a);e=e[:a]+e[b:];e=e.replace('updateDetailTotals();','updateDetailTotals();if(f===\'plate\'){r.plateNotRequired=false;render();}');put('editRow',e)
    put('updateDetailTotals', '''function updateDetailTotals(){for(const p of scoped()){const rows=data.working.filter(r=>r.project===p&&r.month===ui.month&&r.cat===ui.cat),gross=document.querySelector(`[data-project-gross="${p}"]`),net=document.querySelector(`[data-project-net="${p}"]`);if(gross)gross.textContent=fmt(rows.reduce((a,r)=>a+r.amount,0));if(net)net.textContent=detailNetTotal(rows);}}
function plateExemption(r){if(r.plate.trim()&&!r.plateNotRequired)return '';return `<label class="plate-exemption"><input type="checkbox" aria-label="${r.id}无需车牌" ${r.plateNotRequired?'checked':''} onchange="setNoPlate('${r.id}',this.checked)">无需车牌</label>`;}
function plateField(r){return `<div class="plate-field">${detailInput(r,'plate','车牌')}${plateExemption(r)}</div>`;}
function setNoPlate(id,value){const r=data.working.find(r=>r.id===id);if(!r)return;r.plateNotRequired=value;markDirty(r.project);if(ui.onlyProblems)render();notify(value?'已标记无需车牌，不再作为待补字段。':'已恢复车牌字段检查。');}''')
    put('seedIssueEditor', '''function seedIssueEditor(id){const i=data.issues.find(i=>i.id===id)||{project:(ui.issueScope||scoped())[0],note:''};window.editIssue=id;dialog(id?'核对事项 · '+names[i.project]:'新增核对事项',`<div class="formline"><label for="issue-p">项目</label><select id="issue-p" class="inp" aria-label="事项项目">${data.order.map(p=>`<option value="${p}" ${p===i.project?'selected':''}>${esc(names[p])}</option>`).join('')}</select></div><div class="formline"><label for="issue-note">事项／处理备注</label><textarea id="issue-note" class="inp" rows="3" placeholder="记一句需要项目核查或已约定的事">${esc(i.note||'')}</textarea></div>`,`<button class="btn" onclick="closeDialog()">取消</button><button class="btn" onclick="saveIssue(false)">保存</button><button class="btn pri" onclick="saveIssue(true)">确认完成</button>`);}''')
    put('saveIssue', '''function saveIssue(complete){const project=Number(document.getElementById('issue-p').value),note=document.getElementById('issue-note').value.trim();if(!data.order.includes(project)||!note){notify('请选择项目，记一句事项或处理备注。');return;}const old=data.issues.find(i=>i.id===window.editIssue),item={...old,id:old?.id||Date.now(),project,note,status:complete?'已确认完成':'未完成',flow:complete?'已完成':'待处理'};data.issues=data.issues.filter(x=>x.id!==item.id);data.issues.push(item);closeDialog();if(document.getElementById('issues-dlg').open)refreshIssues();const sv=document.getElementById('scrollview'),top=sv.scrollTop;render();sv.scrollTop=top;notify(complete?'事项已由你确认完成，金额保持原样。':'事项已保存。');}''')
    put('issuesView', '''function issuesView(){const items=data.issues.filter(i=>(ui.issueScope||scoped()).includes(i.project)&&(ui.issueFilter==='all'||i.status==='未完成'));return `<div class="bd"><div class="actionbar"><strong>核对事项</strong><select class="inp" style="width:auto" aria-label="事项范围" onchange="ui.issueFilter=this.value;refreshIssues()"><option value="open" ${ui.issueFilter!=='all'?'selected':''}>未完成</option><option value="all" ${ui.issueFilter==='all'?'selected':''}>全部</option></select><span class="mut sm">${items.length}项</span><div class="sp"><button class="btn pri" onclick="issueEditor()">新增事项</button></div></div><div class="tw" style="min-height:0"><table class="dt issue-list"><thead><tr><th>项目</th><th>事项／处理备注</th><th>状态</th><th>操作</th></tr></thead><tbody>${items.map(i=>`<tr><td>${esc(names[i.project])}</td><td class="note">${esc(i.note)}${i.reply?`<div class="table-sub">${esc(i.reply)}</div>`:''}${i.evidence?`<div class="table-sub">${esc(i.evidence)}</div>`:''}</td><td>${esc(i.status)}</td><td><button class="btn sm" onclick="issueEditor(${i.id})">处理</button></td></tr>`).join('')||'<tr><td colspan="4" class="empty">当前范围没有事项。</td></tr>'}</tbody></table></div></div>`;}''')
    s=s.replace('c.diff!==0||c.second!==0',"(c.diff!==0&&!differenceIgnored(p,'fees'))||(c.second!==0&&!differenceIgnored(p,'internal'))")
    s=s.replace('正常项目（${normal.length}）','已对平／已忽略（${normal.length}）')
    s=s.replace('<td class="num ${c.diff?\'danger-text\':\'\'}">${fmt(c.diff)}</td>',"${differenceCell(p,'fees',c.diff)}")
    s=s.replace('<td class="num ${c.second?\'danger-text\':\'\'}">${fmt(c.second)}</td>',"${differenceCell(p,'internal',c.second)}")
    s=s.replace('class="link" onclick="billDetail(${p})">${bs.length}张 · 查看','class="link bill-warning" onclick="billDetail(${p})">${bs.length}张不同 · 查看')
    s=s.replace(":'尚无跟进事项'", ":differenceIgnored(p,'fees')||differenceIgnored(p,'internal')?'本次差额已忽略':'尚无跟进事项'")
    s=s.replace('<td class="num">${fmt(b.approval-b.settlement)}</td>','<td class="num danger-text"><b>${fmt(b.approval-b.settlement)}</b></td>')
    s=s.replace('function render(){','function render(){\npruneIgnoredDifferences();',1)
    extra='''
function differenceSignature(p,relation){const c=cumulative(p);return relation==='fees'?JSON.stringify([c.fees,c.usage,c.i6]):JSON.stringify([c.usage,c.x,c.approval]);}
function differenceIgnored(p,relation){return data.ignoredDifferences?.[`${p}|${relation}`]===differenceSignature(p,relation);}
function pruneIgnoredDifferences(){for(const k of Object.keys(data.ignoredDifferences||{})){const [p,r]=k.split('|');if(data.ignoredDifferences[k]!==differenceSignature(Number(p),r))delete data.ignoredDifferences[k];}}
function ignoreDifference(p,relation,undo=false){const c=cumulative(p),value=relation==='fees'?c.diff:c.second;if(value===null||value===0)return;data.ignoredDifferences||={};const k=`${p}|${relation}`;if(undo)delete data.ignoredDifferences[k];else data.ignoredDifferences[k]=differenceSignature(p,relation);data.audits.push({kind:undo?'撤销忽略差额':'忽略本次差额',project:p,relation,value});render();notify(undo?'已恢复提醒。':'已忽略这次差额；核对金额变化后重新提醒。');}
function differenceCell(p,relation,value){const ignored=differenceIgnored(p,relation);return `<td class="num ${value&&!ignored?'danger-text':''}">${fmt(value)}${value!==null&&value!==0?`<div><button class="link sm ${ignored?'mut':''}" aria-label="${esc(names[p])}${relation==='fees'?'报表':'内部'}${ignored?'撤销忽略':'忽略本次差额'}" onclick="ignoreDifference(${p},'${relation}',${ignored})">${ignored?'已忽略 · 撤销':'忽略本次差额'}</button></div>`:''}</td>`;}
'''
    s=s.replace('\nrender();\n</script>',extra+'\nrender();\n</script>')
    s=s.replace('r.vendor,r.plate,r.memo','r.vendor,r.plateNotRequired?\'无需车牌\':r.plate,r.memo')
    s=s.replace('r.plate||r.memo]',"r.plateNotRequired?(r.memo?r.memo+' ／ 无需车牌':'无需车牌'):r.plate||r.memo]")
    s=s.replace('</style>', '''
.source-details thead th{top:0!important}.source-details .detail-project td{font-weight:600}.source-details .detail-project .row-actions{background:var(--pri-l)}
.plate-field{display:flex;align-items:center;gap:6px}.plate-field .inp{min-width:90px}.plate-exemption{display:inline-flex;align-items:center;gap:3px;font-size:12px;white-space:nowrap;margin-left:5px}.plate-exemption input{width:14px;height:14px}
.bill-warning{color:var(--dg-d)!important;background:var(--dg-l)!important;border:1px solid var(--dg-bd)!important;border-radius:4px;padding:4px!important;font-weight:700!important;white-space:normal}.issue-list{min-width:0!important;width:100%}.issue-list .note{white-space:normal;min-width:220px}
</style>''',1)
    s=s.replace("!(r.plateNotRequired||r.plate.trim())",'plateMissing(r)')
    put('plateExemption', '''function plateExemption(r){if(!plateApplies(r))return '';if(r.plate.trim()&&!r.plateNotRequired)return '';return `<label class="plate-exemption"><input type="checkbox" aria-label="${r.id}无需车牌" ${r.plateNotRequired?'checked':''} onchange="setNoPlate('${r.id}',this.checked)">无需车牌</label>`;}''')
    put('plateField', '''function plateField(r){return `<div class="plate-field" title="${plateApplies(r)?'道路车辆或待确认设备，检查车牌':'按历史设备类别，无需道路车牌'}">${detailInput(r,'plate',plateApplies(r)?'车牌':'车牌（选填）')}${plateExemption(r)}</div>`;}
function plateApplies(r){if(r.cat==='monthly'&&r.month<'2026-06')return false;return !/^(挖机|挖掘机|叉车|铲车|压路机|发电机|塔吊|塔吊安装费|履带吊|升降平台|升降平台车|升降车(?:10米|12米)?|直臂式高空作业车|直臂车)$/.test(r.device.trim());}
function plateMissing(r){if(!plateApplies(r)||r.plateNotRequired)return false;return !r.plate.trim()||/^(无|无牌|场内|炮捶|加班.*|有加班)$/.test(r.plate.trim());}''')
    s=s.replace('按原表列序和项目分段编辑；租赁日期可填单日或期间。','场内设备按类别免查车牌；道路车辆缺牌才待补。旧包月表未设车牌栏的月份免查。租赁日期可填单日或期间。')
    # Per-bill exceptions remain independent of the two cumulative comparisons.
    s=s.replace('data.billDifferences.some(b=>b.project===p)||unresolved(p)',"data.billDifferences.some(b=>b.project===p&&!billIgnored(b))||unresolved(p)")
    s=s.replace('const bs=data.billDifferences.filter(b=>b.project===p);dialog', 'const bs=data.billDifferences.filter(b=>b.project===p);dialog')
    a=s.index('${bs.length?`<button class="link bill-warning"');b=s.index('</td><td>',a)
    s=s[:a]+'${billDifferenceCell(p,bs)}'+s[b:]
    s=s.replace('<th class="num">审批－结算</th></tr>', '<th class="num">审批－结算</th><th>操作</th></tr>')
    s=s.replace('<b>${fmt(b.approval-b.settlement)}</b></td></tr>', '''<b>${fmt(b.approval-b.settlement)}</b></td><td><button class="link" onclick="ignoreBill('${b.bill}',${billIgnored(b)})">${billIgnored(b)?'撤销忽略':'忽略此单差额'}</button></td></tr>''')
    extra='''
function billSignature(b){return JSON.stringify([b.project,b.bill,b.settlement,b.approval]);}
function billIgnored(b){return (data.ignoredBills||[]).includes(billSignature(b));}
function ignoreBill(bill,undo=false){const b=data.billDifferences.find(b=>b.bill===bill);if(!b)return;const signature=billSignature(b);data.ignoredBills||=[];data.ignoredBills=data.ignoredBills.filter(s=>s!==signature);if(!undo)data.ignoredBills.push(signature);saveIgnored();const wasOpen=document.getElementById('dlg').open;render();if(wasOpen)billDetail(b.project);notify(undo?'已恢复该单差额提醒。':'已忽略该单这次结算／审批差额。');}
function billDifferenceCell(p,bs){if(!bs.length)return '—';const pending=bs.filter(b=>!billIgnored(b));return `<div class="bill-comparison ${pending.length?'has-difference':''}">${bs.map(b=>`<div class="bill-amounts"><span>结 ${fmt(b.settlement)}</span><span>审 ${fmt(b.approval)}</span></div>`).join('')}<div class="bill-links"><button class="link sm" onclick="billDetail(${p})">${pending.length?bs.length+'张 · 明细':'已忽略 · 明细'}</button>${bs.length===1?`<button class="link sm" aria-label="${esc(names[p])}单据${billIgnored(bs[0])?'撤销忽略':'忽略本次差额'}" onclick="ignoreBill('${bs[0].bill}',${billIgnored(bs[0])})">${billIgnored(bs[0])?'撤销':'忽略'}</button>`:''}</div></div>`;}
function saveIgnored(){try{localStorage.setItem('machinery-prototype-ignore-v2',JSON.stringify({differences:data.ignoredDifferences||{},bills:data.ignoredBills||[]}));}catch{notify('浏览器未能保存忽略记录，请保留本页。');}}
function loadIgnored(){try{const saved=JSON.parse(localStorage.getItem('machinery-prototype-ignore-v2')||'{}');data.ignoredDifferences=saved.differences||{};data.ignoredBills=Array.isArray(saved.bills)?saved.bills:[];}catch{data.ignoredDifferences={};data.ignoredBills=[];}}
'''
    s=s.replace('\nrender();\n</script>',extra+'\nloadIgnored();\nrender();\n</script>')
    s=s.replace('data.audits.push({kind:undo?', 'saveIgnored();data.audits.push({kind:undo?')
    s=s.replace('修改仅在内存，刷新恢复载入值。','金额编辑刷新恢复；忽略记录保存在本机浏览器。')
    s=s.replace('data=makeDemo();ui={...ui,', 'data=makeDemo();saveIgnored();ui={...ui,')
    s=s.replace('<col style="width:90px">','<col style="width:160px">')
    s=s.replace('.cumulative-table{min-width:1200px;', '.cumulative-table{min-width:1270px;')
    s=s.replace('</style>', '''
.bill-comparison{text-align:right;font-size:12px;line-height:1.45}.bill-comparison.has-difference .bill-amounts{color:var(--dg-d)}.bill-amounts span{display:block;font-variant-numeric:tabular-nums}.bill-links{display:flex;justify-content:flex-end;gap:12px}.bill-links .link{font-size:11px}.cumulative-table .bill-comparison{padding:3px 0}
</style>''',1)
    put('differenceIgnored', '''function differenceIgnored(p,relation){const c=cumulative(p),raw=relation==='fees'?c.diff:c.second;return raw!==null&&raw!==0&&remainingDifference(p,relation)===0;}
function remainingDifference(p,relation){const c=cumulative(p),raw=relation==='fees'?c.diff:c.second;if(raw===null||raw===0)return raw;return raw-(Number(data.ignoredDifferences?.[`${p}|${relation}`])||0);}''')
    put('pruneIgnoredDifferences', '''function pruneIgnoredDifferences(){/* Ignored amounts are a durable baseline, independent of future cumulative totals. */}''')
    put('ignoreDifference', '''function ignoreDifference(p,relation,undo=false){const c=cumulative(p),raw=relation==='fees'?c.diff:c.second;if(raw===null)return;data.ignoredDifferences||={};const k=`${p}|${relation}`,before=Number(data.ignoredDifferences[k])||0;if(undo)delete data.ignoredDifferences[k];else data.ignoredDifferences[k]=raw;data.audits.push({kind:undo?'撤销忽略差额':'忽略新增差额',project:p,relation,value:raw-before,baseline:undo?0:raw,at:new Date().toISOString()});saveIgnored();render();notify(undo?'已恢复差额提醒。':'已留底忽略金额，以后只提示新增差额。');}''')
    put('differenceCell', '''function differenceCell(p,relation,value){const pending=remainingDifference(p,relation),baseline=Number(data.ignoredDifferences?.[`${p}|${relation}`])||0;return `<td class="num ${pending?'danger-text':''}">${fmt(pending)}${value!==null&&(value!==0||baseline)?`<div>${pending?`<button class="link sm" aria-label="${esc(names[p])}${relation==='fees'?'报表':'内部'}忽略本次差额" onclick="ignoreDifference(${p},'${relation}')">忽略新增差额</button>`:baseline?`<button class="link sm mut" aria-label="${esc(names[p])}${relation==='fees'?'报表':'内部'}撤销忽略" onclick="ignoreDifference(${p},'${relation}',true)">已忽略 · 撤销</button>`:''}</div>`:''}</td>`;}''')
    put('loadIgnored', '''function loadIgnored(){try{const saved=JSON.parse(localStorage.getItem('machinery-prototype-ignore-v2')||'{}');data.ignoredDifferences={};for(const [k,v] of Object.entries(saved.differences||{})){if(typeof v==='number'&&Number.isFinite(v))data.ignoredDifferences[k]=v;else if(typeof v==='string'){const a=JSON.parse(v);if(Array.isArray(a)&&a.every(x=>x===null||Number.isFinite(x)))data.ignoredDifferences[k]=k.endsWith('|fees')?a[0]-a[1]-(a[2]||0):a[0]-a[1]-a[2];}}data.ignoredBills=Array.isArray(saved.bills)?saved.bills:[];}catch{data.ignoredDifferences={};data.ignoredBills=[];}}''')
    s=s.replace("(c.diff!==0&&!differenceIgnored(p,'fees'))||(c.second!==0&&!differenceIgnored(p,'internal'))", "remainingDifference(p,'fees')!==0||remainingDifference(p,'internal')!==0")
    s=s.replace('差额＝左－右','待处理差额')
    s=s.replace('两条差额均为左侧减右侧。班组消耗采用审批金额；结算／审批不同仍逐单保留。','待处理差额＝左侧－右侧－已忽略金额；原始差额和忽略留底见“依据”。班组消耗采用审批金额，单据两额不同单独处理。')
    s=s.replace('<span>累计沿最新年度汇总接续，历史月报按当时报送版本保留。</span>', '''<span>原始差额：报表 ${fmt(c.diff)}，内部 ${fmt(c.second)}；已忽略留底：报表 ${fmt(Number(data.ignoredDifferences?.[p+'|fees'])||0)}，内部 ${fmt(Number(data.ignoredDifferences?.[p+'|internal'])||0)}。累计沿最新年度汇总接续。</span>''')
    for obsolete in ['differenceSignature','pruneIgnoredDifferences']:
        s=s.replace(get(obsolete),'')
    s=s.replace('pruneIgnoredDifferences();','')
    s=s.replace('两条累计关系的差额', '两条累计关系的待处理差额')
    s=s.replace('试用修改只在页面内存，刷新恢复。原Excel和i8单据不修改。','金额和明细编辑只在页面内存，刷新恢复；忽略留底单独保存在本机浏览器，重置试用会清除。原Excel和i8单据不修改。')
    s=re.sub(r'<div class="fi"><label for="project-focus">.*?</select></div>','',s)
    s='\n'.join(line for line in s.split('\n') if "document.getElementById('project-focus')" not in line)
    s=s.replace("function render(){", "function render(){\nif(ui.view!=='details'||ui.preview)ui.focus='all';",1)
    s=s.replace("const scoped=()=>data.order.filter(p=>data.selected.includes(p)&&(ui.focus==='all'||p===Number(ui.focus)));", "const scoped=()=>data.order.filter(p=>data.selected.includes(p)&&(ui.view!=='details'||ui.preview||ui.focus==='all'||p===Number(ui.focus)));")
    s=s.replace("function navigate(v){if(v==='issues'){openIssues();return;}ui.preview=false;", "function navigate(v){if(v==='issues'){openIssues();return;}ui.focus='all';ui.preview=false;")
    s=s.replace("ui.focus=ui.returnFocus??'all';", "ui.focus='all';")
    s=s.replace("ui.month=m;data.checked=[];", "ui.month=m;ui.focus='all';data.checked=[];")
    s=s.replace("<button class=\"btn sm\" onclick=\"ui.focus='all';ui.onlyProblems=false;render()\">查看全部所选项目</button>", "${ui.focus!=='all'?`<span class=\"mut sm\">临时筛选：${esc(names[Number(ui.focus)])}</span><button class=\"btn sm\" onclick=\"ui.focus='all';render()\">取消筛选</button>`:''}")
    s=s.replace('${plateExemption(r)}','')
    put('plateField', '''function plateField(r){if(!plateApplies(r)&&!r.plate.trim())return '<span class="mut sm" title="按设备类别规则免查道路车牌">无需车牌</span>';return detailInput(r,'plate',plateApplies(r)?'车牌':'车牌（选填）');}''')
    s=s.replace('if(!plateApplies(r)||r.plateNotRequired)return false;', 'if(!plateApplies(r))return false;')
    for obsolete in ['plateExemption','setNoPlate']:
        s=s.replace(get(obsolete),'')
    put('plateApplies', '''function plateApplies(r){if(r.cat==='monthly'&&r.month<'2026-06')return false;return !(data.plateExemptDevices??defaultPlateExemptDevices()).includes(r.device.trim());}
function defaultPlateExemptDevices(){return ['挖机','挖掘机','叉车','铲车','压路机','发电机','塔吊','履带吊','升降','直臂式高空作业车','直臂车'];}''')
    d=get('detailView').replace('<div class="sp"><button class="btn" onclick="saveDetails()">','<div class="sp"><button class="btn" onclick="openPlateRules()">车牌规则</button><button class="btn" onclick="saveDetails()">')
    d=d.replace('场内设备按类别免查车牌；道路车辆缺牌才待补。','车牌按设备规则检查，可在右上角“车牌规则”调整。')
    put('detailView',d)
    extra='''
function openPlateRules(){dialog('无需车牌名单',`<p class="section-note">名单内无需车牌，其余设备需要车牌。每行一个设备名称，按完整名称匹配；零租、包月及所有项目共用。</p><div class="formline"><label for="plate-exempt-list">设备名称</label><textarea id="plate-exempt-list" class="inp" rows="12" maxlength="5000">${esc((data.plateExemptDevices??defaultPlateExemptDevices()).join('\\n'))}</textarea></div><p class="section-note">旧包月表1—5月未设车牌栏，仍免查未采集字段。</p>`,`<button class="btn" onclick="closeDialog()">取消</button><button class="btn pri" onclick="savePlateRules()">保存名单</button>`);}
function savePlateRules(){const devices=[...new Set(document.getElementById('plate-exempt-list').value.split(/\\r?\\n/).map(s=>s.trim()).filter(Boolean))];if(devices.some(s=>s.length>40)){notify('每行填写一个设备名称，最长40字。');return;}try{localStorage.setItem('machinery-prototype-plate-exempt-v2',JSON.stringify(devices));}catch{notify('未能保存名单，请检查浏览器本地存储后重试。');return;}data.plateExemptDevices=devices;closeDialog();render();notify('无需车牌名单已保存，待补检查已统一更新。');}
function loadPlateRules(){data.plateExemptDevices=defaultPlateExemptDevices();try{const saved=JSON.parse(localStorage.getItem('machinery-prototype-plate-exempt-v2')||'null');if(Array.isArray(saved)){if(!saved.every(s=>typeof s==='string'&&s.trim()&&s.length<=40))throw new Error('invalid list');data.plateExemptDevices=[...new Set(saved.map(s=>s.trim()))];}else{const old=JSON.parse(localStorage.getItem('machinery-prototype-plate-rules-v1')||'{}');if(Object.keys(old).length)data.plateExemptDevices=Object.entries(old).filter(([name,value])=>value===false&&name.trim()&&name.length<=40).map(([name])=>name.trim());}}catch{notify('名单读取失败，暂用历史分类默认名单。');}}
function clearPlateRules(){try{localStorage.setItem('machinery-prototype-plate-rules-v1','{}');localStorage.setItem('machinery-prototype-plate-exempt-v2','null');}catch{notify('未能清除本机车牌名单。');}}
'''
    s=s.replace('\nloadIgnored();\nrender();',extra+'\nloadIgnored();\nloadPlateRules();\nrender();')
    s=s.replace('data=makeDemo();saveIgnored();','data=makeDemo();saveIgnored();clearPlateRules();')
    s=s.replace(".includes(r.device.trim());", ".some(keyword=>r.device.trim().includes(keyword));")
    s=s.replace('每行一个设备名称，按完整名称匹配；零租、包月及所有项目共用。','每行一个关键词，设备名称包含任意一个关键词即免查。例如“升降”覆盖升降车、升降平台、升降车12米；零租、包月及所有项目共用。')
    s=s.replace('名单内无需车牌，其余设备需要车牌。','命中关键词的设备无需车牌，其余设备需要车牌。')
    s=s.replace('<label for="plate-exempt-list">设备名称</label>', '<label for="plate-exempt-list">免查关键词</label>')
    s=s.replace('每行填写一个设备名称，最长40字。','每行填写一个关键词，最长40字。')
    return s
