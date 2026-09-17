"""`ACC-PRJ-LIST-001`（项目候选与显示名解析）验收断言。

⚠️ `001-07`（长项目名完整可读）在基线待建区标为 **B·人工复核**（渲染层，DOM-stub 测不到裁切）
   ⇒ 本文件**不建机器断言**，保持「待建」态。
"""

from __future__ import annotations

from app.mod01_projects.domain import (
    build_candidates,
    combine_filters,
    multi_select_keys,
    resolve_display,
)
from app.mod01_projects.models import STATUS_ARCHIVED, TYPE_SHELL, TYPE_SMALL
from tests.acc_plugin import acc
from tests.m01_helpers import make_project


@acc("ACC-PRJ-LIST-001", "001-01")
def test_候选含归档排最后且带标注():
    active = make_project(1, name_full="甲", warehouse="甲仓", order=1)
    archived = make_project(2, name_full="乙", warehouse="乙仓", order=0, status=STATUS_ARCHIVED)
    cands = build_candidates([active, archived])
    assert any(c.archived for c in cands)          # 含归档（是刻意，不是漏过滤）
    assert cands[-1].archived is True              # 归档排最后
    assert cands[-1].key == "乙仓"                  # 带归档标注（archived 标志）


@acc("ACC-PRJ-LIST-001", "001-02")
def test_候选键为仓库名显示为展示名():
    p = make_project(1, name_full="某项目全名（很长的合同名）", warehouse="仓库X", disp="展示X")
    c = build_candidates([p])[0]
    assert c.key == "仓库X"        # 键 = 仓库名
    assert c.display == "展示X"     # 显示 = 展示名
    assert c.key != p.name_full     # **全名不作候选键**


@acc("ACC-PRJ-LIST-001", "001-03")
def test_只有能定位到仓库的档案进候选():
    has_wh = make_project(1, name_full="有仓库的", warehouse="仓库X")
    no_wh = make_project(2, name_full="未建档的项目名", warehouse=None)  # 无仓库 ⇒ 不可定位
    cands = build_candidates([has_wh, no_wh])
    assert [c.key for c in cands] == ["仓库X"]


@acc("ACC-PRJ-LIST-001", "001-04")
def test_小微壳不进任何候选():
    shell = make_project(1, name_full="壳小微项目", warehouse=None, ptype=TYPE_SHELL)
    small = make_project(2, name_full="壳小微项目", warehouse="小微仓库", ptype=TYPE_SMALL, parent_shell_id=1)
    cands = build_candidates([shell, small])
    assert len(cands) == 1 and cands[0].key == "小微仓库"   # 壳没有仓库 ⇒ 不进候选


@acc("ACC-PRJ-LIST-001", "001-05")
def test_多选语义空选全部与按与组合():
    keys = ["甲仓", "乙仓", "丙仓"]
    assert multi_select_keys([], keys) == keys                    # 空选 = 全部
    assert multi_select_keys(["甲仓", "丙仓"], keys) == ["甲仓", "丙仓"]  # 多选取并集
    assert combine_filters(["甲仓", "乙仓"], ["乙仓", "丙仓"]) == ["乙仓"]  # 与其它筛选按「与」


@acc("ACC-PRJ-LIST-001", "001-06")
def test_展示名解析未建档与待指定():
    normal = make_project(1, name_full="普通项目", warehouse="仓库", disp="展示名")
    # 无匹配 ⇒ **必须显式标「未建档」**（不得静默留空）
    assert resolve_display("查无此名的项目", [normal]) == "未建档"
    # 归一后命中（尾码剥离）
    assert resolve_display("普通项目(XMCB2025080001)", [normal]) == "展示名"

    shell = make_project(2, name_full="壳小微项目", warehouse=None, ptype=TYPE_SHELL)
    s1 = make_project(3, name_full="壳小微项目", warehouse="微1仓", disp="微1展示", ptype=TYPE_SMALL, parent_shell_id=2)
    s2 = make_project(4, name_full="壳小微项目", warehouse="微2仓", disp="微2展示", ptype=TYPE_SMALL, parent_shell_id=2)
    # 壳全名多命中 ⇒ 标「待指定」
    assert resolve_display("壳小微项目", [shell, s1, s2]) == "待指定"
    # 只剩一个具体小微 ⇒ 直接显示它
    assert resolve_display("壳小微项目", [shell, s1]) == "微1展示"
