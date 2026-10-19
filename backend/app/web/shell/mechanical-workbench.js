/* 机械费四页工作区。有效月值及核对判定以系统回执为准，编辑草稿只驻留内存。 */
const MW = {
  data: null, month: bjMonth(-1), tab: 'summary', scope: '', onlyProblems: false,
  drafts: new Map(), internal: new Map(), busy: false, error: '', loading: false,
  filter: 'pending', preview: null, picker: null, confirmation: [], sequence: 0,
};
const MW_FIELDS = {
  zero: [['device','设备名称'],['spec','规格型号'],['unit','单位'],['qty','数量'],['rate','零租单价'],['amount','合价（元）'],['tax','票种／税率'],['net','不含税价'],['date','租赁日期／期间'],['use','用途'],['team','使用班组'],['reviewer','审核人'],['vendor','出租单位'],['plate','车牌号'],['memo','备注']],
  monthly: [['device','设备名称'],['spec','规格型号'],['unit','单位'],['plan','计划月数'],['used','已包月数'],['rate','包月单价'],['amount','合价（元）'],['net','不含税价'],['date','入场日期'],['vendor','出租单位'],['reviewer','审核人'],['tax','票种／税率'],['oil','含油说明'],['plate','车牌号'],['memo','原备注']],
};
const mwKey = (warehouse, category, month=MW.month) => JSON.stringify([warehouse, month, category]);
const mwProjectKey = p => typeof p === 'string' ? p : p.warehouse;
const mwProjects = () => (MW.data?.projects || []).map(mwProjectKey);
const mwName = key => {
  const project = (MW.data?.projects || []).find(p => mwProjectKey(p) === key);
  return project?.name || project?.display_name || (typeof pjLabel === 'function' ? pjLabel(key) : key);
};
const mwConfig = () => MW.data?.settings || {};
const mwShown = () => mwConfig().shown_projects || mwProjects();
const mwScoped = () => MW.scope ? [MW.scope] : mwShown();
const mwCategory = () => MW.tab === 'monthly' ? 'monthly' : 'zero';
const mwDetail = (warehouse, category=mwCategory()) => (MW.data?.details || []).find(x => x.warehouse===warehouse && x.ym===MW.month && x.category===category) || {warehouse, ym:MW.month, category, revision:0, rows:[], totals:{}, issues:[]};
const mwRows = (warehouse, category=mwCategory()) => MW.drafts.get(mwKey(warehouse,category))?.rows || mwDetail(warehouse,category).rows;
const mwEffective = warehouse => (MW.data?.effective || []).find(x => x.warehouse===warehouse && x.ym===MW.month) || {values:{},signature:''};
const mwInternal = warehouse => MW.internal.get(mwKey(warehouse,'internal'))?.values || {};
const mwInternalValid = value => /^\d+(?:\.\d{1,2})?$/.test(String(value).trim());
function mwNumber(value) {
  if(value===null || value===undefined || String(value).trim()==='') return null;
  const text=String(value).trim();
  if(!/^-?\d+(?:\.\d+)?$/.test(text)) return null;
  const sign=text.startsWith('-')?-1n:1n, [whole,fraction='']=text.replace(/^-/, '').split('.');
  return {value:sign*BigInt(whole+fraction),places:fraction.length};
}
const mwRound = (value,divisor) => (value<0n?-1n:1n)*(((value<0n?-value:value)*2n+divisor)/(divisor*2n));
const mwCents = value => {const number=mwNumber(value);return number?mwRound(number.value*100n,10n**BigInt(number.places)):null;};
function mwSum(values) {
  const numbers=values.map(mwNumber).filter(Boolean);if(!numbers.length)return null;
  const places=Math.max(...numbers.map(number=>number.places));
  const total=numbers.reduce((sum,number)=>sum+number.value*10n**BigInt(places-number.places),0n);
  return mwDecimal(mwRound(total*100n,10n**BigInt(places)));
}
function mwEqual(left,right) {
  const a=mwNumber(left),b=mwNumber(right);if(!a||!b)return false;
  return a.value*10n**BigInt(b.places)===b.value*10n**BigInt(a.places);
}
function mwMoney(value) {
  const cents=mwCents(value); if(cents===null) return '—';
  const abs=cents<0n?-cents:cents;
  return (cents<0n?'-':'')+(abs/100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g,',')+'.'+(abs%100n).toString().padStart(2,'0');
}
const mwDecimal = cents => cents===null ? null : (cents<0n?'-':'')+((cents<0n?-cents:cents)/100n)+'.'+((cents<0n?-cents:cents)%100n).toString().padStart(2,'0');
function mwNet(row) {
  if(Object.hasOwn(row,'net')) return mwNumber(row.net)?String(row.net):null;
  const amount=mwNumber(row.amount); if(amount===null || !row.tax) return null;
  const ordinary=String(row.tax).includes('普票');
  const match=String(row.tax).trim().match(/^(?:专票\s*)?(\d+(?:\.\d+)?)\s*%(?:\s*专票?)?(?:[，,\s].*)?$/);
  if(!ordinary&&(!match||Number(match[1])>100))return null;
  if(mwNumber(row.sourceNet)&&mwEqual(row.amount,row.originalAmount ?? row.original)&&row.tax===(row.originalTax ?? row.rawTax)) return String(row.sourceNet);
  if(ordinary) return String(row.amount);
  const rate=BigInt(match[1].replace('.','')), scale=10n**BigInt((match[1].split('.')[1]||'').length), base=100n*scale, divisor=base+rate;
  return mwDecimal(mwRound(amount.value*100n*base,divisor*10n**BigInt(amount.places)));
}
function mwTotals(rows) {
  const nets=rows.map(mwNet);
  return {amount:mwSum(rows.map(row=>row.amount)),net:mwSum(nets),missing:nets.filter(value=>value===null).length};
}
function mwPlateRequired(row, category=mwCategory()) {
  if(category==='monthly' && MW.month<'2026-06') return false;
  return !(mwConfig().plate_keywords || []).some(word=>String(row.device||'').includes(word));
}
function mwRowProblems(row, category=mwCategory()) {
  const problems=[];
  if(!String(row.device||'').trim()) problems.push('设备待补');
  if(mwCents(row.amount)===null) problems.push('合价待补');
  if(mwNet(row)===null) problems.push('票种／税率待补');
  if(mwPlateRequired(row,category) && (!String(row.plate||'').trim() || /^(无|无牌|场内|炮捶|加班.*|有加班)$/.test(String(row.plate).trim()))) problems.push('车牌待补');
  return problems;
}
function mwButton(label, action, attrs='', primary=false) {
  return `<button class="btn${primary?' pri':''}" data-act="${action}" ${attrs} ${MW.busy?'disabled data-mw-busy="1" title="正在处理，请稍候"':''}>${label}</button>`;
}
function mwNotify(message) { toast(esc(message)); }
function mwPaint() { if(VIEW==='m10') render(); }
function clearMechanicalWorkbenchScope() { MW.scope=''; MW.onlyProblems=false; }
async function reloadMechanicalWorkbench() {
  const request=++MW.sequence, month=MW.month;
  MW.loading=true; MW.error='';
  try {
    const data=await API.get('/api/m06/workbench?ym='+encodeURIComponent(month));
    if(data.ok===false) throw errHuman(data.message || '机械费没能读取，请重试。');
    if(request!==MW.sequence || month!==MW.month) return;
    MW.data=data;
  } catch(error) {
    if(request===MW.sequence) MW.error=error.message || '机械费没能读取，请重试。';
    throw error;
  } finally { if(request===MW.sequence) MW.loading=false; }
}
async function mwPost(action, body) {
  const result=await API.post('/api/m06/workbench/'+action,body);
  if(result.ok===false) throw errHuman(result.message || '修改没能保存，请核对后重试。');
  MW.needsRefresh=true;
  return result;
}
async function mwRefresh() {
  await reloadMechanicalWorkbench();
  await Promise.all([reloadMech(),reloadProc()]);
  MW.needsRefresh=false;
}
async function mwRun(work) {
  if(MW.busy) return;
  MW.busy=true; mwPaint();
  try { await work(); }
  catch(error) {
    if(MW.needsRefresh){try{await mwRefresh();}catch(refreshError){MW.error=refreshError.message||'保存后没能重新读取，请重试。';}}
    mwNotify(error.message || '这一步没能完成，请重试。');
  }
  finally { MW.busy=false; document.querySelectorAll('[data-mw-busy]').forEach(button=>{button.disabled=false;button.removeAttribute('data-mw-busy');});mwPaint(); }
}
function mwToolbar() {
  return `<div class="mw-toolbar"><nav class="mw-tabs" aria-label="机械费报表">${[['summary','表1·公司汇总'],['zero','表2·零租明细'],['monthly','表3·包月明细'],['work','核对工作台']].map(([id,label])=>`<button class="btn ${MW.tab===id?'on':''}" data-act="mwTab" data-tab="${id}" aria-current="${MW.tab===id?'page':'false'}">${label}</button>`).join('')}</nav><div class="sp"><label class="mw-month">月份 <input class="inp" type="month" aria-label="机械费查看月份" data-act="mwMonth" value="${esc(MW.month)}" ${MW.busy?'disabled':''}></label>${mwButton('显示项目','mwProjects')}${mwButton('录入预览','mwImport')}</div></div>`;
}
function mwSummary() {
  const fields=[['mech_2','零租'],['mech_3','包月'],['weekly','周材'],['mech_1','内租（租赁公司）'],['mech_0','内租（工程公司）']];
  const shown=mwShown();
  const sum=mwSum;
  return `<div class="mw-actions"><strong>公司汇总</strong><span class="mut">金额单位：元</span><div class="sp">${mwButton('确认内租（'+MW.internal.size+'项）','mwInternalReview')}${mwButton('取消内租修改','mwInternalCancel')}${mwButton('导出预览','mwPreview','',true)}</div></div><p class="mw-note">零租、包月从明细确认更新；点击月值进入明细。内租填数后确认生效。</p><div class="tw mw-scroll"><table class="dt mw-company"><thead><tr><th rowspan="2">序号</th><th rowspan="2" class="mw-project">项目名称</th><th colspan="2" class="vsep">开工日期</th><th colspan="5" class="vsep">开工累计费用（元）</th><th colspan="5" class="vsep">本月产生费用（元）</th><th rowspan="2" class="vsep">备注</th></tr><tr><th class="vsep">年份</th><th>月份</th>${[...fields,...fields].map(([,label],index)=>`<th${index%fields.length===0?' class="vsep"':''}>${label}</th>`).join('')}</tr></thead><tbody>${shown.map((warehouse,index)=>{
    const effective=mwEffective(warehouse), values=effective.values||{}, cumulative=mwCumulative(warehouse);
    const summary=(MW.data.summary||[]).find(item=>item.warehouse===warehouse&&item.ym===MW.month)||{};
    const history=(MW.data.histories||[]).find(item=>item.warehouse===warehouse)||{}, meta=history.meta_at?.[MW.month]||{};
    return `<tr><td>${index+1}</td><td class="mw-project"><b>${esc(mwName(warehouse))}</b></td><td class="vsep">${esc(meta.year||summary.start_year||'—')}</td><td>${esc(meta.month||summary.start_month||'—')}</td>${fields.map(([key],index)=>`<td class="num${index===0?' vsep':''}">${mwMoney(cumulative[key])}</td>`).join('')}${fields.map(([key,label],index)=>{
      if(key==='mech_2'||key==='mech_3') return `<td class="num${index===0?' vsep':''}"><button class="text-link" data-act="mwOpenDetail" data-pj="${esc(warehouse)}" data-category="${key==='mech_2'?'zero':'monthly'}"><span class="text-link-label">${mwMoney(values[key])}</span></button></td>`;
      if(key==='weekly') return '<td class="num">'+mwMoney(history.original_months?.[MW.month]?.weekly)+'</td>';
      const value=mwInternal(warehouse)[key] ?? values[key] ?? '';
      return `<td><input class="inp num${mwInternal(warehouse)[key]!==undefined?' mw-dirty':''}" aria-label="${esc(mwName(warehouse)+label)}" inputmode="decimal" data-act="mwInternalEdit" data-pj="${esc(warehouse)}" data-field="${key}" value="${esc(value)}" ${MW.busy?'disabled':''}></td>`;
    }).join('')}<td class="vsep">${esc(summary.note||'')}</td></tr>`;
  }).join('') || '<tr><td colspan="15" class="empty">尚未选择显示项目。用“显示项目”选入已有项目。</td></tr>'}${shown.length?`<tr class="sumrow"><td colspan="4">已知合计</td>${fields.map(([key],index)=>`<td class="num${index===0?' vsep':''}">${mwMoney(sum(shown.map(warehouse=>mwCumulative(warehouse)[key])))}</td>`).join('')}${fields.map(([key],index)=>`<td class="num${index===0?' vsep':''}">${mwMoney(sum(shown.map(warehouse=>mwEffective(warehouse).values[key])))}</td>`).join('')}<td class="vsep"></td></tr>`:''}</tbody></table></div>`;
}
function mwCumulative(warehouse) {
  const entry=(MW.data?.summary||[]).find(x=>x.warehouse===warehouse&&x.ym===MW.month);
  const values=entry?.cumulative || mwEffective(warehouse).cumulative || {};
  return {mech_2:values.zero,mech_3:values.monthly,weekly:values.weekly,mech_1:values.internal,mech_0:values.company};
}
function mwInput(row,field,label,index,warehouse) {
  const num=['qty','plan','used','rate','amount'].includes(field);
  const attrs=`data-act="mwEdit" data-pj="${esc(warehouse)}" data-index="${index}" data-field="${field}" aria-label="${esc(mwName(warehouse)+' 第'+(index+1)+'行 '+label)}"`;
  if(field==='net') return `<span class="mw-net">${mwNet(row)===null?'待补税率':mwMoney(mwNet(row))}</span>`;
  if(field==='plate' && !mwPlateRequired(row) && !row.plate) return `<span class="mut mw-exempt">无需车牌</span>`;
  const alias={use:'usage',vendor:'lessor',memo:'note'}[field];
  return `<input class="inp ${num?'num':''}" type="text" ${num?'inputmode="decimal"':''} ${attrs} value="${esc(row[field]??row[alias]??'')}" ${MW.busy?'disabled':''}>`;
}
function mwDetails() {
  const category=mwCategory(), fields=MW_FIELDS[category], gross=fields.findIndex(([key])=>key==='amount')+1, net=fields.findIndex(([key])=>key==='net')+1;
  let count=0;
  const body=mwScoped().map(warehouse=>{
    const rows=mwRows(warehouse), shown=rows.map((row,index)=>({row,index})).filter(({row})=>!MW.onlyProblems||mwRowProblems(row).length);
    const saved=mwDetail(warehouse), draft=MW.drafts.has(mwKey(warehouse,category)), totals=draft?mwTotals(rows):{amount:saved.totals.gross,net:saved.totals.net,missing:rows.filter(row=>mwNet(row)===null).length};
    count+=shown.length;
    const group=`<tr class="mw-group"><td colspan="${gross}"><b>${esc(mwName(warehouse))}</b><span class="mut"> · ${shown.length}条${draft?' · 待保存（草稿参考）':''}</span></td>${fields.slice(gross-1).map(([,label],offset)=>{
      const col=gross+offset;
      return `<td class="${col===gross||col===net?'num':''}" ${col===gross?'data-mw-gross="'+esc(warehouse)+'"':col===net?'data-mw-net="'+esc(warehouse)+'"':''}>${col===gross?mwMoney(totals.amount):col===net?mwMoney(totals.net)+(totals.missing?'（'+totals.missing+'条待补）':''):''}</td>`;
    }).join('')}<td class="mw-row-actions">${mwButton('增行','mwAdd','data-pj="'+esc(warehouse)+'"')}</td></tr>`;
    const data=shown.map(({row,index})=>`<tr data-mw-row="${index}"><td class="mut">${index+1}</td>${fields.map(([field,label])=>`<td class="${field==='net'?'num':''}">${mwInput(row,field,label,index,warehouse)}</td>`).join('')}<td class="mw-row-actions"><button class="text-link mw-danger" data-act="mwRemove" data-pj="${esc(warehouse)}" data-index="${index}" ${MW.busy?'disabled title="正在处理，请稍候"':''}><span class="text-link-label">移除</span></button></td></tr>`).join('');
    return group+data+(!shown.length?`<tr><td colspan="${fields.length+2}" class="mw-empty">${MW.onlyProblems?'此项目没有待补字段。':'尚无明细；在项目右侧“增行”录入。有效月值保留。'}</td></tr>`:'');
  }).join('');
  return `<div class="mw-actions"><strong>${category==='zero'?'零租设备月报':'包月外租设备月报'}</strong>${MW.scope?`<span class="mut">临时筛选：${esc(mwName(MW.scope))}</span>${mwButton('取消筛选','mwClearScope')}`:''}<label class="mw-check"><input type="checkbox" data-act="mwProblems" ${MW.onlyProblems?'checked':''}> 仅看待补字段</label><div class="sp">${mwButton('车牌规则','mwPlate')}${mwButton('撤销未保存修改','mwDiscard')}${mwButton('仅保存明细','mwSave')}${mwButton('保存并确认汇总','mwSaveConfirm','',true)}${mwButton('导出预览','mwPreview')}</div></div><p class="mw-note">保存明细不会改变有效月值；确认汇总后生效。待补筛选只改变显示，项目合计包含全部明细。</p><div class="tw mw-scroll"><table class="dt mw-details ${category}"><thead><tr><th>序号</th>${fields.map(([,label])=>`<th>${label}</th>`).join('')}<th class="mw-row-actions">操作</th></tr></thead><tbody>${body||`<tr><td class="empty" colspan="${fields.length+2}">尚未选择显示项目。用“显示项目”选入已有项目后增行。</td></tr>`}</tbody></table></div><div class="mw-footer mut">当前显示 ${count} 条 · 项目合计见合价、不含税价列</div>`;
}
function mwRelation(rec,relation) { return rec[relation] || {}; }
function mwReconciliations() {
  return mwProjects().map(warehouse=>{
    const rows=(MW.data?.reconciliations||[]).filter(r=>r.warehouse===warehouse);
    return {warehouse, report:rows.find(r=>r.relation==='report')||{}, internal:rows.find(r=>r.relation==='internal')||{},
      fetched_at:rows[0]?.fetched_at, documents:(MW.data?.billDifferences||[]).filter(d=>d.warehouse===warehouse).map(d=>({...d,id:d.document_id,document_no:d.bill,period:d.periodName||d.periodKey}))};
  });
}
function mwPending(rec) {
  return (mwHasData(rec)&&['report','internal'].some(relation=>mwCents(mwRelation(rec,relation).pending)!==0n)) || (rec.documents||[]).some(d=>!d.ignored) || (MW.data?.matters||[]).some(m=>m.warehouse===rec.warehouse&&!m.completed);
}
function mwHasData(rec) {
  const warehouse=rec.warehouse;
  return ['report','internal'].some(relation=>['left','right'].some(key=>mwNumber(mwRelation(rec,relation)[key])!==null)) || (rec.documents||[]).length>0 || (MW.data?.effective||[]).some(row=>row.warehouse===warehouse&&Object.values(row.values||{}).some(value=>mwNumber(value)!==null)) || (MW.data?.details||[]).some(row=>row.warehouse===warehouse&&row.rows.length>0) || (MW.data?.i8||[]).some(row=>row.warehouse===warehouse&&Object.values(row.sources||{}).some(rows=>rows.length>0));
}
function mwDifference(rec,relation) {
  const value=mwRelation(rec,relation), pending=mwCents(value.pending), ignored=mwCents(value.ignored);
  return `<td class="num ${pending!==null&&pending!==0n?'mw-danger':''}">${mwMoney(value.pending)}${pending===null&&mwHasData(rec)?`<div class="mw-sub">${rec.fetched_at?'待核对':'待取数'}</div>`:pending!==null&&pending!==0n?`<div><button class="text-link sm" data-act="mwIgnore" data-pj="${esc(rec.warehouse)}" data-relation="${relation}"><span class="text-link-label">忽略新增差额</span></button></div>`:ignored!==null&&ignored!==0n?`<div><button class="text-link sm" data-act="mwIgnore" data-pj="${esc(rec.warehouse)}" data-relation="${relation}" data-undo="1"><span class="text-link-label">已忽略 · 撤销</span></button></div>`:''}</td>`;
}
function mwWorkTable(records) {
  return `<div class="tw mw-work-scroll"><table class="dt mw-work"><thead><tr><th rowspan="2" class="mw-project">项目</th><th colspan="3" class="vsep">报表核对</th><th colspan="3" class="vsep">i8内部核对</th><th rowspan="2" class="vsep">结算／审批不同</th><th rowspan="2" class="vsep mw-followup">跟进事项</th><th rowspan="2" class="vsep">操作</th></tr><tr><th class="vsep">报表费用累计</th><th>班组使用累计<br>（含历史接续）</th><th>待处理差额</th><th class="vsep">班组使用累计</th><th>项目结算<br>＋班组审批</th><th>待处理差额</th></tr></thead><tbody>${records.map(rec=>{
    const warehouse=rec.warehouse, report=mwRelation(rec,'report'), internal=mwRelation(rec,'internal'), discoveries=(MW.data?.discoveries||[]).filter(d=>d.warehouse===warehouse&&d.status==='pending'), matters=(MW.data?.matters||[]).filter(m=>m.warehouse===warehouse&&!m.completed);
    return `<tr><td class="mw-project"><b>${esc(mwName(warehouse))}</b><div class="mw-sub">${esc(rec.read_at||rec.fetched_at||(mwHasData(rec)?'尚未取数':'尚未录入'))}</div>${MW.filter==='findings'?discoveries.map(d=>`<div><button class="text-link" data-act="mwDiscovery" data-id="${esc(d.id)}"><span class="text-link-label">${esc(d.kind==='first'?'首次取数 · 核实':'取数变化 · 核实')}</span></button></div>`).join(''):''}</td><td class="num vsep">${mwMoney(report.left)}</td><td class="num">${mwMoney(report.right)}</td>${mwDifference(rec,'report')}<td class="num vsep">${mwMoney(internal.left)}</td><td class="num">${mwMoney(internal.right)}</td>${mwDifference(rec,'internal')}<td class="vsep">${(rec.documents||[]).map(document=>`<div class="mw-document ${document.ignored?'':'mw-danger'}"><div>结 ${mwMoney(document.settlement)}<br>审 ${mwMoney(document.approval)}</div><button class="text-link sm" data-act="mwDocument" data-pj="${esc(warehouse)}" data-id="${esc(document.id)}" data-undo="${document.ignored?'1':'0'}"><span class="text-link-label">${document.ignored?'已忽略 · 撤销':'忽略此单差额'}</span></button><span class="mw-sub">${esc(document.document_no||document.id)} · ${esc(document.period||'周期未取得')}</span></div>`).join('')||'—'}</td><td class="vsep mw-followup"><button class="text-link" data-act="mwMatters" data-pj="${esc(warehouse)}"><span class="text-link-label">${matters.length?matters.length+'项未完成':'记录跟进'}</span></button>${matters.length?`<div class="mw-sub">${esc(matters[0].text)}</div>`:''}</td><td class="vsep mw-work-actions">${mwButton('更新i8','mwI8','data-pj="'+esc(warehouse)+'"')}${mwButton('依据','mwBasis','data-pj="'+esc(warehouse)+'"')}${!mwShown().includes(warehouse)?mwButton('加入显示','mwShowProject','data-pj="'+esc(warehouse)+'"'):''}</td></tr>`;
  }).join('')||'<tr><td colspan="10" class="empty">当前范围没有此类项目。</td></tr>'}</tbody></table></div>`;
}
function mwWork() {
  const discoveries=(MW.data?.discoveries||[]).filter(d=>d.status==='pending'), found=new Set(discoveries.map(d=>d.warehouse));
  const unmapped=discoveries.filter(d=>!d.warehouse);
  const records=mwReconciliations().filter(r=>MW.filter==='findings'?found.has(r.warehouse):mwShown().includes(r.warehouse));
  const shown=MW.filter==='pending'?records.filter(mwPending):records, normal=MW.filter==='pending'?records.filter(r=>mwHasData(r)&&!mwPending(r)):[];
  return `<div class="mw-actions">${[['pending','待处理'],['findings','取数变化（'+discoveries.length+'）'],['all','全部显示项目']].map(([filter,label])=>`<button class="btn ${MW.filter===filter?'on':''}" data-act="mwFilter" data-filter="${filter}">${label}</button>`).join('')}<div class="sp">${mwButton('全部跟进','mwMatters')}${mwButton('历史接续','mwHistory')}${mwButton('全量取数','mwI8','',true)}</div></div><p class="mw-note">始终核对当前累计，不随查看月份截断。累计差额与单据结算／审批差额分别处理；原始差额和忽略留底见“依据”。</p>${MW.filter==='findings'&&unmapped.length?`<section><h4>归属待确认</h4><p class="mw-note">未唯一对应档案的i8项目保留来源，不分配金额。核实档案后重新取数，或记录本轮无需补报的说明。</p><table class="dt"><thead><tr><th>i8项目</th><th>班组使用</th><th>项目结算</th><th>班组审批</th><th>操作</th></tr></thead><tbody>${unmapped.map(d=>`<tr><td>${esc(d.projectName||d.projectId)}</td><td>${mwMoney(d.totals?.usage)}</td><td>${mwMoney(d.totals?.project)}</td><td>${mwMoney(d.totals?.team)}</td><td>${mwButton('核实发现','mwDiscovery','data-id="'+esc(d.id)+'"')}</td></tr>`).join('')}</tbody></table></section>`:''}${mwWorkTable(shown)}${normal.length?`<details class="mw-normal"><summary>已对平／已忽略（${normal.length}）</summary>${mwWorkTable(normal)}</details>`:''}`;
}
function mwPreviewView() {
  const preview=MW.preview;
  return `<div class="mw-actions"><strong>报送导出预览 · ${esc(MW.month)}</strong><div class="sp">${mwButton('返回查看／编辑','mwPreviewBack')}${mwButton('下载四页Excel','mwExport','',true)}</div></div><p class="mw-note">采用已保存／已确认版本；未保存修改不进入本次导出。</p>${(preview.warnings||[]).map(w=>`<p class="mw-warning">${esc(typeof w==='string'?w:w.message||w.reason||'存在待核内容')}</p>`).join('')}${(preview.sheets||[]).map(sheet=>`<section class="mw-report"><h4>${esc(sheet.name)}</h4><div class="tw"><table class="dt"><tbody>${(sheet.rows||[]).map(row=>`<tr>${row.map(cell=>`<td ${cell.colspan?'colspan="'+Number(cell.colspan)+'"':''} ${cell.rowspan?'rowspan="'+Number(cell.rowspan)+'"':''}>${esc(cell.formatted??cell.value??'')}</td>`).join('')}</tr>`).join('')}</tbody></table></div></section>`).join('')}`;
}
function mechanicalWorkbenchView() {
  const header=mwToolbar(), status=`<div class="mw-status" role="status">${MW.busy?'正在处理，请稍候。':`明细待保存 ${MW.drafts.size}组 · 内租待确认 ${MW.internal.size}项`}</div>`;
  if(MW.loading&&!MW.data) return `<div class="mw-root">${header}<div class="mw-loading" role="status">正在读取机械费…</div></div>`;
  if(MW.error) return `<div class="mw-root">${header}<div class="mw-error" role="alert">${esc(MW.error)} ${mwButton('重新读取','mwReload')}</div>${status}</div>`;
  if(!MW.data) return `<div class="mw-root">${header}<div class="mw-empty">请读取机械费数据。 ${mwButton('读取','mwReload')}</div></div>`;
  return `<div class="mw-root">${header}<section class="card">${MW.preview?mwPreviewView():MW.tab==='summary'?mwSummary():MW.tab==='work'?mwWork():mwDetails()}</section>${status}</div>`;
}
V.m10=mechanicalWorkbenchView;

function mwEditDraft(warehouse) {
  const key=mwKey(warehouse,mwCategory());
  if(!MW.drafts.has(key)) {
    const detail=mwDetail(warehouse);
    MW.drafts.set(key,{warehouse,ym:MW.month,category:mwCategory(),revision:detail.revision,rows:structuredClone(detail.rows)});
  }
  return MW.drafts.get(key);
}
function mwPicker(type='display') {
  MW.picker={type,order:[...mwShown(),...mwProjects().filter(p=>!mwShown().includes(p))],selected:[...mwShown()]};
  mwDrawPicker();
}
function mwDrawPicker() {
  const picker=MW.picker;
  modal({title:picker.type==='display'?'选择显示项目及顺序':'选择本次报送项目',body:`<div class="mw-picker"><p class="mw-note">${picker.type==='display'?'按勾选项目显示，顺序可调整；其他项目的数据保留。':'本次选择只用于导出预览。'}</p><div class="mw-actions">${mwButton('全选','mwPickAll')}${mwButton('全不选','mwPickNone')}<span class="mut">已选 ${picker.selected.length} 个项目</span></div><div class="mw-picker-list">${picker.order.map((warehouse,index)=>`<div class="mw-picker-row"><label><input type="checkbox" class="chk" data-act="mwPick" data-pj="${esc(warehouse)}" ${picker.selected.includes(warehouse)?'checked':''}> ${esc(mwName(warehouse))}</label>${picker.type==='display'?`<span>${mwButton('上移','mwOrder','data-index="'+index+'" data-step="-1" '+(index===0?'disabled':''))}${mwButton('下移','mwOrder','data-index="'+index+'" data-step="1" '+(index===picker.order.length-1?'disabled':''))}</span>`:''}</div>`).join('')}</div></div>`,footer:`<button class="btn" data-act="closeModal">取消</button>${mwButton(picker.type==='display'?'应用项目选择':'生成报送预览','mwPickApply','',true)}`});
}
async function mwSaveDetails() {
  const targets=[...MW.drafts].filter(([,draft])=>draft.ym===MW.month&&draft.category===mwCategory()&&mwScoped().includes(draft.warehouse));
  for(const [key,draft] of targets) {
    await mwPost('details-save',draft);
    MW.drafts.delete(key);
  }
  await mwRefresh();
  return targets.length;
}
function mwConfirmDialog() {
  MW.confirmation=mwScoped().map(warehouse=>{
    const detail=mwDetail(warehouse), effective=mwEffective(warehouse), column=mwCategory()==='zero'?'mech_2':'mech_3';
    return {warehouse, detail, effective, columns:[column,mwCategory()==='zero'?'mech_4':'mech_5']};
  });
  modal({title:'确认有效月值 · '+(mwCategory()==='zero'?'零租':'包月'),wide:true,body:`<p class="mw-note">含税、不含税分别勾选；原人工采用额默认保留。确认后，该格在过程资料中只读。</p><div class="tw mw-confirm-scroll"><table class="dt"><thead><tr><th>项目</th><th>金额</th><th class="num">原有效值</th><th class="num">明细汇总</th><th>采用明细</th><th>状态</th></tr></thead><tbody>${MW.confirmation.flatMap((item,index)=>item.columns.map((column,offset)=>{
    const existing=item.effective.values?.[column],manual=existing!=null&&item.effective.sources?.[column]?.mode!=='detail',label=offset?'不含税':'含税';
    const blocked=!item.detail.rows.length||(item.detail.blocked_columns?.[column]??item.detail.issues).length>0;
    return `<tr><td>${esc(mwName(item.warehouse))}</td><td>${label}</td><td class="num">${mwMoney(existing)}</td><td class="num">${mwMoney(item.detail.totals[offset?'net':'gross'])}</td><td><input type="checkbox" class="chk" data-mw-confirm="${index}" data-column="${column}" ${blocked?'disabled':!manual?'checked':''} aria-label="采用${esc(mwName(item.warehouse))}${label}明细金额"></td><td>${blocked?(!item.detail.rows.length?'缺明细，保留原值':'字段待补，保留原值'):manual?'人工采用值，勾选后替换':'可确认'}</td></tr>`;
  })).join('')}</tbody></table></div>`,footer:`<button class="btn" data-act="closeModal">返回</button>${mwButton('确认勾选金额','mwConfirmApply','',true)}`});
}
function mwMattersDialog(warehouse='') {
  MW.matterScope=warehouse;
  const items=(MW.data?.matters||[]).filter(m=>!warehouse||m.warehouse===warehouse);
  modal({title:'跟进事项'+(warehouse?' · '+esc(mwName(warehouse)):''),wide:true,body:`<div class="mw-matters"><div class="mw-actions"><span class="mut">事项保存／完成不改变费用或忽略记录。</span><div class="sp">${mwButton('新增跟进','mwMatterEdit','data-pj="'+esc(warehouse)+'"',true)}</div></div><table class="dt"><thead><tr><th>项目</th><th>事项／处理备注</th><th>状态</th><th>操作</th></tr></thead><tbody>${items.map(item=>`<tr><td>${esc(mwName(item.warehouse))}</td><td class="mw-matter-text">${esc(item.text)}${mwMatterMetadata(item.metadata)}</td><td>${item.completed?'已确认完成':'未完成'}</td><td>${mwButton('处理','mwMatterEdit','data-id="'+esc(item.id)+'"')}</td></tr>`).join('')||'<tr><td colspan="4" class="empty">当前范围没有跟进事项。</td></tr>'}</tbody></table></div>`});
}
function mwMatterMetadata(metadata={}) {
  const labels={origin:'关联月份',due:'约定月份',amount:'约定金额',mode:'处理方式',evidence:'依据',status:'历史状态',flow:'核查进度',reply:'项目回复'};
  return Object.entries(labels).filter(([key])=>metadata[key]!=null&&metadata[key]!=='').map(([key,label])=>`<div class="mw-sub">${label}：${esc(metadata[key])}</div>`).join('');
}
function mwMatterEditor(id,warehouse) {
  const item=(MW.data?.matters||[]).find(m=>m.id===id)||{warehouse:warehouse||'',text:''};
  MW.editMatter=item;
  modal({title:item.id?'处理跟进事项':'新增跟进事项',body:`<div class="fld"><label for="mwMatterProject">项目</label><select class="inp" id="mwMatterProject"><option value="">请选择项目</option>${mwProjects().map(p=>`<option value="${esc(p)}" ${p===item.warehouse?'selected':''}>${esc(mwName(p))}</option>`).join('')}</select></div><div class="fld"><label for="mwMatterText">事项／处理备注</label><textarea class="inp" id="mwMatterText" rows="4">${esc(item.text)}</textarea></div>`,footer:`<button class="btn" data-act="mwMattersBack">返回跟进</button>${mwButton('保存','mwMatterSave')}${mwButton('确认完成','mwMatterSave','data-completed="1"',true)}`});
}
function mwHistoryBasis(history) {
  return `<div class="mw-note">累计基线：${esc(history.base_month||'未取得')} · ${esc(history.fee_base_source||'来源待核')}<br>原报项目：${esc(history.report_project||mwName(history.warehouse))}</div><table class="dt"><thead><tr><th>月份</th><th>事项</th><th class="num">原报／采用金额</th><th class="num">另一来源金额</th></tr></thead><tbody>${(history.quality||[]).map(item=>`<tr><td>${esc(item.month)}</td><td>${item.cat==='zero'?'零租':'包月'} · ${esc(item.kind||'明细与采用值不同')}</td><td class="num">${mwMoney(item.adopted)}</td><td class="num">明细 ${mwMoney(item.detail)}</td></tr>`).join('')}${(history.month_conflicts||[]).map(item=>`<tr><td>${esc(item.month)}</td><td>当时报送与最新年度不同</td><td class="num">${mwMoney(item.original_month_report)}</td><td class="num">${mwMoney(item.latest_annual_reference)}</td></tr>`).join('')}</tbody></table>${(history.issues||[]).map(item=>`<p class="mw-note">${esc(item.note||'')}${item.reply?'<br>'+esc(item.reply):''}${item.evidence?'<br>依据：'+esc(item.evidence):''}</p>`).join('')}`;
}
function mwBasisDialog(warehouse) {
  const record=mwReconciliations().find(r=>r.warehouse===warehouse), snapshot=(MW.data?.i8||[]).find(r=>r.warehouse===warehouse), history=(MW.data?.histories||[]).find(h=>h.warehouse===warehouse);
  const sources=snapshot?.sources || {};
  modal({title:'核对依据 · '+esc(mwName(warehouse)),wide:true,body:`<div class="mw-basis"><table class="dt"><thead><tr><th>核对关系</th><th class="num">左侧金额</th><th class="num">右侧金额</th><th class="num">原始差额</th><th class="num">忽略留底</th></tr></thead><tbody>${[['report','报表核对'],['internal','i8内部核对']].map(([key,label])=>{const value=record?.[key]||{};return `<tr><td>${label}</td><td class="num">${mwMoney(value.left)}</td><td class="num">${mwMoney(value.right)}</td><td class="num">${mwMoney(value.raw)}</td><td class="num">${mwMoney(value.ignored)}</td></tr>`;}).join('')}</tbody></table><p class="mw-note">取数时间：${esc(record?.fetched_at||'未取得')} · 范围：${esc(typeof snapshot?.scope==='string'?snapshot.scope:JSON.stringify(snapshot?.scope||'未取得'))}</p>${history?`<details><summary>历史来源说明</summary><pre>${esc(JSON.stringify(history,null,2))}</pre></details>`:''}${[['usage','班组设备使用'],['project','项目机械结算'],['team','班组机械消耗']].map(([key,label])=>`<details><summary>${label}（${(sources[key]||[]).length}条）</summary><div class="tw"><table class="dt"><thead><tr><th>单号</th><th>来源周期</th><th class="num">本期结算额</th><th class="num">本期审批额</th></tr></thead><tbody>${(sources[key]||[]).map(row=>`<tr><td>${esc(row.bill||row.id)}</td><td>${esc(row.periodName||row.periodKey||'未可靠映射')}</td><td class="num">${mwMoney(row.amount)}</td><td class="num">${mwMoney(row.approval)}</td></tr>`).join('')}</tbody></table></div></details>`).join('')}</div>`,footer:`<button class="btn" data-act="closeModal">关闭</button>${mwButton('复制核对摘要','mwCopy','data-pj="'+esc(warehouse)+'"')}`});
}
Object.assign(ACT, {
  mwReload:()=>mwRun(async()=>{await mwRefresh();}),
  mwTab:t=>{MW.tab=t.dataset.tab;MW.preview=null;clearMechanicalWorkbenchScope();mwPaint();},
  mwMonth:t=>{
    if(!/^\d{4}-\d{2}$/.test(t.value)){t.value=MW.month;return;}
    MW.month=t.value;MW.preview=null;clearMechanicalWorkbenchScope();
    return mwRun(async()=>{await reloadMechanicalWorkbench();});
  },
  mwOpenDetail:t=>{MW.tab=t.dataset.category;MW.scope=t.dataset.pj;MW.onlyProblems=false;MW.preview=null;mwPaint();},
  mwClearScope:()=>{clearMechanicalWorkbenchScope();mwPaint();},
  mwProblems:t=>{MW.onlyProblems=t.checked;mwPaint();},
  mwProjects:()=>mwPicker('display'),
  mwPick:t=>{const selected=MW.picker.selected; MW.picker.selected=t.checked?[...selected,t.dataset.pj]:selected.filter(p=>p!==t.dataset.pj);mwDrawPicker();},
  mwPickAll:()=>{MW.picker.selected=[...MW.picker.order];mwDrawPicker();},
  mwPickNone:()=>{MW.picker.selected=[];mwDrawPicker();},
  mwOrder:t=>{const index=Number(t.dataset.index), next=index+Number(t.dataset.step),order=MW.picker.order;if(next<0||next>=order.length)return;[order[index],order[next]]=[order[next],order[index]];mwDrawPicker();},
  mwPickApply:()=>mwRun(async()=>{
    const picker=MW.picker, selected=picker.order.filter(p=>picker.selected.includes(p));
    if(picker.type==='export') {
      if(!selected.length) {mwNotify('请至少选择一个报送项目。');return;}
      const preview=await API.get('/api/m06/workbench/preview?ym='+encodeURIComponent(MW.month)+'&projects='+encodeURIComponent(JSON.stringify(selected)));
      if(preview.ok===false)throw errHuman(preview.message||'预览没能生成，请重试。');
      MW.preview={...preview,projects:selected};clearMechanicalWorkbenchScope();closeModal();
    } else {await mwPost('settings',{revision:mwConfig().revision,shown_projects:selected,plate_keywords:mwConfig().plate_keywords||[]});await reloadMechanicalWorkbench();clearMechanicalWorkbenchScope();closeModal();}
  }),
  mwPlate:()=>modal({title:'无需车牌名单',body:`<div class="mw-plate-rules"><p class="mw-note">设备名称包含任一关键词即免查。每行一个关键词，零租、包月及所有项目共用；名单为空时全部设备需要车牌。旧包月1—5月未设车牌栏，仍免查。</p><div class="fld"><label for="mwPlateKeywords">免查关键词</label><textarea class="inp" id="mwPlateKeywords" rows="10" maxlength="5000">${esc((mwConfig().plate_keywords||[]).join('\n'))}</textarea></div></div>`,footer:`<button class="btn" data-act="closeModal">取消</button>${mwButton('保存名单','mwPlateSave','',true)}`}),
  mwPlateSave:()=>mwRun(async()=>{
    const keywords=[...new Set($('#mwPlateKeywords').value.split(/\r?\n/).map(v=>v.trim()).filter(Boolean))];
    await mwPost('settings',{revision:mwConfig().revision,shown_projects:mwShown(),plate_keywords:keywords});await reloadMechanicalWorkbench();closeModal();mwNotify('无需车牌名单已保存。');
  }),
  mwAdd:t=>{const draft=mwEditDraft(t.dataset.pj);draft.rows.push({id:crypto.randomUUID(),device:'',spec:'',unit:'台班',qty:'',plan:'',used:'',rate:'',amount:'',tax:'',date:'',use:'',team:'',reviewer:'',vendor:'',plate:'',memo:'',oil:'',sourceNet:null,original:null});mwPaint();},
  mwRemove:t=>{mwEditDraft(t.dataset.pj).rows.splice(Number(t.dataset.index),1);mwPaint();mwNotify('已从编辑明细移除，保存后生效；有效月值保留。');},
  mwEdit:t=>{
    const draft=mwEditDraft(t.dataset.pj), row=draft.rows[Number(t.dataset.index)], field=t.dataset.field, value=t.value;
    const alias={use:'usage',vendor:'lessor',memo:'note'}[field];
    row[field]=value;if(alias)delete row[alias];
    t.classList.add('mw-dirty');
    const measure=mwCategory()==='zero'?'qty':'used';
    if((field==='rate'||field===measure)&&mwCents(row.rate)!==null&&/^\d+(?:\.\d{1,3})?$/.test(String(row[measure]??''))) {
      const rate=mwNumber(row.rate), quantity=mwNumber(row[measure]);
      row.amount=mwDecimal(mwRound(rate.value*quantity.value*100n,10n**BigInt(rate.places+quantity.places)));
    }
    if(['amount','rate',measure,'tax'].includes(field))delete row.net;
    const tr=t.closest('tr'), amountInput=tr?.querySelector('[data-field="amount"]'), netCell=tr?.querySelector('.mw-net');
    if(amountInput)amountInput.value=row.amount??'';
    if(netCell)netCell.textContent=mwNet(row)===null?'待补税率':mwMoney(mwNet(row));
    const totals=mwTotals(draft.rows);
    document.querySelectorAll('[data-mw-gross]').forEach(cell=>{if(cell.dataset.mwGross===draft.warehouse)cell.textContent=mwMoney(totals.amount);});
    document.querySelectorAll('[data-mw-net]').forEach(cell=>{if(cell.dataset.mwNet===draft.warehouse)cell.textContent=mwMoney(totals.net)+(totals.missing?'（'+totals.missing+'条待补）':'');});
    const status=document.querySelector('.mw-status');if(status)status.textContent=`明细待保存 ${MW.drafts.size}组 · 内租待确认 ${MW.internal.size}项`;
  },
  mwDiscard:()=>{
    const keys=[...MW.drafts].filter(([,draft])=>draft.ym===MW.month&&draft.category===mwCategory()&&mwScoped().includes(draft.warehouse)).map(([key])=>key);
    if(!keys.length){mwNotify('当前范围没有未保存的明细修改。');return;}
    modal({title:'撤销未保存修改',body:`<p>撤销当前范围 ${keys.length} 个项目的未保存修改，恢复最近已保存的明细。</p>`,footer:`<button class="btn" data-act="closeModal">保留修改</button>${mwButton('确认撤销','mwDiscardApply','',true)}`});MW.discardKeys=keys;
  },
  mwDiscardApply:()=>{(MW.discardKeys||[]).forEach(key=>MW.drafts.delete(key));closeModal();mwPaint();mwNotify('已撤销当前范围未保存的修改。');},
  mwSave:()=>mwRun(async()=>{const count=await mwSaveDetails();mwNotify(count?'明细已保存，有效月值仍待确认。':'当前范围没有待保存的修改。');}),
  mwSaveConfirm:()=>mwRun(async()=>{await mwSaveDetails();mwConfirmDialog();}),
  mwConfirmApply:()=>mwRun(async()=>{
    const selected=new Map(),month=MW.month,category=mwCategory(),confirmation=MW.confirmation;
    document.querySelectorAll('[data-mw-confirm]:checked').forEach(el=>{const index=Number(el.dataset.mwConfirm);if(!selected.has(index))selected.set(index,[]);selected.get(index).push(el.dataset.column);});
    if(!selected.size){mwNotify('请勾选需要采用的金额。');return;}
    for(const [index,columns] of selected){const item=confirmation[index];await mwPost('amounts-confirm',{warehouse:item.warehouse,ym:month,category,columns,revision:item.detail.revision,effective_signature:item.effective.signature});}
    await mwRefresh();closeModal();mwNotify('已确认勾选金额的有效月值。');
  }),
  procMechManual:t=>{
    const warehouse=t.dataset.wh,ym=t.dataset.ym,column='mech_'+t.dataset.i;
    MW.manualSource={warehouse,ym,columns:[column],effective_signature:MECH_SIGNATURES[warehouse]?.[ym],confirmed:true};
    modal({title:'切为手填 · '+MECH_LABELS[Number(t.dataset.i)],body:`<p>${esc(pjLabel(warehouse))} · ${esc(ym)}</p><p>当前金额 ${mwMoney(mach6Arr(warehouse,ym)[Number(t.dataset.i)])} 元。切换后保留金额，该格可在过程资料中手填，之后确认明细可重新采用明细汇总。</p>`,footer:`<button class="btn" data-act="closeModal">保留明细来源</button>${mwButton('确认切为手填','procMechManualApply','',true)}`});
  },
  procMechManualApply:()=>mwRun(async()=>{
    const source=MW.manualSource;
    await procMechWrites;
    await mwPost('source-manual',source);
    await mwRefresh();closeModal();render();mwNotify('已切为手填，金额保留。');
  }),
  mwInternalEdit:t=>{MW.internal.set(mwKey(t.dataset.pj,'internal'),{warehouse:t.dataset.pj,ym:MW.month,values:{...mwInternal(t.dataset.pj),[t.dataset.field]:t.value}});t.classList.add('mw-dirty');const status=document.querySelector('.mw-status');if(status)status.textContent=`明细待保存 ${MW.drafts.size}组 · 内租待确认 ${MW.internal.size}项`;},
  mwInternalCancel:()=>{MW.internal.clear();mwPaint();mwNotify('已取消本次内租修改。');},
  mwInternalReview:()=>{
    if(!MW.internal.size){mwNotify('没有待确认的内租修改。');return;}
    modal({title:'确认内租填数',body:`<table class="dt"><thead><tr><th>项目／月份</th><th>类别</th><th class="num">原有效值</th><th class="num">拟采用值</th></tr></thead><tbody>${[...MW.internal.values()].flatMap(draft=>Object.entries(draft.values).map(([key,value])=>`<tr><td>${esc(mwName(draft.warehouse))}／${esc(draft.ym)}</td><td>${key==='mech_0'?'工程公司内租':'租赁公司内租'}</td><td class="num">${mwMoney((MW.data.effective||[]).find(e=>e.warehouse===draft.warehouse&&e.ym===draft.ym)?.values[key])}</td><td class="num">${mwCents(value)===null?'金额无效':mwMoney(value)}</td></tr>`)).join('')}</tbody></table>`,footer:`<button class="btn" data-act="closeModal">返回修改</button>${mwButton('确认更新内租','mwInternalApply','',true)}`});
  },
  mwInternalApply:()=>mwRun(async()=>{
    if([...MW.internal.values()].some(draft=>Object.values(draft.values).some(value=>!mwInternalValid(value)))){mwNotify('内租须填写非负金额，最多两位小数。');return;}
    for(const [key,draft] of MW.internal){const effective=(MW.data.effective||[]).find(e=>e.warehouse===draft.warehouse&&e.ym===draft.ym);await mwPost('internal-save',{...draft,effective_signature:effective?.signature});MW.internal.delete(key);}
    await mwRefresh();closeModal();mwNotify('内租有效月值已确认。');
  }),
  mwFilter:t=>{MW.filter=t.dataset.filter;mwPaint();},
  mwIgnore:t=>mwRun(async()=>{
    const record=(MW.data.reconciliations||[]).find(r=>r.warehouse===t.dataset.pj&&r.relation===t.dataset.relation);
    await mwPost('ignore',{warehouse:record.warehouse,relation:record.relation,revision:record.revision,raw:record.raw,i8_revision:record.i8_revision,undo:t.dataset.undo==='1'});await mwRefresh();mwNotify(t.dataset.undo==='1'?'已恢复差额提醒。':'已留底忽略金额，以后只提示新增差额。');
  }),
  mwDocument:t=>mwRun(async()=>{
    const document=MW.data.billDifferences.find(d=>d.warehouse===t.dataset.pj&&d.document_id===t.dataset.id);
    await mwPost('document-ignore',{warehouse:document.warehouse,document_id:document.document_id,fact:document.fact,revision:document.revision,undo:t.dataset.undo==='1'});await mwRefresh();mwNotify(t.dataset.undo==='1'?'已恢复该单差额提醒。':'已忽略该单这次结算／审批差额。');
  }),
  mwBasis:t=>mwBasisDialog(t.dataset.pj),
  mwCopy:t=>mwRun(async()=>{
    const record=mwReconciliations().find(r=>r.warehouse===t.dataset.pj);
    const text=`${mwName(record.warehouse)}：请核查机械费。\n取数时间：${record.fetched_at||'未取得'}\n报表核对原始差额 ${mwMoney(record.report.raw)} 元，待处理 ${mwMoney(record.report.pending)} 元。\ni8内部原始差额 ${mwMoney(record.internal.raw)} 元，待处理 ${mwMoney(record.internal.pending)} 元。\n`+(record.documents||[]).map(d=>`单据${d.document_no||d.id}，结算${mwMoney(d.settlement)}，审批${mwMoney(d.approval)}。`).join('\n');
    await navigator.clipboard.writeText(text);mwNotify('核对摘要已复制，请自行发送。');
  }),
  mwMatters:t=>mwMattersDialog(t?.dataset.pj||''),
  mwMatterEdit:t=>mwMatterEditor(t.dataset.id,t.dataset.pj),
  mwMattersBack:()=>mwMattersDialog(MW.matterScope),
  mwMatterSave:t=>mwRun(async()=>{
    const warehouse=$('#mwMatterProject').value, text=$('#mwMatterText').value.trim();
    if(!warehouse||!text){mwNotify('请选择项目，记一句事项或处理备注。');return;}
    await mwPost('matter-save',{...MW.editMatter,warehouse,text,completed:t.dataset.completed==='1'});await mwRefresh();mwMattersDialog(MW.matterScope);mwNotify(t.dataset.completed==='1'?'事项已确认完成，金额保持原样。':'事项已保存。');
  }),
  mwDiscovery:t=>{
    const item=MW.data.discoveries.find(d=>d.id===t.dataset.id);MW.discovery=item;
    modal({title:'取数变化 · '+esc(item.warehouse?mwName(item.warehouse):(item.projectName||item.projectId)),body:`<p class="mw-note">${esc(item.kind==='unmapped'?'归属尚未唯一确定，金额未分配；请先核实对应项目。':item.kind==='first'?'首次发现，不据历史非零直接认定漏报。':item.kind==='missing-project'?'原有项目本轮未返回，旧值保留。':'i8单据或金额有变化，请核实报表是否覆盖。')}</p>${item.kind==='unmapped'?`<details><summary>来源依据</summary><p>i8项目：${esc(item.projectId)}</p>${Object.entries(item.sources||{}).map(([kind,rows])=>`<p>${esc(({usage:'班组使用',project:'项目结算',team:'班组消耗'})[kind]||kind)}：${rows.length}条；周期 ${esc([...new Set(rows.map(r=>r.periodName||r.periodKey||'未取得'))].join('、'))}</p>`).join('')}</details>`:''}<div class="fld"><label for="mwDiscoveryNote">本轮无需补报的核实说明</label><textarea class="inp" id="mwDiscoveryNote" rows="4">${esc(item.note||'')}</textarea></div>`,footer:`<button class="btn" data-act="closeModal">返回</button>${mwButton('已核实，本轮无需补报','mwDiscoveryResolve','',true)}`});
  },
  mwDiscoveryResolve:()=>mwRun(async()=>{const note=$('#mwDiscoveryNote').value.trim();if(!note){mwNotify('请填写本轮无需补报的核实说明。');return;}await mwPost('discovery-resolve',{id:MW.discovery.id,revision:MW.discovery.revision,note});await mwRefresh();closeModal();mwNotify('本轮取数变化已核实，以后有新变化仍会提示。');}),
  mwShowProject:t=>mwRun(async()=>{await mwPost('settings',{revision:mwConfig().revision,shown_projects:[...mwShown(),t.dataset.pj],plate_keywords:mwConfig().plate_keywords||[]});await reloadMechanicalWorkbench();mwNotify('已加入显示名单，报表金额保持原样。');}),
  mwHistory:()=>modal({title:'历史接续 · 固定底数',body:`<p class="mw-note">i6仅计入报表核对；老项目可从显示名单退出，历史依据保留。</p><table class="dt"><thead><tr><th>项目</th><th class="num">固定i6</th></tr></thead><tbody>${(MW.data?.reconciliations||[]).filter(r=>r.relation==='report').map(r=>`<tr><td>${esc(mwName(r.warehouse))}</td><td class="num">${mwMoney(r.i6)}</td></tr>`).join('')}</tbody></table>`}),
  mwPreview:()=>{clearMechanicalWorkbenchScope();mwPicker('export');},
  mwPreviewBack:()=>{MW.preview=null;clearMechanicalWorkbenchScope();mwPaint();},
  mwExport:()=>mwRun(async()=>{const filename=await dlExport('/api/m06/workbench/export?ym='+encodeURIComponent(MW.month)+'&projects='+encodeURIComponent(JSON.stringify(MW.preview.projects))+'&snapshot_token='+encodeURIComponent(MW.preview.snapshot_token||''),{name:'机械费报表.xlsx',label:'导出机械费'});if(filename)mwNotify('已导出四页机械费报表。');}),
  mwImport:()=>mechanicalWorkbenchImportDialog(),
  mwI8:t=>mechanicalWorkbenchI8Dialog(t?.dataset.pj||null),
});
const mwOriginalGo=ACT.go;
ACT.go=(...args)=>{if(VIEW==='m10')clearMechanicalWorkbenchScope();return mwOriginalGo(...args);};
