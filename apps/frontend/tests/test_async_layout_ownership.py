"""Controlled DOM reproduction of the actual useTextGridLayout source hook.

This is an isolated browser specimen, not a business-page performance result.
It uses the one registered preview origin, no extra HTTP server, and a minimal
GridApi adapter. React portals, measuring hosts, font waits and row geometry
come from the production hook. No business response is mocked or submitted.
"""
import json
import subprocess
from pathlib import Path

import pytest

from test_preview import browser_page, server  # noqa: F401


FRONTEND = Path(__file__).resolve().parents[1]
HARNESS = r"""
import React, {useLayoutEffect, useMemo, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {useTextGridLayout} from '__HOOK__';
const nativeLoad = document.fonts.load.bind(document.fonts);
const gates = {};
const waitA = new Promise(resolve => gates.releaseA = resolve);
const waitB = new Promise(resolve => gates.releaseB = resolve);
window.layoutProbe = {gates, aHeld:false, bHeld:false, aCompleted:false, calls:[]};
document.fonts.load = async (font, text) => {
  window.layoutProbe.calls.push({font,text,portal:Boolean(document.querySelector('[data-probe-row]'))});
  const loaded = await nativeLoad(font, text);
  if (!window.layoutProbe.aHeld && text?.endsWith('0123456789,.-')) {
    window.layoutProbe.aHeld = true;
    await waitA;
    window.layoutProbe.aCompleted = true;
  } else if (!window.layoutProbe.bHeld && document.querySelector('[data-probe-row]') && /^([AB])tex$/.test(text ?? '')) {
    window.layoutProbe.bHeld = true;
    await waitB;
  }
  return loaded;
};
function Probe() {
  const root = useRef(null), [rows,setRows] = useState([{id:'A',text:'Atext'}]);
  const totals = useMemo(()=>[],[]);
  const rowId = useMemo(()=>row=>row.id,[]);
  const columns = useMemo(()=>[{id:'probe',text:row=>row.text,wrap:true,
    render:row=>React.createElement('div', {'data-probe-row':row.id,style:{height:84}}, row.text)}],[]);
  const api = useMemo(()=>{
    const listeners = new Map(), options = {domLayout:'normal',headerHeight:28};
    const column = {getColId:()=> 'probe',getActualWidth:()=> 220,getColDef:()=>({headerName:'Probe'})};
    return {listeners, options, node:{rowHeight:28,setRowHeight(value){this.rowHeight=value;}},
      isDestroyed:()=>false,getEditingCells:()=>[],getGridOption:key=>options[key],
      setGridOption:(key,value)=>{options[key]=value;},getAllDisplayedColumns:()=>[column],
      forEachNode(fn){this.node.data=window.layoutProbe.rows[0];fn(this.node);},
      getPinnedBottomRowCount:()=>0,onRowHeightChanged:()=>{},
      addEventListener:(key,fn)=>listeners.set(key,fn),removeEventListener:(key,fn)=>{if(listeners.get(key)===fn)listeners.delete(key);}};
  },[]);
  const prepared=useTextGridLayout({root,active:true,rows,totals,columns,rowId,minimum:28,headerMinimum:28,scope:'probe',identity:'probe'});
  useLayoutEffect(()=>{prepared.attach(api);},[api]);
  window.layoutProbe.rows=rows;
  window.layoutProbe.replaceRows=()=>setRows([{id:'B',text:'Btext'}]);
  window.layoutProbe.reschedule=()=>api.listeners.get('columnResized')?.({finished:true});
  window.layoutProbe.snapshot=()=>({state:prepared.state,error:prepared.error,height:api.node.rowHeight,
    portals:document.querySelectorAll('[data-probe-row]').length,hosts:document.querySelectorAll('.grid-layout-measure').length});
  return React.createElement('div',{ref:root,style:{width:440,height:300}},
    React.createElement('div',{className:'ag-root'},React.createElement('div',{className:'ag-body-viewport'})),prepared.measurement);
}
createRoot(document.getElementById('probe')).render(React.createElement(Probe));
"""


def bundle_browser_specimen(source):
    # Vite bundles the current source into memory only. This is not a product
    # build and does not create or replace registered build/version metadata.
    command = r"""
import {build} from 'vite';
import {createRequire} from 'node:module';
import path from 'node:path';
let input=''; for await (const chunk of process.stdin) input+=chunk;
const source=JSON.parse(input), require=createRequire(path.join(process.cwd(),'package.json'));
const result=await build({configFile:false,logLevel:'silent',
  define:{'process.env.NODE_ENV':JSON.stringify('production')},
  resolve:{alias:{react:path.dirname(require.resolve('react/package.json')),'react-dom':path.dirname(require.resolve('react-dom/package.json'))}},
  plugins:[{name:'browser-specimen',resolveId(id){if(id.includes('browser-specimen.tsx'))return '/virtual/browser-specimen.tsx';},load(id){if(id==='/virtual/browser-specimen.tsx')return source;}}],
  build:{write:false,minify:false,lib:{entry:'virtual:browser-specimen.tsx',name:'BrowserSpecimen',formats:['iife']}}});
process.stdout.write(JSON.stringify((Array.isArray(result)?result[0]:result).output.find(item=>item.type==='chunk').code));
"""
    result = subprocess.run(['node', '--input-type=module', '-e', command],
                            input=json.dumps(source).encode('utf-8'), cwd=FRONTEND,
                            capture_output=True, check=False)
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')
    return json.loads(result.stdout.decode('utf-8'))


@pytest.fixture(scope='module')
def actual_hook_bundle():
    return bundle_browser_specimen(HARNESS.replace('__HOOK__', (FRONTEND / 'src/grid-layout.ts').as_posix()))


@pytest.mark.parametrize('interleaving', ['same-effect', 'cross-effect'])
def test_old_measurement_finally_keeps_new_portal(server, browser_page, actual_hook_bundle, interleaving):
    page, _ = browser_page
    document_url = str(server) + '/preview/__async_layout_specimen__'
    script_url = document_url + '.js'
    page.route(script_url, lambda route: route.fulfill(content_type='application/javascript', body=actual_hook_bundle))
    page.route(document_url, lambda route: route.fulfill(content_type='text/html', body=
        '<!doctype html><style>body{font:14px Arial}.ag-cell{box-sizing:border-box;padding:0;border:0}</style>'
        '<div id="probe"></div><script src="' + script_url + '"></script>'))
    page.goto(document_url, wait_until='domcontentloaded')
    page.wait_for_function('window.layoutProbe?.aHeld')
    page.evaluate('window.layoutProbe.' + ('replaceRows()' if interleaving == 'cross-effect' else 'reschedule()'))
    page.wait_for_function('window.layoutProbe.bHeld && document.querySelectorAll("[data-probe-row]").length === 1')
    before = page.evaluate('window.layoutProbe.snapshot()')
    page.evaluate('window.layoutProbe.gates.releaseA()')
    page.wait_for_function('window.layoutProbe.aCompleted')
    page.evaluate('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
    after_old = page.evaluate('window.layoutProbe.snapshot()')
    page.evaluate('window.layoutProbe.gates.releaseB()')
    page.wait_for_function('window.layoutProbe.snapshot().state === "ready"')
    complete = page.evaluate('window.layoutProbe.snapshot()')
    evidence = {'interleaving':interleaving,'before_old_finally':before,'after_old_finally':after_old,'completed':complete,
                'font_calls':page.evaluate('window.layoutProbe.calls')}
    assert after_old['portals'] == 1, evidence
    assert after_old['hosts'] == 1, evidence
    assert complete['height'] == 84, evidence
    assert complete['hosts'] == complete['portals'] == 0, evidence
