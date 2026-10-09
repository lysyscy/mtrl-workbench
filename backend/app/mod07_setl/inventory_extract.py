"""焊材/气体库存年度汇总：统一读取原单入库金额，复用分类规则及按年聚合。"""
from decimal import Decimal
from sqlalchemy.orm import Session
from app.core.money import sum_money
from app.mod07_setl import extract as X
from app.mod08_inv.service import load_original_details as list_details


def load_amounts(s: Session) -> dict:
    """核算年月及原单入库金额；不读收发结存、价税合计或调整单。读取失败向上传递。"""
    rows = [dict(resource_name=d.material_name, warehouse=d.warehouse_name, ym=d.ym, **{'in':d.amount})
            for d in list_details(s) if d.direction == '入库']
    return X.extract_amounts(rows)


def annual_grid(amounts, kind: str, *, warehouses, year: str, balances=None) -> dict:
    """往年仅展示；历史值及年度合计复用模板网格，2025年早月留空。"""
    months = X.month_columns(year)
    template = X.extract_template_grid(amounts, kind, warehouses=warehouses, year=year, balances=balances)
    by_wh = {row["warehouse"]:row for row in template["rows"]}
    rows = []
    for warehouse in warehouses:
        values = amounts.get(kind, {}).get(warehouse, {})
        prior = sum_money([value for ym,value in values.items() if ym < months[0]])
        base = by_wh[warehouse]
        cells = [None if ym <= '2025-11' else (value or Decimal('0.00'))
                 for ym, value in zip(months, base['cells'])]
        rows.append({'warehouse':warehouse, 'prior':prior, 'cells':cells,
                     'balance':base['balance'], 'total':base['total']})
    sums = [None if months[i] <= '2025-11' else sum_money([row['cells'][i] for row in rows]) for i in range(12)]
    return {'kind':kind, 'year':year, 'months':months, 'rows':rows,
            'sum_row':[sum_money([row['prior'] for row in rows]), *sums,
                       sum_money([row['total'] for row in rows])]}
