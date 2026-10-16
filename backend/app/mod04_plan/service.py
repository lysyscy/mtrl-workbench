"""停用计划数据的只读关联出口；不恢复旧页面或写入入口。"""


def project_references(session, project_id, warehouse, *, lock=False):
    from app.core.references import project_references as read
    from .models import PlanRow

    return read(session, ((PlanRow, '停用付款计划'),), project_id, warehouse, lock=lock)
