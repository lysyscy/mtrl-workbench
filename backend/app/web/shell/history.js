/* 全站业务撤销；输入框内的文字撤销仍交给浏览器。 */
const HISTORY={undo:null,redo:null,busy:false,writes:0,loading:false,request:0,notice:'',owner:''};
function historyRender(){
  const root=$('#historyControls'); if(!root) return;
  ['undo','redo'].forEach(direction=>{
    const label=direction==='undo'?'撤销':'重做', item=HISTORY[direction];
    const key=direction==='undo'?'Ctrl+Z':'Ctrl+Y';
    const reason=!CUR.role?'请先登录':HISTORY.busy?'正在撤销或重做，请稍候':HISTORY.writes?'请等当前操作保存完成':HISTORY.loading?'正在读取操作历史':!item?`暂无可${label}的操作（${key}）`:'';
    const title=reason||`${label}：${item.label}（${item.count}条，${key}）`;
    const disabled=!CUR.role||!item||HISTORY.busy||HISTORY.writes||HISTORY.loading;
    const button=root.querySelector(`[data-act="history${direction==='undo'?'Undo':'Redo'}"]`);
    button.disabled=!!disabled;button.title=title;
  });
  root.querySelector('[role=status]').textContent=HISTORY.notice;
}
async function historyRefresh(){
  const request=++HISTORY.request;
  const owner=String(CUR.id||CUR.acc||'');
  if(owner!==HISTORY.owner){HISTORY.owner=owner;HISTORY.undo=HISTORY.redo=null;HISTORY.notice='';}
  if(!CUR.role){ HISTORY.undo=HISTORY.redo=null;HISTORY.notice='';HISTORY.loading=false;historyRender();return; }
  HISTORY.loading=true;historyRender();
  try{
    const state=await API.get('/api/history/status');
    if(request!==HISTORY.request) return;
    HISTORY.undo=state.undo||null;HISTORY.redo=state.redo||null;
    HISTORY.notice=state.notice||'';
  }catch(e){
    if(request!==HISTORY.request) return;
    HISTORY.undo=HISTORY.redo=null;HISTORY.notice='操作历史未能读取，请刷新重试';
  }finally{ if(request===HISTORY.request){HISTORY.loading=false;historyRender();} }
}
function historyWriteStarted(){ HISTORY.writes++;historyRender(); }
async function historyWriteFinished(response){
  try{
    if(response){
      const result=response.headers.get('X-Operation-History');
      if(response.ok||result) await historyRefresh();
    }
  }finally{HISTORY.writes=Math.max(0,HISTORY.writes-1);historyRender();}
}
async function historyApply(direction){
  if(HISTORY.busy||HISTORY.writes||HISTORY.loading) return toast('请等当前操作保存完成后再试');
  const item=HISTORY[direction];if(!CUR.role||!item) return;
  if($('#modalRoot').childElementCount) return toast('请先保存或关闭当前弹窗，再撤销或重做');
  HISTORY.busy=true;historyRender();
  try{
    const result=await API.send('POST',`/api/history/${direction}`,{operation_id:item.id});
    pickSet.clear();
    markPending(PAGE_LOAD[VIEW]||[]);render();
    await loadPaths(PAGE_LOAD[VIEW]||[]);
    toast(esc(result.message));
  }catch(e){toast(esc(String(e.message||e)));}
  finally{await historyRefresh();HISTORY.busy=false;historyRender();}
}
function historyKey(e){
  if(!(e.ctrlKey||e.metaKey)||e.altKey||e.isComposing) return false;
  if(e.target instanceof Element&&e.target.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"])')) return false;
  const key=e.key.toLowerCase();
  const direction=key==='z'?(e.shiftKey?'redo':'undo'):key==='y'?'redo':'';
  if(!direction) return false;
  e.preventDefault();historyApply(direction);return true;
}
window.addEventListener('focus',()=>{if(!HISTORY.busy&&!HISTORY.writes)historyRefresh();});
