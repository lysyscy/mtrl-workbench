# -*- coding: utf-8 -*-
"""
时间边界统一工具（2026-09-10，业务口径：核算期 = 自然月，1 号 ~ 月末）。

背景（用户澄清）：时间只有「点 / 区间」两种形态；i8 的「月」= 核算期，
每个核算期配置首日 + 末日，此处核算期即自然月。故「归月」与「流水区间」是
同一套区间逻辑（日期 ∈ [首日, 末日]）。本模块是后端时间边界计算的统一入口，
前端对应 `app/static/app.js` 的 monthBounds / yearBounds / rangePresets。
"""
import calendar


def month_bounds(yyyy_mm):
    """'YYYY-MM' -> (start_date, end_date)，核算期自然月 1 号 ~ 月末。

    返回 'YYYY-MM-DD' 闭区间；非法月份/空值返回 (None, None)。
    """
    try:
        y, m = map(int, str(yyyy_mm).strip().split('-'))
    except (ValueError, AttributeError):
        return None, None
    if not y or m < 1 or m > 12:
        return None, None
    start = '%04d-%02d-01' % (y, m)
    end = '%04d-%02d-%02d' % (y, m, calendar.monthrange(y, m)[1])
    return start, end


def export_range(body):
    """从请求体解析「起止日期」导出范围，返回 (start_date, end_date) 或 (None, None)。

    优先新契约 start_date / end_date（'YYYY-MM-DD' 闭区间）；
    兼容旧契约 sy/sm/ey/em 数字（核算期=自然月：start=开始月1号，end=结束月末日）。
    """
    if not isinstance(body, dict):
        return None, None
    sd = str(body.get('start_date') or '').strip()
    ed = str(body.get('end_date') or '').strip()
    if sd and ed:
        return sd, ed
    # 旧契约：sy/sm/ey/em 数字
    try:
        sy = int(body.get('sy'))
        sm = int(body.get('sm'))
    except (TypeError, ValueError):
        return None, None
    ey = int(body.get('ey') or sy)
    em = int(body.get('em') or sm)
    start, _ = month_bounds('%04d-%02d' % (sy, sm))
    _, end = month_bounds('%04d-%02d' % (ey, em))
    return start, end


def parse_range_or_month(args):
    """从查询参数解析时间筛选，返回 (start_date, end_date) 或 (None, None)。

    优先新契约 start_date / end_date（'YYYY-MM-DD' 闭区间）；
    否则 month（'YYYY-MM'）→ month_bounds（核算期自然月）。
    供查询类端点（notices/facets/debt/mach_settle/plans 等）统一使用。
    """
    if not args:
        return None, None
    sd = str(args.get('start_date') or '').strip()
    ed = str(args.get('end_date') or '').strip()
    if sd and ed:
        return sd, ed
    m = str(args.get('month') or '').strip()
    if m:
        return month_bounds(m)
    return None, None
