"""Real API/DOM selection helpers; never seed or fabricate business responses."""
from decimal import Decimal
import json
from playwright.sync_api import expect
from test_preview import login


def get(api, path, **params):
    response = api.get(path, params=params)
    response.raise_for_status()
    return response.json()


def money(value):
    return format(Decimal(str(value)), ',.2f')


def grid_row(page, grid, key):
    return page.locator(grid + ' [row-id=' + json.dumps(str(key), ensure_ascii=False) + ']').first


def open_page(page, base, route, title, *, authenticated=True):
    if authenticated:
        login(page, base)
    path='/preview'+('/'+route if route else '')
    if authenticated:
        if route!='projects':page.locator('a[href="'+path+'"]').click()
    else:
        page.goto(base+path)
    expect(page.locator('#page-title')).to_have_text(title)
    page.wait_for_load_state('networkidle')


def ledger_sample(api, projects, *, editable=False):
    for project in projects:
        if project['project_type'] == 'shell':
            continue
        data = get(api, '/api/m05/ledger', project_id=project['id'], end_ym='')
        for side in data['sides']:
            for row in side['rows']:
                if not editable or row['editable']:
                    key = side['category'] + ':' + row['row_kind'] + ':' + str(row['record_id'] if row['row_kind']=='manual' else row['month'])
                    return project, side, row, key
    raise AssertionError('真实副本缺少所需台账行，代表路径未覆盖')


def contract_sample(api):
    rows=get(api,'/api/m11/list')['rows']
    for row in rows:
        label=row['contract_no'] or row['material']
        if label and sum((r['contract_no'] or r['material'])==label for r in rows)==1:
            return row,label
    raise AssertionError('真实副本缺少可稳定定位的合同，合同交互未覆盖')
