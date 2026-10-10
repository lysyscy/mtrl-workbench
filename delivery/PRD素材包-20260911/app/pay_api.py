# -*- coding: utf-8 -*-
"""
付款域 API 蓝图（从 api.py 拆分，见《架构说明.md》§四）。

拆分原则：**端点路径、请求/响应结构一律不变**，只是换一个 Blueprint 承载，
因此前端与回归脚本无需任何改动。注册见 server.py：api / pay_api 两个蓝图并列注册，均无 url_prefix。
"""
import os
import sys
import time

from flask import Blueprint, request, session

import db
import importer
import pay_service
from api import _err, _ok          # 响应包装复用 api.py，保持返回结构一致
from auth import login_required
from rules import BIZ_ORDER, is_valid_biz_class  # S7-2：规则下沉

pay_api = Blueprint('pay_api', __name__)


# ================= 付款通知书 =================
@pay_api.get('/api/pay/notices')
@login_required
def pay_notices():
    from common_time import parse_range_or_month
    conn = db.get_conn()
    try:
        where, args = [], []
        v = request.args.get('biz_class')
        if v:
            where.append('biz_class=?')
            args.append(v)
        stat = request.args.get('stat_name')
        if stat:
            where.append('stat_name=?')
            args.append(stat)
        # 时间筛选：start_date/end_date 或 month（归约到起止日期，核算期=自然月）
        sd, ed = parse_range_or_month(request.args)
        if sd and ed:
            where.append('单据日期 >= ? AND 单据日期 <= ?')
            args += [sd, ed]
        status = request.args.get('status')
        if status in ('在建', '完工'):
            where.append("COALESCE(stat_name,'') IN (SELECT name FROM projects WHERE status=?)")
            args.append(status)
        sql = 'SELECT * FROM pay_notice WHERE deleted=0'
        if where:
            sql += ' AND ' + ' AND '.join(where)
        # 浏览排序：规则下沉到 rules.BIZ_ORDER（待确认最前→机械→辅材→剔除→其他，同分类按日期倒序）
        sql += BIZ_ORDER + ' LIMIT 2000'
        # 派生字段：已付款金额 / 剩余未付 / 付款状态（供 Tab1 与 Tab2 共用）
        rows = [pay_service.notice_view(conn, r) for r in conn.execute(sql, args)]
        # 付款状态筛选（派生字段，无法进 SQL WHERE，取完再过滤）
        pay_st = request.args.get('pay_status')
        if pay_st:
            rows = [r for r in rows if r['付款状态'] == pay_st]
        return _ok(rows)
    finally:
        conn.close()


@pay_api.get('/api/pay/notices/facets')
@login_required
def pay_notices_facets():
    """筛选面（distinct 月份/项目/分类），供前端下拉置灰联动。
    关键：每个维度的可选值用「其他维度」过滤、排除「自己」——否则选了一个项目后，
    项目维度的可选值会被 stat_name=? 过滤到只剩这一个，其余全被误置灰。"""
    conn = db.get_conn()
    try:
        from common_time import parse_range_or_month
        sd, ed = parse_range_or_month(request.args)
        cls = request.args.get('biz_class')
        proj = request.args.get('stat_name')
        status = request.args.get('status')

        def _base(exclude):
            """exclude: 'month'/'proj'/'cls'，该维度自身不参与自己的过滤"""
            where = ['deleted=0']
            args = []
            if sd and ed and exclude != 'month':
                where.append('单据日期 >= ? AND 单据日期 <= ?'); args += [sd, ed]
            if cls and exclude != 'cls':
                where.append('biz_class=?'); args.append(cls)
            if proj and exclude != 'proj':
                where.append('stat_name=?'); args.append(proj)
            if status in ('在建', '完工'):
                where.append("COALESCE(stat_name,'') IN (SELECT name FROM projects WHERE status=?)")
                args.append(status)
            return ' FROM pay_notice WHERE ' + ' AND '.join(where), args

        _col_expr = {'month': "substr(单据日期,1,7)", 'proj': "stat_name", 'cls': "biz_class"}

        def distinct(kind, exclude):
            col = _col_expr[kind]   # 列名来自白名单映射，杜绝自由字符串拼进 SQL 标识符
            base, args = _base(exclude)
            return [r[0] for r in conn.execute('SELECT DISTINCT %s%s ORDER BY %s' % (col, base, col), args) if r[0]]

        return _ok({
            'months': distinct('month', 'month'),
            'projects': distinct('proj', 'proj'),
            'classes': distinct('cls', 'cls'),
        })
    finally:
        conn.close()


@pay_api.post('/api/pay_notice/export')
@login_required
def pay_notice_export():
    """按起止日期（核算期=自然月）从信息化抓付款通知书并入库（同步：getList → 组装 xlsx → import_pay_notice）。
    入参优先 start_date/end_date（'YYYY-MM-DD' 闭区间），兼容旧 sy/sm/ey/em 数字（见 common_time.export_range）。
    cookie 过期时 login_cookie 会尝试浏览器登录，NSSM 服务 Session 0 下可能失败——
    失败提示用户在桌面环境刷新 cookie。"""
    from common_time import export_range
    body = request.get_json(force=True) or {}
    start_date, end_date = export_range(body)
    if not start_date or not end_date:
        return _err('参数错误：需要 start_date/end_date（或旧 sy/sm 年月）')
    _inp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'input')
    if _inp not in sys.path:
        sys.path.insert(0, _inp)
    import pay_notice_export_http as peh
    # 账号绑定（阶段二）：查当前登录人绑定的 i8 账号/密码
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
    try:
        out = peh.export(start_date=start_date, end_date=end_date, user=user, password=password)
    except Exception as e:
        return _err('抓取失败：%s（cookie 可能过期，请在桌面环境刷新）' % e)
    if not out:
        return _err('当月无付款通知书数据，或 cookie 已过期')
    month = start_date[:7]   # 'YYYY-MM'
    result = importer.import_pay_notice(out, source_month=month)
    return _ok(result)


@pay_api.post('/api/pay/notice/confirm')
@login_required
def pay_confirm():
    body = request.get_json(force=True)
    nid = body.get('id')
    cls = body.get('biz_class')
    expect = body.get('expect_ts')   # 乐观锁：前端提交时带上它"看到"的 updated_at（可选）
    by = body.get('by') or session.get('display_name') or session.get('user') or ''  # 操作人留痕
    if not nid or not is_valid_biz_class(cls):
        return _err('参数错误：需要 id 和 biz_class(辅材/机械/剔除/忽略)')
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    conn = db.get_conn()
    try:
        row = conn.execute('SELECT 单据编码, updated_at FROM pay_notice WHERE id=?', (nid,)).fetchone()
        if row is None:
            return _err('单据不存在', 404)
        # 两人共用：所见版本 ≠ 库内版本 → 有人刚改过，拒绝写入（前端提示刷新）
        if expect is not None and (row['updated_at'] or '') != expect:
            return _err('该单据刚被修改（%s），请刷新后重试' % (row['updated_at'] or '未知时间'))
        # 只改分类并标记人工调整（重导时保留）；统计名/项目不传就不动，避免误清空
        conn.execute('UPDATE pay_notice SET biz_class=?, manual=1, updated_at=?, updated_by=? WHERE id=?',
                     (cls, now, by, nid))
        conn.commit()
        return _ok({'id': nid, 'biz_class': cls, 'updated_at': now})
    finally:
        conn.close()


@pay_api.post('/api/pay/notice/batch_confirm')
@login_required
def pay_batch_confirm():
    body = request.get_json(force=True)
    ids = body.get('ids') or []
    cls = body.get('biz_class')
    ids = [int(i) for i in ids if str(i).isdigit()]
    if not ids or not is_valid_biz_class(cls):
        return _err('参数错误：需要 ids 和 biz_class(辅材/机械/剔除/忽略)')
    conn = db.get_conn()
    try:
        # 批量不做逐行 CAS（勾选集来自加载时刻，逐行比对会大量误报）；
        # 只写留痕，单行冲突由单行按钮的乐观锁兜底
        now = time.strftime('%Y-%m-%d %H:%M:%S')
        conn.executemany('UPDATE pay_notice SET biz_class=?, manual=1, updated_at=?, updated_by=? WHERE id=?',
                         [(cls, now, body.get('by') or session.get('display_name') or session.get('user') or '', i) for i in ids])
        conn.commit()
        return _ok({'updated': len(ids)})
    finally:
        conn.close()


@pay_api.post('/api/pay/notice/remove')
@login_required
def pay_remove():
    """二次导入时确认信息化上已删除的单据：标记删除（列表/欠款均排除，可追溯）"""
    body = request.get_json(force=True)
    ids = body.get('ids') or []
    ids = [int(i) for i in ids if str(i).isdigit()]
    if not ids:
        return _err('参数错误：需要 ids')
    conn = db.get_conn()
    try:
        conn.executemany('UPDATE pay_notice SET deleted=1 WHERE id=?', [(i,) for i in ids])
        conn.commit()
        return _ok({'deleted': len(ids)})
    finally:
        conn.close()


# ================= 付款（记一笔 / 撤销 / 统计口径） =================
@pay_api.post('/api/pay/pay')
@login_required
def pay_do():
    """记一笔付款。入参：notice_id, amount, pay_way, pay_way_note, pay_date, allow_over, note, request_id"""
    body = request.get_json(force=True) or {}
    nid = body.get('notice_id')
    if not nid:
        return _err('参数错误：需要 notice_id')
    way_in = (body.get('pay_way') or '').strip()
    std, matched = pay_service.match_pay_way(way_in)
    if not matched:
        # 匹配不上 → 归"其他"，并回传提示前端让用户手填具体方式
        std = '其他'
    conn = db.get_conn()
    try:
        r = pay_service.pay(conn, int(nid), body.get('amount'), pay_way=std,
                            pay_way_note=(body.get('pay_way_note') or '').strip(),
                            pay_date=(body.get('pay_date') or '').strip() or None,
                            operator=(session.get('display_name') or session.get('user') or ''),
                            request_id=(body.get('request_id') or '').strip(),
                            allow_over=bool(body.get('allow_over')),
                            note=(body.get('note') or '').strip())
        r['pay_way_matched'] = matched
        r['pay_way'] = std
        if not matched:
            r['warning'] = (r.get('warning') or '') + ' 付款方式未匹配，已归为「其他」，请填写具体付款方式。'
        return _ok(r)
    except pay_service.PayError as e:
        return _err(e.msg)
    finally:
        conn.close()


@pay_api.post('/api/pay/void')
@login_required
def pay_void():
    """撤销一笔付款（软删除 + 留痕）。入参：flow_id, reason"""
    body = request.get_json(force=True) or {}
    fid = body.get('flow_id')
    if not fid:
        return _err('参数错误：需要 flow_id')
    conn = db.get_conn()
    try:
        return _ok(pay_service.void_flow(conn, int(fid),
                                         operator=(session.get('display_name') or session.get('user') or ''),
                                         reason=(body.get('reason') or '').strip()))
    except pay_service.PayError as e:
        return _err(e.msg)
    finally:
        conn.close()


@pay_api.post('/api/pay/notice/count')
@login_required
def pay_notice_count():
    """设置单据的「计入统计结算 / 计入统计付款」（NULL=跟随实际值）。传空字符串表示清空恢复跟随。"""
    body = request.get_json(force=True) or {}
    nid = body.get('notice_id')
    if not nid:
        return _err('参数错误：需要 notice_id')
    settle = body.get('计入统计结算')       # None 表示不改；'' 表示清空
    paid = body.get('计入统计付款')
    sets, args = [], []
    if settle is not None:
        sets.append('计入统计结算=?')
        args.append(None if settle == '' else float(settle))
    if paid is not None:
        sets.append('计入统计付款=?')
        args.append(None if paid == '' else float(paid))
    if not sets:
        return _err('没有要更新的字段')
    args.append(int(nid))
    conn = db.get_conn()
    try:
        conn.execute('UPDATE pay_notice SET ' + ', '.join(sets) + ' WHERE id=?', args)
        conn.commit()
        row = conn.execute('SELECT * FROM pay_notice WHERE id=?', (int(nid),)).fetchone()
        return _ok(pay_service.notice_view(conn, row) if row else {})
    finally:
        conn.close()


@pay_api.get('/api/pay/flows')
@login_required
def pay_flows():
    """付款流水查询（**按实际付款日期 pay_date**，支持 start/end 自由范围）。
    注：与欠款台账的"单据日期归月"是两套口径，此处只按 pay_date。"""
    start = (request.args.get('start') or '').strip()
    end = (request.args.get('end') or '').strip()
    where, args = ['pf.voided=0'], []
    if start:
        where.append('pf.pay_date>=?'); args.append(start)
    if end:
        where.append('pf.pay_date<=?'); args.append(end)
    sql = ('SELECT pf.*, pn.stat_name AS 项目, pn.单据日期, pn.单据名称, pn.审批金额 '
           'FROM pay_flow pf LEFT JOIN pay_notice pn ON pn.id=pf.notice_id WHERE '
           + ' AND '.join(where) + ' ORDER BY pf.pay_date DESC, pf.id DESC LIMIT 2000')
    conn = db.get_conn()
    try:
        return _ok([dict(r) for r in conn.execute(sql, args)])
    finally:
        conn.close()


@pay_api.get('/api/pay/stats')
@login_required
def pay_stats():
    """付款统计（**按实际付款日期 pay_date**，与欠款台账的单据日期口径分开）。
    dim: day / week(自然周,周一起) / month / year / range（不分组）
    入参: start, end, dim, group(way=按付款方式分组 / project=按项目分组)
    """
    dim = request.args.get('dim') or 'month'
    grp = request.args.get('group') or 'way'
    start = (request.args.get('start') or '').strip()
    end = (request.args.get('end') or '').strip()
    # expr/gcol 均为内部硬编码 SQL 片段：dim 仅作 dict 键查找（缺省回落固定值），grp 仅作等值判断，
    # 二者都不直接拼接用户输入，故下方 % (expr, gcol) 无注入风险。
    expr = {
        'day': "substr(pf.pay_date,1,10)",
        # 自然周（周一为起点）：%w 周日=0，故 (w+6)%7 得到距周一的天数
        'week': "date(pf.pay_date, '-' || ((CAST(strftime('%w', pf.pay_date) AS INTEGER)+6)%7) || ' days')",
        'month': "substr(pf.pay_date,1,7)",
        'year': "substr(pf.pay_date,1,4)",
        'range': "'全部'",
    }.get(dim, "substr(pf.pay_date,1,7)")
    gcol = 'pf.pay_way' if grp == 'way' else 'COALESCE(pn.stat_name, "(无项目)")'
    where, args = ['pf.voided=0'], []
    if start:
        where.append('pf.pay_date>=?'); args.append(start)
    if end:
        where.append('pf.pay_date<=?'); args.append(end)
    sql = ('SELECT %s AS period, %s AS grp, COUNT(*) AS cnt, '
           'COALESCE(SUM(pf.pay_amount),0) AS amount '
           'FROM pay_flow pf LEFT JOIN pay_notice pn ON pn.id=pf.notice_id WHERE '
           + ' AND '.join(where) + ' GROUP BY period, grp ORDER BY period DESC') % (expr, gcol)
    conn = db.get_conn()
    try:
        rows = [dict(r) for r in conn.execute(sql, args)]
        return _ok({'rows': rows, 'dim': dim, 'group': grp,
                    'total': round(sum((r['amount'] or 0) for r in rows), 2),
                    'count': sum((r['cnt'] or 0) for r in rows)})
    finally:
        conn.close()


@pay_api.get('/api/pay/export')
@login_required
def pay_export():
    """导出付款流水为 xlsx（按 pay_date 过滤，排除已撤销）。"""
    import io as _io
    import openpyxl as _oxl
    from flask import send_file
    start = (request.args.get('start') or '').strip()
    end = (request.args.get('end') or '').strip()
    where, args = ['pf.voided=0'], []
    if start:
        where.append('pf.pay_date>=?'); args.append(start)
    if end:
        where.append('pf.pay_date<=?'); args.append(end)
    sql = ('SELECT pf.pay_date, pf.单据编码, pf.pay_amount, pf.pay_way, pf.pay_way_note, '
           'pf.note, pn.stat_name AS 项目, pn.单据日期, pn.单据名称, pn.审批金额 '
           'FROM pay_flow pf LEFT JOIN pay_notice pn ON pn.id=pf.notice_id WHERE '
           + ' AND '.join(where) + ' ORDER BY pf.pay_date, pf.id')
    conn = db.get_conn()
    try:
        rows = conn.execute(sql, args).fetchall()
    finally:
        conn.close()
    wb = _oxl.Workbook()
    ws = wb.active
    ws.title = '付款流水'
    ws.append(['付款日期', '单据编码', '付款金额', '付款方式', '具体方式',
               '项目', '单据日期', '单据名称', '审批金额', '备注'])
    for r in rows:
        ws.append([r['pay_date'], r['单据编码'], r['pay_amount'], r['pay_way'],
                   r['pay_way_note'], r['项目'], r['单据日期'], r['单据名称'],
                   r['审批金额'], r['note']])
    buf = _io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return send_file(buf, as_attachment=True,
                     download_name='付款流水_%s_%s.xlsx' % (start or '全部', end or '全部'),
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@pay_api.get('/api/pay/plan/pick')
@login_required
def pay_plan_pick():
    """按付款计划生成**勾选建议**（只勾选、不付款，真正付款走 /api/pay/pay）。
    入参: start_date/end_date 或 month（计划月份，归约到起止日期）, project（项目名，可选）
    返回 picks: [{notice_id, 单据编码, 计划金额, 审批金额, diff, 审批状态}]
      - diff != 0 → 计划金额与单据审批金额不符，前端标黄提醒（可能是多单合并报计划）
      - 单据在库里找不到 → 进 missing 列表
    """
    from common_time import parse_range_or_month
    sd, _ed = parse_range_or_month(request.args)
    month = sd[:7] if sd else ''
    proj = (request.args.get('project') or '').strip()
    if not month:
        return _err('需要 start_date/end_date 或 month')
    conn = db.get_conn()
    try:
        sql = ('SELECT 单据号, 预付款金额, 流程金额 FROM pay_plan '
               'WHERE month=? AND 预付款金额 IS NOT NULL AND 预付款金额>0')
        args = [month]
        if proj:
            pid = conn.execute('SELECT id FROM projects WHERE name=?', (proj,)).fetchone()
            if pid:
                sql += ' AND project_id=?'
                args.append(pid['id'])
        picks, missing = [], []
        for p in conn.execute(sql, args).fetchall():
            code = (p['单据号'] or '').strip()
            if not code:
                continue
            n = conn.execute(
                'SELECT id, 单据编码, 审批金额, 审批状态 FROM pay_notice '
                'WHERE 单据编码=? AND deleted=0', (code,)).fetchone()
            if not n:
                missing.append(code)
                continue
            amt = float(p['预付款金额'] or 0)
            appr = float(n['审批金额'] or 0)
            picks.append({'notice_id': n['id'], '单据编码': code,
                          '计划金额': round(amt, 2), '审批金额': round(appr, 2),
                          'diff': round(amt - appr, 2), '审批状态': n['审批状态']})
        return _ok({'picks': picks, 'missing': missing})
    finally:
        conn.close()


# ================= 欠款 =================
@pay_api.get('/api/debt')
@login_required
def debt():
    conn = db.get_conn()
    try:
        from common_time import parse_range_or_month
        cls = request.args.get('cls')
        sd, _ed = parse_range_or_month(request.args)
        month = sd[:7] if sd else None
        sql = 'SELECT * FROM v_debt'
        where, args = [], []
        if cls:
            where.append('cls=?')
            args.append(cls)
        if month:
            where.append('month=?')
            args.append(month)
        if where:
            sql += ' WHERE ' + ' AND '.join(where)
        sql += ' ORDER BY month DESC, project'
        rows = [dict(r) for r in conn.execute(sql, args)]
        total = sum((r['debt'] or 0) for r in rows)
        # 期初占位行（25.11 及之前旧信息化）：只在不筛选时计入总账。
        # 口径：账 = 期初欠款 + 25.12 起各月欠款（期初欠款 = Σ期初结算 − Σ期初付款）。
        # 有 month/cls 筛选时，期初不属于任何具体月/类别，故不计入，避免污染小计。
        initial = None
        if not cls and not month:
            ir = conn.execute(
                'SELECT COALESCE(SUM(期初结算),0) AS s, COALESCE(SUM(期初付款),0) AS p '
                'FROM debt_initial').fetchone()
            isettle = round(float(ir['s'] or 0), 2)
            ipay = round(float(ir['p'] or 0), 2)
            initial = {'settle': isettle, 'pay': ipay, 'debt': round(isettle - ipay, 2)}
            total = round((initial['debt']) + total, 2)
        return _ok({'rows': rows, 'total_debt': total, 'initial': initial})
    finally:
        conn.close()


# ================= 机械费月结算（手动录入优先，未录入按通知书） =================
@pay_api.get('/api/mach/settle')
@login_required
def mach_settle_get():
    """机械费月结算表（项目×月）：最终结算 = 手动录入（有则用）否则通知书机械类审批金额。
    返回 rows: [{project, 自动结算, 手动结算, 结算金额, 机械付款, 机械欠款, is_manual, note, operator}]"""
    from common_time import parse_range_or_month
    sd, ed = parse_range_or_month(request.args)
    month = sd[:7] if sd else ''
    conn = db.get_conn()
    try:
        where = ['pn.biz_class=? AND pn.deleted=0']
        args = ['机械']
        if sd and ed:
            where.append('pn.单据日期 >= ? AND pn.单据日期 <= ?')
            args += [sd, ed]
        # 自动结算（按项目，含单据级"计入统计结算"覆盖）
        auto = {}
        for r in conn.execute(
                'SELECT COALESCE(NULLIF(pn.stat_name,""),"(无项目)") AS project, '
                'SUM(COALESCE(pn.计入统计结算, pn.审批金额)) AS amount '
                'FROM pay_notice pn WHERE ' + ' AND '.join(where) + ' GROUP BY project', args):
            auto[r['project']] = float(r['amount'] or 0)
        # 机械付款（按项目，有效流水）
        pay = {}
        for r in conn.execute(
                'SELECT COALESCE(NULLIF(pn.stat_name,""),"(无项目)") AS project, '
                'SUM(pf.pay_amount) AS amount '
                'FROM pay_notice pn JOIN pay_flow pf ON pf.notice_id=pn.id '
                'WHERE pn.biz_class=? AND pn.deleted=0 AND pf.voided=0'
                + (' AND pn.单据日期 >= ? AND pn.单据日期 <= ?' if sd and ed else ''),
                ['机械'] + ([sd, ed] if sd and ed else [])):
            pay[r['project']] = float(r['amount'] or 0)
        # 手动覆盖
        manual = {}
        if month:
            for r in conn.execute(
                    'SELECT project, amount, note, operator, updated_at FROM mach_settle WHERE month=?',
                    (month,)):
                manual[r['project']] = r
        rows = []
        for p in sorted(set(auto) | set(pay) | set(manual)):
            a = auto.get(p, 0.0)
            m = manual.get(p)
            settle = float(m['amount']) if m else a
            rows.append({
                'project': p,
                '自动结算': round(a, 2),
                '手动结算': round(float(m['amount']), 2) if m else None,
                '结算金额': round(settle, 2),
                '机械付款': round(pay.get(p, 0.0), 2),
                '机械欠款': round(settle - pay.get(p, 0.0), 2),
                'is_manual': bool(m),
                'note': (m['note'] or '') if m else '',
                'operator': (m['operator'] or '') if m else '',
            })
        return _ok(rows)
    finally:
        conn.close()


@pay_api.post('/api/mach/settle')
@login_required
def mach_settle_post():
    """录入/覆盖机械费月结算金额：{project, month, amount, note}。amount 为空/0 → 视为清除恢复自动。"""
    body = request.get_json(force=True) or {}
    project = (body.get('project') or '').strip()
    month = (body.get('month') or '').strip()
    if not project or not month:
        return _err('需要 project 和 month')
    raw = body.get('amount')
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return mach_settle_clear()
    try:
        amt = float(raw)
    except (TypeError, ValueError):
        return _err('金额必须是数字')
    if amt < 0:
        return _err('金额不能为负')
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    op = session.get('display_name') or session.get('user') or ''
    note = (body.get('note') or '').strip()
    conn = db.get_conn()
    try:
        conn.execute(
            'INSERT INTO mach_settle(project, month, amount, note, operator, updated_at) '
            'VALUES(?,?,?,?,?,?) '
            'ON CONFLICT(project, month) DO UPDATE SET amount=excluded.amount, '
            'note=excluded.note, operator=excluded.operator, updated_at=excluded.updated_at',
            (project, month, amt, note, op, now))
        conn.commit()
        return _ok({'project': project, 'month': month, 'amount': amt})
    finally:
        conn.close()


@pay_api.post('/api/mach/settle/clear')
@login_required
def mach_settle_clear():
    """清除某项目某月的手动录入，恢复按付款通知书自动计算。"""
    body = request.get_json(force=True) or {}
    project = (body.get('project') or '').strip()
    month = (body.get('month') or '').strip()
    if not project or not month:
        return _err('需要 project 和 month')
    conn = db.get_conn()
    try:
        conn.execute('DELETE FROM mach_settle WHERE project=? AND month=?', (project, month))
        conn.commit()
        return _ok({'project': project, 'month': month})
    finally:
        conn.close()


# ================= 期初占位行（25.11 及之前旧信息化，一次性录入，可整笔冲减） =================
@pay_api.get('/api/debt/initial')
@login_required
def debt_initial_get():
    """期初占位行列表 + 合计。欠款 = 期初结算 − 期初付款；账 = 期初 + 25.12起结算 − 25.12起付款。"""
    conn = db.get_conn()
    try:
        rows = [dict(r) for r in conn.execute(
            'SELECT id, 项目, 期初结算, 期初付款, 备注, operator, updated_at '
            'FROM debt_initial ORDER BY 项目')]
        ts = round(sum((r['期初结算'] or 0) for r in rows), 2)
        tp = round(sum((r['期初付款'] or 0) for r in rows), 2)
        return _ok({'rows': rows, 'total_settle': ts, 'total_pay': tp,
                    'total_debt': round(ts - tp, 2)})
    finally:
        conn.close()


@pay_api.post('/api/debt/initial')
@login_required
def debt_initial_post():
    """录入/覆盖期初占位行 {project, 期初结算, 期初付款, 备注}（项目唯一 upsert）。
    后续付款冲减 = 改「期初付款」（或改结算），无金额即视为删除由 delete 承担。"""
    body = request.get_json(force=True) or {}
    project = (body.get('project') or '').strip()
    if not project:
        return _err('需要 project')
    try:
        settle = float(body.get('期初结算', 0) or 0)
        pay = float(body.get('期初付款', 0) or 0)
    except (TypeError, ValueError):
        return _err('期初结算/期初付款必须是数字')
    if settle < 0 or pay < 0:
        return _err('金额不能为负')
    note = (body.get('备注') or '').strip()
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    op = session.get('display_name') or session.get('user') or ''
    conn = db.get_conn()
    try:
        conn.execute(
            'INSERT INTO debt_initial(项目, 期初结算, 期初付款, 备注, operator, updated_at) '
            'VALUES(?,?,?,?,?,?) '
            'ON CONFLICT(项目) DO UPDATE SET 期初结算=excluded.期初结算, '
            '期初付款=excluded.期初付款, 备注=excluded.备注, '
            'operator=excluded.operator, updated_at=excluded.updated_at',
            (project, settle, pay, note, op, now))
        conn.commit()
        return _ok({'project': project, '期初结算': settle, '期初付款': pay})
    finally:
        conn.close()


@pay_api.post('/api/debt/initial/delete')
@login_required
def debt_initial_delete():
    """删除某项目期初占位行 {id 或 project}。"""
    body = request.get_json(force=True) or {}
    iid = body.get('id')
    project = (body.get('project') or '').strip()
    if not iid and not project:
        return _err('需要 id 或 project')
    conn = db.get_conn()
    try:
        if iid:
            cur = conn.execute('DELETE FROM debt_initial WHERE id=?', (int(iid),))
        else:
            cur = conn.execute('DELETE FROM debt_initial WHERE 项目=?', (project,))
        conn.commit()
        return _ok({'deleted': cur.rowcount})
    finally:
        conn.close()


# ================= 付款计划 =================
@pay_api.get('/api/pay/plans')
@login_required
def pay_plans():
    """付款计划列表。筛选项: start_date/end_date 或 month(计划月份) / project / match_status / q"""
    from common_time import parse_range_or_month
    conn = db.get_conn()
    try:
        sd, _ed = parse_range_or_month(request.args)
        month = sd[:7] if sd else None
        proj = request.args.get('project')
        st = request.args.get('match_status')
        q = (request.args.get('q') or '').strip()
        sql = ('SELECT pp.*, pj.name AS 项目名 FROM pay_plan pp '
               'LEFT JOIN projects pj ON pj.id = pp.project_id')
        where, args = [], []
        if month:
            where.append('pp.month=?'); args.append(month)
        if proj:
            where.append('pj.name=?'); args.append(proj)
        if st:
            where.append('pp.match_status=?'); args.append(st)
        if q:
            where.append('(pp.单据号 LIKE ? OR pp.供应商 LIKE ?)')
            args += ['%' + q + '%', '%' + q + '%']
        if where:
            sql += ' WHERE ' + ' AND '.join(where)
        sql += ' ORDER BY pp.id DESC LIMIT 1000'
        rows = [dict(r) for r in conn.execute(sql, args)]
        return _ok(rows)
    finally:
        conn.close()


@pay_api.post('/api/pay/plan/batch')
@login_required
def pay_plan_batch():
    """批量修改付款计划 {ids:[..], 分类?: str, project?: 项目名}。
    分类直接改 pay_plan.分类；project 按项目名映射 projects.id 后改 project_id。
    ids 走参数化 IN 占位符，无注入。"""
    body = request.get_json(force=True) or {}
    ids = body.get('ids') or []
    if not ids:
        return _err('需要 ids')
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        return _err('ids 必须是整数数组')
    cls = body.get('分类')
    proj = (body.get('project') or '').strip()
    if cls is None and not proj:
        return _err('需要 分类 或 project 至少一项')
    conn = db.get_conn()
    try:
        updated = 0
        if cls is not None:
            cls = (cls or '').strip()
            ph = ','.join('?' * len(ids))
            cur = conn.execute('UPDATE pay_plan SET 分类=? WHERE id IN (%s)' % ph, [cls] + ids)
            updated += cur.rowcount
        if proj:
            row = conn.execute('SELECT id FROM projects WHERE name=?', (proj,)).fetchone()
            if not row:
                return _err('项目不存在：' + proj, 404)
            ph = ','.join('?' * len(ids))
            cur = conn.execute('UPDATE pay_plan SET project_id=? WHERE id IN (%s)' % ph,
                               [row['id']] + ids)
            updated += cur.rowcount
        conn.commit()
        return _ok({'updated': updated})
    finally:
        conn.close()
