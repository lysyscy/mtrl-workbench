"""Measure an existing isolated read-only React preview; never start or replace it."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.audit.workspace_paths import output_dir, finish_run

PAGES = [('', '首页'), ('projects', '项目档案'), ('i8', 'i8 接入层'),
         ('notices', '付款通知书'), ('ledger', '付款流水与欠款统计'),
         ('contracts', '集采台账'), ('process', '过程资料'), ('settlement', '收发结存与提取'),
         ('big', '月度会大表'), ('inventory', '库存单据与调整单'), ('fees', '特殊费用'),
         ('mechanical', '机械费'), ('rules', '规则配置'), ('users', '用户管理')]
SCREEN_PAGES = [p for p in PAGES if p[0] in {'ledger', 'contracts', 'inventory'}]
FIELDS = ['ready_ms', 'fcp_ms', 'lcp_ms', 'cls', 'layout_shift_all',
          'main_thread_ms', 'observed_blocking_ms', 'transfer_bytes']
OPTIONS = dict(viewport={'width': 1350, 'height': 940}, device_scale_factor=1,
               locale='zh-CN', timezone_id='Asia/Shanghai')

OBSERVER="""(()=>{window.__measure={long:[],shifts:[],lcp:[]};
new PerformanceObserver(l=>{for(const x of l.getEntries())window.__measure.long.push({start:x.startTime,duration:x.duration})}).observe({type:'longtask',buffered:true});
new PerformanceObserver(l=>{for(const x of l.getEntries())window.__measure.shifts.push({start:x.startTime,value:x.value,recent:x.hadRecentInput})}).observe({type:'layout-shift',buffered:true});
new PerformanceObserver(l=>{for(const x of l.getEntries())window.__measure.lcp.push({start:x.startTime,size:x.size})}).observe({type:'largest-contentful-paint',buffered:true});})()"""
EXTRACT="""start=>({observer:window.__measure,paints:performance.getEntriesByType('paint').map(x=>({name:x.name,start:x.startTime})),navigation:performance.getEntriesByType('navigation').map(x=>({ttfb:x.responseStart,dom:x.domContentLoadedEventEnd,load:x.loadEventEnd})),resources:performance.getEntriesByType('resource').filter(x=>x.startTime>=start).map(x=>({url:x.name.replace(location.origin,''),start:x.startTime,duration:x.duration,ttfb:x.responseStart-x.startTime,transfer:x.transferSize,encoded:x.encodedBodySize,decoded:x.decodedBodySize,type:x.initiatorType})),fontLoaded:document.fonts.check('16px MiSans'),fontStatus:document.fonts.status,visibleRows:[...document.querySelectorAll('.page-view:not([hidden]) .ag-row,.page-view:not([hidden]) tbody tr')].length,contentChars:document.querySelector('.page-view:not([hidden])')?.innerText.length??0,alerts:[...document.querySelectorAll('.page-view:not([hidden]) [role=alert]')].filter(x=>x.offsetParent!==null).length})"""
EVENT_OBSERVER = """()=>{window.__measure.events=[];new PerformanceObserver(l=>{for(const x of l.getEntries())window.__measure.events.push({name:x.name,start:x.startTime,duration:x.duration,interactionId:x.interactionId})}).observe({type:'event',buffered:true,durationThreshold:16})}"""


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def quality(rows, *, expected=None, interactions=()):
    errors, warnings = [], []
    counts = Counter((r['kind'], r['route']) for r in rows)
    if (not rows or (expected is not None and counts != expected)
            or len({(r['kind'], r['route'], r['sample']) for r in rows}) != len(rows)):
        errors.append({'reason': 'missing-or-duplicate-samples'})
    for row in rows:
        key = [row['kind'], row['route'], row['sample']]
        if (any(row[k] for k in ['errors', 'bad_responses', 'failed_requests'])
                or row['font_loaded'] is not True or row['content_chars'] <= 0
                or any(not isinstance(row[k], (float, int)) or not math.isfinite(row[k])
                       or row[k] < 0 for k in ['ready_ms', 'main_thread_ms', 'transfer_bytes'])):
            errors.append({'sample': key, 'reason': 'failed-or-invalid-sample'})
        if row['font_status'] != 'loaded':
            warnings.append({'sample': key, 'reason': 'font-set-still-loading'})
    for row in interactions:
        if row['action'] in {'inventory-input', 'inventory-clear'} and row.get('api'):
            errors.append({'action': row['action'], 'reason': 'unexpected-filter-request'})
        if row.get('next_two_frames_ms') is not None and row['action'].endswith('return'):
            warnings.append({'action': row['action'],
                             'reason': 'navigation-automation-time-not-user-latency'})
    return {'ok': not errors, 'errors': errors, 'warnings': warnings,
            'font_set_stable_for_all_samples': bool(rows) and all(r['font_status'] == 'loaded' for r in rows),
            'navigation_automation_time_is_user_latency': False}


def summarize(rows):
    result = []
    for kind, route in dict.fromkeys((r['kind'], r['route']) for r in rows):
        samples = [r for r in rows if (r['kind'], r['route']) == (kind, route)]
        row = {'kind': kind, 'route': route, 'n': len(samples)}
        for field in FIELDS:
            vals = [r[field] for r in samples if r[field] is not None]
            row[field] = dict(median=statistics.median(vals), min=min(vals), max=max(vals)) if vals else None
        result.append(row)
    return result


def regressions(rows, baseline):
    """A screening alarm (>25% AND >50ms), not an acceptance target."""
    old = {(r['kind'], r['route']): r for r in baseline}
    hits = []
    for row in summarize(rows):
        before = old.get((row['kind'], row['route']))
        if before is None:
            raise ValueError('Baseline is missing a screened page')
        for field in ['ready_ms', 'main_thread_ms']:
            a, b = before[field]['median'], row[field]['median']
            if b > a * 1.25 and b - a > 50:
                hits.append({'route': row['route'], 'metric': field, 'before': a, 'after': b})
    return hits


def cls(entries):
    best = score = 0
    start = last = None
    for x in entries:
        if x['recent']:
            continue
        t = x['start']
        if start is None or t-last > 1000 or t-start > 5000:
            start, score = t, 0
        score += x['value']
        best, last = max(best, score), t
    return best


def ready(page, title):
    page.locator('#page-title').filter(has_text=title).wait_for(timeout=30000)
    page.wait_for_load_state('networkidle', timeout=60000)
    page.evaluate('document.fonts.ready')
    page.evaluate('()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))')
    return page.evaluate('performance.now()')


def metrics(cdp):
    return {x['name']: x['value'] for x in cdp.send('Performance.getMetrics')['metrics']}


def sample(page, cdp, base, kind, route, title, n):
    errors, bad, failed = [], [], []
    def error(e): errors.append(str(e)[:200])
    def response(r):
        if r.status >= 400: bad.append({'url': r.url.replace(base, ''), 'status': r.status})
    def failure(r): failed.append({'url': r.url.replace(base, ''), 'failure': r.failure})
    page.on('pageerror', error)
    page.on('response', response)
    page.on('requestfailed', failure)
    try:
        before = metrics(cdp)
        if kind == 'cold':
            start = 0
            page.goto(base+'/preview'+('/'+route if route else ''), wait_until='domcontentloaded')
        else:
            start = page.evaluate('performance.now()')
            page.locator('.sidebar nav a').filter(has_text=title).click()
        end = ready(page, title)
        page.wait_for_timeout(100)  # Preserve the historical observer drain window.
        data, after = page.evaluate(EXTRACT, start), metrics(cdp)
        longs = [x for x in data['observer']['long'] if x['start'] >= start]
        shifts = [x for x in data['observer']['shifts'] if x['start'] >= start]
        return dict(kind=kind, route=route or 'home', sample=n, ready_ms=end-start,
                    fcp_ms=next((x['start'] for x in data['paints'] if x['name']=='first-contentful-paint'), None) if kind=='cold' else None,
                    lcp_ms=data['observer']['lcp'][-1]['start'] if kind=='cold' and data['observer']['lcp'] else None,
                    cls=cls(shifts), layout_shift_all=sum(x['value'] for x in shifts),
                    main_thread_ms=1000*(after.get('TaskDuration', 0)-before.get('TaskDuration', 0)),
                    script_ms=1000*(after.get('ScriptDuration', 0)-before.get('ScriptDuration', 0)),
                    layout_ms=1000*(after.get('LayoutDuration', 0)-before.get('LayoutDuration', 0)),
                    long_tasks=longs, observed_blocking_ms=sum(max(0, x['duration']-50) for x in longs),
                    shifts=shifts, resources=data['resources'], transfer_bytes=sum(x['transfer'] for x in data['resources']),
                    font_loaded=data['fontLoaded'], font_status=data['fontStatus'], rows_rendered=data['visibleRows'],
                    content_chars=data['contentChars'], visible_alerts=data['alerts'],
                    errors=errors, bad_responses=bad, failed_requests=failed, navigation=data['navigation'])
    finally:
        page.remove_listener('pageerror', error)
        page.remove_listener('response', response)
        page.remove_listener('requestfailed', failure)


def page_context(browser, state):
    context = browser.new_context(**OPTIONS, storage_state=state)
    context.add_init_script(OBSERVER)
    page = context.new_page()
    cdp = context.new_cdp_session(page)
    cdp.send('Performance.enable')
    return context, page, cdp


def prime(page, base):
    page.goto(base+'/preview', wait_until='networkidle')
    for route, title in PAGES:
        page.locator('.sidebar nav a').filter(has_text=title).click()
        ready(page, title)


def inventory_interactions(page):
    page.evaluate(EVENT_OBSERVER)
    sys.path.insert(0, str(ROOT/'apps/frontend/tests'))
    from preview_select import pick_option
    page.locator('.sidebar nav a').filter(has_text='库存单据与调整单').click()
    ready(page, '库存单据与调整单')
    pick_option(page, '库存核算期间模式', '全部')
    page.get_by_role('button', name='列筛选', exact=True).click()
    field = page.get_by_label('列包含文字', exact=True)
    clear = page.get_by_role('button', name='清除全部列', exact=True)
    field.press_sequentially('钢')
    clear.click()
    ready(page, '库存单据与调整单')
    rows = []
    for n in range(1, 6):
        for name, fn in [('inventory-input', lambda: field.press_sequentially('钢')), ('inventory-clear', clear.click)]:
            start = page.evaluate('performance.now()')
            fn()
            ready(page, '库存单据与调整单')
            page.wait_for_timeout(100)
            data = page.evaluate("""start=>({events:window.__measure.events.filter(x=>x.start>=start),longs:window.__measure.long.filter(x=>x.start>=start),api:performance.getEntriesByType('resource').filter(x=>x.startTime>=start&&x.name.includes('/api/')).map(x=>({path:x.name.replace(location.origin,''),duration:x.duration}))})""", start)
            rows.append(dict(action=name, sample=n, **data))
    return rows


def preview_identity(run):
    run = run.resolve(strict=True)
    if not run.is_relative_to(ROOT/'.artifacts/active'):
        raise ValueError('Preview run must belong to this checkout active artifacts')
    owner, version = read_json(run/'reports/real_owner.json'), read_json(run/'reports/version.json')
    if (owner['status'] != 'ready' or owner['host'] != '127.0.0.1' or owner['port'] == 8000
            or not 1024 <= owner['port'] <= 65535 or owner['read_only'] is not True
            or version.get('diagnostic_instrumentation') is not False
            or owner['database'] != 'mtrl_workbench_test' or owner['schema'] == 'public'
            or owner['preview_account'] != 'preview-user' or not owner['cookie_name'].startswith('mw_real_preview_')):
        raise ValueError('Not a supported isolated read-only preview')
    build = Path(version['build_path']).resolve(strict=True)
    if not build.is_relative_to(run/'work') or owner['index_sha256'] != version['index_sha256']:
        raise ValueError('Preview build identity mismatch')
    if hashlib.sha256((build/'index.html').read_bytes()).hexdigest() != version['index_sha256']:
        raise ValueError('Preview index changed')
    for name, digest in version['files'].items():
        asset = (build/name).resolve(strict=True)
        if not asset.is_relative_to(build) or hashlib.sha256(asset.read_bytes()).hexdigest() != digest:
            raise ValueError('Preview asset changed')
    return owner, version


def measure(args):
    from playwright.sync_api import sync_playwright
    owner, version = preview_identity(args.preview_run)
    baseline = read_json(args.baseline_summary)
    baseline_owner = read_json(args.baseline_summary.parent/'real_owner.json')
    if any(owner[k] != baseline_owner[k] for k in ['database', 'schema', 'revision']):
        raise ValueError('Baseline data identity differs')
    baseline_env = read_json(args.baseline_summary.with_name(args.baseline_summary.name.replace('summary', 'environment', 1)))
    base = f'http://127.0.0.1:{owner["port"]}'
    reports = output_dir()
    write_json(reports/'input.json', dict(preview_run=str(args.preview_run.resolve()), version=version,
               data_identity={k: owner[k] for k in ['database', 'schema', 'revision']}, baseline_summary=str(args.baseline_summary.resolve()),
               baseline_sha256=hashlib.sha256(args.baseline_summary.read_bytes()).hexdigest(), label=args.label,
               measurement_entry_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
    print(f'OUTPUT {reports}', flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            env = dict(browser_version=browser.version, **OPTIONS,
                       cpu_throttling=1, network='local loopback, no artificial throttling',
                       cold_cache='new context each sample + CDP cache disabled; DB/OS caches not flushed',
                       warm_cache='one context, full-site priming pass then 3 rounds; HTTP cache normal, React Query and kept-alive state retained',
                       font='normal local MiSans 400/500/600, no blocking/substitution',
                       ready_definition='title + networkidle 500ms + fonts.ready + 2 rAF; diagnostic proxy, not INP or SPA LCP')
            env['executable'] = p.chromium.executable_path
            env['timezone'] = env.pop('timezone_id')
            for key in ['browser_version', 'viewport', 'device_scale_factor', 'locale', 'timezone', 'cpu_throttling', 'font', 'network', 'cold_cache', 'warm_cache', 'ready_definition']:
                if env[key] != baseline_env[key]: raise ValueError(f'Baseline condition changed: {key}')
            write_json(reports/'environment.json', env)
            with browser.new_context(**OPTIONS) as auth:
                response = auth.request.get(base+'/preview')
                if response.status != 200 or hashlib.sha256(response.body()).hexdigest() != version['index_sha256']:
                    raise ValueError('Live preview index mismatch')
                if not auth.request.post(base+'/m15/login', form={'account':'preview-user', 'password':''}).ok:
                    raise ValueError('Preview login failed')
                prefs = auth.request.get(base+'/api/m15/theme?surface=react').json()
                write_json(reports/'appearance.json', {k:prefs[k] for k in ['theme','default','ui_scale']})
                if prefs['theme'] != prefs['default'] or prefs['ui_scale'] != 'standard':
                    raise ValueError('Use default theme/standard scale; this tool does not change preferences')
                state = auth.storage_state()  # Memory only; never serialize session cookies.
            rows = []
            context, page, cdp = page_context(browser, state)
            with context:
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)[:200]))
                page.on('requestfailed', lambda r: errors.append('requestfailed: '+r.url.replace(base, '')))
                page.on('response', lambda r: errors.append(f'HTTP {r.status}: '+r.url.replace(base, '')) if r.status >= 400 else None)
                prime(page, base)
                with (reports/'screen-samples.jsonl').open('x', encoding='utf-8') as raw:
                    for n in range(1, 4):
                        for route, title in SCREEN_PAGES:
                            row = sample(page, cdp, base, 'warm', route, title, n)
                            rows.append(row)
                            raw.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')
                            raw.flush()
                interactions = inventory_interactions(page)
            write_json(reports/'screen-interactions.json', dict(results=interactions, errors=errors,
                       timing='EventTiming16ms; scripted input, not physical IME or RUM INP; no host response-body navigation timer'))
            q = quality(rows, expected=Counter({('warm', r):3 for r, _ in SCREEN_PAGES}), interactions=interactions)
            if errors: q['errors'].append({'reason':'interaction-script-errors'}); q['ok'] = False
            q['regressions'] = regressions(rows, baseline)
            q['full_allowed'] = q['ok'] and not q['regressions']
            q['alarm'] = '>25% AND >50ms ready/main-thread median; screening only, selected-route order differs from full14'
            write_json(reports/'screen-quality.json', q)
            if not q['full_allowed']: return 2
            if args.stage == 'screen': return 0
            full = []
            with (reports/'samples.jsonl').open('x', encoding='utf-8') as raw:
                def collect(page, cdp, kind, route, title, n):
                    row = sample(page, cdp, base, kind, route, title, n)
                    full.append(row)
                    raw.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')
                    raw.flush()
                    print(kind, route or 'home', n, round(row['ready_ms']), flush=True)
                for n in range(1, 4):
                    for route, title in PAGES:
                        context, page, cdp = page_context(browser, state)
                        with context:
                            cdp.send('Network.enable')
                            cdp.send('Network.setCacheDisabled', {'cacheDisabled':True})
                            collect(page, cdp, 'cold', route, title, n)
                context, page, cdp = page_context(browser, state)
                with context:
                    prime(page, base)
                    for n in range(1, 4):
                        for route, title in PAGES: collect(page, cdp, 'warm', route, title, n)
            write_json(reports/'summary.json', summarize(full))
            q = quality(full, expected=Counter({(k, r or 'home'):3 for k in ['cold','warm'] for r, _ in PAGES}))
            write_json(reports/'quality.json', q)
            return 0 if q['ok'] else 2
        finally:
            browser.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('check', help='Read existing raw evidence; never modify it')
    check.add_argument('--samples', type=Path, required=True)
    check.add_argument('--interactions', type=Path)
    run = sub.add_parser('run', help='Screen first, then optionally collect full84')
    run.add_argument('--preview-run', type=Path, required=True)
    run.add_argument('--baseline-summary', type=Path, required=True)
    run.add_argument('--label', required=True)
    run.add_argument('--stage', choices=['screen', 'all'], default='all')
    args = parser.parse_args(argv)
    if args.command == 'check':
        rows = [json.loads(s) for s in args.samples.read_text(encoding='utf-8-sig').splitlines() if s.strip()]
        data = read_json(args.interactions) if args.interactions else {'results': [], 'errors': []}
        interactions = data['results']
        q = quality(rows, expected=Counter({(k, r or 'home'):3 for k in ['cold','warm'] for r, _ in PAGES}), interactions=interactions)
        if data.get('errors'):
            q['errors'].append({'reason': 'interaction-script-errors'})
            q['ok'] = False
        print(json.dumps(q, ensure_ascii=False, indent=2))
        return 0 if q['ok'] else 2
    os.environ.setdefault('MTRL_EFFORT', 'frontend-measure')
    return measure(args)


if __name__ == '__main__':
    try:
        raise SystemExit(finish_run(main()))
    except Exception as exc:
        print(f'MEASURE FAILED: {type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(1)
