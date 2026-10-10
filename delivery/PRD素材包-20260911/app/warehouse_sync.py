# -*- coding: utf-8 -*-
"""
仓库列表同步：纯 HTTP 抓信息化「仓库列表」（GetWareHouseList），得「仓库名 → 全名」映射，
缓存到 var/cache/仓库列表.json，供导入兜底建档（仓库名 ↔ 全名 双向匹配）。

无浏览器依赖（NSSM 服务 Session 0 可跑）；cookie 过期时 login_cookie 兜底（需桌面环境）。

调用方：import_pay_notice / import_sfjc / import_kcdj 匹配不到时查缓存兜底；
        api.py POST /api/projects/sync_warehouse 主动刷新。
"""
import os
import re
import sys
import time
import json
import urllib.request
import urllib.parse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 项目根
APP = os.path.dirname(os.path.abspath(__file__))                      # app/
INPUT = os.path.join(BASE, 'input')
sys.path.insert(0, APP)
sys.path.insert(0, BASE)
sys.path.insert(0, INPUT)

import db  # noqa
from consts import BASE_URL  # noqa
import common_export as ce  # noqa

CACHE_DIR = os.path.join(BASE, 'var', 'cache')
CACHE_FILE = os.path.join(CACHE_DIR, '仓库列表.json')

WH_API = BASE_URL + '/PMS/PMM/KcBaseSetting/GetWareHouseList'
WH_PARAMS = {
    'orgQuery': '#type:ORG#curOrg:3700000000000014#subOrg:#curProj:#cubProj:#parentNode:',
    'pcid': '0', 'page': '0', 'start': '0', 'limit': '100',
    'sort': '[{"property":"PhidPc_EXName","direction":"ASC"}]', 'ng3_logid': '',
}

# 全名尾部「(XMCB2025080001)」式项目编号剥掉
_TRAIL = re.compile(r'\s*[（(][A-Za-z]{2,}[0-9]+[)）]$')


def strip_code(s):
    return _TRAIL.sub('', (s or '').strip()).strip() or (s or '').strip()


def load_cache():
    try:
        with open(CACHE_FILE, encoding='utf-8') as f:
            d = json.load(f)
        if d.get('items'):
            return d
    except Exception:
        pass
    return None


def save_cache(items):
    os.makedirs(CACHE_DIR, exist_ok=True)
    d = {'items': items, 'fetched_at': time.strftime('%Y-%m-%d %H:%M:%S'), 'count': len(items)}
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
    return d


def _lookup(items, key, field):
    for it in items:
        if it.get(field) == key:
            return it
    return None


def lookup_by_name(name, cache=None):
    """仓库名 → item（含 full_name）；无缓存返回 None"""
    c = cache or load_cache()
    if not c:
        return None
    return _lookup(c['items'], name, 'name')


def lookup_by_full(full_name, cache=None):
    """全名 → item（含 name/仓库名）；无缓存返回 None"""
    c = cache or load_cache()
    if not c:
        return None
    return _lookup(c['items'], full_name, 'full_name')


def fetch_warehouse_map(log=print):
    """纯 HTTP 抓仓库列表，返回 [{name:仓库名, full_name:全名}]；失败返回 []"""
    cookie = ce.load_cookie()
    for attempt in range(2):
        if not cookie:
            cookie = ce.login_cookie()
            ce.save_cookie(cookie)
        body = urllib.parse.urlencode(WH_PARAMS).encode('utf-8')
        req = urllib.request.Request(WH_API, data=body, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8')
        req.add_header('Cookie', cookie)
        req.add_header('User-Agent', 'Mozilla/5.0')
        req.add_header('X-Requested-With', 'XMLHttpRequest')
        try:
            raw = urllib.request.urlopen(req, timeout=60).read().decode('utf-8', 'ignore')
            d = json.loads(raw)
            recs = d.get('Record') or []
            items = []
            for r in recs:
                if str(r.get('Nullify')) == '1':   # 作废的仓库跳过
                    continue
                name = (r.get('Whname') or '').strip()
                full = strip_code(r.get('PhidPc_EXName') or '')
                if name:
                    items.append({'name': name, 'full_name': full})
            if items:
                log('仓库列表抓取 %d 条' % len(items))
                return items
            return []
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt == 0:
                cookie = ce.login_cookie()
                ce.save_cookie(cookie)
                continue
            log('!! 仓库列表抓取 HTTP %s' % e.code)
            return []
        except Exception as e:
            log('!! 仓库列表抓取异常: %s' % e)
            return []
    return []


def sync_warehouse(log=print):
    """抓取仓库列表 → 缓存 → 建/校正 projects（name=仓库名, full_name=全名）。

    full_name 统一存「所属项目全名」：普通项目=自己的全名（唯一）、小微仓库=壳全名（一对多）。
    壳全名不再存 aliases（那是别名，不是全名）。"""
    items = fetch_warehouse_map(log)
    if not items:
        return {'ok': False, 'count': 0, 'added': 0, 'updated': 0}
    save_cache(items)
    conn = db.get_conn()
    added = updated = 0
    try:
        for it in items:
            name = it['name']
            full = it['full_name']
            is_small = '是' if ('小微' in full) else '否'
            row = conn.execute('SELECT id, full_name, name, is_small FROM projects WHERE name=?',
                               (name,)).fetchone()
            # 普通项目才按 full_name 匹配（小微 full_name=壳全名 是一对多，按它匹配会歧义）
            if row is None and full and is_small == '否':
                row = conn.execute('SELECT id, full_name, name, is_small FROM projects WHERE full_name=?',
                                   (full,)).fetchone()
            if row is None:
                # 只建具体小微（full_name 含「小微」）；普通项目匹配不到 = 老项目（不在常用项目列表），
                # 不建（老项目靠欠款类数据导入建档，见总纲 §0.6 建档入口收敛）
                if is_small == '是':
                    conn.execute('INSERT INTO projects(name, full_name, is_small) VALUES(?,?,?)',
                                 (name, full, is_small))
                    added += 1
            else:
                sets, args = [], []
                if full and not (row['full_name'] or ''):
                    sets.append('full_name=?'); args.append(full)
                if row['name'] != name:
                    sets.append('name=?'); args.append(name)
                if row['is_small'] != is_small:
                    sets.append('is_small=?'); args.append(is_small)
                if sets:
                    args.append(row['id'])
                    conn.execute('UPDATE projects SET ' + ', '.join(sets) + ' WHERE id=?', args)
                    updated += 1
        # 壳行（小微合并项目，name 含"小微"）校正 is_small=是
        conn.execute("UPDATE projects SET is_small='是' WHERE name LIKE '%小微%' AND is_small <> '是'")
        conn.commit()
    finally:
        conn.close()
    return {'ok': True, 'count': len(items), 'added': added, 'updated': updated}
