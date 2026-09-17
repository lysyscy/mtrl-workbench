"""`ACC-PRJ-OWN-001`（归属判定 / 链路 C）8 个判据点的验收断言。"""

from __future__ import annotations

import pytest

from app.core.errors import MustReportError
from app.mod01_projects.domain import (
    append_keyword_dedup,
    ensure_batch_settled,
    resolve_ownership,
    validate_keyword_in_doc,
)
from app.mod01_projects.models import STATUS_ARCHIVED, TYPE_SHELL, TYPE_SMALL
from tests.acc_plugin import acc
from tests.m01_helpers import make_project

_SHELL_A = "第四工程公司 2024甲小微项目"
_SHELL_B = "第四工程公司 2024乙小微项目"


def _two_shells_same_keyword():
    """两个壳、关键词**故意重复**（决策 4 允许重复 ⇒ 不跨壳就必须区分得开）。"""
    shell_a = make_project(1, name_full=_SHELL_A, ptype=TYPE_SHELL)
    small_a = make_project(11, name_full=_SHELL_A, warehouse="甲仓库", ptype=TYPE_SMALL,
                           parent_shell_id=1, keywords=["大唐雷州"])
    shell_b = make_project(2, name_full=_SHELL_B, ptype=TYPE_SHELL)
    small_b = make_project(21, name_full=_SHELL_B, warehouse="乙仓库", ptype=TYPE_SMALL,
                           parent_shell_id=2, keywords=["大唐雷州"])
    return [shell_a, small_a, shell_b, small_b]


@acc("ACC-PRJ-OWN-001", "001-01")
def test_普通项目全名归属自动确定永不待指定():
    p = make_project(1, name_full="百通宏达热力热电联产项目", warehouse="泗阳百通4#锅炉项目仓库")
    d = resolve_ownership(
        name_full="百通宏达热力热电联产项目(XMCB2025080001)",  # 带尾码 → 归一后仍命中
        doc_name="付进度款",
        projects=[p],
    )
    assert d.kind == "normal" and d.target_id == 1 and d.settled


@acc("ACC-PRJ-OWN-001", "001-02")
def test_壳全名关键词命中则自动归集不弹窗():
    d = resolve_ownership(name_full=_SHELL_A, doc_name="付大唐雷州项目进度款", projects=_two_shells_same_keyword())
    assert d.kind == "small" and d.target_id == 11 and d.settled
    assert d.keyword_to_add == "大唐雷州"


@acc("ACC-PRJ-OWN-001", "001-03")
def test_匹配范围只在该壳下不跨壳():
    d = resolve_ownership(name_full=_SHELL_A, doc_name="付大唐雷州项目进度款", projects=_two_shells_same_keyword())
    # 只命中甲壳下的 11；**绝不**命中乙壳的 21（否则别的壳把钱抢走）
    assert 21 not in [d.target_id, *d.matched_ids]
    assert d.target_id == 11


@acc("ACC-PRJ-OWN-001", "001-04")
def test_命中多个或未命中须弹窗问用户():
    shell = make_project(1, name_full=_SHELL_A, ptype=TYPE_SHELL)
    a = make_project(11, name_full=_SHELL_A, warehouse="甲1", ptype=TYPE_SMALL, parent_shell_id=1, keywords=["大唐"])
    b = make_project(12, name_full=_SHELL_A, warehouse="甲2", ptype=TYPE_SMALL, parent_shell_id=1, keywords=["雷州"])
    multi = resolve_ownership(name_full=_SHELL_A, doc_name="大唐雷州项目款", projects=[shell, a, b])
    assert multi.kind == "needs_choice" and set(multi.matched_ids) == {11, 12} and not multi.settled
    none = resolve_ownership(name_full=_SHELL_A, doc_name="某工程款", projects=[shell, a, b])
    assert none.kind == "needs_keyword" and not none.settled


@acc("ACC-PRJ-OWN-001", "001-05")
def test_拟补关键词未出现在单据名里须拒绝归集():
    with pytest.raises(MustReportError):
        validate_keyword_in_doc("焦作百利", "大唐雷州项目进度款")
    with pytest.raises(MustReportError):
        validate_keyword_in_doc("", "大唐雷州项目进度款")
    assert validate_keyword_in_doc("大唐雷州", "大唐雷州项目进度款") == "大唐雷州"


@acc("ACC-PRJ-OWN-001", "001-06")
def test_写库按id且关键词去重追加():
    # 关键词去重追加
    assert append_keyword_dedup(["雷州"], "雷州") == ["雷州"]
    assert append_keyword_dedup(["雷州"], "大唐") == ["雷州", "大唐"]
    assert append_keyword_dedup(None, "新词") == ["新词"]
    # 归属按 id：**改全名不影响**（不按全名反查）
    small = make_project(11, name_full=_SHELL_A, warehouse="甲仓库", ptype=TYPE_SMALL,
                         parent_shell_id=1, keywords=["大唐雷州"])
    shell = make_project(1, name_full=_SHELL_A, ptype=TYPE_SHELL)
    d = resolve_ownership(name_full=_SHELL_A, doc_name="大唐雷州款", projects=[shell, small])
    assert d.target_id == 11


@acc("ACC-PRJ-OWN-001", "001-07")
def test_匹配范围含已归档小微():
    shell = make_project(1, name_full=_SHELL_A, ptype=TYPE_SHELL)
    archived_small = make_project(11, name_full=_SHELL_A, warehouse="甲仓库", ptype=TYPE_SMALL,
                                  parent_shell_id=1, status=STATUS_ARCHIVED, keywords=["大唐雷州"])
    d = resolve_ownership(name_full=_SHELL_A, doc_name="大唐雷州项目款", projects=[shell, archived_small])
    assert d.kind == "small" and d.target_id == 11   # 壳归档后仍可有新单据 ⇒ 只匹配在建会阻塞导入


@acc("ACC-PRJ-OWN-001", "001-08")
def test_归属未走完则整批不入库():
    shell = make_project(1, name_full=_SHELL_A, ptype=TYPE_SHELL)
    small = make_project(11, name_full=_SHELL_A, warehouse="甲仓库", ptype=TYPE_SMALL,
                         parent_shell_id=1, keywords=["大唐雷州"])
    rows = [
        {"name_full": _SHELL_A, "doc_name": "大唐雷州项目款"},  # 已走完
        {"name_full": _SHELL_A, "doc_name": "未知项目款"},      # 未走完
    ]
    decisions = [
        resolve_ownership(name_full=r["name_full"], doc_name=r["doc_name"], projects=[shell, small])
        for r in rows
    ]
    assert any(not d.settled for d in decisions)
    # 只要有一行未走完 ⇒ **整批拒绝**（库里不得出现「待指定」的行）
    with pytest.raises(MustReportError):
        ensure_batch_settled(decisions)
    # 全部走完 ⇒ 放行
    ensure_batch_settled([decisions[0]])
