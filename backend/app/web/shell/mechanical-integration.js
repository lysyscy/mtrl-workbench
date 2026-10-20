/* 录入与i8先预览后采用；业务写入与外部Agent使用同一系统入口。 */
const MW_FLOW = {preview:null,kind:'',conflicts:[],file:null};
function mechanicalWorkbenchImportDialog() {
  MW_FLOW.file=null;
  modal({title:'录入原报明细',body:`<label class="mw-field">Agent整理的录入文件<input id="mw-import-file" type="file" accept=".json,application/json"></label><p class="mut">先查看零租／包月明细、来源和修订冲突；确认后才写入。月值在明细页另行确认更新。</p>`,footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="mwImportPreview">查看录入预览</button>`});
}
function mwConflictRows() {
  return MW_FLOW.conflicts.map((c,i)=>`<tr><td>${esc(c.label)}</td><td>${esc(typeof c.current==='object'?JSON.stringify(c.current):c.current??'空白')}</td><td>${esc(typeof c.incoming==='object'?JSON.stringify(c.incoming):c.incoming??'空白')}</td><td><select class="inp" data-mw-resolution="${i}"><option value="">请选择</option><option value="current">保留系统值</option><option value="incoming">采用原报值</option></select></td></tr>`).join('');
}
function mwImportReview(result) {
  MW_FLOW.preview=result;MW_FLOW.kind='import';MW_FLOW.conflicts=[];
  const rows=result.batches.map(b=>{
      b.conflicts.forEach(c=>MW_FLOW.conflicts.push({...c,key:b.key+'|'+c.id,label:mwName(b.warehouse)+'／'+b.ym+'／'+c.field}));
      const totals=mwTotals(b.incoming),gross=b.category==='zero'?'mech_2':'mech_3',net=b.category==='zero'?'mech_4':'mech_5';
      return `<tr><td>${esc(mwName(b.warehouse))}</td><td>${esc(b.ym)}</td><td>${b.category==='zero'?'零租':'包月'}</td><td class="num">${b.rows.length}</td><td class="num">${mwMoney(b.effective?.values?.[gross])} → ${mwMoney(totals.amount)}</td><td class="num">${mwMoney(b.effective?.values?.[net])} → ${mwMoney(totals.net)}${totals.missing?'<br>部分净额待核':''}</td><td>${esc(typeof b.source==='string'?b.source:b.source?.file||'已附来源')}</td></tr>`;
    }).join('');
  const details=result.batches.map(b=>`<details><summary>${esc(mwName(b.warehouse))}／${esc(b.ym)}／${b.category==='zero'?'零租':'包月'} · 查看明细</summary><div class="tw mw-import-table"><table class="dt"><thead><tr><th>设备／规格</th><th>出租单位</th><th>车牌</th><th>日期／期间</th><th class="num">含税</th><th>票种／税率</th><th class="num">不含税</th><th>来源</th><th>待补</th></tr></thead><tbody>${b.incoming.map(r=>`<tr><td>${esc(r.device)} ${esc(r.spec||'')}</td><td>${esc(r.vendor||'')}</td><td>${esc(r.plate||'待补')}</td><td>${esc(r.date||'')}</td><td class="num">${mwMoney(r.amount)}</td><td>${esc(r.tax||'待核')}</td><td class="num">${mwMoney(mwNet(r))}</td><td>${esc(r.source?.sheet||'')} ${esc(r.source?.row||'')}</td><td>${esc(mwRowProblems(r,b.category,b.ym).join('、')||'—')}</td></tr>`).join('')}</tbody></table></div></details>`).join('');
  modal({title:'确认录入明细',wide:true,body:`<p class="mw-note">含税与净额展示系统月值 → 原报建议额（冲突选择影响最终保存内容）。确认只保存明细，月值在明细页另行确认更新。</p><div class="tw mw-import-table"><table class="dt"><thead><tr><th>项目</th><th>月份</th><th>类别</th><th>记录</th><th>含税</th><th>不含税</th><th>来源</th></tr></thead><tbody>${rows}</tbody></table></div>${details}${MW_FLOW.conflicts.length?`<h4>逐项确认修订冲突</h4><div class="tw mw-import-table"><table class="dt"><thead><tr><th>位置</th><th>系统当前值</th><th>原报新值</th><th>采用</th></tr></thead><tbody>${mwConflictRows()}</tbody></table></div>`:'<p>没有需要人工选择的修订冲突。</p>'}`,footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="mwImportConfirm">确认写入明细</button>`});
}
function mwI8Delta(before,after,complete){
  if(!complete||mwCents(after)===null)return {label:'待核实',cls:'mw-i8-unchanged'};
  const old=mwCents(before),next=mwCents(after);
  if(old===null)return {label:'首次取得',cls:'mw-i8-delta'};
  const delta=next-old;
  return {label:delta===0n?'未变化':(delta>0n?'+':'−')+mwMoney(mwDecimal(delta<0n?-delta:delta)),
    cls:delta===0n?'mw-i8-unchanged':delta<0n?'mw-i8-delta mw-i8-reduction':'mw-i8-delta'};
}
function mwI8Review(result,warehouse){
  MW_FLOW.preview=result;MW_FLOW.kind='i8';
  const counts=result.counts||{},projects=result.projects||[],keys=['usage','project','team'];
  const first=p=>!p.before||!Object.keys(p.before).length;
  const changed=p=>p.complete&&!first(p)&&keys.some(k=>mwCents(p.before?.totals?.[k])!==mwCents(p.totals?.[k]));
  const total=(predicate)=>projects.filter(predicate).length;
  modal({title:warehouse?'更新本项目i8累计':'抓取 i8 · 累计变化核对',wide:true,body:`<div class="mw-i8-review">
    <p class="mw-note">已读取班组使用 ${esc(counts.usage??'—')} 条、项目结算 ${esc(counts.project??'—')} 条、班组消耗 ${esc(counts.team??'—')} 条。确认只更新勾选项目。</p>
    <div class="mw-i8-summary"><b>${projects.length} 个项目</b><span>${total(changed)} 项金额变化</span><span>${total(p=>p.complete&&first(p))} 项首次取得</span><span>${total(p=>p.complete&&!first(p)&&!changed(p))} 项金额未变化</span><span class="wn">${total(p=>!p.complete)} 项来源未齐</span><span style="margin-left:auto">金额单位：元</span></div>
    <div class="tw"><table class="dt"><colgroup><col style="width:48px"><col style="width:160px">${'<col>'.repeat(9)}<col style="width:142px"></colgroup><thead><tr><th rowspan="2">采用</th><th rowspan="2">项目</th>${['班组使用累计','项目结算累计','班组审批累计'].map(label=>`<th colspan="3" class="mw-i8-group">${label}</th>`).join('')}<th rowspan="2" class="mw-i8-group">状态</th></tr><tr>${keys.map(()=>'<th class="mw-i8-group">原值</th><th>本次取得</th><th>变化额</th>').join('')}</tr></thead><tbody>${projects.map((p,i)=>`<tr><td><input type="checkbox" aria-label="采用${esc(mwName(p.warehouse))}" data-mw-i8="${i}" ${p.complete&&(!warehouse||p.warehouse===warehouse)?'checked':''} ${!p.complete?'disabled':''}></td><td><b>${esc(mwName(p.warehouse))}</b></td>${keys.map(k=>{
      const old=p.before?.totals?.[k],value=p.totals?.[k],change=mwI8Delta(old,value,p.complete);
      return `<td class="num mw-i8-group mut">${mwMoney(old)}</td><td class="num">${mwMoney(value)}</td><td class="num ${change.cls}">${change.label}</td>`;
    }).join('')}<td class="mw-i8-group">${!p.complete?'<span class="tag t-wn">来源未齐</span><div class="mut sm">保留全部旧值</div>':p.reduction?'<span class="tag t-wn">含减少，需核实</span>':first(p)?'<span class="tag t-in">首次发现</span>':changed(p)?'<span class="tag t-in">金额变化</span>':p.changed?'<span class="tag t-in" title="来源单据或内容有变化，累计金额未变化">单据有变化</span>':'<span class="mut">金额未变化</span>'}</td></tr>`).join('')||'<tr><td colspan="12" class="empty">本次没有可采用的项目。</td></tr>'}</tbody></table></div>
    ${result.unmapped_projects?.length?`<p class="tip wn">发现 ${result.unmapped_projects.length} 个未对应档案的项目；明确映射后再采用。</p>`:''}
    <div class="mw-i8-legend"><span><b class="mw-i8-increase">＋ 增加</b> · 主题底色标出变化额</span><span><b class="wn">− 减少</b> · 核实后采用</span><span>首次取得不当作历史增加额；来源未齐不替换旧值</span></div>
    <div class="mw-i8-reason"><label><input type="checkbox" id="mw-i8-reduction"> 已核实查询范围及单据减少</label><textarea class="inp" id="mw-i8-reason" aria-label="减少采用依据" placeholder="存在减少时，填写核实依据"></textarea></div>
    </div>`,footer:`<button class="btn" data-act="closeModal">暂不采用</button><button class="btn pri" data-act="mwI8Confirm" ${projects.some(p=>p.complete)?'':'disabled'}>确认所选项目</button>`});  const head=document.querySelector('.mw-i8-review thead tr');
  if(head)head.closest('table').style.setProperty('--mw-i8-head',head.getBoundingClientRect().height+'px');
}
async function mechanicalWorkbenchI8Dialog(warehouse) {
  await mwRun(async()=>{
    const result=await mwPost('i8-fetch',{request_id:crypto.randomUUID()});
    mwI8Review(result,warehouse);
    await reloadMechanicalWorkbench();
  });
}
Object.assign(ACT, {
  mwImportPreview:()=>mwRun(async()=>{
    const file=document.getElementById('mw-import-file').files[0];
    if(!file){mwNotify('请选择Agent整理的录入文件。');return;}
    if(file.size>25*1024*1024){mwNotify('文件超过25MB，请按月份拆分。');return;}
    let data;try{data=JSON.parse(await file.text());}catch(error){mwNotify('文件内容无法识别，请核对录入文件。');return;}
    data=data.detail_import||data;
    if(!Array.isArray(data.batches)||!data.batches.length){mwNotify('请选择零租／包月明细录入文件。');return;}
    mwImportReview(await mwPost('import-preview',{...data,request_id:crypto.randomUUID()}));
  }),
  mwImportConfirm:()=>mwRun(async()=>{
    const resolutions={};let missing=false;
    document.querySelectorAll('[data-mw-resolution]').forEach(select=>{if(!select.value)missing=true;else resolutions[MW_FLOW.conflicts[Number(select.dataset.mwResolution)].key]=select.value;});
    if(missing){mwNotify('请逐项选择修订冲突。');return;}
    await mwPost(MW_FLOW.kind+'-confirm',{preview_id:MW_FLOW.preview.preview_id,resolutions,confirm_amounts:false});
    await mwRefresh();closeModal();mwNotify('已写入本次确认内容。');
  }),
  mwI8Confirm:()=>mwRun(async()=>{
    const warehouses=[...document.querySelectorAll('[data-mw-i8]:checked')].map(input=>MW_FLOW.preview.projects[Number(input.dataset.mwI8)].warehouse);
    if(!warehouses.length){mwNotify('请至少选择一个来源完整的项目。');return;}
    await mwPost('i8-confirm',{preview_id:MW_FLOW.preview.preview_id,warehouses,allow_reduction:document.getElementById('mw-i8-reduction').checked,reduction_reason:document.getElementById('mw-i8-reason').value});
    await mwRefresh();closeModal();mwNotify('已更新所选项目的i8累计。');
  }),
});
