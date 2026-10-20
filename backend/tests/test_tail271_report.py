"""机械报表真实PG写入及多表解析：确认、覆盖、缺失保留与失败回滚。"""

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from io import BytesIO

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.core.errors import MustReportError
from app.mod06_proc import mech_report as reader, mech_report_spec as domain, repository
from app.mod06_proc.models import ProcMechMatchRule
from tests.test_proc_split_cutoffs import session


def book():
    wb = Workbook()
    s = wb.active
    s.title = "年度汇总"
    s.append(["项目", "费用", "往年合计", "1月", datetime(2026, 9, 1), datetime(2026, 8, 1),
              2023.9, 2023.1, 2024.1, 2024.9, 2024.1, "合计"])
    s.append(["报表A", "当月零租费", 999999, 17, 100, 200, 9, 10, 1, 9, 10, 888888])
    s.append(["报表A", "当月包月费", None, None, 300])
    s.append(["报表A", "当月内租费", None, None, 30])
    s.append(["报表B", "当月零租费", None, None, 0])
    s.append(["灵宝一期项目", "当月零租费", None, None, 999])
    s.append(["合计", "当月零租费", None, None, 999999])
    for name, col in [("零租设备月报表", 9), ("包月外租设备月报", 15)]:
        s = wb.create_sheet(name)
        s.cell(3, 1, "2026年9月")
        s.cell(5, 1, "一"); s.cell(5, 2, "报表A"); s.cell(5, col, 9999)
        for row, value in [(6, 12.345), (7, 12.345)]:
            s.cell(row, 1, row-5); s.cell(row, 2, "汽车吊"); s.cell(row, col, value)
        s.cell(8, 1, "合计"); s.cell(8, 2, "合计"); s.cell(8, col, 9999)
        s.cell(9, 2, "无序号设备"); s.cell(9, col, 1.005)
        s.cell(10, 1, "本页小计"); s.cell(10, col, 9999)
    # 不创建工程公司汇总表；解析必须仅依赖已确认的三张来源。
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture
def rules(session, monkeypatch):
    from app.mod06_proc import mech_matching as matching
    session.query(ProcMechMatchRule).delete()
    session.add_all([ProcMechMatchRule(warehouse_name="A", aliases=["报表A"]),
                     ProcMechMatchRule(warehouse_name="B", aliases=["报表B"])])
    session.flush()
    monkeypatch.setattr(matching, "project_rows", lambda s: [
        {"warehouse": "A", "display": "项目A"}, {"warehouse": "B", "display": "项目B"}])
    return session


def test_month_sources_history_and_aggregate_rounding():
    data = book()
    rows = {r["报表项目名"]: r for r in reader.read_months(data, ["2026-09"])}
    assert rows["报表A"] == {"核算月": "2026-09", "报表项目名": "报表A", "内租设备": "30.00",
                            "外租零租含税": "100.00", "外租包月含税": "300.00",
                            "外租零租不含税": "25.70", "外租包月不含税": "25.70"}
    assert rows["报表B"]["外租零租含税"] == "0.00"
    assert "内租设备" not in rows["报表B"]
    old = reader.read_months(data, ["2023-10", "2024-01", "2024-10", "2025-01", "2026-08"])
    amounts = {r["核算月"]: r["外租零租含税"] for r in old if r["报表项目名"] == "报表A"}
    assert amounts == {"2023-10": "10.00", "2024-01": "1.00", "2024-10": "10.00",
                       "2025-01": "17.00", "2026-08": "200.00"}
    assert all("外租零租不含税" not in r for r in old)
    with pytest.raises(MustReportError, match="月份"):
        reader.read_file(data, "")


def test_confirmation_overwrite_and_missing_preserved(rules):
    s = rules
    repository.save_mech(s, ym="2026-09", warehouse="A", values={"mech_0": 77, "mech_2": 9})
    repository.save_mech(s, ym="2026-09", warehouse="B", values={"mech_1": 88, "mech_2": 99})
    repository.save_mech(s, ym="2026-08", warehouse="A", values={"mech_2": 123})
    records = reader.read_months(book(), ["2026-09"])
    options = {"year_month": "2026-09"}
    before = repository.load_mech(s)
    p = domain.preview(s, records, {}, options)
    assert p["writable"] == 2 and p["kpis"]["未匹配项目"] == 1
    assert p["blocks"][0]["rows"] and repository.load_mech(s) == before
    with pytest.raises(MustReportError, match="确认"):
        domain.commit(s, records, {}, "测试", options)
    assert repository.load_mech(s) == before
    options["confirmed"] = True
    domain.commit(s, records, {}, "测试", options)
    found = {(r["warehouse"], r["ym"]): r for r in repository.load_mech(s)}
    assert found["A", "2026-09"]["mech_0"] == Decimal("77")
    assert found["A", "2026-09"]["mech_2"] == Decimal("100")
    assert found["B", "2026-09"]["mech_1"] == Decimal("88")
    assert found["B", "2026-09"]["mech_2"] == Decimal("0")
    assert found["A", "2026-08"]["mech_2"] == Decimal("123")
    p = domain.preview(s, records, {}, options)
    assert not p["blocks"][0]["rows"] and "没有差异" in p["confirmation"]["message"]
    assert "确认还要导入么" in p["confirmation"]["message"]
    repository.save_mech(s, ym="2026-09", warehouse="A", values={"mech_2": 222})
    assert next(r for r in repository.load_mech(s) if r["warehouse"] == "A" and r["ym"] == "2026-09")["mech_2"] == 222
    domain.commit(s, records, {}, "测试", options)
    assert next(r for r in repository.load_mech(s) if r["warehouse"] == "A" and r["ym"] == "2026-09")["mech_2"] == 100
    with pytest.raises(MustReportError, match="月份已改变"):
        domain.preview(s, records, {}, {"year_month": "2026-08"})


def test_entire_transaction_rolls_back(rules, monkeypatch):
    s = rules
    repository.save_mech(s, ym="2026-09", warehouse="A", values={"mech_2": 9})
    before = repository.load_mech(s)
    save = repository.save_mech
    def fail_second(s, **kwargs):
        if kwargs["warehouse"] == "B":
            raise RuntimeError("模拟第二项目写入失败")
        return save(s, **kwargs)
    monkeypatch.setattr(repository, "save_mech", fail_second)
    with pytest.raises(RuntimeError):
        domain.commit(s, reader.read_months(book(), ["2026-09"]), {}, "测试",
                      {"year_month": "2026-09", "confirmed": True})
    assert repository.load_mech(s) == before


def test_editing_stored_rule_changes_import_target(rules):
    from app.mod06_proc import mech_matching as matching
    matching.save_rule(rules, warehouse="A", aliases=["新报表A"])
    record = {"核算月": "2026-09", "报表项目名": "新报表A", "外租零租含税": "123.45"}
    domain.commit(rules, [record], {}, "测试", {"year_month": "2026-09", "confirmed": True})
    assert repository.load_mech(rules)[0]["warehouse"] == "A"
    assert repository.load_mech(rules)[0]["mech_2"] == Decimal("123.45")
    old = {**record, "报表项目名": "报表A"}
    p = domain.preview(rules, [old], {}, {"year_month": "2026-09"})
    assert p["writable"] == 0 and p["kpis"]["未匹配项目"] == 1
    with pytest.raises(MustReportError, match="多个项目"):
        matching.save_rule(rules, warehouse="B", aliases=["新报表A"])


def test_generic_api_parse_preview_commit(rules, monkeypatch, tmp_path):
    from app.import_kit import api
    from app.core import preview_store
    from app.import_kit.profile_store import ProfileStore
    @contextmanager
    def scope():
        yield rules
    monkeypatch.setattr(api, "session_scope", scope)
    monkeypatch.setattr(api, "current_operator", lambda: "测试")
    monkeypatch.setattr(preview_store, "PREVIEW_DIR", tmp_path)
    app = FastAPI()
    app.include_router(api.build_router(domain.SPEC, domain.HOOKS, ProfileStore(tmp_path / "profile.json")))
    client = TestClient(app)
    url = "/api/imp/" + domain.DOMAIN
    assert not client.post(url + "/parse", files={"file": ("机械.xlsx", book())}).json()["ok"]
    parsed = client.post(url + "/parse", files={"file": ("机械.xlsx", book())},
                         data={"year_month": "2026-09"}).json()
    assert parsed["ok"]
    body = {"token": parsed["token"], "options": {"year_month": "2026-09"}}
    before = repository.load_mech(rules)
    p = client.post(url + "/preview", json=body).json()
    assert p["ok"] and p["confirmation"] and p["writable"] == 2
    assert before == repository.load_mech(rules)
    assert not client.post(url + "/commit", json=body).json()["ok"]
    body["options"]["confirmed"] = True
    result = client.post(url + "/commit", json=body).json()
    assert result["ok"] and result["report"]["rows"] == 2
