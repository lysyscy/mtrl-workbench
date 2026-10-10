# -*- coding: utf-8 -*-
"""
API 层：Flask 蓝图。所有业务动作都走这里（导入/查询/付款操作/配置）。
"""
import os
import sys
import subprocess
import tempfile
import time
import json

from flask import Blueprint, jsonify, request, session

import db
import importer
import export_runner
from auth import login_required

api = Blueprint('api', __name__)


def _err(msg, code=400):
    return jsonify({'ok': False, 'error': msg}), code


def _ok(data=None):
    return jsonify({'ok': True, 'data': data})


# ================= 鉴权（用户名+密码） =================
@api.post('/api/login')
def login():
    """body {username, password}；校验通过写 session（authed/user/display_name），失败 401。"""
    body = request.get_json(force=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    if not username or not password:
        return _err('请输入用户名和密码', 401)
    u = db.verify_user(username, password)
    if not u:
        return _err('用户名或密码错误', 401)
    session['authed'] = True
    session['user'] = u['username']
    session['display_name'] = u['display_name']
    return _ok({'authed': True, 'user': u['username'], 'display_name': u['display_name']})


@api.post('/api/logout')
def logout():
    session.pop('authed', None)
    session.pop('user', None)
    session.pop('display_name', None)
    return _ok({'authed': False})


@api.get('/api/auth/status')
def auth_status():
    return _ok({'authed': bool(session.get('authed')),
                'user': session.get('user') or '',
                'display_name': session.get('display_name') or ''})


# ================= 用户管理（支持人员更迭） =================
@api.get('/api/users')
@login_required
def users_list():
    return _ok(db.list_users())


@api.post('/api/users')
@login_required
def users_add():
    """新增用户：{username, password, display_name, i8_account?, i8_password?}。用户名唯一，密码 >= 4 位。"""
    from auth import hash_password, obfuscate_i8_password
    body = request.get_json(force=True) or {}
    username = (body.get('username') or '').strip()
    password = body.get('password') or ''
    display_name = (body.get('display_name') or '').strip() or username
    i8_account = (body.get('i8_account') or '').strip()
    i8_password = body.get('i8_password') or ''
    if not username:
        return _err('用户名不能为空')
    if len(password) < 4:
        return _err('密码至少 4 位')
    conn = db.get_conn()
    try:
        if conn.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
            return _err('用户名已存在')
        conn.execute('INSERT INTO users(username, password_hash, display_name, i8_account, i8_password) VALUES(?,?,?,?,?)',
                     (username, hash_password(password), display_name,
                      i8_account, obfuscate_i8_password(i8_password)))
        conn.commit()
        return _ok({'username': username})
    finally:
        conn.close()


@api.post('/api/users/reset')
@login_required
def users_reset():
    """重置密码：{id, password}。"""
    from auth import hash_password
    body = request.get_json(force=True) or {}
    uid = body.get('id')
    password = body.get('password') or ''
    if not uid or len(password) < 4:
        return _err('需要 id 和至少 4 位的新密码')
    conn = db.get_conn()
    try:
        cur = conn.execute('UPDATE users SET password_hash=? WHERE id=?',
                           (hash_password(password), int(uid)))
        conn.commit()
        if cur.rowcount == 0:
            return _err('用户不存在', 404)
        return _ok({'id': int(uid)})
    finally:
        conn.close()


@api.post('/api/users/toggle')
@login_required
def users_toggle():
    """启用/停用：{id, is_active}。不可停用自己。"""
    body = request.get_json(force=True) or {}
    uid = body.get('id')
    active = 1 if body.get('is_active') else 0
    if not uid:
        return _err('需要 id')
    conn = db.get_conn()
    try:
        row = conn.execute('SELECT username FROM users WHERE id=?', (int(uid),)).fetchone()
        if row is None:
            return _err('用户不存在', 404)
        if not active and row['username'] == session.get('user'):
            return _err('不能停用当前登录账号')
        conn.execute('UPDATE users SET is_active=? WHERE id=?', (active, int(uid)))
        conn.commit()
        return _ok({'id': int(uid), 'is_active': active})
    finally:
        conn.close()


@api.post('/api/users/delete')
@login_required
def users_delete():
    """删除用户：{id}。不可删除自己，且至少保留一个账号。"""
    body = request.get_json(force=True) or {}
    uid = body.get('id')
    if not uid:
        return _err('需要 id')
    conn = db.get_conn()
    try:
        row = conn.execute('SELECT username FROM users WHERE id=?', (int(uid),)).fetchone()
        if row is None:
            return _err('用户不存在', 404)
        if row['username'] == session.get('user'):
            return _err('不能删除当前登录账号')
        if conn.execute('SELECT COUNT(*) c FROM users').fetchone()['c'] <= 1:
            return _err('至少保留一个账号')
        conn.execute('DELETE FROM users WHERE id=?', (int(uid),))
        conn.commit()
        return _ok({'id': int(uid)})
    finally:
        conn.close()


@api.post('/api/users/i8')
@login_required
def users_i8():
    """更新用户的 i8 账号绑定：{id, i8_account, i8_password?}。
    i8_password 不传 = 不修改密码（保持原值）；传空串 = 清空密码。"""
    from auth import obfuscate_i8_password
    body = request.get_json(force=True) or {}
    uid = body.get('id')
    if not uid:
        return _err('需要 id')
    i8_account = (body.get('i8_account') or '').strip()
    conn = db.get_conn()
    try:
        row = conn.execute('SELECT username FROM users WHERE id=?', (int(uid),)).fetchone()
        if row is None:
            return _err('用户不存在', 404)
        sets, args = ['i8_account=?'], [i8_account]
        if 'i8_password' in body:
            pwd = body.get('i8_password') or ''
            sets.append('i8_password=?')
            args.append(obfuscate_i8_password(pwd))
        args.append(int(uid))
        conn.execute('UPDATE users SET ' + ', '.join(sets) + ' WHERE id=?', args)
        conn.commit()
        return _ok({'id': int(uid), 'i8_account': i8_account})
    finally:
        conn.close()


# ================= 概览 =================
@api.get('/api/overview')
@login_required
def overview():
    conn = db.get_conn()
    try:
        r = lambda q: conn.execute(q).fetchone()[0]  # noqa
        months_stock = [x[0] for x in conn.execute(
            'SELECT DISTINCT month FROM stock_monthly ORDER BY month DESC LIMIT 12')]
        months_inv = [x[0] for x in conn.execute(
            'SELECT DISTINCT month FROM inv_detail ORDER BY month DESC LIMIT 12')]
        pending = conn.execute(
            "SELECT COUNT(*) FROM pay_notice WHERE biz_class='待确认'").fetchone()[0]
        d = {
            'projects': r('SELECT COUNT(*) FROM projects'),
            'projects_active': r("SELECT COUNT(*) FROM projects WHERE status='在建'"),
            'stock_months': months_stock,
            'inv_months': months_inv,
            'pay_rows': r('SELECT COUNT(*) FROM pay_notice'),
            'pay_pending': pending,
            'debt_rows': r('SELECT COUNT(*) FROM (SELECT 1 FROM v_debt)'),
        }
        # 欠款汇总（按当前视图）
        total = conn.execute('SELECT cls, SUM(debt) AS s FROM v_debt GROUP BY cls').fetchall()
        d['debt_total'] = {x['cls']: x['s'] or 0 for x in total}
        return _ok(d)
    finally:
        conn.close()


# ================= 导入 =================
@api.post('/api/import')
@login_required
def do_import():
    f = request.files.get('file')
    if f is None:
        return _err('未选择文件')
    month = (request.form.get('month') or '').strip()
    forced = (request.form.get('type') or '').strip() or None
    suffix = os.path.splitext(f.filename)[1] or '.xlsx'
    tmp = tempfile.mktemp(suffix=suffix)
    f.save(tmp)
    try:
        result = importer.import_file(tmp, month=month or None, forced_type=forced)
        return _ok(result)
    except Exception as e:
        return _err(str(e))
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


# ================= 配置 =================
@api.get('/api/config')
@login_required
def get_all_config():
    conn = db.get_conn()
    try:
        rows = [dict(r) for r in conn.execute('SELECT * FROM config ORDER BY key')]
        out = {}
        for r in rows:
            try:
                out[r['key']] = json.loads(r['value'])
            except ValueError:
                out[r['key']] = r['value']
        return _ok(out)
    finally:
        conn.close()


@api.post('/api/config')
@login_required
def save_config():
    body = request.get_json(force=True)
    key = (body.get('key') or '').strip()
    value = body.get('value')
    note = (body.get('note') or '').strip()
    if not key or value is None:
        return _err('需要 key 和 value')
    db.set_config(key, value, note)
    return _ok({'key': key})


# ================= 一键导出任务 =================
TASK_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'var', 'state', 'export_task.json')


def _read_task():
    try:
        with open(TASK_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


@api.get('/api/export/task')
@login_required
def export_task_get():
    return _ok(_read_task())


@api.post('/api/export/task')
@login_required
def export_task_post():
    """创建一键导出任务（由程序壳记录，对话中执行 bu 导出后回调 done）"""
    body = request.get_json(force=True)
    t = body.get('type')
    sy, sm = body.get('sy'), body.get('sm')
    ey, em = body.get('ey'), body.get('em')
    if t not in ('sfjc', 'kcdj') or not sy or not sm:
        return _err('参数错误：需要 type(sfjc/kcdj) 和 开始年月')
    if not ey or not em:
        ey, em = sy, sm
    opt = body.get('options')
    if not isinstance(opt, dict):
        opt = {}
    # 账号绑定（阶段二）：查当前登录人绑定的 i8 账号/密码，写入任务供导出子进程使用
    from auth import deobfuscate_i8_password
    user = ''
    password = ''
    uname = session.get('user')
    if uname:
        conn = db.get_conn()
        try:
            row = conn.execute('SELECT i8_account, i8_password FROM users WHERE username=?', (uname,)).fetchone()
            if row:
                user = (row['i8_account'] or '').strip()
                password = deobfuscate_i8_password(row['i8_password'] or '')
        finally:
            conn.close()
    task = {'type': t, 'sy': int(sy), 'sm': int(sm), 'ey': int(ey), 'em': int(em),
            'options': {'pack': bool(opt.get('pack', True)), 'extract': bool(opt.get('extract', True))},
            'user': user, 'password': password,
            'status': 'pending', 'progress': {'pct': 0, 'msg': '待执行'},
            'created': time.strftime('%Y-%m-%d %H:%M:%S'), 'result': None}
    os.makedirs(os.path.dirname(TASK_FILE), exist_ok=True)
    with open(TASK_FILE, 'w', encoding='utf-8') as f:
        json.dump(task, f, ensure_ascii=False, indent=2)
    return _ok(task)


@api.post('/api/export/task/done')
@login_required
def export_task_done():
    """导出执行完毕回调：标记完成并记录结果"""
    body = request.get_json(force=True)
    task = _read_task()
    if not task:
        return _err('没有待执行的任务')
    task['status'] = 'done' if body.get('ok') else 'failed'
    task['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    task['result'] = body.get('result') or body.get('error')
    with open(TASK_FILE, 'w', encoding='utf-8') as f:
        json.dump(task, f, ensure_ascii=False, indent=2)
    return _ok(task)


@api.post('/api/export/run')
@login_required
def export_run():
    """立即执行一键导出任务：Popen 启动独立进程（与Flask解耦，隐藏独立控制台）"""
    task = _read_task()
    if not task:
        return _err('没有待执行的任务')
    if task.get('status') == 'running':
        return _err('任务正在执行中')
    if task.get('status') == 'done':
        return _err('任务已完成，请先发起新任务')
    # 两人共用：另一台电脑正在导出 → 拒绝（文件锁互斥，15 分钟无心跳自动失效）
    holder = export_runner.lock_status()
    if holder:
        return _err('另一台电脑（%s）正在执行导出（%s 开始），请稍候再试'
                    % (holder.get('host') or '?', holder.get('at') or '?'))
    task['status'] = 'running'
    task['started'] = time.strftime('%Y-%m-%d %H:%M:%S')
    task['result'] = None
    task['progress'] = {'pct': 5, 'msg': '开始执行'}
    with open(TASK_FILE, 'w', encoding='utf-8') as f:
        json.dump(task, f, ensure_ascii=False, indent=2)
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'export_worker.py')
    # worker 日志：所有 print/异常堆栈都落到文件，否则一旦子进程死在没人看的控制台就完全失联
    # （历史教训：12:32 那次 worker 死在 55% 之后，export_error.log 为空就是因为 stdout 没重定向）
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'export_worker.log')
    log_f = open(log_path, 'a', encoding='utf-8')
    log_f.write('\n===== worker started %s pid=%s =====\n'
                % (time.strftime('%Y-%m-%d %H:%M:%S'), task.get('started')))
    log_f.flush()
    # DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP：worker 完全脱离 server.py 进程组
    # 即使 server.py 死了，worker 也不会被连带 kill；stdin=DEVNULL 防止 stdin 关闭触发子进程退出
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    subprocess.Popen([sys.executable, worker],
                     stdin=subprocess.DEVNULL, stdout=log_f, stderr=subprocess.STDOUT,
                     creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
                     startupinfo=si, close_fds=True)
    return _ok(task)


# ================= 项目 =================
@api.get('/api/projects')
@login_required
def projects():
    conn = db.get_conn()
    try:
        rows = [dict(r) for r in conn.execute(
            'SELECT * FROM projects ORDER BY sort_order, id')]
        for r in rows:
            r['data_count'] = _child_ref_counts(conn, r['id'])
        return _ok(rows)
    finally:
        conn.close()


@api.post('/api/projects/update')
@login_required
def projects_update():
    """批量更新项目：状态（在建/完工）、排序号、别名（|分隔）"""
    body = request.get_json(force=True)
    items = body.get('items') or []
    if not items:
        return _err('参数错误：需要 items')
    conn = db.get_conn()
    try:
        for it in items:
            pid = it.get('id')
            if not pid:
                continue
            sets, args = [], []
            if it.get('status') in ('在建', '完工', '归档'):
                sets.append('status=?'); args.append(it['status'])
            if 'sort_order' in it:
                try:
                    n = int(it['sort_order'])
                except (ValueError, TypeError):
                    n = 0
                sets.append('sort_order=?'); args.append(n)
            if 'aliases' in it:
                # 规范化 |a|b| 存储：去重、去空白
                parts = [x.strip() for x in (it['aliases'] or '').replace('|', '\n').split('\n') if x.strip()]
                sets.append('aliases=?'); args.append('|' + '|'.join(dict.fromkeys(parts)) + '|' if parts else '')
            if sets:
                args.append(pid)
                conn.execute('UPDATE projects SET ' + ', '.join(sets) + ' WHERE id=?', args)
        conn.commit()
        return _ok({'updated': len(items)})
    finally:
        conn.close()


@api.post('/api/projects/sync')
@login_required
def projects_sync():
    """从信息化获取项目 ID 列表并写入项目表（phid 列）"""
    import project_sync
    try:
        r = project_sync.sync_projects()
        return _ok(r)
    except Exception as e:
        return _err('同步失败：%s' % e)


@api.get('/api/projects/archive_candidates')
@login_required
def projects_archive_candidates():
    """归档候选：完工项目的欠款一览（欠款=0 标可归档）。
    欠款 = 辅材机械(v_debt) + 期初(debt_initial) + 其他(debt_other)；集采(jc_*) 未实现暂不计入。"""
    conn = db.get_conn()
    try:
        done = conn.execute("SELECT id, name FROM projects WHERE status='完工' ORDER BY sort_order, id").fetchall()
        vdebt = {r['project']: round(r['debt'] or 0, 2)
                 for r in conn.execute("SELECT project, SUM(debt) AS debt FROM v_debt GROUP BY project")}
        dinit = {r['项目']: round((r['期初结算'] or 0) - (r['期初付款'] or 0), 2)
                 for r in conn.execute("SELECT 项目, 期初结算, 期初付款 FROM debt_initial")}
        dother = {r['name']: round(r['amt'] or 0, 2)
                  for r in conn.execute("SELECT p.name, SUM(d.金额) AS amt FROM debt_other d "
                                        "JOIN projects p ON p.id=d.project_id GROUP BY p.name")}
        out = []
        for r in done:
            name = r['name']
            debt = round((vdebt.get(name, 0) or 0) + (dinit.get(name, 0) or 0) + (dother.get(name, 0) or 0), 2)
            out.append({'id': r['id'], 'name': name, 'debt': debt,
                        'detail': {'辅材机械': vdebt.get(name, 0) or 0,
                                   '期初': dinit.get(name, 0) or 0,
                                   '其他': dother.get(name, 0) or 0},
                        'archivable': abs(debt) < 0.01})
        return _ok({'items': out})
    finally:
        conn.close()


# ================= 项目管理（增删改查 + 合并去重 + 完整性）=================

_REF_TABLES = ('stock_monthly', 'inv_detail', 'pay_notice', 'pay_plan', 'jc_contract', 'debt_other')
_JC_TABLES = ('jc_invoice', 'jc_settle', 'jc_pay')
_SAFE_TABLES = set(_REF_TABLES) | set(_JC_TABLES)


def _safe_table(t):
    """表名必须是内部白名单常量（_REF_TABLES/_JC_TABLES），杜绝把用户输入拼进 SQL 标识符。"""
    if t not in _SAFE_TABLES:
        raise ValueError('非法表名: %s' % t)
    return t


def _norm_aliases(aliases):
    """规范化别名：去空白、去重，|x|y| 格式"""
    parts = [x.strip() for x in (aliases or '').replace('|', '\n').split('\n') if x.strip()]
    return '|' + '|'.join(dict.fromkeys(parts)) + '|' if parts else ''


def _child_ref_counts(conn, pid):
    """统计某项目 6 表引用行数"""
    n = 0
    for t in _REF_TABLES:
        n += conn.execute('SELECT COUNT(*) FROM %s WHERE project_id=?' % _safe_table(t), (pid,)).fetchone()[0]
    return n


@api.post('/api/projects/add')
@login_required
def projects_add():
    """新增项目：name=仓库名（必填唯一）、full_name=全名、display_name=展示名 等"""
    body = request.get_json(force=True) or {}
    name = (body.get('name') or '').strip()
    full_name = (body.get('full_name') or '').strip()
    if not name:
        return _err('项目名（仓库名）不能为空')
    conn = db.get_conn()
    try:
        dup = conn.execute(
            "SELECT id FROM projects WHERE name=? OR (full_name <> '' AND full_name=?)",
            (name, full_name)).fetchone()
        if dup:
            return _err('已存在同名项目或相同全名')
        conn.execute(
            'INSERT INTO projects(name, full_name, display_name, aliases, phid, is_small, status, note) '
            'VALUES(?,?,?,?,?,?,?,?)',
            (name, full_name, (body.get('display_name') or '').strip(), _norm_aliases(body.get('aliases')),
             (body.get('phid') or '').strip(), body.get('is_small') or '否',
             body.get('status') or '在建', (body.get('note') or '').strip()))
        conn.commit()
        return _ok({'id': conn.execute('SELECT last_insert_rowid() AS i').fetchone()['i']})
    finally:
        conn.close()


@api.post('/api/projects/rename')
@login_required
def projects_rename():
    """重命名：field = name(仓库名) / display_name(展示名) / full_name(全名)，各自同步文本引用"""
    body = request.get_json(force=True) or {}
    pid = body.get('id')
    field = body.get('field')
    value = (body.get('value') or '').strip()
    if not pid or field not in ('name', 'display_name', 'full_name') or not value:
        return _err('参数错误：需要 id 和 field(name/display_name/full_name) 和 value')
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    conn = db.get_conn()
    try:
        row = conn.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
        if row is None:
            return _err('项目不存在', 404)
        old = row[field] or ''
        if field == 'name':
            dup = conn.execute('SELECT id FROM projects WHERE name=? AND id<>?', (value, pid)).fetchone()
            if dup:
                return _err('已存在同名项目')
            conn.execute('UPDATE projects SET name=?, updated_at=? WHERE id=?', (value, now, pid))
            if old and old != value:
                conn.execute('UPDATE stock_monthly SET 仓库=? WHERE project_id=? AND 仓库=?', (value, pid, old))
                conn.execute('UPDATE inv_detail SET 仓库=? WHERE project_id=? AND 仓库=?', (value, pid, old))
                conn.execute('UPDATE mtrl_extract SET wh=? WHERE wh=?', (value, old))
                parts = [x.strip() for x in (row['aliases'] or '').split('|') if x.strip()]
                if old not in parts:
                    parts.append(old)
                conn.execute('UPDATE projects SET aliases=? WHERE id=?',
                             ('|' + '|'.join(parts) + '|' if parts else '', pid))
        elif field == 'display_name':
            conn.execute('UPDATE projects SET display_name=?, updated_at=? WHERE id=?', (value, now, pid))
            if old:
                conn.execute('UPDATE pay_notice SET stat_name=? WHERE project_id=? AND stat_name=?', (value, pid, old))
        else:  # full_name
            dup = conn.execute("SELECT id FROM projects WHERE full_name=? AND full_name<>'' AND id<>?",
                               (value, pid)).fetchone()
            if dup:
                return _err('已存在相同全名')
            conn.execute('UPDATE projects SET full_name=?, updated_at=? WHERE id=?', (value, now, pid))
        conn.commit()
        return _ok({'id': pid, 'field': field, 'value': value})
    finally:
        conn.close()


@api.post('/api/projects/delete/preview')
@login_required
def projects_delete_preview():
    """删除预检：返回该项目下 6 表 + 材机提取的行数，供前端确认框展示"""
    body = request.get_json(force=True) or {}
    pid = body.get('id')
    if not pid:
        return _err('需要 id')
    conn = db.get_conn()
    try:
        row = conn.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
        if row is None:
            return _err('项目不存在', 404)
        counts = {}
        for t in _REF_TABLES:
            counts[t] = conn.execute('SELECT COUNT(*) FROM %s WHERE project_id=?' % _safe_table(t), (pid,)).fetchone()[0]
        name = row['name'] or ''
        wh = conn.execute('SELECT COUNT(*) FROM mtrl_extract WHERE wh=?', (name,)).fetchone()[0] if name else 0
        # 小微壳：连同具体小微项目一起删
        small_map = db.get_config('small_map', {})
        children = []
        if name in small_map:
            for sm in small_map[name]:
                cr = conn.execute('SELECT id, name FROM projects WHERE name=?', (sm,)).fetchone()
                if cr:
                    children.append({'id': cr['id'], 'name': cr['name']})
        return _ok({'id': pid, 'name': name, 'display_name': row['display_name'] or name,
                    'counts': counts, 'mtrl_extract': wh, 'total': sum(counts.values()) + wh,
                    'children': children})
    finally:
        conn.close()


@api.post('/api/projects/delete')
@login_required
def projects_delete():
    """级联删除项目（删前自动备份）；小微壳连同具体小微项目一起删。前端已勾选确认。"""
    body = request.get_json(force=True) or {}
    pid = body.get('id')
    if not pid or not body.get('confirm'):
        return _err('需要 id 和 confirm')
    conn = db.get_conn()
    try:
        row = conn.execute('SELECT * FROM projects WHERE id=?', (pid,)).fetchone()
        if row is None:
            return _err('项目不存在', 404)
        name = row['name'] or ''
        small_map = db.get_config('small_map', {})
        ids = [pid]
        if name in small_map:
            for sm in small_map[name]:
                cr = conn.execute('SELECT id FROM projects WHERE name=?', (sm,)).fetchone()
                if cr:
                    ids.append(cr['id'])
        db.backup_db('del_project_%s' % pid)
        for cid in ids:
            cname = conn.execute('SELECT name FROM projects WHERE id=?', (cid,)).fetchone()
            cname = cname['name'] if cname else ''
            conn.execute('DELETE FROM pay_flow WHERE notice_id IN (SELECT id FROM pay_notice WHERE project_id=?)', (cid,))
            conn.execute('DELETE FROM pay_notice WHERE project_id=?', (cid,))
            conn.execute('DELETE FROM pay_plan WHERE project_id=?', (cid,))
            for jc in ('jc_invoice', 'jc_settle', 'jc_pay'):
                conn.execute('DELETE FROM %s WHERE contract_id IN (SELECT id FROM jc_contract WHERE project_id=?)' % _safe_table(jc), (cid,))
            conn.execute('DELETE FROM jc_contract WHERE project_id=?', (cid,))
            conn.execute('DELETE FROM debt_other WHERE project_id=?', (cid,))
            conn.execute('DELETE FROM inv_detail WHERE project_id=?', (cid,))
            conn.execute('DELETE FROM stock_monthly WHERE project_id=?', (cid,))
            if cname:
                conn.execute('DELETE FROM mtrl_extract WHERE wh=?', (cname,))
            conn.execute('DELETE FROM projects WHERE id=?', (cid,))
        conn.commit()
        return _ok({'deleted': pid, 'children': len(ids) - 1})
    finally:
        conn.close()


@api.get('/api/projects/duplicates')
@login_required
def projects_duplicates():
    """重复候选分组（启发式：phid 相等 / 名称互含 / 抽实义词后共享关键词）"""
    conn = db.get_conn()
    try:
        rows = [dict(r) for r in conn.execute('SELECT id, name, full_name, aliases, phid FROM projects')]
        stop = ('项目', '仓库', '项目部', '工程', '公司', '有限公司', '第四工程公司', '小微', '（', '）', '(', ')')
        def kw(s):
            x = s or ''
            for w in stop:
                x = x.replace(w, '')
            return x
        groups = []
        seen = set()
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                key = (min(a['id'], b['id']), max(a['id'], b['id']))
                if key in seen:
                    continue
                reason = None
                if a['phid'] and a['phid'] == b['phid']:
                    reason = 'phid 相同'
                elif a['name'] and (a['name'] in (b['name'] or '') or a['name'] in (b['aliases'] or '')):
                    reason = '名称互含'
                elif b['name'] and (b['name'] in (a['name'] or '') or b['name'] in (a['aliases'] or '')):
                    reason = '名称互含'
                else:
                    ka, kb = kw(a['name']), kw(b['name'])
                    if ka and kb and len(ka) >= 2 and len(kb) >= 2 and (ka in kb or kb in ka):
                        reason = '关键词相似'
                if reason:
                    seen.add(key)
                    groups.append({'a': a['id'], 'b': b['id'],
                                   'a_name': a['name'], 'b_name': b['name'], 'reason': reason})
        return _ok(groups)
    finally:
        conn.close()


@api.post('/api/projects/merge/preview')
@login_required
def projects_merge_preview():
    """合并预检：返回每个 dup 的迁移行数 + 将并入的 phid/别名"""
    body = request.get_json(force=True) or {}
    keep_id = body.get('keep_id')
    dup_ids = body.get('dup_ids') or []
    if not keep_id or not dup_ids:
        return _err('需要 keep_id 和 dup_ids')
    conn = db.get_conn()
    try:
        keep = conn.execute('SELECT id, name FROM projects WHERE id=?', (keep_id,)).fetchone()
        if keep is None:
            return _err('保留项不存在', 404)
        per_dup = []
        for did in dup_ids:
            dup = conn.execute('SELECT id, name, phid, aliases FROM projects WHERE id=?', (did,)).fetchone()
            if dup is None:
                continue
            per_dup.append({'id': did, 'name': dup['name'], 'counts': _child_ref_counts(conn, did),
                            'phid': dup['phid'], 'aliases': dup['aliases']})
        return _ok({'keep_id': keep_id, 'keep_name': keep['name'], 'per_dup': per_dup})
    finally:
        conn.close()


@api.post('/api/projects/merge')
@login_required
def projects_merge():
    """执行合并：dup 的 6 表 project_id → keep，四名收敛，删 dup（删前自动备份）。前端已勾选确认。"""
    body = request.get_json(force=True) or {}
    keep_id = body.get('keep_id')
    dup_ids = body.get('dup_ids') or []
    if not keep_id or not dup_ids or not body.get('confirm'):
        return _err('需要 keep_id、dup_ids 和 confirm')
    conn = db.get_conn()
    try:
        keep = conn.execute('SELECT * FROM projects WHERE id=?', (keep_id,)).fetchone()
        if keep is None:
            return _err('保留项不存在', 404)
        db.backup_db('merge_projects')
        merged = 0
        for did in dup_ids:
            dup = conn.execute('SELECT * FROM projects WHERE id=?', (did,)).fetchone()
            if dup is None or did == keep_id:
                continue
            for t in _REF_TABLES:
                conn.execute('UPDATE %s SET project_id=? WHERE project_id=?' % _safe_table(t), (keep_id, did))
            # 仓库名/展示名文本统一
            if dup['name'] and dup['name'] != keep['name']:
                conn.execute('UPDATE stock_monthly SET 仓库=? WHERE project_id=? AND 仓库=?', (keep['name'], keep_id, dup['name']))
                conn.execute('UPDATE inv_detail SET 仓库=? WHERE project_id=? AND 仓库=?', (keep['name'], keep_id, dup['name']))
                conn.execute('UPDATE mtrl_extract SET wh=? WHERE wh=?', (keep['name'], dup['name']))
            dup_disp = dup['display_name'] or dup['name']
            keep_disp = keep['display_name'] or keep['name']
            if dup_disp and dup_disp != keep_disp:
                conn.execute('UPDATE pay_notice SET stat_name=? WHERE project_id=? AND stat_name=?', (keep_disp, keep_id, dup_disp))
            # 四名收敛
            if not keep['phid'] and dup['phid']:
                conn.execute('UPDATE projects SET phid=? WHERE id=?', (dup['phid'], keep_id))
            if not keep['full_name'] and dup['full_name']:
                conn.execute('UPDATE projects SET full_name=? WHERE id=?', (dup['full_name'], keep_id))
            if not keep['display_name'] and dup['display_name']:
                conn.execute('UPDATE projects SET display_name=? WHERE id=?', (dup['display_name'], keep_id))
            parts = [x.strip() for x in (keep['aliases'] or '').split('|') if x.strip()]
            for x in (dup['aliases'] or '').split('|'):
                x = x.strip()
                if x and x not in parts:
                    parts.append(x)
            if dup['name'] and dup['name'] not in parts:
                parts.append(dup['name'])
            conn.execute('UPDATE projects SET aliases=?, updated_at=? WHERE id=?',
                         ('|' + '|'.join(parts) + '|' if parts else '', time.strftime('%Y-%m-%d %H:%M:%S'), keep_id))
            conn.execute('DELETE FROM projects WHERE id=?', (did,))
            merged += 1
        conn.commit()
        return _ok({'keep_id': keep_id, 'merged': merged})
    finally:
        conn.close()


@api.get('/api/projects/integrity')
@login_required
def projects_integrity():
    """数据完整性体检：悬空硬引用 / 悬空仓库名 / 悬空展示名 / 小微标记不一致 / 空项目"""
    conn = db.get_conn()
    try:
        res = {}
        for t in _REF_TABLES:
            res['orphan_' + t] = conn.execute(
                'SELECT COUNT(*) FROM %s WHERE project_id IS NOT NULL AND project_id NOT IN (SELECT id FROM projects)' % _safe_table(t)).fetchone()[0]
        res['orphan_mtrl'] = conn.execute(
            "SELECT COUNT(*) FROM mtrl_extract WHERE wh NOT IN (SELECT name FROM projects) "
            "AND wh NOT IN (SELECT full_name FROM projects WHERE full_name <> '')").fetchone()[0]
        res['orphan_stat'] = conn.execute(
            "SELECT COUNT(*) FROM pay_notice WHERE stat_name IS NOT NULL AND stat_name <> '' "
            "AND stat_name NOT IN (SELECT name FROM projects) "
            "AND stat_name NOT IN (SELECT display_name FROM projects WHERE display_name <> '')").fetchone()[0]
        # 小微标记不一致：name 在 small_map 的 value keys 里（具体小微）却 is_small != 是
        small_map = db.get_config('small_map', {})
        small_names = set()
        for sms in small_map.values():
            if isinstance(sms, dict):
                small_names.update(sms.keys())
        bad_small = [r['name'] for r in conn.execute("SELECT name FROM projects WHERE is_small<>'是'") if r['name'] in small_names]
        res['small_mark_mismatch'] = bad_small
        # 空项目
        empty = []
        for r in conn.execute('SELECT * FROM projects'):
            if _child_ref_counts(conn, r['id']) == 0 and not (r['phid'] or ''):
                empty.append({'id': r['id'], 'name': r['name']})
        res['empty_projects'] = empty
        return _ok(res)
    finally:
        conn.close()


@api.post('/api/projects/sync_warehouse')
@login_required
def projects_sync_warehouse():
    """刷新仓库列表缓存 + 建/校正 projects（name=仓库名、full_name=全名）"""
    import warehouse_sync
    try:
        r = warehouse_sync.sync_warehouse()
        return _ok(r)
    except Exception as e:
        return _err('同步仓库列表失败：%s' % e)
