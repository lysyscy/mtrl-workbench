import assert from 'node:assert/strict';
import test from 'node:test';
import { bindGridWidths, gridWidthKey } from '../../src/grid-width-state.ts';
import { manualGridColumns } from '../../src/grid-manual-widths.ts';

function fixture(storage, owner = 'reader', scoped = true, scale = 1) {
  const original = [
    {field:'name',minWidth:120*scale,maxWidth:240*scale,initialWidth:180*scale,flex:1},
    {field:'amount',minWidth:140*scale,maxWidth:180*scale,initialWidth:140*scale},
    {field:'pick',minWidth:28*scale,maxWidth:28*scale,width:28*scale,resizable:false},
  ];
  let definitions = scoped ? manualGridColumns(original,scale,{name:64}) : original;
  const listeners = new Map(), states = new Map(definitions.map(c=>[c.field,{colId:c.field,width:c.initialWidth??c.width,flex:c.flex??null}]));
  const emit = (type, event) => { for (const listener of listeners.get(type)??[]) listener(event); };
  const column = id => ({getColDef:()=>definitions.find(c=>c.field===id),getColId:()=>id,getActualWidth:()=>states.get(id).width,getFlex:()=>states.get(id).flex});
  const api = {
    isDestroyed:()=>false,
    getGridOption:()=>definitions,
    setGridOption:(_key,next)=>{definitions=next;emit('newColumnsLoaded',{});},
    getColumnState:()=>[...states.values()].map(s=>({...s})),
    applyColumnState:({state})=>{for(const update of state){const current=states.get(update.colId),def=column(update.colId).getColDef();Object.assign(current,update);current.width=Math.max(def.minWidth??20,Math.min(def.maxWidth??Infinity,current.width));}},
    getColumn:id=>states.has(id)?column(id):undefined,
    getAllDisplayedColumns:()=>[...states.keys()].map(column),
    resetColumnState:()=>{for(const def of definitions)states.set(def.field,{colId:def.field,width:def.initialWidth??def.width,flex:def.flex??null});},
    autoSizeColumns:()=>{},
    addEventListener:(type,listener)=>{if(!listeners.has(type))listeners.set(type,new Set());listeners.get(type).add(listener);},
    removeEventListener:(type,listener)=>listeners.get(type)?.delete(listener),
  };
  const binding=bindGridWidths(api,{owner,table:'ledger',storage:()=>storage,scale:()=>scale,changed:()=>{}});
  return {api,binding,definition:id=>column(id).getColDef(),width:id=>states.get(id).width,
    drag:(id,width)=>{
      emit('dragStarted',{target:{closest:()=>({closest:()=>({getAttribute:()=>id})})}});
      api.applyColumnState({state:[{colId:id,width,flex:null}]});
      emit('columnResized',{source:'uiColumnResized',finished:true,column:column(id)});
      emit('dragStopped',{});
    }};
}
function memoryStorage() {const data=new Map();return {getItem:key=>data.get(key)??null,setItem:(key,value)=>data.set(key,value),removeItem:key=>data.delete(key)};}

test('scoped manual widths cross automatic bounds, persist, scale and reset to automatic bounds',async()=>{
  const storage=memoryStorage(),first=fixture(storage);
  assert.equal(first.definition('name').maxWidth,240);
  first.drag('name',620);
  assert.equal(first.width('name'),620);
  assert.equal(first.definition('name').maxWidth,undefined);
  first.drag('name',72);
  assert.equal(first.width('name'),72);
  await Promise.resolve();first.binding.dispose();
  const reloaded=fixture(storage,'reader',true,1.25);
  assert.equal(reloaded.width('name'),90);
  assert.equal(reloaded.definition('name').minWidth,80);
  reloaded.binding.reset();await Promise.resolve();
  assert.equal(reloaded.definition('name').minWidth,150);
  assert.equal(reloaded.definition('name').maxWidth,300);
  assert.equal(reloaded.width('name'),225);
  assert.equal(reloaded.api.getColumnState().find(c=>c.colId==='name').flex,1);
  assert.equal(storage.getItem(gridWidthKey('reader','ledger')),null);
  reloaded.binding.dispose();
});

test('protected floors and fixed columns remain protected; other owners and unscoped grids keep defaults',async()=>{
  const storage=memoryStorage(),scoped=fixture(storage);
  scoped.drag('amount',50);
  assert.equal(scoped.width('amount'),140);
  scoped.drag('amount',460);
  assert.equal(scoped.width('amount'),460);
  scoped.drag('pick',100);
  assert.equal(scoped.width('pick'),28);
  const other=fixture(storage,'other');
  assert.equal(other.width('name'),180);
  const normal=fixture(memoryStorage(),'normal',false);
  normal.drag('name',620);
  assert.equal(normal.width('name'),240);
  normal.drag('name',50);
  assert.equal(normal.width('name'),120);
  await Promise.resolve();
  scoped.binding.dispose();other.binding.dispose();normal.binding.dispose();
});
