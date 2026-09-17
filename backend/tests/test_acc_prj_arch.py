"""`ACC-PRJ-ARCH-001`（归档不变式）7 个判据点的验收断言。"""

from __future__ import annotations

import pytest

from app.core.errors import MustReportError
from app.mod01_projects.domain import apply_status_change, can_create_small
from app.mod01_projects.models import (
    STATUS_ACTIVE,
    STATUS_ARCHIVED,
    TYPE_NORMAL,
    TYPE_SHELL,
    TYPE_SMALL,
)
from tests.acc_plugin import acc
from tests.m01_helpers import make_project

_SHELL_NAME = "第四工程公司 2024小微项目"


def _shell_and_smalls(*statuses: str):
    shell = make_project(1, name_full=_SHELL_NAME, ptype=TYPE_SHELL, order=1)
    smalls = [
        make_project(
            10 + i,
            name_full=_SHELL_NAME,
            warehouse=f"小微仓库{i}",
            ptype=TYPE_SMALL,
            parent_shell_id=1,
            status=st,
            keywords=[f"关键词{i}"],
        )
        for i, st in enumerate(statuses)
    ]
    return shell, smalls


@acc("ACC-PRJ-ARCH-001", "001-01")
def test_壳下有在建小微则归档被拦截():
    shell, smalls = _shell_and_smalls(STATUS_ACTIVE, STATUS_ACTIVE)
    r = apply_status_change(shell, STATUS_ARCHIVED, [shell, *smalls])
    assert r.allowed is False
    assert r.writes == []              # 状态不改、**不写留痕**
    assert len(r.blocked_by) == 2


@acc("ACC-PRJ-ARCH-001", "001-02")
def test_拦截时列出未归档小微():
    shell, smalls = _shell_and_smalls(STATUS_ACTIVE)
    r = apply_status_change(shell, STATUS_ARCHIVED, [shell, *smalls])
    assert r.blocked_by and r.blocked_by[0]["warehouse_name"] == "小微仓库0"
    # 讲清"为什么 + 怎么解决"，不是只禁用按钮
    assert "小微仓库0" in r.message and "归档" in r.message


@acc("ACC-PRJ-ARCH-001", "001-03")
def test_壳下全部归档后壳可归档():
    shell, smalls = _shell_and_smalls(STATUS_ARCHIVED, STATUS_ARCHIVED)
    r = apply_status_change(shell, STATUS_ARCHIVED, [shell, *smalls])
    assert r.allowed is True
    assert r.writes == [{"id": 1, "field": "status", "value": STATUS_ARCHIVED}]


@acc("ACC-PRJ-ARCH-001", "001-04")
def test_归档最后一个在建小微则壳自动跟随():
    shell, smalls = _shell_and_smalls(STATUS_ARCHIVED, STATUS_ACTIVE)
    last = smalls[1]
    r = apply_status_change(last, STATUS_ARCHIVED, [shell, *smalls])
    assert r.allowed is True
    assert {w["id"] for w in r.writes} == {last.id, shell.id}   # 壳跟着归档
    assert r.follow_ups and r.follow_ups[0]["id"] == shell.id
    assert r.follow_ups[0]["needs_log"] is True                 # 给壳**单独留痕**


@acc("ACC-PRJ-ARCH-001", "001-05")
def test_已归档壳下不许新建小微():
    shell, _ = _shell_and_smalls()
    shell.status = STATUS_ARCHIVED
    with pytest.raises(MustReportError):
        can_create_small(shell)


@acc("ACC-PRJ-ARCH-001", "001-06")
def test_归档只改状态字段不动业务数据():
    p = make_project(1, name_full="普通项目A", warehouse="普通A仓库", ptype=TYPE_NORMAL)
    other = make_project(2, name_full="普通项目B", warehouse="普通B仓库")
    r = apply_status_change(p, STATUS_ARCHIVED, [p, other])
    assert r.allowed is True
    assert r.follow_ups == []
    # ⚠️ 写集**只含 status**（该项目的通知书/库存单据/… 一行不改）
    assert {w["field"] for w in r.writes} == {"status"}


@acc("ACC-PRJ-ARCH-001", "001-07")
def test_归档可改回在建不锁死():
    p = make_project(1, name_full="普通项目A", warehouse="普通A仓库")
    p.status = STATUS_ARCHIVED
    back = apply_status_change(p, STATUS_ACTIVE, [p])
    assert back.allowed is True
    assert back.writes == [{"id": 1, "field": "status", "value": STATUS_ACTIVE}]
