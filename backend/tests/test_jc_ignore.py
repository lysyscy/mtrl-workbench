"""`TAIL-96` 集采**剔除名单**（不要的项目 ⇒ 抓取时先剔除）—— 行为判据。

⚠️ 非破坏：末尾 `s.rollback()`（同 `test_acc_jc_fetch.py` 的约定，⛔ 一行不留）。
⚠️ 用 `@acc()`（**实现层自检**）而不是判据点号 —— 用户可见的口径判据点待与契约面同批补
   （`TAIL-97` 那批一起动 `验收基线.json`，避免"判据点先加、契约没跟"的分叉）。

判据四条（都能证伪）：
1. 名单命中 ⇒ **摘出**（且不动未命中的行）；
2. 名单为空 ⇒ **原样返回**（与加名单之前逐字节一致 —— 防回归）；
3. ⛔ **反例**：名单**不许**让"未走完的行"变得可落库（防"有名单就放行"）；
4. 名单写入**同名幂等** ＋ 停用后**不再参与过滤**（但仍留在册，可复活）。
"""
from __future__ import annotations

from app.core.db import session_scope
from app.mod01_projects import repository as pj_repo
from app.mod01_projects.models import TYPE_NORMAL
from app.mod11_jc import repository as R
from app.mod11_jc.fetch_service import match_projects, split_ignored
from tests.acc_plugin import acc

WH = "__自检仓_剔除名单__"
FULL = f"{WH}项目"


def _rows() -> list:
    return [{"contract_no": "IG1", "project_name": FULL, "fields": {"BillName": "单-A"}},
            {"contract_no": "IG2", "project_name": "另有其名的项目", "fields": {"BillName": "单-B"}}]


@acc()
def test_名单命中则摘出_名单空则原样():
    with session_scope() as s:
        try:
            keep0, out0 = split_ignored(s, _rows())
            assert len(out0) == 0 and len(keep0) == 2, "名单为空时不许动任何一行（防回归）"

            R.add_ignored(s, name_full=FULL, reason="自检", operator="自检")
            keep, out = split_ignored(s, _rows())
            assert [r["contract_no"] for r in out] == ["IG1"], "命中名单的行必须被摘出"
            assert [r["contract_no"] for r in keep] == ["IG2"], "未命中的行必须原样留下"
        finally:
            s.rollback()


@acc()
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


@acc()
def test_写入同名幂等_停用后不再过滤但留在册():
    with session_scope() as s:
        try:
            a = R.add_ignored(s, name_full=FULL, reason="自检", operator="自检")
            b = R.add_ignored(s, name_full=FULL, reason="自检2", operator="自检")
            assert b["reused"] is True, "同名必须复用（⛔ 不重复插）"
            assert a["id"] == b["id"]
            assert len(R.ignored_names(s)) == 1

            assert R.set_ignored_active(s, ignore_id=int(a["id"]), active=False) == 1
            assert len(R.ignored_names(s)) == 0, "停用后不再参与抓取过滤"
            assert any(x["id"] == a["id"] for x in R.list_ignored(s)), "停用必须**留在册**（可复活）"
        finally:
            s.rollback()
