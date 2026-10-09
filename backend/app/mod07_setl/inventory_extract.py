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


def annual_grid(amounts, kind: str, *, warehouses, year: str) -> dict:
    """成功读取后的缺月为零；往年为年初前，总额截至所选年末，人工结余独立。"""
    months = X.month_columns(year)
    rows = []
    for warehouse in warehouses:
        values = amounts.get(kind, {}).get(warehouse, {})
        prior = sum_money([value for ym,value in values.items() if ym < months[0]])
        cells = [values.get(ym, Decimal('0.00')) for ym in months]
        rows.append({'warehouse':warehouse, 'prior':prior, 'cells':cells,
                     'total':sum_money([prior, *cells])})
    sums = [sum_money([row['cells'][i] for row in rows]) for i in range(12)]
    return {'kind':kind, 'year':year, 'months':months, 'rows':rows,
            'sum_row':[sum_money([row['prior'] for row in rows]), *sums,
                       sum_money([row['total'] for row in rows])]}
