# -*- coding: utf-8 -*-
"""付款域服务层：付款 / 撤销 / 状态派生 / 欠款统计。

设计要点（2026-09-09 与用户确认）：
- 实际结算 = pay_notice.审批金额；实际付款 = SUM(pay_flow WHERE voided=0)（**均不冗余存储**）
- 欠款 = COALESCE(计入统计结算, 审批金额) − COALESCE(计入统计付款, 实际付款)
  （「计入统计」两列 NULL 时跟随实际值，用户填了就以填的为准 → 油卡/超付等口径可调）
- 欠款台账：结算与付款**都按 pay_notice.单据日期 归月**（6 月单据 8 月付 → 记进 6 月的账）
- 金额一律转「分」整数比较，消除浮点累积误差
- 付款写操作：BEGIN IMMEDIATE 事务 + 事务内重算余额（防并发超付）+ request_id 唯一（防连点）
"""
import time

# 金额比较容差（元）：小于半分视为相等
EPS_CENTS = 1

# 参与欠款统计的分类（剔除/待确认不计入）
DEBT_BIZ_CLASS = ('辅材', '机械')

# 禁止付款的来源（无流程不付款：手动增加的通知书行不可付款）
PAY_BLOCK_SOURCE = ('manual',)

# 付款方式标准值 + 模糊匹配词（匹配不上 → 归"其他"并提示用户手填具体方式）
PAY_WAY_STD = ('现汇', '承兑', '供应链')
PAY_WAY_ALIAS = {
    '现汇': ('现汇', '电汇', '网银', '转账'),
    '承兑': ('承兑', '银行承兑', '电子承兑', '商业承兑', '汇票'),
    '供应链': ('供应链', '保理', '反向保理'),
}


def to_cents(x):
    """金额转分（整数）。非法值一律按 0 处理，避免 NaN/字符串污染比较。"""
    try:
        v = float(x or 0)
        if v != v:  # NaN
            return 0
        return int(round(v * 100))
    except (TypeError, ValueError):
        return 0


def match_pay_way(text):
    """付款方式模糊匹配 → (标准值, 是否匹配上)。匹配不上返回 ('其他', False)，由调用方提示手填。"""
    s = (text or '').strip()
    if not s:
        return ('', True)
    for std, words in PAY_WAY_ALIAS.items():
        for w in words:
            if w in s:
                return (std, True)
    return ('其他', False)


def _begin_immediate(conn):
    """开启 IMMEDIATE 事务（立即取写锁，防并发下锁升级失败）。
    sqlite3 默认 isolation_level='' 会在 DML 前自动 BEGIN(deferred)，
    故先置 None 才能手动 BEGIN IMMEDIATE。"""
    conn.isolation_level = None
    conn.execute('BEGIN IMMEDIATE')


def _end(conn, ok=True):
    try:
        conn.execute('COMMIT' if ok else 'ROLLBACK')
    finally:
        conn.isolation_level = ''


def paid_amount(conn, notice_id):
    """已付款金额（派生：该单据有效流水之和）"""
    r = conn.execute(
        'SELECT COALESCE(SUM(pay_amount),0) FROM pay_flow WHERE notice_id=? AND voided=0',
        (notice_id,)).fetchone()
    return float(r[0] or 0)


def calc_pay_status(approve, paid):
    """付款状态派生：未付款 / 部分付款 / 已付款（按分比较）"""
    a, p = to_cents(approve), to_cents(paid)
    if p <= 0:
        return '未付款'
    if p >= a:
        return '已付款'
    return '部分付款'


def notice_view(conn, row):
    """给单据行补派生字段（已付款金额 / 剩余未付 / 付款状态），row 为 sqlite3.Row 或 dict"""
    d = dict(row)
    approve = float(d.get('审批金额') or 0)
    paid = paid_amount(conn, d['id'])
    d['已付款金额'] = round(paid, 2)
    d['剩余未付'] = round(approve - paid, 2)
    d['付款状态'] = calc_pay_status(approve, paid)
    return d


class PayError(Exception):
    """付款业务异常（携带可展示给用户的消息与可选 warning）"""

    def __init__(self, msg, warning=None):
        Exception.__init__(self, msg)
        self.msg = msg
        self.warning = warning


def pay(conn, notice_id, amount, pay_way='现汇', pay_way_note='', pay_date=None,
        operator='', request_id='', allow_over=False, note=''):
    """记一笔付款。

    防御性校验顺序：
      ① 单据存在且未删除
      ② 有效性：审批状态='已审批'（无流程不付款）；source 不在禁止列表
      ③ 金额：>0 且为数字
      ④ 防连点：request_id 已存在 → 幂等返回（不重复写）
      ⑤ 防超付：累计+本次 > 审批金额 → 默认拦截（allow_over=True 才放行）
      ⑥ 事务：BEGIN IMMEDIATE + 事务内重算余额（防并发下双双付全额）
    返回 dict(ok, flow_id, 付款状态, 已付款金额, warning)
    """
    warning = None
    row = conn.execute('SELECT * FROM pay_notice WHERE id=? AND deleted=0', (notice_id,)).fetchone()
    if not row:
        raise PayError('付款单不存在或已删除')

    # ② 有效性
    if (row['审批状态'] or '').strip() not in ('已审批',):
        raise PayError('该单据审批状态为「%s」，未审批不可付款（无流程不付款）'
                       % ((row['审批状态'] or '空') or '空'))
    if (row['source'] or '') in PAY_BLOCK_SOURCE:
        raise PayError('手动增加的行不可付款（无流程不付款），请补录通知书后再付')

    # ③ 金额
    amt_c = to_cents(amount)
    if amt_c <= 0:
        raise PayError('付款金额必须大于 0')

    approve = float(row['审批金额'] or 0)
    _begin_immediate(conn)
    try:
        # ④ 防连点（同一 request_id 只写一次）
        if request_id:
            dup = conn.execute('SELECT id FROM pay_flow WHERE request_id=?', (request_id,)).fetchone()
            if dup:
                _end(conn, True)
                paid = paid_amount(conn, notice_id)
                return {'ok': True, 'duplicated': True, 'flow_id': dup['id'],
                        '付款状态': calc_pay_status(approve, paid),
                        '已付款金额': round(paid, 2), 'warning': '重复提交已忽略'}

        # ⑥ 事务内重算余额（关键：不能用例外算好的 paid，否则并发下会超付）
        paid_c = to_cents(paid_amount(conn, notice_id))
        total_c = paid_c + amt_c
        over = total_c - to_cents(approve)
        if over > EPS_CENTS and not allow_over:
            _end(conn, False)
            raise PayError('本次付款将导致超付：单据金额 %.2f，已付 %.2f，本次 %.2f（超出 %.2f）。'
                           '确需超付请勾选允许超付并填写说明。'
                           % (approve, paid_c / 100.0, amt_c / 100.0, over / 100.0))
        if over > EPS_CENTS:
            warning = '该笔为超付（超出 %.2f 元），已记录；超付部分是否计入统计请到单据上设置「计入统计付款」。' % (over / 100.0)

        cur = conn.execute(
            'INSERT INTO pay_flow(notice_id, 单据编码, pay_date, pay_amount, pay_way, '
            'pay_way_note, source, note, request_id, voided) '
            'VALUES(?,?,?,?,?,?,?,?,?,0)',
            (notice_id, row['单据编码'] or '',
             pay_date or time.strftime('%Y-%m-%d'),
             round(amt_c / 100.0, 2), pay_way, pay_way_note,
             'manual', note or '', request_id or ''))
        flow_id = cur.lastrowid
        conn.execute(
            'INSERT INTO pay_flow_log(flow_id, action, 新值, 操作人) VALUES(?,?,?,?)',
            (flow_id, '付款', '金额 %s / 方式 %s%s'
             % (round(amt_c / 100.0, 2), pay_way, ('/' + pay_way_note) if pay_way_note else ''),
             operator or ''))
        # 付款后 bump updated_at，让改分类的乐观锁能感知"这单刚被付过"
        conn.execute("UPDATE pay_notice SET updated_at=? WHERE id=?",
                     (time.strftime('%Y-%m-%d %H:%M:%S'), notice_id))
        _end(conn, True)
    except PayError:
        raise
    except Exception:
        try:
            _end(conn, False)
        except Exception:
            pass
        raise

    paid = paid_amount(conn, notice_id)
    return {'ok': True, 'flow_id': flow_id, '已付款金额': round(paid, 2),
            '付款状态': calc_pay_status(approve, paid), 'warning': warning}


def void_flow(conn, flow_id, operator='', reason=''):
    """撤销一笔付款（软删除 + 留痕）。不限制跨月，但返回 warning 提示影响已出报表。"""
    r = conn.execute('SELECT * FROM pay_flow WHERE id=?', (flow_id,)).fetchone()
    if not r:
        raise PayError('流水不存在')
    if r['voided']:
        raise PayError('该流水已撤销')
    if not (reason or '').strip():
        raise PayError('撤销必须填写原因')

    notice_id = r['notice_id']
    _begin_immediate(conn)
    try:
        conn.execute('UPDATE pay_flow SET voided=1 WHERE id=?', (flow_id,))
        conn.execute(
            'INSERT INTO pay_flow_log(flow_id, action, 旧值, 操作人, 原因) VALUES(?,?,?,?,?)',
            (flow_id, '撤销', '金额 %s / 日期 %s' % (r['pay_amount'], r['pay_date']),
             operator or '', reason))
        conn.execute("UPDATE pay_notice SET updated_at=? WHERE id=?",
                     (time.strftime('%Y-%m-%d %H:%M:%S'), notice_id))
        _end(conn, True)
    except Exception:
        try:
            _end(conn, False)
        except Exception:
            pass
        raise

    row = conn.execute('SELECT 审批金额 FROM pay_notice WHERE id=?', (notice_id,)).fetchone()
    approve = float(row['审批金额'] or 0) if row else 0
    paid = paid_amount(conn, notice_id)
    warning = None
    if (r['pay_date'] or '')[:7] != time.strftime('%Y-%m'):
        warning = '该笔归属 %s，若该月报表已上报请同步更新。' % ((r['pay_date'] or '')[:7] or '未知')
    return {'ok': True, '已付款金额': round(paid, 2),
            '付款状态': calc_pay_status(approve, paid), 'warning': warning}
