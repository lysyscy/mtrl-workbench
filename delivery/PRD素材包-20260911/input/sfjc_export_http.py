# -*- coding: utf-8 -*-
"""
收发结存表导出（HTTP 版，薄封装 common_export 通用引擎）：
用法: python sfjc_export_http.py <开始年> <开始月> <结束年> <结束月> [--refresh] [--pc id,id]
项目ID参数 key=pc；reportName 需传表名
"""
import sys
import os
import time
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common_export as ce
from consts import PORTAL_URL, BASE_URL

REPORT_PATH = (BASE_URL + '/ngweb/report/index.html#/tableDesign/TableManager/preview'
               '?AppTitle=收发结存表&menucode=e5a4c0d1-489a-9f05-0fe7-01b63b0d9437'
               '&rep_id=3700000000000085&multiCooperate=0&busCode=null')
REPORT_URL = (PORTAL_URL + '#/sub/iframe?appTitle='
              '%E6%94%B6%E5%8F%91%E7%BB%93%E5%AD%98%E8%A1%A8&path=' + quote(REPORT_PATH, safe=''))
REPORT_ID = '3700000000000085'
DATASET_ID = '3700000000000178'
REPORT_NAME = '收发结存表'


def _opt(args, name):
    """解析 --name value 形式可选参数，返回 (value, 剩余args)"""
    if name in args:
        i = args.index(name)
        v = args[i + 1] if i + 1 < len(args) else None
        return v, args[:i] + args[i + 2:]
    return None, args


def main():
    args = [a for a in sys.argv[1:] if a != '--refresh']
    refresh = '--refresh' in sys.argv[1:]
    pc_arg, args = _opt(args, '--pc')
    user_arg, args = _opt(args, '--user')
    pwd_arg, args = _opt(args, '--password')
    if len(args) < 4:
        print('用法: python sfjc_export_http.py <开始年> <开始月> <结束年> <结束月> [--refresh] [--pc <id,id,...>] [--user <账号>] [--password <密码>]')
        return 1
    y1, m1, y2, m2 = args[0], args[1], args[2], args[3]
    out = ce.export_report(y1, m1, y2, m2,
                           report_id=REPORT_ID, dataset_id=DATASET_ID, proj_param='pc',
                           report_name=REPORT_NAME, report_url=REPORT_URL,
                           proj_ids=pc_arg, refresh=refresh, user=user_arg, password=pwd_arg)
    return 0 if out else 1


if __name__ == '__main__':
    sys.exit(main())
