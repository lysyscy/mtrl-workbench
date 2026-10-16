"""按调用域提供的模型读取项目关联；不改变业务记录。"""
from sqlalchemy import or_, select, text


def project_references(session, models, project_id, warehouse, *, lock=False):
    groups = []
    for model, label in models:
        table = model.__table__
        if lock:
            # 文本仓库键没有外键；删除事务须阻止检查之后又插入关联。
            name = session.bind.dialect.identifier_preparer.quote(table.name)
            session.execute(text(f'LOCK TABLE {name} IN SHARE ROW EXCLUSIVE MODE'))
        predicates = [c == project_id for c in table.columns
                      if any(f.target_fullname == 'project.id' for f in c.foreign_keys)]
        for key in ('warehouse_name', 'project_key'):
            if warehouse and key in table.c:
                predicates.append(table.c[key] == warehouse)
        if not predicates:
            if any(key in table.c for key in ('warehouse_name', 'project_key')):
                groups.append({'table': table.name, 'label': label, 'count': 0, 'rows': []})
                continue
            raise ValueError('关联模型没有项目键')
        columns = [c for c in table.columns if c.primary_key or c.name in {
            'project_id', 'ownership_id', 'warehouse_name', 'project_key', 'ym', 'year_month',
            'batch_no', 'code', 'doc_no', 'name_full', 'status', 'field',
            'old_value', 'new_value', 'item_name', 'contract_no', 'notice_id',
            'bill_no', 'doc_date', 'contract_date', 'supplier',
        }]
        rows = [dict(r) for r in session.execute(select(*columns).where(or_(*predicates))).mappings()]
        groups.append({'table': table.name, 'label': label, 'count': len(rows), 'rows': rows})
    return groups
