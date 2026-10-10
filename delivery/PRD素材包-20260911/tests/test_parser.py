# -*- coding: utf-8 -*-
"""解析层单测：数字解析 / 表头识别 / 收发结存网格读取 / raw_json 瘦身。"""
import os
import tempfile
import json

import openpyxl
from schema_cols import (to_number, read_sfjc_grid, SFJC_HEADER,
                        KCDJ_COLS, KCDJ_RAW_FIELDS)
import importer


def test_to_number():
    assert to_number('1,234.5') == 1234.5
    assert to_number('100') == 100.0
    assert to_number('  3,000 ') == 3000.0
    assert to_number('0') == 0.0
    assert to_number('') is None
    assert to_number('null') is None
    assert to_number(None) is None


def _tmp_xlsx(rows, sheet='报表1'):
    fd, path = tempfile.mkstemp(suffix='.xlsx')
    os.close(fd)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet
    for r in rows:
        ws.append(r)
    wb.save(path)
    return path


def test_detect_sfjc():
    p = _tmp_xlsx([SFJC_HEADER, ['仓A'] + ['a'] * 16])
    assert importer.detect_type(p) == 'sfjc'
    os.remove(p)


def test_detect_kcdj():
    p = _tmp_xlsx([['核算年', '出入库方向', '仓库'], [2026, '入库', '仓A']])
    assert importer.detect_type(p) == 'kcdj'
    os.remove(p)


def test_read_sfjc_grid_drops_empty_keeps_total():
    fd, path = tempfile.mkstemp(suffix='.xlsx')
    os.close(fd)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = '报表1'
    ws.append(['x'] * 17)            # row1 占位表头
    ws.append(['y'] * 17)            # row2 占位表头
    ws.append(['仓A'] + ['a'] * 16)  # row3 数据
    ws.append(['合计'] + ['b'] * 16)  # row4 合计（read_sfjc_grid 不剔，交给调用方）
    wb.save(path)
    grid = read_sfjc_grid(path)
    assert len(grid) == 2
    assert grid[0][0] == '仓A'
    assert grid[1][0] == '合计'
    os.remove(path)


def test_build_kcdj_raw_only_raw_fields():
    d = {k: k for k in KCDJ_COLS.values()}
    raw = importer.build_kcdj_raw(d)
    obj = json.loads(raw)
    # 只保留未独立成列的非结构化字段
    assert set(obj.keys()) == set(KCDJ_RAW_FIELDS)
    assert '仓库' not in obj and '序号' not in obj and '金额' not in obj
