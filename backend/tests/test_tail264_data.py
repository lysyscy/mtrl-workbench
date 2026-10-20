"""TAIL-264：真实存储出口按合同ID修改，刷新及导出取数一致，并保持抓取空才填。"""
from app.core.db import session_scope
from app.mod01_projects import repository as projects
from app.mod01_projects.models import TYPE_NORMAL
from app.mod11_jc import service, repository
from app.mod11_jc.models import JcContract


def test_material_name_update_is_scoped_and_survives_reload():
    with session_scope() as s:
        p = projects.create_project(s, project_type=TYPE_NORMAL, name_full='简称材料测试', warehouse_name='__TAIL264__', phid='')
        a = service.act_add_contract(s, project_id=p.id, material_name='同名', supplier='河南安装集团')
        b = service.act_add_contract(s, project_id=p.id, material_name='同名', supplier='河南物资公司')
        assert service.act_update_contract(s, contract_id=a['id'], material_name='人工材料')['ok']
        s.expire_all()
        assert s.get(JcContract, a['id']).material_name == '人工材料'
        assert s.get(JcContract, b['id']).material_name == '同名'
        rows = service.build_list(s, project_key='__TAIL264__')['rows']
        assert {r['id']:r['material'] for r in rows} == {a['id']:'人工材料', b['id']:'同名'}
        from app.report_export.jc_export import build_xlsx
        from openpyxl import load_workbook
        from io import BytesIO
        exported = list(load_workbook(BytesIO(build_xlsx(rows)), data_only=True).active.values)
        assert [row[2] for row in exported[1:-1]] == [r['material'] for r in rows]
        assert 'material_name' in repository.FETCH_ONLY_WHEN_BLANK
        assert service.act_update_contract(s, contract_id=a['id'], material_name='')['ok']
        s.expire_all()
        assert s.get(JcContract, a['id']).material_name == ''
        s.rollback()
