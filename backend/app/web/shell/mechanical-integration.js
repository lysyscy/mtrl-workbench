/* 录入与i8先预览后采用；业务写入与外部Agent使用同一系统入口。 */
const MW_FLOW = {preview:null,kind:'',conflicts:[],file:null};
function mechanicalWorkbenchImportDialog() {
  MW_FLOW.file=null;
  modal({title:'录入原报',body:`<label class="mw-field">Agent整理的录入文件<input id="mw-import-file" type="file" accept=".json,application/json"></label><label class="mw-field">本次录入<select id="mw-import-kind" class="inp"><option value="import">零租／包月明细</option><option value="history">历史月值与累计接续</option></select></label><p class="mut">先查看项目、月份、来源和修订冲突；确认后才写入。明细录入不会自动确认月值。</p>`,footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="mwImportPreview">查看录入预览</button>`});
}
function mwConflictRows() {
  return MW_FLOW.conflicts.map((c,i)=>`<tr><td>${esc(c.label)}</td><td>${esc(typeof c.current==='object'?JSON.stringify(c.current):c.current??'空白')}</td><td>${esc(typeof c.incoming==='object'?JSON.stringify(c.incoming):c.incoming??'空白')}</td><td><select class="inp" data-mw-resolution="${i}"><option value="">请选择</option><option value="current">保留系统值</option><option value="incoming">采用原报值</option></select></td></tr>`).join('');
}
function mwImportReview(result, kind) {
  MW_FLOW.preview=result;MW_FLOW.kind=kind;MW_FLOW.conflicts=[];
  let rows='';
  if(kind==='import') {
    rows=result.batches.map(b=>{
      b.conflicts.forEach(c=>MW_FLOW.conflicts.push({...c,key:b.key+'|'+c.id,label:mwName(b.warehouse)+'／'+b.ym+'／'+c.field}));
      return `<tr><td>${esc(mwName(b.warehouse))}</td><td>${esc(b.ym)}</td><td>${b.category==='zero'?'零租':'包月'}</td><td class="num">${b.rows.length}</td><td>${esc(typeof b.source==='string'?b.source:b.source?.file||'已附来源')}</td></tr>`;
    }).join('');
  } else {
    rows=result.projects.flatMap(p=>{
      if(p.before_history && Object.keys(p.before_history).length)MW_FLOW.conflicts.push({key:p.warehouse+'|history',label:mwName(p.warehouse)+'／历史参考',current:'已有历史参考',incoming:'新文件历史参考'});
      return p.months.map(m=>{
        m.conflicts.forEach(c=>MW_FLOW.conflicts.push({...c,key:c.id,label:mwName(p.warehouse)+'／'+m.ym+'／'+c.column}));
        return `<tr><td>${esc(mwName(p.warehouse))}</td><td>${esc(m.ym)}</td><td>历史月值</td><td>${Object.keys(m.values).length}项</td><td>${esc(m.source?.file||'已附来源')}</td></tr>`;
      });
    }).join('');
  }
  modal({title:kind==='import'?'确认录入明细':'确认历史接续',body:`<div class="tw"><table class="dt"><thead><tr><th>项目</th><th>月份</th><th>类别</th><th>记录</th><th>来源</th></tr></thead><tbody>${rows}</tbody></table></div>${MW_FLOW.conflicts.length?`<h4>逐项确认修订冲突</h4><div class="tw"><table class="dt"><thead><tr><th>位置</th><th>系统当前值</th><th>原报新值</th><th>采用</th></tr></thead><tbody>${mwConflictRows()}</tbody></table></div>`:'<p>没有需要人工选择的修订冲突。</p>'}`,footer:`<button class="btn" data-act="closeModal">取消</button><button class="btn pri" data-act="mwImportConfirm">确认写入${kind==='import'?'明细':'历史接续'}</button>`});
}
async function mechanicalWorkbenchI8Dialog(warehouse) {
  await mwRun(async()=>{
    const result=await mwPost('i8-fetch',{request_id:crypto.randomUUID()});
    MW_FLOW.preview=result;MW_FLOW.kind='i8';
    const counts=result.counts||{};
    modal({title:warehouse?'更新本项目i8累计':'i8全量发现',body:`<p class="mw-note">已读取班组使用${counts.usage??'—'}条、项目结算${counts.project??'—'}条、班组消耗${counts.team??'—'}条。以下为原 → 新；确认只更新勾选项目。</p><div class="tw"><table class="dt"><thead><tr><th>采用</th><th>项目</th><th>班组使用</th><th>项目结算</th><th>班组审批</th><th>状态</th></tr></thead><tbody>${result.projects.map((p,i)=>`<tr><td><input type="checkbox" data-mw-i8="${i}" ${p.complete&&(!warehouse||p.warehouse===warehouse)?'checked':''} ${!p.complete?'disabled':''}></td><td>${esc(mwName(p.warehouse))}</td>${['usage','project','team'].map(k=>`<td class="num">${mwMoney(p.before?.totals?.[k])} → ${mwMoney(p.totals?.[k])}</td>`).join('')}<td>${!p.complete?'来源未齐，保留旧值':p.reduction?'有减少，须核实':p.before&&Object.keys(p.before).length?'已完整取得':'首次发现'}</td></tr>`).join('')}</tbody></table></div>${result.unmapped_projects?.length?`<p class="wn">发现${result.unmapped_projects.length}个未对应档案的项目，已保留在发现记录；明确映射后再采用。</p>`:''}<label class="mw-field"><span><input type="checkbox" id="mw-i8-reduction"> 已核实查询范围及单据减少，采用减少后的结果</span><textarea class="inp" id="mw-i8-reason" aria-label="减少采用依据" placeholder="仅有减少时填写核实依据"></textarea></label>`,footer:`<button class="btn" data-act="closeModal">暂不采用</button><button class="btn pri" data-act="mwI8Confirm">确认所选项目</button>`});
    await reloadMechanicalWorkbench();
  });
}
Object.assign(ACT, {
  mwImportPreview:()=>mwRun(async()=>{
    const file=document.getElementById('mw-import-file').files[0];
    if(!file){mwNotify('请选择Agent整理的录入文件。');return;}
    if(file.size>25*1024*1024){mwNotify('文件超过25MB，请按月份拆分。');return;}
    let data;try{data=JSON.parse(await file.text());}catch(error){mwNotify('文件内容无法识别，请核对录入文件。');return;}
    const kind=document.getElementById('mw-import-kind').value;
    data=(kind==='history'?data.history_import:data.detail_import)||data;
    mwImportReview(await mwPost(kind+'-preview',{...data,request_id:crypto.randomUUID()}),kind);
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
