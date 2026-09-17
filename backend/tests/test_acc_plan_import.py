"""`ACC-PLAN-IMPORT-001`（付款计划导入 / 项目列匹配）7 个判据点的验收断言。"""

from __future__ import annotations

from app.core.period import default_period
from app.mod04_plan.domain import (
    BUCKET_ALL,
    MATCH_AMBIGUOUS,
    MATCH_MATCHED,
    MATCH_UNMATCHED,
    PROJECT_COLUMN_HEADER,
    ProjectBrief,
    default_plan_filters,
    match_project,
)
from app.mod04_plan.models import PlanRow
from tests.acc_plugin import acc

_PROJECTS = [
    ProjectBrief(id=1, disp="泗阳百通4#锅炉项目仓库", warehouse_name="泗阳百通4#锅炉项目仓库",
                 name_full="百通宏达热力（泗阳）有限公司热电联产项目#4锅炉建筑及安装工程"),
    ProjectBrief(id=2, disp="甲展示名", warehouse_name="甲仓", name_full="甲的全名"),
    ProjectBrief(id=3, disp="重名项目", warehouse_name="仓A", name_full="重名项目全名"),
    ProjectBrief(id=4, disp="重名项目", warehouse_name="仓B", name_full="重名项目全名"),
]


@acc("ACC-PLAN-IMPORT-001", "001-01")
def test_导入前先选月份且计划行自带年月():
    col = PlanRow.__table__.columns["year_month"]
    assert col.nullable is False          # 年月必填（导入前先选月份）
    assert col.index is True


@acc("ACC-PLAN-IMPORT-001", "001-02")
def test_项目列按展示名或仓库名匹配全名不作键():
    assert match_project("甲展示名", _PROJECTS).project_id == 2
    assert match_project("甲仓", _PROJECTS).project_id == 2
    # ⚠️ 全名**不作匹配键**
    assert match_project("甲的全名", _PROJECTS).status == MATCH_UNMATCHED
    assert match_project(
        "百通宏达热力（泗阳）有限公司热电联产项目#4锅炉建筑及安装工程", _PROJECTS
    ).status == MATCH_UNMATCHED


@acc("ACC-PLAN-IMPORT-001", "001-03")
def test_两种填法归到同一项目共用同一筛选键():
    by_disp = match_project("甲展示名", _PROJECTS)
    by_wh = match_project("甲仓", _PROJECTS)
    assert by_disp.project_id == by_wh.project_id == 2          # 归到同一个项目
    # 共用同一个筛选键 = 该档案行的**仓库名**
    key = next(p.warehouse_name for p in _PROJECTS if p.id == by_disp.project_id)
    assert key == "甲仓"


@acc("ACC-PLAN-IMPORT-001", "001-04")
def test_档案里没有的项目名不猜显式标未匹配():
    r = match_project("查无此项目", _PROJECTS)
    assert r.status == MATCH_UNMATCHED and r.project_id is None
    # 重名（命中多条）⇒ 标「重名 N 条」，也不猜
    amb = match_project("重名项目", _PROJECTS)
    assert amb.status == MATCH_AMBIGUOUS and amb.candidates == 2 and amb.project_id is None


@acc("ACC-PLAN-IMPORT-001", "001-05")
def test_列头写明填报口径():
    assert "展示名" in PROJECT_COLUMN_HEADER and "仓库名" in PROJECT_COLUMN_HEADER


@acc("ACC-PLAN-IMPORT-001", "001-06")
def test_项目列显示规范展示名且未匹配行标出():
    hit = match_project("甲仓", _PROJECTS)
    assert hit.is_matched and hit.display == "甲展示名"     # 显示**规范展示名**（不是填的"甲仓"）
    miss = match_project("查无此项目", _PROJECTS)
    assert miss.status == MATCH_UNMATCHED and miss.display == ""   # 未匹配 ⇒ 必须标出来


@acc("ACC-PLAN-IMPORT-001", "001-07")
def test_默认筛选年月当月且审查结果全部():
    f = default_plan_filters()
    assert f["year_month"] == default_period("plan")        # 北京时间**当月**
    assert f["audit_bucket"] == BUCKET_ALL                   # 审查结果默认「全部」
