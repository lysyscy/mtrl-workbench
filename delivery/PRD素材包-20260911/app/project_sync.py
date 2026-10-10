# -*- coding: utf-8 -*-
"""
项目列表同步：从信息化 GetCommonUseList 抓全量项目（PhId/BillNo/BillName/简称），
按名称 upsert 进 projects 表（写入 phid）。
调用方：api.py /api/projects/sync；也可命令行单独跑。
"""
import os
import re
import sys
import json
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db

# 复用 input/sfjc_export_http 的 cookie 缓存逻辑
INPUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'input')
sys.path.insert(0, INPUT)
from common_export import load_cookie, login_cookie, save_cookie  # noqa: E402
from consts import BASE_URL  # noqa: E402

BASE = BASE_URL
HELP_URL = (BASE + '/SUP/RichHelp/GetCommonUseList'
            '?helpid=project_table_pchelp&ORMMode=true&skipInfoAuth=1')

# BillName 尾部 "项目代码" 形式（如 "新疆慧能横窑安装项目(XMCB2025080001)"）剥掉
_TRAIL = re.compile(r'\s*[（(][A-Z]{3,}\d+[)）]$')


def strip_trail(name):
    return _TRAIL.sub('', name).strip() or name


def fetch_project_map():
    """HTTP 抓全量项目，返回 [{phid, code, name, ab}]；cookie 失败时浏览器刷新重试一次"""
    cookie = load_cookie()
    for attempt in range(2):
        try:
            req = urllib.request.Request(HELP_URL)
            req.add_header('User-Agent', 'Mozilla/5.0')
            req.add_header('Cookie', cookie or '')
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
            d = json.loads(b.decode('utf-8', 'ignore'))
            recs = d.get('Record') or d.get('record') or []
            if recs:
                return [{'phid': str(x.get('PhId') or ''),
                         'code': str(x.get('BillNo') or ''),
                         'name': strip_trail(str(x.get('BillName') or '')),
                         'ab': str(x.get('Ab') or '')} for x in recs]
            return []
        except Exception:
            if attempt == 0:
                cookie = login_cookie()   # 真登录（优先纯 HTTP，失败回退浏览器）
                save_cookie(cookie)
    return []


def sync_projects(conn=None):
    """抓取并写入 projects.phid。按全名(full_name)匹配，命中补写 phid/full_name；
    未命中用全名建档（name 暂=全名，等仓库列表/库存单据导入时校正为仓库名）。
    project_map 导入匹配已退役（映射改由仓库列表自动建立）。
    返回 {'added': n, 'updated': m, 'total': t}"""
    rows = fetch_project_map()
    own = conn is None
    if own:
        conn = db.get_conn()
    added = updated = 0
    try:
        for p in rows:
            if not p['phid'] or not p['name']:
                continue
            full = p['name']   # 全名（BillName 去尾部项目代码后）
            # name 优先：小微壳 name=壳全名，优先命中壳，避免 full_name（壳全名）误命中多个具体小微
            row = conn.execute('SELECT id, phid, full_name, name, is_small FROM projects WHERE name=?',
                               (full,)).fetchone()
            if row is None:
                row = conn.execute('SELECT id, phid, full_name, name, is_small FROM projects WHERE full_name=?',
                                   (full,)).fetchone()
            # 不再按 aliases 兜底匹配：具体小微项目的 aliases 存了壳全名，
            # aliases 匹配会把壳的 phid 误写到具体小微（2026-09-08 实测）
            if row is None:
                # 壳（全名含"小微"）full_name 空（壳就是全名本身）；普通项目 full_name=全名
                store_full = '' if ('小微' in full) else full
                conn.execute('INSERT INTO projects(name, full_name, phid) VALUES(?,?,?)',
                             (full, store_full, p['phid']))
                added += 1
            else:
                # 具体小微项目（依附壳、无 phid）不写 phid/full_name；小微壳（name 含"小微"）只写 phid 不补 full_name
                is_concrete_small = (row['is_small'] == '是' and '小微' not in (row['name'] or ''))
                is_shell = ('小微' in (row['name'] or ''))
                sets, args = [], []
                if not (row['full_name'] or '') and not is_concrete_small and not is_shell:
                    sets.append('full_name=?'); args.append(full)
                if row['phid'] != p['phid'] and not is_concrete_small:
                    sets.append('phid=?'); args.append(p['phid'])
                if sets:
                    args.append(row['id'])
                    conn.execute('UPDATE projects SET ' + ', '.join(sets) + ' WHERE id=?', args)
                    updated += 1
        # 三态同步：常用列表移除 → 本地有 phid 的在建正常项目转「完工」（=收尾）
        # 仅当成功抓到常用列表（rows 非空）时执行，避免 fetch 失败误伤全部项目
        retired = 0
        retired_names = []
        if rows:
            fetched = {p['name'] for p in rows if p.get('name')}
            for r in conn.execute("SELECT id, name, full_name FROM projects "
                                  "WHERE status='在建' AND is_small='否' AND phid != ''").fetchall():
                if r['name'] not in fetched and (r['full_name'] or '') not in fetched:
                    conn.execute("UPDATE projects SET status='完工' WHERE id=?", (r['id'],))
                    retired += 1
                    retired_names.append(r['name'])
        conn.commit()
        total = conn.execute('SELECT COUNT(*) FROM projects').fetchone()[0]
        return {'added': added, 'updated': updated, 'retired': retired,
                'retired_names': retired_names, 'total': total, 'fetched': len(rows)}
    finally:
        if own:
            conn.close()


if __name__ == '__main__':
    db.init_db()
    print(json.dumps(sync_projects(), ensure_ascii=False))
