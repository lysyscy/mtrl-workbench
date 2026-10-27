"""Linked inventory values; Decimal and rounding remain owned by core.money."""
from __future__ import annotations

import hashlib
import json
from decimal import InvalidOperation, localcontext
from typing import Mapping

from app.core.money import MoneyError, amount_text, require_non_negative, to_money

NUMERIC_FIELDS = ('qty', 'price_excl', 'price_incl', 'amount', 'tax_total')
VALUE_FIELDS = (*NUMERIC_FIELDS, 'material_property')
LABELS = dict(qty='数量', price_excl='不含税单价', price_incl='含税单价',
              amount='金额', tax_total='价税合计', material_property='物料性质')
PAIRS = {'amount': 'price_excl', 'tax_total': 'price_incl'}


def number(value, field):
    try:
        if isinstance(value, bool):
            raise MoneyError('不接受布尔值')
        result = require_non_negative(amount_text(value), field=LABELS[field])
        if result >= 10 ** 16:
            raise MoneyError('超出允许范围')
        return result
    except (MoneyError, InvalidOperation, ValueError) as exc:
        raise ValueError(f'{LABELS[field]}无效：{exc}') from exc


def calculate_values(values: Mapping, basis: Mapping | None = None, *, baseline: Mapping | None = None) -> dict[str, str]:
    """A total can be driven by price, by its manual amount, or left unchanged."""
    if set(values) != set(VALUE_FIELDS):
        raise ValueError('调整字段不完整或包含不支持字段，请重读原单')
    basis = basis or {}
    if set(basis) - set(PAIRS) or any(mode not in ('unchanged', 'price', 'amount') for mode in basis.values()):
        raise ValueError('联算方式无效')
    result = {field: number(values[field], field) for field in NUMERIC_FIELDS}
    with localcontext() as context:
        context.prec = 40
        for total, price in PAIRS.items():
            mode = basis.get(total, 'unchanged')
            if mode == 'unchanged':
                if baseline is not None and any(result[key] != number(baseline[key], key) for key in ('qty', price, total)):
                    raise ValueError(f'{LABELS[total]}关联数值已改变，请先按数量或单价联算')
            elif mode == 'price':
                result[total] = number(to_money(result['qty'] * result[price]), total)
            elif result['qty'] == 0:
                if result[total] != 0:
                    raise ValueError(f'数量为0时不能从{LABELS[total]}反算单价，请先填写数量')
            else:
                result[price] = number(to_money(result[total] / result['qty']), price)
    prop = values['material_property']
    if not isinstance(prop, str) or len(prop.strip()) > 32:
        raise ValueError('物料性质无效')
    return {**{field: format(value, '.2f') for field, value in result.items()}, 'material_property': prop.strip()}


def adjustment_values(adjustment) -> dict:
    if adjustment is None:
        return {}
    values = getattr(adjustment, 'overrides', None)
    return dict(values) if values is not None else {'amount': format(to_money(adjustment.amount), '.2f')}


def original_values(row: Mapping) -> dict[str, str]:
    return {**{field: format(to_money(row[field]), '.2f') for field in NUMERIC_FIELDS},
            'material_property': str(row.get('material_property') or '')}


def effective_value(row: Mapping, field: str):
    values = row.get('adjusted_values') or {}
    if field in values:
        return values[field]
    if field == 'amount' and row.get('adj_amount') not in (None, ''):
        return row['adj_amount']
    return row.get(field)


def edit_token(row: Mapping, adjustment) -> str:
    source = {**{key: str(row.get(key) or '') for key in ('id', 'ym', 'warehouse', 'doc_no', 'seq')},
              **original_values(row)}
    current = None if adjustment is None else {
        'id': adjustment.id, 'values': adjustment_values(adjustment),
        'remark': adjustment.remark, 'at': str(adjustment.changed_at)}
    return hashlib.sha256(json.dumps([source, current], ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
