"""直接编辑历史行与月份覆盖，页面、汇总、Excel保持同一金额。"""
from decimal import Decimal as D
import pytest
from sqlalchemy import text
from app.core.errors import MustReportError
from app.mod05_flow import history, service
from app.mod05_flow.models import OpeningBalance
from app.mod06_proc import repository as proc
from tests.test_ledger_opening_range import project, notice
from tests.test_proc_split_cutoffs import session  # noqa: F401


def data(p, **kw):
    return dict(project_id=p.id,category="material",entry_kind="manual",cutoff_ym="2025-11",
                settle_amount="1000.12",paid_amount="1000.12",remark="已付清",**kw)


def side(s,p,index=0):
    return service.build_ledger(s,project_id=p.id)["sides"][index]


def test_material_same_month_multiple_rows_edit_delete_and_export(session):
    p=project(session,"__simple_material__")
    first=history.save(session,data(p))
    second=history.save(session,data(p))
    assert first["id"]!=second["id"]
    raw=side(session,p)
    assert len(raw["rows"])==2
    assert all(r["row_kind"]=="manual" and not r["is_opening"] for r in raw["rows"])
    r=next(r for r in raw["rows"] if r["record_id"]==second["id"])
    payload=data(p,id=r["record_id"]);payload["paid_amount"]="900.12"
    history.save(session,payload,r["token"])
    from app.report_export.ledger_export import ledger_spec
    spec=ledger_spec("辅材",side(session,p),display=p.disp)
    assert spec["tail"][0][1]=={"C":D("2000.24"),"D":D("1900.24"),"E":D("100")}
    assert [r[1]["B"] for r in spec["rows"]]==["2025-11","2025-11"]
    summary=next(r for r in service.total_debt_rows(session)["items"] if r["project"]==p.disp)
    assert summary["material"]==D("100")
    row=session.get(OpeningBalance,second["id"])
    history.delete(session,row.id,history.record_token(row));session.flush()
    assert len(side(session,p)["rows"])==1


def test_mechanical_month_payment_is_absolute_and_settlement_keeps_ledger_source(session):
    p=project(session,"__simple_mech__")
    proc.save_mech(session,warehouse=p.warehouse_name,ym="2025-10",values={"mech_2":1000,"mech_3":500})
    n=notice(session,p,"mechanical","2025-10-01",200)
    r=next(r for r in side(session,p,1)["rows"] if r["month"]=="2025-10")
    payload=dict(id=None,project_id=p.id,category="mechanical",entry_kind="month",cutoff_ym="2025-10",
                 settle_amount="1500",paid_amount="1600",remark="历史付款")
    result=history.save(session,payload,r["token"])
    r=next(r for r in side(session,p,1)["rows"] if r["month"]=="2025-10")
    assert (r["other_expense"],r["payment"],r["debt"])==("1500.00","1600.00","-100.00")
    assert session.get(OpeningBalance,result["id"]).settle_amount==0
    n.stat_paid=D(250);session.flush()
    assert next(r for r in side(session,p,1)["rows"] if r["month"]=="2025-10")["payment"]=="1600.00"
    item=next(r for r in service.total_debt_rows(session)["items"] if r["project"]==p.disp)
    assert item["mech"]==D(-100)
    proc.save_mech(session,warehouse=p.warehouse_name,ym="2025-10",values={"mech_2":1200})
    r=next(r for r in side(session,p,1)["rows"] if r["month"]=="2025-10")
    assert r["debt"]=="100.00" and r["payment"]=="1600.00"


def test_material_historical_month_override_is_not_added_twice(session):
    p=project(session,"__simple_override__")
    notice(session,p,"material","2025-11-01",40)
    notice(session,p,"material","2025-12-01",10)
    r=next(r for r in side(session,p)["rows"] if r["month"]=="2025-11")
    payload=data(p);payload.update(entry_kind="month",settle_amount="500",paid_amount="600")
    history.save(session,payload,r["token"])
    rows=side(session,p)["rows"]
    assert [(r["other_expense"],r["payment"]) for r in rows]==[("500.00","600.00"),("100.00","10.00")]
    item=next(r for r in service.total_debt_rows(session)["items"] if r["project"]==p.disp)
    assert item["material"]==D(-10)


def test_history_rejects_stale_cell_wrong_project_and_outside_cutoff(session):
    p=project(session,"__simple_validate__")
    result=history.save(session,data(p))
    row=session.get(OpeningBalance,result["id"]);token=history.record_token(row)
    payload=data(p,id=row.id);payload["paid_amount"]="0"
    history.save(session,payload,token)
    with pytest.raises(MustReportError,match="已变化"):history.save(session,payload,token)
    for field,value in [("cutoff_ym","2025-12"),("cutoff_ym","2025-13"),("paid_amount","NaN")]:
        invalid=data(p);invalid[field]=value
        with pytest.raises(MustReportError):history.save(session,invalid)
    other=project(session,"__simple_other__")
    payload["project_id"]=other.id
    with pytest.raises(MustReportError):history.save(session,payload,history.record_token(row))
    with pytest.raises(MustReportError):history.delete(session,row.id,token)


def test_migration_splits_confirmed_totals_without_changing_net_debt(session):
    import importlib.util
    from pathlib import Path
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    conn = session.connection()
    conn.execute(text("""CREATE TEMP TABLE opening_balance (
        id serial primary key, category varchar(16), project_id integer, cutoff_ym varchar(7),
        settle_amount numeric(18,2), paid_amount numeric(18,2), remark varchar(512), created_at timestamp)
        ON COMMIT DROP"""))
    conn.execute(text("""CREATE TEMP TABLE payment_notice (
        ownership_id integer, category varchar(16), excluded boolean, doc_date varchar(32), stat_paid numeric(18,2))
        ON COMMIT DROP"""))
    conn.execute(text("""INSERT INTO opening_balance(category,project_id,cutoff_ym,settle_amount,paid_amount,remark,created_at)
        VALUES ('material',1,'2025-11',1000.12,1000.12,'已付清',now()),
               ('material',10,'2025-11',500.34,500.34,'已付清',now())"""))
    path = Path(__file__).parents[1] / "alembic/versions/c390261021_historical_balances.py"
    spec = importlib.util.spec_from_file_location("history_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(conn)):
        module.upgrade()
    rows = conn.execute(text("SELECT * FROM opening_balance ORDER BY id")).mappings().all()
    assert len(rows) == 4
    assert sum(r["settle_amount"] for r in rows) == D("1500.46")
    assert sum(r["paid_amount"] for r in rows) == D("1500.46")
    assert [r["entry_kind"] for r in rows] == ["settlement", "settlement", "payment", "payment"]

    path = Path(__file__).parents[1] / "alembic/versions/c391261021_simple_ledger.py"
    spec = importlib.util.spec_from_file_location("simple_migration", path)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with Operations.context(MigrationContext.configure(conn)):module.upgrade()
    rows = conn.execute(text("SELECT * FROM opening_balance ORDER BY id")).mappings().all()
    assert len(rows)==2
    assert all(r["entry_kind"]=="manual" and r["settle_amount"]==r["paid_amount"] for r in rows)
    assert sum(r["settle_amount"] for r in rows)==D("1500.46")
    assert "paid_basis" not in rows[0]
