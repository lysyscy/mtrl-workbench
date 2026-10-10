# -*- coding: utf-8 -*-
"""
一键导出执行器：读任务文件 -> 逐月跑 playwright 导出 -> 入库 -> 出成品zip -> 删原始文件 -> 标记完成
由 Flask 后台线程调用（浏览器自动化弹窗在用户桌面可见）。
"""
import json
import os
import subprocess
import sys
import time

# 模块顶部 reconfigure：worker 进程 import 此模块后 stdout/stderr 走 UTF-8 + 容错，
# 修复 ✓ 等 GBK 无法编码字符（fix UnicodeEncodeError at sfjc_process.py:322）
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

import db
import importer
import datacheck

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 项目根
INPUT = os.path.join(BASE, 'input')
OUTPUT = os.path.join(BASE, 'output')
TASK_FILE = os.path.join(BASE, 'var', 'state', 'export_task.json')
LOCK_FILE = os.path.join(BASE, 'var', 'state', 'export.lock')   # 两人共用：导出互斥锁
LOCK_STALE = 900                                              # 秒；无心跳超过此值视为死锁可接管
EXPORT_PW_SFJC = os.path.join(INPUT, 'sfjc_export_http.py')
EXPORT_PW_KCDJ = os.path.join(INPUT, 'kcdj_export_http.py')

# 月份范围工具
def _ym_list(sy, sm, ey, em):
    out = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        out.append((y, m))
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def _read_task():
    try:
        with open(TASK_FILE, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _write_task(task):
    os.makedirs(os.path.dirname(TASK_FILE), exist_ok=True)
    with open(TASK_FILE, 'w', encoding='utf-8') as f:
        json.dump(task, f, ensure_ascii=False, indent=2)


def _run_export(sy, sm, ey, em, task_type='sfjc', user=None, password=None):
    """跑导出脚本（HTTP 导出，无浏览器时为最快路径），返回原始导出路径；日志落盘便于排查"""
    log_dir = os.path.join(BASE, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, 'export_run.log')
    script = EXPORT_PW_KCDJ if task_type == 'kcdj' else EXPORT_PW_SFJC
    cmd = [sys.executable, script, str(sy), str(sm), str(ey), str(em)]
    # 账号绑定（阶段二）：传 i8 账号/密码，cookie 按账号分文件
    if user:
        cmd += ['--user', user]
    if password:
        cmd += ['--password', password]
    # 数据库有项目ID（phid）时直接传 --pc/--xmid，跳过浏览器选项目环节
    try:
        conn = db.get_conn()
        try:
            ids = [r['phid'] for r in conn.execute(
                "SELECT phid FROM projects WHERE phid != '' ORDER BY sort_order, id")]
        finally:
            conn.close()
        if ids:
            cmd += (['--xmid', ','.join(ids)] if task_type == 'kcdj'
                    else ['--pc', ','.join(ids)])
    except Exception:
        pass
    try:
        # CREATE_NEW_CONSOLE+SW_HIDE：无控制台父进程下 Edge 下载会异常退出，需独立隐藏控制台
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding='utf-8', errors='replace', startupinfo=si,
                             creationflags=subprocess.CREATE_NEW_CONSOLE)
        lines = []
        for line in p.stdout:
            lines.append(line)
            _export_progress(line)
        try:
            p.wait(timeout=600)
        except subprocess.TimeoutExpired:
            p.kill()
            raise RuntimeError('导出超时（600秒），详见 %s' % log_file)
    except subprocess.TimeoutExpired:
        raise RuntimeError('导出超时（600秒），详见 %s' % log_file)
    stdout = ''.join(lines)
    # 日志轮转：超过 500KB 清空重写，防止无限增长
    try:
        if os.path.exists(log_file) and os.path.getsize(log_file) > 500 * 1024:
            os.remove(log_file)
    except OSError:
        pass
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write('\n===== %s =====\n' % time.strftime('%Y-%m-%d %H:%M:%S'))
        f.write(stdout)
    if p.returncode != 0:
        raise RuntimeError('导出失败，详见 %s' % log_file)
    for line in stdout.splitlines():
        if line.startswith('RESULT_PATH='):
            return line[len('RESULT_PATH='):].strip()
    raise RuntimeError('导出未返回文件路径，详见 %s' % log_file)


def _export_progress(line):
    """按导出脚本输出行更新任务进度（真实进度感；子进程在跑时逐行推进）"""
    task = _read_task()
    if not task or task.get('status') != 'running':
        return
    if '使用数据库项目ID' in line or '使用缓存项目列表' in line or '无缓存项目列表' in line:
        _set_progress(task, 15, '正在请求信息化数据…')
    elif '正在请求信息化导出' in line:
        _set_progress(task, 30, '正在导出数据…')
    elif '导出完成' in line:
        _set_progress(task, 45, '导出完成，正在处理')
    elif 'RESULT_PATH=' in line:
        _set_progress(task, 50, '导出文件已获取')


def _process_sfjc(src, y, m):
    """入库 + 出成品zip，返回 (入库行数, zip路径)"""
    month = '%04d-%02d' % (y, m)
    stat = importer.import_sfjc(src, month)
    label = '%d年%d月' % (y, m)
    out_dir = os.path.join(OUTPUT, '收发结存', label)
    os.makedirs(out_dir, exist_ok=True)
    sys.path.insert(0, INPUT)
    import sfjc_process
    sfjc_process.main(src, out_dir, label)
    zip_fn = os.path.join(out_dir, '第四工程公司%s收发结存表.zip' % label)
    return stat, zip_fn


def _extract_sfjc(src, y, m, export_excel):
    """焊材/气体提取：总是入库 mtrl_extract；export_excel=True 时另出 xlsx。返回统计"""
    sys.path.insert(0, INPUT)
    import sfjc_extract
    r = sfjc_extract.extract_data(
        src,
        # 不传兜底值：缺键时由 db.get_config 回退 DEFAULT_CONFIG（配置唯一真源）
        gas_list=db.get_config('gas_list'),
        weld_kw=db.get_config('weld_keywords'),
        not_weld=db.get_config('not_weld'),
    )
    month = '%04d-%02d' % (y, m)
    conn = db.get_conn()
    try:
        for cat in ('气体', '焊材'):
            for wh, amt in r[cat].items():
                conn.execute('INSERT INTO mtrl_extract(month, cat, wh, amount) VALUES(?,?,?,?) '
                             'ON CONFLICT(month, cat, wh) DO UPDATE SET amount=excluded.amount',
                             (month, cat, wh, amt))
        conn.commit()
    finally:
        conn.close()
    out = _write_extract_excel(r, y, m) if export_excel else None
    return {'气体仓': len(r['气体']), '焊材仓': len(r['焊材']), 'xlsx': out}


def _write_extract_excel(r, y, m):
    """焊材/气体按仓库汇总 xlsx（行=仓库+合计）"""
    import xlsxwriter
    label = '%d年%d月' % (y, m)
    out_dir = os.path.join(OUTPUT, '收发结存', label)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, '焊材气体_%s.xlsx' % label)
    wb = xlsxwriter.Workbook(out)
    head_fmt = wb.add_format({'bold': True, 'bg_color': '#ED7D31', 'border': 1, 'align': 'center'})
    wh_fmt = wb.add_format({'border': 1, 'valign': 'vcenter'})
    num_fmt = wb.add_format({'border': 1, 'num_format': '#,##0.00', 'align': 'right'})
    tot_fmt = wb.add_format({'border': 1, 'bold': True, 'num_format': '#,##0.00', 'align': 'right'})
    for cat in ('气体', '焊材'):
        ws = wb.add_worksheet(cat)
        ws.write(0, 0, '仓库', head_fmt)
        ws.write(0, 1, '入库金额', head_fmt)
        ws.set_column(0, 0, 42)
        ws.set_column(1, 1, 16)
        rows = sorted(r[cat].items())
        for i, (wh, amt) in enumerate(rows, start=1):
            ws.write(i, 0, wh, wh_fmt)
            ws.write_number(i, 1, amt, num_fmt)
        ws.write(len(rows) + 1, 0, '合计', wh_fmt)
        ws.write_number(len(rows) + 1, 1, sum(r[cat].values()), tot_fmt)
    wb.close()
    return out


def _verify_month(y, m):
    """当月有基准时自动回归对账；无基准(rc=2)/异常时跳过不阻断。返回 (ok, msg)"""
    try:
        sys.path.insert(0, os.path.join(BASE, 'scripts', 'regression'))
        import verify_sfjc
        rc = verify_sfjc.check(y, m)
        if rc == 0:
            return True, '对账通过'
        if rc == 2:  # 无基准文件：首次月份，跳过
            return True, ''
        return False, '对账不一致，见控制台'
    except Exception:
        return True, ''


# ---------- 导出互斥锁（两人共用：防止两台电脑同时导出互相覆盖任务文件） ----------
def acquire_lock():
    """原子创建锁文件（O_CREAT|O_EXCL）。成功返回 (锁文件路径, None)；
    已被占用且未过期返回 (None, 持有者信息)；过期（死锁）则接管重试。"""
    os.makedirs(os.path.dirname(LOCK_FILE), exist_ok=True)
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            with open(LOCK_FILE, encoding='utf-8') as f:
                info = json.load(f)
            if time.time() - info.get('ts', 0) < LOCK_STALE:
                return None, info
        except Exception:
            info = {}
        try:
            os.remove(LOCK_FILE)     # 死锁接管
        except OSError:
            return None, info
        return acquire_lock()
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump({'pid': os.getpid(), 'host': os.environ.get('COMPUTERNAME', '?'),
                   'ts': time.time(), 'at': time.strftime('%Y-%m-%d %H:%M:%S')}, f)
    return LOCK_FILE, None


def release_lock():
    try:
        os.remove(LOCK_FILE)
    except OSError:
        pass


def lock_status():
    """返回当前有效锁的持有者信息（无锁/过期返回 None）"""
    try:
        with open(LOCK_FILE, encoding='utf-8') as f:
            info = json.load(f)
        if time.time() - info.get('ts', 0) < LOCK_STALE:
            return info
    except Exception:
        pass
    return None


def heartbeat_lock():
    """长任务推进时刷新锁心跳（防被误判死锁后遭他人接管）"""
    try:
        with open(LOCK_FILE, encoding='utf-8') as f:
            info = json.load(f)
        info['ts'] = time.time()
        with open(LOCK_FILE, 'w', encoding='utf-8') as f:
            json.dump(info, f)
    except Exception:
        pass


def _missing_project_ids():
    """在建项目中缺信息化ID(phid)的清单。
    导出是按 phid 传参的，缺 ID 的项目会**静默漏数**（不报错、不告警），
    2026-09-08 实测 18 个项目中 6 个缺 ID，故导出前必须提示。"""
    conn = db.get_conn()
    try:
        return [r['name'] for r in conn.execute(
            "SELECT name FROM projects WHERE status='在建' "
            "AND (phid IS NULL OR phid='') ORDER BY sort_order, id")]
    finally:
        conn.close()


def _set_progress(task, pct, msg):
    """更新任务进度并落盘（前端轮询显示进度条）；同时刷新导出锁心跳"""
    task['progress'] = {'pct': pct, 'msg': msg}
    _write_task(task)
    heartbeat_lock()


def run_once():
    """执行一次任务；成功返回结果dict，失败抛异常"""
    task = _read_task()
    if not task:
        raise RuntimeError('没有待执行的任务')
    options = task.get('options') or {}   # 收发结存：pack=出资产处zip, extract=出焊材气体xlsx；默认都开
    user = task.get('user') or ''          # 账号绑定：任务创建时写入的 i8 账号
    password = task.get('password') or ''
    total = {'zip': [], 'months': 0, 'rows': 0, 'verify': [], 'extract': [], 'check': [], 'warn': []}
    miss = _missing_project_ids()
    if miss:
        total['warn'].append('⚠ 缺信息化ID %d 个（导出不含这些项目）：%s'
                             % (len(miss), '、'.join(miss[:8]) + ('…' if len(miss) > 8 else '')))
    for y, m in _ym_list(task['sy'], task['sm'], task['ey'], task['em']):
        _set_progress(task, 5, '正在从信息化导出数据…')
        src = _run_export(y, m, y, m, task.get('type', 'sfjc'), user=user, password=password)
        try:
            if task.get('type') == 'kcdj':
                _set_progress(task, 55, '导出完成，正在入库')
                from importer import import_kcdj
                stat = import_kcdj(src, '%04d-%02d' % (y, m))
                _set_progress(task, 70, '入库完成，正在生成成品')
                label = '%d年%d月' % (y, m)
                out_dir = os.path.join(OUTPUT, '库存单据明细表', label)
                sys.path.insert(0, INPUT)
                import kcdj_process
                out = kcdj_process.main(src, out_dir)
                total['zip'].append(out)
            else:
                # 收发结存：先打包（sfjc_process 会清空输出目录，须在提取前），再提取焊材/气体入库
                if options.get('pack', True):
                    _set_progress(task, 55, '导出完成，正在处理打包')
                    stat, zip_fn = _process_sfjc(src, y, m)
                    total['zip'].append(zip_fn)
                    ok, msg = _verify_month(y, m)
                    if msg:
                        total['verify'].append('%d年%d月%s' % (y, m, msg))
                    # 数据体检（只报告不阻断）：无验收基准的月份也必须有防线
                    for c in datacheck.check_sfjc('%04d-%02d' % (y, m)):
                        total['check'].append('%d年%d月[%s] %s' % (y, m, c['level'], c['msg']))
                else:
                    stat = {'rows': 0}
                _set_progress(task, 75, '打包完成，正在提取焊材/气体')
                ex = _extract_sfjc(src, y, m, export_excel=options.get('extract', True))
                total['extract'].append('%d年%d月 气体%d仓/焊材%d仓' % (y, m, ex['气体仓'], ex['焊材仓']))
                if ex['xlsx']:
                    total['zip'].append(ex['xlsx'])
            total['months'] += 1
            total['rows'] += stat.get('rows', 0)
            _set_progress(task, 95, '正在写入完成结果')
        finally:
            try:
                os.remove(src)  # 原始导出用完即删
            except OSError:
                pass
    task['status'] = 'done'
    task['finished'] = time.strftime('%Y-%m-%d %H:%M:%S')
    task['result'] = '完成 %d 个月，入库 %d 行，%s%s%s%s%s' % (
        total['months'], total['rows'],
        ('；'.join(total['extract']) + '；' if total['extract'] else ''),
        ('；'.join(total['zip']) + '；' if total['zip'] else ''),
        ('；'.join(total['warn']) + '；' if total['warn'] else ''),
        ('；'.join(total['check']) + '；' if total['check'] else ''),
        '；'.join(total['verify']))
    _set_progress(task, 100, '完成')
    return task
