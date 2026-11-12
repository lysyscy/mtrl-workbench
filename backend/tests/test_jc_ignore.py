"""集采抓取剔除的匹配、旧名单兼容和规则新增删除。"""
from __future__ import annotations

from sqlalchemy import text

from app.core.db import session_scope
from app.mod01_projects import repository as pj_repo
from app.mod01_projects.models import TYPE_NORMAL
from app.mod11_jc import repository as R
from app.mod11_jc.fetch_service import match_projects, split_ignored

WH = "__自检仓_剔除名单__"
FULL = f"{WH}项目"


def _rows() -> list:
    return [{"contract_no": "IG1", "project_name": FULL, "fields": {"BillName": "单-A"}},
            {"contract_no": "IG2", "project_name": "另有其名的项目", "fields": {"BillName": "单-B"}}]


def test_名单命中则摘出_且不动未命中的行():
    """⭐ 命中名单只摘**那几行** —— 未命中的行**一行不动**（防"连坐"）。"""
    with session_scope() as s:
        try:
            R.add_ignored(s, name_full=FULL, reason="自检", operator="自检")
            keep, out = split_ignored(s, _rows())
            assert [r["contract_no"] for r in out] == ["IG1"], "命中名单的行必须被摘出"
            assert [r["contract_no"] for r in keep] == ["IG2"], "未命中的行必须原样留下"
        finally:
            s.rollback()


def test_名单为空时与加名单之前逐字节一致():
    """⭐ 防回归：**名单为空**才是常态（多数时候没人登记）⇒ 它必须与"没有这个功能"完全一样。

    ⚠️ "原样返回"= **连顺序都不许变**（⛔ 不是"返回等价集合"）—— 抓取链路的行序会影响回执与日志。
    """
    with session_scope() as s:
        try:
            rows = _rows()
            keep0, out0 = split_ignored(s, rows)
            assert len(out0) == 0 and len(keep0) == 2, "名单为空时不许动任何一行（防回归）"
            assert [r["contract_no"] for r in keep0] == [r["contract_no"] for r in rows], "顺序也不许变"
        finally:
            s.rollback()


def test_反例_名单不许让未走完的行落库():
    """⭐ 这条是防"顺手放宽"的：摘掉忽略行之后，**未走完的行依然不落库**。"""
    with session_scope() as s:
        try:
            p = pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full=FULL,
                                       warehouse_name=WH, phid="")
            s.flush()
            R.add_ignored(s, name_full="另一个不要的项目", reason="自检", operator="自检")
            # `未建档的项目` ⇒ 归属走不完 ⇒ 它在有名单的情况下**仍不许**进 matched
            rows = [{"contract_no": "IG3", "project_name": "压根没建档的项目", "fields": {"BillName": "单-C"}}]
            keep, _ = split_ignored(s, rows)
            m = match_projects(keep, pj_repo.all_projects(s))
            assert m["matched"] == [], "⛔ 有名单也不许把「未走完」的行落库"
            assert len(m["unmatched"]) == 1 and m["unmatched"][0]["unsettled_kind"] == "not_archived"
        finally:
            s.rollback()


def test_同条件幂等_删除即停止匹配():
    with session_scope() as s:
        try:
            a = R.add_ignored(s, name_full=FULL, reason="自检", operator="自检")
            b = R.add_ignored(s, name_full=f" {FULL} ", reason="自检2", operator="自检")
            assert b == {"id": a["id"], "reused": True}
            assert len(R.list_ignored(s)) == 1

            R.delete_ignored(s, ignore_id=a["id"])
            R.delete_ignored(s, ignore_id=a["id"])
            assert R.list_ignored(s) == []
            assert split_ignored(s, _rows())[1] == []
        finally:
            s.rollback()


def test_旧名单保留原有效范围_新建同名不恢复旧记录():
    with session_scope() as s:
        try:
            legacy = s.execute(text(
                "INSERT INTO jc_ignore_project(name_full, reason, operator, active, created_at) "
                "VALUES (:name, '', '', :active, CURRENT_TIMESTAMP) RETURNING id"
            ), {"name": FULL, "active": True}).scalar_one()
            retired = s.execute(text(
                "INSERT INTO jc_ignore_project(name_full, reason, operator, active, created_at) "
                "VALUES (:name, '', '', :active, CURRENT_TIMESTAMP) RETURNING id"
            ), {"name": "另有其名的项目", "active": False}).scalar_one()
            keep, ignored = split_ignored(s, _rows())
            assert [row["contract_no"] for row in keep] == ["IG2"]
            assert [rule["id"] for rule in ignored[0]["matches"]] == [legacy]
            assert [(rule["id"], rule["kind"]) for rule in R.list_ignored(s)] == [(legacy, "project")]

            added = R.add_ignored(s, name_full="另有其名的项目")
            assert not added["reused"] and added["id"] != retired
            R.delete_ignored(s, ignore_id=added["id"])
            assert s.execute(text("SELECT active FROM jc_ignore_project WHERE id = :id"),
                             {"id": retired}).scalar_one() is False
        finally:
            s.rollback()


def test_三种条件_完整编号和项目范围_每份合同保留全部命中():
    with session_scope() as s:
        try:
            project = R.add_ignored(s, name_full=FULL)["id"]
            number = R.add_ignored(s, kind="contract", contract_no=" IG1 ")["id"]
            keyword = R.add_ignored(s, kind="keyword", name_full=FULL, bill_name_keyword="测试")["id"]
            scoped = R.add_ignored(s, kind="keyword", name_full="其他项目", bill_name_keyword="测试")["id"]
            rows = [
                {"contract_no": " IG1 ", "project_name": FULL, "bill_name": "检测测试合同"},
                {"contract_no": "IG1", "project_name": FULL, "bill_name": "检测测试合同"},
                {"contract_no": "IG10", "project_name": "项目外", "bill_name": "测试"},
                {"contract_no": "IG11", "project_name": "其他项目", "bill_name": "测试"},
                {"contract_no": "IG12", "project_name": "其他项目", "bill_name": "其他"},
                {"contract_no": "IG13", "project_name": "项目外", "bill_name": "其他"},
                {"contract_no": "IG1", "project_name": "项目外", "bill_name": "其他"},
            ]
            keep, ignored = split_ignored(s, rows)
            assert keep == [rows[2], rows[4], rows[5]]
            assert keep[0] is rows[2]
            assert [row["contract_no"] for row in ignored] == ["IG1", "IG11"]
            assert {rule["id"] for rule in ignored[0]["matches"]} == {project, number, keyword}
            assert [rule["id"] for rule in ignored[1]["matches"]] == [scoped]
            assert ignored[0]["doc_name"] == "检测测试合同"
        finally:
            s.rollback()
