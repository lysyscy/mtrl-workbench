# -*- coding: utf-8 -*-
"""
数据体检：入库后自动校验，**只报告不阻断**（观察层，不改变数据）。

背景（2026-09-08 事故）：导入只 UPSERT 不清当月旧行，导致 2026-09 混入 636 行 8 月残留，
跨月衔接对不上（安徽国风 8 月结存 185,596.47 vs 9 月期初 0），而系统零告警——靠人工比对才发现。
原有 verify_sfjc 只在"当月有验收基准"时运行，首月/新月份完全没有防线。

三项检查：
  ① 跨月衔接：当月期初 ≈ 上月结存（按仓库比对，容差 0.05）——最能发现"混月/漏项目"
  ② 规模突变：行数 / 仓库数环比变化 > 50% → 提示确认（未月结、漏项目都会体现）
  ③ 基线输出：始终给出 行数 / 仓库数 / 四列合计，供人工核对与日后补建基准
"""
import db

TOL = 0.05          # 金额比对容差（分位误差、多物料求和误差）

# 列名白名单：_sum_by_wh 只允许这些内部列名，杜绝把用户输入拼进 SQL 标识符
_SAFE_COLS = ('期初金额', '结存金额', '收金额', '发金额')


def _prev_month(month):
    y, m = int(month[:4]), int(month[5:7])
    m -= 1
    if m == 0:
        y, m = y - 1, 12
    return '%04d-%02d' % (y, m)


def _sum_by_wh(month, col):
    """按仓库求和。col 必须是 _SAFE_COLS 白名单内的内部列名（非用户输入）。"""
    if col not in _SAFE_COLS:
        raise ValueError('非法列名: %s' % col)
    conn = db.get_conn()
    try:
        rows = conn.execute(
            'SELECT 仓库, ROUND(SUM(%s),2) s FROM stock_monthly WHERE month=? GROUP BY 仓库' % col,
            (month,)).fetchall()
        return {r['仓库']: (r['s'] or 0) for r in rows}
    finally:
        conn.close()


def check_sfjc(month):
    """返回 [{'level': 'error'|'warn'|'info', 'msg': str}]"""
    out = []
    prev = _prev_month(month)
    conn = db.get_conn()
    try:
        n = conn.execute('SELECT COUNT(*) c FROM stock_monthly WHERE month=?', (month,)).fetchone()['c']
        nprev = conn.execute('SELECT COUNT(*) c FROM stock_monthly WHERE month=?', (prev,)).fetchone()['c']
        whs = [r[0] for r in conn.execute(
            'SELECT DISTINCT 仓库 FROM stock_monthly WHERE month=? ORDER BY 仓库', (month,))]
        whs_prev = [r[0] for r in conn.execute(
            'SELECT DISTINCT 仓库 FROM stock_monthly WHERE month=? ORDER BY 仓库', (prev,))]
        tot = conn.execute(
            'SELECT ROUND(SUM(期初金额),2) a, ROUND(SUM(收金额),2) b, '
            'ROUND(SUM(发金额),2) c, ROUND(SUM(结存金额),2) d '
            'FROM stock_monthly WHERE month=?', (month,)).fetchone()
    finally:
        conn.close()

    if n == 0:
        return [{'level': 'error', 'msg': '%s 入库 0 行：导出失败或解析异常' % month}]

    # ① 跨月衔接
    if nprev:
        cur0 = _sum_by_wh(month, '期初金额')
        prev_end = _sum_by_wh(prev, '结存金额')
        bad = []
        for wh in sorted(set(cur0) | set(prev_end)):
            a, b = prev_end.get(wh, 0), cur0.get(wh, 0)
            if abs((a or 0) - (b or 0)) > TOL:
                bad.append('%s：上月结存 %s vs 本月期初 %s' % (wh, a, b))
        if bad:
            out.append({'level': 'warn', 'msg': '跨月衔接不符 → ' + '；'.join(bad)})
        else:
            out.append({'level': 'info', 'msg': '跨月衔接通过（对比 %s）' % prev})

    # ② 规模突变
    if nprev:
        for label, a, b in (('行数', n, nprev), ('仓库数', len(whs), len(whs_prev))):
            if b and abs(a - b) / b > 0.5:
                out.append({'level': 'warn',
                            'msg': '%s 环比 %+.0f%%（%s → %s）：请确认是未月结还是漏项目'
                                   % (label, (a - b) / b * 100.0, b, a)})

    # ③ 基线（始终输出）
    out.append({'level': 'info',
                'msg': '%s 基线：%d 行 / %d 仓库，期初 %s、收 %s、发 %s、结存 %s'
                       % (month, n, len(whs), tot['a'], tot['b'], tot['c'], tot['d'])})
    return out
