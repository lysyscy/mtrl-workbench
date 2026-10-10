# -*- coding: utf-8 -*-
"""
付款通知书 HTTP 导出（按月）：抓 getList（queryfilter 单据起止日期）→ 字段映射组装 xlsx → 落盘。
用法: python pay_notice_export_http.py <开始年> <开始月> <结束年> <结束月>
     （年月为 1-based；结束月=开始月时导出单月）
关键：dataKey 必须传空字符串（随机 UUID 返回空）；queryfilter 带 BillDt*date*ge*1/le*1 按月抓。
"""
import sys
import os
import json
import calendar
import urllib.request
import urllib.parse
import urllib.error

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common_export as ce
from consts import BASE_URL

# 子进程 stdio 统一 UTF-8 + 容错（与 common_export 保持一致：父进程 utf-8 解码 GBK 字节不抛异常）
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

LIST_URL = BASE_URL + '/FC/FM/PaymentBill/getList'

# 表头（最终定稿 12 个字段，2026-09-08 用户拍板；付款组织需 import_pay_notice 支持）
HEADER = ['单据编码', '单据名称', '单据日期', '付款项目', '付款类型', '业务类型',
          '付款组织', '收款单位', '审批金额', '录入人', '审批状态', '备注']

_ZERO = ('0', '', None, 'None', 'null')


def _status(v, yes, no):
    return no if str(v) in _ZERO else yes


def _map(rec):
    """接口 Record → 表头行（仅映射定稿的 12 个字段）"""
    return {
        '单据编码': rec.get('BillNo') or '',
        '单据名称': rec.get('BillName') or '',
        '单据日期': rec.get('BillDt') or '',
        '付款项目': rec.get('PhidPc_EXName') or '',
        '付款类型': rec.get('PhidRecPayType_EXName') or '',
        '业务类型': rec.get('PhidBusType_EXName') or '',
        '付款组织': rec.get('PhidPayOrg_EXName') or '',
        '收款单位': rec.get('user_skdw_EXName') or '',
        '审批金额': rec.get('ApproveAmt'),
        '录入人': rec.get('PhidFillPsn_EXName') or '',
        '审批状态': _status(rec.get('AppStatus'), '已审批', '未审批'),
        '备注': rec.get('Remark') or '',
    }


def fetch(ge, le, cookie):
    """按起止日期抓 getList，返回 Record[]（HTTP 失败/异常返回 None，便于 export() 走重登重试，不再把 HTTPError 冒到上层触发笼统"cookie 过期"提示）。
    None=HTTP/网络/解析失败（外层应重登重试）；[]=请求成功且无数据（正常返回）。
    ge/le 为 'YYYY-MM-DD' 闭区间（核算期=自然月）。"""
    queryfilter = json.dumps({'queryFilter': json.dumps({
        'BillDt*date*ge*1': ge, 'BillDt*date*le*1': le})}, ensure_ascii=False)
    form = {
        'busType': 'PaymentBill', 'pageId': 'Web:PaymentBill', 'isLoadHistory': '1',
        'relateId': '14', 'inputSource': '2', 'queryfilter': queryfilter,
        'phidOrgList': '3700000000000014', 'phidProjList': '', 'dataKey': '',
        'saveTableName': 'fc3_code_table', 'payStatus': '0',
        'summaryCols': 'ApplyAmtFc,ApplyAmt,ApproveAmtFc,ApproveAmt',
        'limit': '5000', 'page': '0', 'start': '0',
    }
    body = urllib.parse.urlencode(form).encode('utf-8')
    req = urllib.request.Request(LIST_URL, data=body, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded; charset=UTF-8')
    req.add_header('Cookie', cookie)
    req.add_header('User-Agent', 'Mozilla/5.0')
    req.add_header('X-Requested-With', 'XMLHttpRequest')
    try:
        raw = urllib.request.urlopen(req, timeout=180).read().decode('utf-8', 'ignore')
    except urllib.error.HTTPError as e:
        ce.log('!! fetch HTTP %s: %s' % (e.code, e.read().decode('utf-8', 'ignore')[:200]))
        return None
    except Exception as e:
        ce.log('!! fetch 异常: %s' % e)
        return None
    try:
        return json.loads(raw).get('Record') or []
    except Exception as e:
        ce.log('!! fetch JSON 解析失败: %s, body=%s' % (e, raw[:200]))
        return None


def export(sy=None, sm=None, ey=None, em=None, user=None, password=None,
           start_date=None, end_date=None):
    """按起止日期抓 getList + 组装 xlsx，返回 xlsx 路径（无数据/抓失败均返回 None）。
    可被 api.py 直接调用（同步式，无需命令行）。user/password 为 i8 账号绑定。

    时间契约（2026-09-10 归约到起止日期）：
      - 优先 start_date / end_date（'YYYY-MM-DD' 闭区间，核算期=自然月）
      - 兼容旧位置参数 sy/sm/ey/em 数字（归一化为 开始月1号 ~ 结束月末日）

    Cookie 三段（对齐 common_export.export_report 工作记忆硬规则「401 必须真登录」）：
      1) load_cookie 缓存（按账号分文件）
      2) probe_cookie 探测；失效则 login_cookie 真登录（纯 HTTP 优先、浏览器兜底）→ save_cookie
      3) fetch 兜底；中途过期 → 再 login_cookie 重试一次

    返回 None 时上层 pay_api 应提示「cookie 失效请刷新」（三段都失败时）。"""
    # 归一化起止日期（核算期=自然月）
    if start_date and end_date:
        ge, le = start_date, end_date
    else:
        if sy is None or sm is None:
            raise ValueError('需要 start_date/end_date 或 sy/sm')
        ey = ey if ey is not None else sy
        em = em if em is not None else sm
        ge = '%04d-%02d-01' % (sy, sm)
        le = '%04d-%02d-%02d' % (ey, em, calendar.monthrange(ey, em)[1])

    # 1) 缓存取 cookie
    cookie = ce.load_cookie(user)
    if not cookie:
        ce.log('无缓存 cookie（账号=%s），登录获取...' % (user or '默认'))
        try:
            cookie = ce.login_cookie(user, password)
            ce.save_cookie(cookie, source='http_login', user=user)
        except Exception as e:
            ce.log('!! 自动登录失败：%s' % e)
            return None
    elif not ce.probe_cookie(cookie):
        # 2) 缓存过期 → 真登录（NSSM Session 0 下走纯 HTTP，不起浏览器）
        ce.log('cookie 已失效（账号=%s），自动重新登录...' % (user or '默认'))
        try:
            cookie = ce.login_cookie(user, password)
            ce.save_cookie(cookie, source='http_login', user=user)
        except Exception as e:
            ce.log('!! 自动登录失败：%s' % e)
            return None

    # 3) 抓取
    ce.log('正在抓取付款通知书 getList（%s ~ %s）...' % (ge, le))
    recs = fetch(ge, le, cookie)
    if recs is None:
        # 兜底：探测通过的 cookie 抓取中途过期
        ce.log('首次抓取失败（多半 cookie 中途过期），重登后重试一次...')
        try:
            cookie = ce.login_cookie(user, password)
            ce.save_cookie(cookie, source='http_login', user=user)
            recs = fetch(ge, le, cookie)
        except Exception as e:
            ce.log('!! 重试登录失败：%s' % e)
            return None
    if not recs:
        return None
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '付款通知书'
    ws.append(HEADER)
    for rec in recs:
        m = _map(rec)
        ws.append([m[h] for h in HEADER])
    out_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                            '..', 'var', 'downloads'))
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, '付款通知书_%s_%s.xlsx' % (ge[:7].replace('-', ''), le[:7].replace('-', '')))
    wb.save(out)
    return out


def main():
    args = sys.argv[1:]
    if len(args) < 4:
        print('用法: python pay_notice_export_http.py <开始年> <开始月> <结束年> <结束月>')
        return 1
    sy, sm, ey, em = map(int, args[:4])
    out = export(sy, sm, ey, em)
    if not out:
        print('RESULT_PATH=')
        print('抓取到 0 条付款通知书', file=sys.stderr)
        return 1
    print('RESULT_PATH=%s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
