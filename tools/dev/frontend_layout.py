"""Collect actual layout on the single registered disposable preview, using its navigation."""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.audit.workspace_paths import close_runs, output_dir
from tools.dev.frontend_capture import capture_preview
from tools.dev.frontend_preview_runtime import active_preview, assert_same_preview, registered_preview, write_json


SNAPSHOT = r"""requireGrid => {
  const active = e => {
    for (let p=e; p; p=p.parentElement) {
      if (p.hidden || getComputedStyle(p).display==='none' || p.tagName==='DETAILS'&&!p.open) return false;
    }
    return true;
  };
  const visible = e => active(e) && getComputedStyle(e).visibility!=='hidden'
    && e.getBoundingClientRect().width>0 && e.getBoundingClientRect().height>0;
  const page=document.querySelector('.page-view:not([hidden])');
  const result={title:document.querySelector('#page-title')?.textContent?.trim()??'',
    viewport:[innerWidth,innerHeight],scale:Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale')),
    state:'pending',reason:'page-not-ready',grids:[]};
  if (!page || page.inert || !visible(page)) return result;
  if (document.fonts.status!=='loaded') return {...result,reason:'fonts-not-ready'};
  const scopes=[...page.querySelectorAll('[data-layout-state]')].filter(active);
  const errors=scopes.filter(e=>e.getAttribute('data-layout-state')==='error'||e.getAttribute('data-layout-error'));
  const alerts=[...page.querySelectorAll('[role=alert]')].filter(visible);
  if (errors.length||alerts.length) return {...result,state:'failed',reason:'page-or-layout-error',errors:errors.length,alerts:alerts.length};
  if (scopes.some(e=>e.getAttribute('data-layout-state')!=='ready')) return {...result,reason:'grid-not-ready'};
  const pending=[...page.querySelectorAll('[role=status],[data-page-loading]')].filter(visible)
    .some(e=>/正在(?:读取|加载|核对)|Loading\.\.\./.test(e.textContent??''));
  if (pending) return {...result,reason:'data-not-ready'};
  const roots=[...page.querySelectorAll('.ag-root-wrapper')].filter(visible);
  if (requireGrid&&!roots.length) {
    const empty=[...page.querySelectorAll('.state')].filter(visible).some(e=>/^\s*(暂无|没有|请选择|尚无)/.test(e.textContent??''));
    return {...result,state:empty?'empty':'pending',reason:empty?'empty-no-grid':'missing-grid'};
  }
  result.pageOverflow=Math.max(page.scrollWidth-page.clientWidth,document.documentElement.scrollWidth-innerWidth);
  result.grids=roots.map(root=>{
    const scroll=[...root.querySelectorAll('.ag-body-horizontal-scroll-viewport')]
      .map(e=>({available:e.clientWidth,total:e.scrollWidth}));
    const bars=[...root.querySelectorAll('.ag-body-horizontal-scroll')]
      .map(e=>({height:e.getBoundingClientRect().height,visible:visible(e)}));
    const rows=[...root.querySelectorAll('.ag-row:not(.ag-row-pinned)')].filter(visible).length;
    const empty=rows===0||[...root.querySelectorAll('.ag-overlay-no-rows-center')].some(visible);
    const clipped=[...root.querySelectorAll('.ag-cell')].filter(visible).map(cell=>{
      const parts=[cell,...cell.querySelectorAll('.ag-cell-value,.ag-cell-wrapper')].filter(visible);
      const extraWidth=Math.max(...parts.map(e=>e.scrollWidth-e.clientWidth));
      const extraHeight=Math.max(...parts.map(e=>e.scrollHeight-e.clientHeight));
      return {column:cell.getAttribute('col-id'),row:cell.closest('[row-id]')?.getAttribute('row-id'),extraWidth,extraHeight};
    }).filter(e=>e.extraWidth>1||e.extraHeight>1);
    return {label:root.closest('[aria-label]')?.getAttribute('aria-label')??'',
      columns:[...root.querySelectorAll('.ag-header-cell')].map(e=>({id:e.getAttribute('col-id'),label:e.textContent?.trim(),width:e.getBoundingClientRect().width})),
      rows,empty,scroll,bars,clipped};
  });
  const overflow=result.pageOverflow>1||result.grids.some(g=>g.clipped.length||g.scroll.some(v=>v.total>v.available+1)||g.bars.some(b=>b.visible));
  const empty=result.grids.some(g=>g.empty);
  return {...result,state:overflow?'failed':empty?'empty':'ready',reason:overflow?'overflow':empty?'empty-grid':''};
}"""


def measure_page(page, *, require_grid=True, timeout=20):
    """A missing table never becomes a successful empty measurement."""
    from playwright.sync_api import TimeoutError as BrowserTimeout
    try:
        page.wait_for_function(f"arg=>({SNAPSHOT})(arg).state!=='pending'", arg=require_grid, timeout=timeout * 1000)
        page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
        return page.evaluate(SNAPSHOT, require_grid)
    except BrowserTimeout:
        return {**page.evaluate(SNAPSHOT, require_grid), 'state': 'failed', 'reason': 'layout-timeout'}


def navigation(page, base):
    links = page.locator('.sidebar nav a').evaluate_all("nodes=>nodes.map(e=>({url:e.href,title:e.textContent.trim()}))")
    origin = urlsplit(base)
    result, seen = [], set()
    for item in links:
        target = urlsplit(item['url'])
        if target.scheme != origin.scheme or target.netloc != origin.netloc or target.query or target.fragment:
            raise ValueError('导航包含非本预览入口')
        path = target.path.rstrip('/')
        if path != '/preview' and not path.startswith('/preview/'):
            raise ValueError('导航不属于预览')
        route = path.removeprefix('/preview')
        if route in seen or not item['title']:
            raise ValueError('导航存在重复或空标题')
        seen.add(route); result.append({**item, 'route': route})
    if not result:
        raise ValueError('没有取得实际导航，页面未核')
    return result


def collect(page, owner, base, routes, *, scale, timeout=20):
    page_errors = []
    page.on('pageerror', lambda error: page_errors.append(type(error).__name__))
    results = []
    for target in routes:
        assert_same_preview(owner, active_preview()[1], disposable=True)
        page_errors.clear()
        try:
            page.get_by_role('link', name=target['title'], exact=True).click()
            page.locator('#page-title').filter(has_text=target['title']).wait_for(timeout=timeout * 1000)
            result = measure_page(page, require_grid=bool(target['route']), timeout=timeout)
            if abs(result['scale'] - scale) > .001:
                result.update(state='failed', reason='appearance-scale-mismatch')
            if result['title'] != target['title'] or page_errors:
                result.update(state='failed', reason='page-title-or-runtime-error')
        except Exception as exc:
            result = {'state': 'failed', 'reason': type(exc).__name__}
        result.update(route=target['route'], title=target['title'])
        if result['state'] != 'ready':
            try:
                image = capture_preview(page, owner, 'layout-' + (target['route'].strip('/') or 'home'))
                result['screenshot'] = str(image)
            except Exception as exc:
                result['screenshot_error'] = type(exc).__name__
        results.append(result)
        print(json.dumps({'route': target['route'], 'state': result['state'], 'reason': result.get('reason', '')}, ensure_ascii=False), flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preview-run', type=Path, required=True, help='本任务已核的预览run，须与当前登记一致')
    parser.add_argument('--width', type=int, default=1920)
    parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--scale', type=float, default=1.12, help='核实际字号，采集器不会更改账号设置')
    parser.add_argument('--route', action='append', help='从实际导航选择，可重复；默认全部')
    parser.add_argument('--timeout', type=int, default=20)
    args = parser.parse_args()
    if args.width < 320 or args.height < 240 or not 1 <= args.timeout <= 120 or not 1 <= args.scale <= 2:
        parser.error('视口、字号或等待时间不合法')
    os.environ.setdefault('MTRL_EFFORT', 'frontend-layout')
    report_path = output_dir('reports') / 'layout.json'
    report = {'started_at': datetime.now(timezone.utc).isoformat(), 'ok': False, 'pages': [],
              'collector_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    try:
        owner_path, owner, base = registered_preview()
        if owner_path.resolve() != args.preview_run.resolve() / 'reports/real_owner.json':
            raise ValueError('当前登记预览不属于指定run，未登录或采集')
        assert_same_preview(owner, owner, disposable=True)
        report.update(owner={key: owner[key] for key in ('schema', 'revision', 'product_digest', 'index_sha256')},
                      expected={'viewport': [args.width, args.height], 'scale': args.scale}, fresh_browser_context=True)
        if sys.platform == 'win32':
            os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', 'C:/ProgramData/ms-playwright')
        from playwright.sync_api import sync_playwright
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(headless=True)
            try:
                with browser.new_context(viewport={'width': args.width, 'height': args.height}, locale='zh-CN', timezone_id='Asia/Shanghai') as context:
                    page = context.new_page()
                    page.goto(base + '/login?next=%2Fpreview')
                    page.locator('[name=account]').fill(owner['preview_account'])
                    page.locator('[name=password]').fill('')
                    page.locator('button[type=submit]').click()
                    page.locator('.page-view:not([hidden]):not([inert])').wait_for(timeout=args.timeout * 1000)
                    identity = page.request.get(base + '/api/m15/users').json()['me']
                    if not identity or identity['account'] != owner['preview_account']:
                        raise ValueError('临时验看账号未登录')
                    actual_scale = page.evaluate("Number(getComputedStyle(document.documentElement).getPropertyValue('--fscale'))")
                    if abs(actual_scale - args.scale) > .001:
                        raise ValueError('实际字号与目标不符，请先在临时账号的外观面板设置')
                    routes = navigation(page, base)
                    report['navigation'] = routes
                    if args.route:
                        requested = set(args.route)
                        if requested - {item['route'] for item in routes}:
                            raise ValueError('所选页面不在实际导航中')
                        routes = [item for item in routes if item['route'] in requested]
                    report['pages'] = collect(page, owner, base, routes, scale=args.scale, timeout=args.timeout)
                    assert_same_preview(owner, registered_preview()[1], disposable=True)
                    report['ok'] = bool(report['pages']) and all(item['state'] == 'ready' for item in report['pages'])
            finally:
                browser.close()
    except Exception as exc:
        report['error'] = str(exc) if isinstance(exc, (ValueError, RuntimeError)) else type(exc).__name__
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    write_json(report_path, report)
    close_runs(success=report['ok'])
    if not report_path.exists():
        report_path = ROOT / '.artifacts/archive' / report_path.relative_to(ROOT / '.artifacts/active')
    print(json.dumps({'ok': report['ok'], 'pages': len(report['pages']), 'report': str(report_path)}, ensure_ascii=False))
    return 0 if report['ok'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
