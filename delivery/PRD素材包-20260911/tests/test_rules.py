# -*- coding: utf-8 -*-
"""规则层单测（S7-2 规则下沉后集中可测）：白名单 / 剔除 / 初判 / 排序。"""
import importer
from rules import BIZ_CLASSES, is_valid_biz_class, BIZ_ORDER_CASE, BIZ_ORDER


def test_whitelist():
    assert is_valid_biz_class('辅材') is True
    assert is_valid_biz_class('忽略') is True
    assert is_valid_biz_class('未知') is False


def test_is_excluded():
    excl = {'付款项目名': ['XX项目'], '收款单位': ['资产处集中采购'],
            '录入人': ['梁丽佳'], '业务类型': ['付劳务公司款'],
            '单据名称关键字': ['水电']}
    assert importer.is_excluded('XX项目', '某', 'r', 'l', 'b', excl) is True
    assert importer.is_excluded('p', '水电费单', 'r', 'l', 'b', excl) is True
    assert importer.is_excluded('p', '正常单', 'r', 'l', 'b', excl) is False


def test_initial_biz_class():
    cls = {'机械锁定业务类型': ['付设备租赁款'],
           '付款类型初判': {'其他支出': '辅材', '付款通知书': '机械'}}
    assert importer.initial_biz_class('付设备租赁款', '其他支出', cls) == '机械'
    assert importer.initial_biz_class('x', '其他支出', cls) == '辅材'
    assert importer.initial_biz_class('x', '未知类型', cls) == '待确认'


def test_decide_biz_class():
    excl = {'付款项目名': ['XX'], '收款单位': [], '录入人': [], '业务类型': [], '单据名称关键字': []}
    cls = {'机械锁定业务类型': ['付设备租赁款'], '付款类型初判': {'其他支出': '辅材'}}
    assert importer.decide_biz_class('XX', 'n', 'r', 'l', 'b', 't', excl, cls) == '剔除'
    assert importer.decide_biz_class('p', 'n', 'r', 'l', '付设备租赁款', 't', excl, cls) == '机械'
    assert importer.decide_biz_class('p', 'n', 'r', 'l', 'b', '其他支出', excl, cls) == '辅材'


def test_biz_order_case_present():
    assert 'CASE biz_class' in BIZ_ORDER_CASE
    assert 'ORDER BY' in BIZ_ORDER
    # 排序权重：待确认(0) < 机械(1) < 辅材(2) < 剔除(3) < 其他(4)
    assert "WHEN '待确认' THEN 0" in BIZ_ORDER_CASE
    assert "WHEN '机械' THEN 1" in BIZ_ORDER_CASE
