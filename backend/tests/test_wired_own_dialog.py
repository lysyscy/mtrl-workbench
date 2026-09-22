"""`TAIL-29`-② ④ · 链路 C 弹窗的**接线断言**（离线）。

配套：
- 真机端到端 = `tools/probe/_e2e_own_assign.py`（真库：补词 → 回读小微关键词 → 清理）
- 静态一致性 = `tools/audit/ui_parity.py`（壳里的弹窗只走适配层，`V.m03` 一行不改）

⚠️ 本文件是**静态/纯函数**检查，**不证明运行时真调通**（那是 e2e 的事）。

判据点都**已存在**（不是新增）—— ② ④ 的病不是"没判据"，而是「**判据绿 ≠ 链路对**」：
`001-04`（命中多个/未命中 ⇒ 弹窗）· `001-05`（词不在单据名里 ⇒ 拒绝）· `001-06`（按 id 写 + 词去重追加）
三条判据早就绿着，而**弹窗从来没做**。
"""

from __future__ import annotations

from pathlib import Path

from tests.acc_plugin import acc

from app.mod01_projects.domain import candidates_of
from app.mod01_projects.models import STATUS_ACTIVE, STATUS_ARCHIVED, TYPE_SHELL, TYPE_SMALL
from tests.m01_helpers import make_project

ROUTER_SRC = (
    Path(__file__).resolve().parents[1] / "app" / "mod03_notice" / "router.py"
).read_text(encoding="utf-8")


# --------------------------------------------------------------- 候选小微（弹窗数据源）


@acc("ACC-PRJ-OWN-001", "001-04")
def test_候选小微按壳取且键是id():
    shell = make_project(1, name_full="某小微项目", ptype=TYPE_SHELL)
    a = make_project(11, name_full="某小微项目", warehouse="甲仓", ptype=TYPE_SMALL,
                     parent_shell_id=1, keywords=["甲"])
    b = make_project(12, name_full="某小微项目", warehouse="乙仓", ptype=TYPE_SMALL,
                     parent_shell_id=1, keywords=["乙"])
    other = make_project(13, name_full="别的", warehouse="丙仓", ptype=TYPE_SMALL, parent_shell_id=99)
    got = candidates_of(1, [shell, a, b, other])
    assert [x["id"] for x in got] == [11, 12], "候选没按壳取，或键不是 id"
    assert got[0]["warehouse_name"] == "甲仓" and got[0]["keywords"] == ["甲"]


@acc("ACC-PRJ-OWN-001", "001-07")
def test_候选含已归档的小微():
    """001-07：壳归档后仍可能有新单据 ⇒ **只匹配在建会阻塞导入**，所以候选要含归档项。"""
    shell = make_project(1, name_full="某小微项目", ptype=TYPE_SHELL)
    live = make_project(11, name_full="某小微项目", warehouse="甲仓", ptype=TYPE_SMALL, parent_shell_id=1)
    gone = make_project(12, name_full="某小微项目", warehouse="乙仓", ptype=TYPE_SMALL,
                        parent_shell_id=1, status=STATUS_ARCHIVED)
    got = candidates_of(1, [shell, live, gone])
    assert [x["id"] for x in got] == [11, 12]
    assert got[1]["status"] == STATUS_ARCHIVED and got[0]["status"] == STATUS_ACTIVE


@acc("ACC-PRJ-OWN-001", "001-04")
def test_壳下没有小微时候选为空():
    shell = make_project(1, name_full="某小微项目", ptype=TYPE_SHELL)
    assert candidates_of(1, [shell]) == []


# --------------------------------------------------------------- 两个端点确实挂上去了


@acc("ACC-PRJ-OWN-001", "001-04")
def test_弹窗数据源端点已挂():
    assert '@router.get("/notices/unresolved"' in ROUTER_SRC
    assert "candidates_of(" in ROUTER_SRC, "端点没去取候选小微 ⇒ 弹窗没有可选项"


@acc("ACC-PRJ-OWN-001", "001-05")
def test_提交端点在且先校验再写():
    """⭐ 顺序断言：**先**校验关键词（不在单据名里就拒绝）**再**写库。"""
    i_validate = ROUTER_SRC.find("keyword = validate_keyword_in_doc(")
    i_write = ROUTER_SRC.find("proj_repo.set_keywords(", i_validate)
    assert i_validate > 0 and i_write > i_validate, "没有「先校验、后写库」"


@acc("ACC-PRJ-OWN-001", "001-06")
def test_补词走去重追加而不是覆盖():
    """001-06：关键词**去重追加** —— ⛔ 直接赋值会把原有词覆盖掉。"""
    i_write = ROUTER_SRC.find("proj_repo.set_keywords(")
    seg = ROUTER_SRC[i_write:i_write + 160]
    assert "append_keyword_dedup(" in seg, "补词没走 append_keyword_dedup（会覆盖原词）"


@acc("ACC-PRJ-OWN-001", "001-06")
def test_新建小微复用建档出口不另写一套():
    """⭐ 「属于新小微」分支必须走 `create_project`（它内部含 001-05 的归档壳校验）。"""
    assert "proj_repo.create_project(" in ROUTER_SRC
    assert "TYPE_SMALL" in ROUTER_SRC
