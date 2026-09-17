"""`ACC-PRJ-ORD-001`（自定义排序 `ord`）7 个判据点的验收断言。"""

from __future__ import annotations

from app.mod01_projects.domain import build_candidates, ordered, reorder
from app.mod01_projects.models import STATUS_ARCHIVED
from tests.acc_plugin import acc
from tests.m01_helpers import make_project


def _rows(with_archive: bool = True):
    a = make_project(1, name_full="甲项目全名", warehouse="甲仓", order=1)
    b = make_project(2, name_full="乙项目全名", warehouse="乙仓", order=2)
    c = make_project(3, name_full="丙项目全名", warehouse="丙仓", order=3)
    rows = [a, b, c]
    if with_archive:
        rows.append(make_project(4, name_full="丁项目全名", warehouse="丁仓", order=0, status=STATUS_ARCHIVED))
    return rows


def _ids_in_order(assignments: list[tuple[int, int]]) -> list[int]:
    return [pid for pid, _ in sorted(assignments, key=lambda t: t[1])]


@acc("ACC-PRJ-ORD-001", "001-01")
def test_序号挂在档案行上三种叫法共用同一条():
    rows = _rows(with_archive=False)
    seq = ordered(rows)
    # 每一行在序里只出现一次 —— 无论用全名 / 仓库名 / 展示名定位，都是同一条档案行
    assert [p.id for p in seq] == [1, 2, 3]
    assert seq[0].ord == 1 and seq[0].name_full == "甲项目全名" and seq[0].warehouse_name == "甲仓"


@acc("ACC-PRJ-ORD-001", "001-02")
def test_归档后置优先于序号():
    a = make_project(1, warehouse="甲仓", order=1)
    d = make_project(4, warehouse="丁仓", order=0, status=STATUS_ARCHIVED)
    assert [p.id for p in ordered([a, d])] == [1, 4]      # 归档恒在最后
    d.ord = -99                                           # 改小序号也翻不到前面
    assert [p.id for p in ordered([a, d])] == [1, 4]


@acc("ACC-PRJ-ORD-001", "001-03")
def test_填序号是插到位置与上下移是对调():
    # 填序号 = 插到那个位置（不是改数字）
    res = reorder(_rows(with_archive=False), project_id=3, to_position=1)
    assert _ids_in_order(res)[:3] == [3, 1, 2]
    # 上移 = 与相邻一行对调
    res2 = reorder(_rows(with_archive=False), project_id=2, direction="up")
    assert _ids_in_order(res2)[:2] == [2, 1]


@acc("ACC-PRJ-ORD-001", "001-04")
def test_改完全表重编号连续无重复():
    rows = _rows()
    res = reorder(rows, project_id=3, to_position=1)
    ords = sorted(o for _, o in res)
    assert ords == list(range(1, len(rows) + 1))          # 1..N 连续、无重复


@acc("ACC-PRJ-ORD-001", "001-05")
def test_改序号全站顺序同步():
    rows = _rows()
    # 列表与「项目候选」共用同一个 ordered() ⇒ 顺序一致（全站跟随）
    assert [c.key for c in build_candidates(rows)] == [p.warehouse_name for p in ordered(rows)]
    reorder(rows, project_id=3, to_position=1)
    assert [c.key for c in build_candidates(rows)] == [p.warehouse_name for p in ordered(rows)]


@acc("ACC-PRJ-ORD-001", "001-06")
def test_移动不得跨在建归档分界():
    rows = _rows()
    # 归档项（组内唯一）上移 ⇒ 到边界不动，绝不进入在建区
    assert _ids_in_order(reorder(rows, project_id=4, direction="up")) == [1, 2, 3, 4]
    # 在建组最后一项下移 ⇒ 到边界不动，绝不进入归档区
    assert _ids_in_order(reorder(rows, project_id=3, direction="down")) == [1, 2, 3, 4]


@acc("ACC-PRJ-ORD-001", "001-07")
def test_排序改动不留痕():
    rows = _rows()
    res = reorder(rows, project_id=3, to_position=1)
    # 返回值**只有** (id, ord) 二元组 —— 不含任何留痕/业务语义
    assert all(len(t) == 2 and isinstance(t[1], int) for t in res)
    # 留痕白名单里没有展示名 / ord（§9.3）
    from app.mod01_projects.models import LOGGED_FIELDS

    assert "ord" not in LOGGED_FIELDS and "disp" not in LOGGED_FIELDS
