# -*- coding: utf-8 -*-
"""付款通知书分类纯函数测试（R3 补强）：is_excluded / initial_biz_class / decide_biz_class 典型 + 边界。"""
import importer

EXCL = {
    '付款项目名': ['机关工程'],
    '收款单位': ['资产处集中采购'],
    '录入人': ['梁丽佳'],
    '业务类型': ['付劳务公司款', '付分包工程款'],
    '单据名称关键字': ['水电', '房租'],
}
CLS = {
    '机械锁定业务类型': ['付设备租赁款'],
    '付款类型初判': {'其他支出': '辅材', '付款通知书': '机械'},
}


def test_is_excluded_hits_each_rule():
    # 按原顺序逐条命中：付款项目名 / 收款单位 / 录入人 / 业务类型 / 单据名称关键字(子串)
    assert importer.is_excluded('机关工程', '正常单', '', '', '', EXCL) is True
    assert importer.is_excluded('', '正常单', '资产处集中采购', '', '', EXCL) is True
    assert importer.is_excluded('', '正常单', '', '梁丽佳', '', EXCL) is True
    assert importer.is_excluded('', '正常单', '', '', '付分包工程款', EXCL) is True
    assert importer.is_excluded('', '某项目水电费', '', '', '', EXCL) is True


def test_is_excluded_not_hit():
    assert importer.is_excluded('', '正常采购单', '', '', '', EXCL) is False


def test_is_excluded_empty_rules_no_false_positive():
    # 空规则字典（缺所有键）不应误伤任何行
    assert importer.is_excluded('机关工程', '水电费', '资产处集中采购', '梁丽佳', '付劳务公司款', {}) is False


def test_initial_biz_class():
    # 机械锁定业务类型优先
    assert importer.initial_biz_class('付设备租赁款', '任何类型', CLS) == '机械'
    # 付款类型初判
    assert importer.initial_biz_class('x', '其他支出', CLS) == '辅材'
    assert importer.initial_biz_class('x', '付款通知书', CLS) == '机械'
    # 未知类型 → 待确认（边界）
    assert importer.initial_biz_class('x', '未知类型', CLS) == '待确认'
    assert importer.initial_biz_class('x', '', CLS) == '待确认'


def test_decide_biz_class():
    # 剔除优先
    assert importer.decide_biz_class('机关工程', 'n', 'r', 'l', 'b', 't', EXCL, CLS) == '剔除'
    # 机械锁定
    assert importer.decide_biz_class('p', 'n', 'r', 'l', '付设备租赁款', 't', EXCL, CLS) == '机械'
    # 付款类型初判
    assert importer.decide_biz_class('p', 'n', 'r', 'l', 'b', '其他支出', EXCL, CLS) == '辅材'
    # 未知 → 待确认（边界）
    assert importer.decide_biz_class('p', 'n', 'r', 'l', 'b', '未知', EXCL, CLS) == '待确认'
