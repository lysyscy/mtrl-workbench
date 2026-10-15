"""`ACC-PRJ-OWN-001`（归属判定 / 链路 C）8 个判据点的验收断言。"""

from __future__ import annotations

import pytest

from app.core.errors import MustReportError
from app.mod01_projects.domain import (
    append_keyword_dedup,
    resolve_ownership,
    validate_keyword_in_doc,
)
from app.mod01_projects.models import STATUS_ARCHIVED, TYPE_SHELL, TYPE_SMALL
from app.mod03_notice.classify import (
    DEFAULT_RULES,
    KIND_PROJECT_NAME,
    decide_placement,
    rows_needing_ownership,
)
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


# ============================================================ 001-09（2026-09-17 新增 · `TAIL-29`-①）


def _rule_hit_row(kind: str = KIND_PROJECT_NAME) -> dict:
    """按**现有规则**造一行「必被规则命中」的记录（⚠️ **不硬编码任何业务取值**）。"""
    rule = next(r for r in DEFAULT_RULES if r.kind == kind)
    return {kind: str(rule.values[0]), "fields": {"BillName": "材料款"}}


@acc("ACC-PRJ-OWN-001", "001-09")
def test_规则剔除行不参与归属校验():
    """§4.2.2「指定项目不在统计范围」的行**天生没有归属** ⇒ 不得拦下整批。

    实测由来：2026-09 真机抓 **61 行**，其中「集团公司第四分公司机关工程」×2 行
    （该值**本来就在** `DEFAULT_RULES` 的「付款项目名」命中值里）**参与了整批校验**
    ⇒ **61 行全被拦下**，该月一条都进不来。
    """
    rows = [
        {"project_name": "某在建项目", "fields": {"BillName": "材料款"}},
        _rule_hit_row(),
    ]
    need = rows_needing_ownership(rows)
    assert [i for i, _ in need] == [0], f"剔除行没被排除：{[i for i, _ in need]}"


@acc("ACC-PRJ-OWN-001", "001-09")
def test_剔除行只是不参与校验_其余行原序号不被挪动():
    """⚠️ 剔除行**不是不落库**（落库时 `decide_placement` 会给它打 `exclude_source=rule`）；
    这里只断言「它不进校验」＋「**其余行的原序号不被挪动**」—— 序号错了落库会串行。"""
    rows = [
        _rule_hit_row(),                                                  # 0：剔除
        {"project_name": "某在建项目", "fields": {"BillName": "材料款"}},    # 1：需归属
        _rule_hit_row(),                                                  # 2：剔除
    ]
    assert [i for i, _ in rows_needing_ownership(rows)] == [1]


@acc("ACC-PRJ-OWN-001", "001-09")
def test_两条判定同源_不许另写一份剔除判定():
    """⭐ 钉住「**同一份规则源**」：`rows_needing_ownership` 与 `decide_placement` 对同一行
    的剔除结论必须**完全一致** —— 谁在编排层抄一份判定，这条就红。"""
    rows = [
        _rule_hit_row(),
        {"project_name": "某在建项目", "fields": {"BillName": "材料款"}},
        {"project_name": "", "fields": {"BillName": ""}},
    ]
    need_idx = {i for i, _ in rows_needing_ownership(rows)}
    for i, row in enumerate(rows):
        assert decide_placement(row).excluded == (i not in need_idx), f"第 {i} 行两条判定不一致"


@acc("ACC-PRJ-OWN-001", "001-09")
def test_整批全是剔除行时校验直接放行():
    """边界：全是被剔除的行 ⇒ **没有需要归属的行** ⇒ 不报错、整批可落库。"""
    rows = [_rule_hit_row(), _rule_hit_row()]
    assert rows_needing_ownership(rows) == []
    assert all(decide_placement(r).excluded for r in rows)
