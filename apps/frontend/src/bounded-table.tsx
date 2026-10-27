import { useLayoutEffect, useRef, useState } from 'react';
import type { ComponentProps } from 'react';
import Button from 'antd/es/button';
import { loadElementFonts } from './appearance-ready';

// Browser auto layout owns content minima and spare space. Only an active
// editing session snapshots actual widths, so typing cannot move its controls.
export function BoundedTable({children,style,prepareFonts=false,layoutVersion,...props}:ComponentProps<'table'>&{prepareFonts?:boolean;layoutVersion?:unknown}) {
  const ref=useRef<HTMLTableElement>(null),[frozen,setFrozen]=useState<number[]>([]);
  const [ready,setReady]=useState(!prepareFonts),[error,setError]=useState(''),[retry,setRetry]=useState(0);
  useLayoutEffect(()=>{
    const table=ref.current;if(!table)return;
    let frame=0;
    const editing=()=>table.contains(document.activeElement)&&document.activeElement?.matches('input:not([type=checkbox]):not([type=radio]),select,textarea,[contenteditable=true]');
    const freeze=()=>{
      if(!editing())return;
      setFrozen(previous=>{
        if(previous.length)return previous;
        const rows=[...table.rows].filter(row=>[...row.cells].every(cell=>cell.colSpan===1));
        const row=rows.sort((a,b)=>b.cells.length-a.cells.length)[0];
        return row?[...row.cells].map(cell=>cell.getBoundingClientRect().width):[];
      });
    };
    const release=()=>{cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{if(!editing())setFrozen([]);});};
    table.addEventListener('focusin',freeze);table.addEventListener('focusout',release);
    return()=>{cancelAnimationFrame(frame);table.removeEventListener('focusin',freeze);table.removeEventListener('focusout',release);};
  },[]);
  useLayoutEffect(()=>{
    const table=ref.current;if(!table)return;let disposed=false;
    void (async()=>{
      try {if(prepareFonts)await loadElementFonts(table);if(!disposed){setReady(true);setError('');}}
      catch(e){if(!disposed)setError(e instanceof Error?e.message:'字体准备失败，请重试。');}
    })();
    return()=>{disposed=true;};
  },[prepareFonts,layoutVersion,retry]);
  return <>{error&&<p role="alert">{error}<Button onClick={()=>setRetry(n=>n+1)}>重试表格加载</Button></p>}<table {...props} ref={ref} data-page-loading={prepareFonts&&!ready&&!error?true:undefined} data-layout-state={prepareFonts?error?'error':ready?'ready':'preparing':undefined} inert={prepareFonts&&!ready} className={`bounded-table ${props.className??''}`} style={{...style,visibility:prepareFonts&&!ready?'hidden':style?.visibility,tableLayout:frozen.length?'fixed':'auto',minWidth:0,maxWidth:'none',width:frozen.length?frozen.reduce((a,b)=>a+b,0):'100%'}}>{frozen.length>0&&<colgroup>{frozen.map((width,i)=><col key={i} style={{width}}/>)}</colgroup>}{children}</table></>;
}
