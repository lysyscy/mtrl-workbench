# -*- coding: utf-8 -*-
"""
业务规则集中（规则下沉，S7-2）。

此前付款分类白名单与列表浏览排序 CASE 直接写死在 api.py 里，与解析/分类逻辑耦合。
集中到本模块单一维护，api 只做校验与序列化：
- BIZ_CLASSES       付款分类白名单（确认/批量确认允许的取值）
- BIZ_ORDER_CASE    SQL ORDER BY 里的 CASE 片段（分类排序权重）
- BIZ_ORDER         拼好的 ORDER BY 子句（待确认最前 → 机械 → 辅材 → 剔除 → 其他，同分类按日期倒序）
- is_valid_biz_class(cls)  白名单校验
"""
# 付款分类白名单（确认/批量确认允许的 biz_class）
BIZ_CLASSES = ('待确认', '机械', '辅材', '剔除', '忽略')

# 列表浏览排序：待确认最前 → 机械 → 辅材 → 剔除 → 其他（SQL CASE 片段）
BIZ_ORDER_CASE = (
    "CASE biz_class WHEN '待确认' THEN 0 WHEN '机械' THEN 1 "
    "WHEN '辅材' THEN 2 WHEN '剔除' THEN 3 ELSE 4 END"
)

# 拼好的 ORDER BY 子句（同分类内按单据日期倒序、id 倒序）
# 注：BIZ_ORDER_CASE 为上方模块级常量（SQL CASE 片段），非用户输入，此处 % 拼接无注入风险。
BIZ_ORDER = " ORDER BY %s, substr(单据日期,1,7) DESC, id DESC" % BIZ_ORDER_CASE


def is_valid_biz_class(cls):
    """白名单校验：仅允许 BIZ_CLASSES 内取值"""
    return cls in BIZ_CLASSES
