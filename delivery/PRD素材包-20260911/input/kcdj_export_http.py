# -*- coding: utf-8 -*-
"""
库存单据明细表导出（HTTP 版，薄封装 common_export 通用引擎）：
用法: python kcdj_export_http.py <开始年> <开始月> <结束年> <结束月> [--refresh] [--xmid id,id]
项目ID参数 key=xmid；reportName 传 None（与收发结存不同，已抓包确认）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common_export as ce
from consts import PORTAL_URL

REPORT_URL = (PORTAL_URL + "#/sub/report?appTitle="
              "%E5%BA%93%E5%AD%98%E5%8D%95%E6%8D%AE%E6%98%8E%E7%BB%86%E8%A1%A8&path="
              "%2Fngweb%2Freport%2Findex.html%23%2FtableDesign%2FTableManager%2Fpreview"
              "%3FAppTitle%3D%E5%BA%93%E5%AD%98%E5%8D%95%E6%8D%AE%E6%98%8E%E7%BB%86%E8%A1%A8"
              "%26rep_id%3D3700000000000104")
REPORT_ID = '3700000000000104'
DATASET_ID = '3700000000000165'   # 与收发结存(3700000000000178)不同，已抓包确认
PROJ_PARAM = 'xmid'               # 库存单据的项目参数key，与收发结存(pc)不同


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
    xmid_arg, args = _opt(args, '--xmid')
    user_arg, args = _opt(args, '--user')
    pwd_arg, args = _opt(args, '--password')
    if len(args) < 4:
        print('用法: python kcdj_export_http.py <开始年> <开始月> <结束年> <结束月> [--refresh] [--xmid <id,id,...>] [--user <账号>] [--password <密码>]')
        return 1
    y1, m1, y2, m2 = args[0], args[1], args[2], args[3]
    out = ce.export_report(y1, m1, y2, m2,
                           report_id=REPORT_ID, dataset_id=DATASET_ID, proj_param=PROJ_PARAM,
                           report_name=None, file_name='库存单据明细表', report_url=REPORT_URL,
                           proj_ids=xmid_arg, refresh=refresh, user=user_arg, password=pwd_arg)
    return 0 if out else 1


if __name__ == '__main__':
    sys.exit(main())
