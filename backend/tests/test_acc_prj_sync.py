"""`ACC-PRJ-SYNC-001` —— i8 名单同步 → **幂等建档**（切片 2 · 阶段 2「占位建档 · 链路 A」）。

判据点与判据 → `PRD/验收/验收基线.json` 的 `cases["ACC-PRJ-SYNC-001"]`。
规则主人 =《全自动建档-实施计划》**§三 链路 A** ＋《说明书》**§2.4.2**。

⚠️ **验收先行**：本文件先写、实现后补。`@acc("ACC-PRJ-SYNC-001", "001-0N")` **成对声明**。
"""

from __future__ import annotations

from decimal import Decimal  # noqa: F401  （保持与本仓测试同风格）

import pytest

from app.mod01_projects import archive as A
from app.mod01_projects.domain import DEFAULT_SMALL_KEYWORD
from app.mod01_projects.models import STATUS_ACTIVE, TYPE_NORMAL, TYPE_SHELL
from tests.acc_plugin import acc

CASE = "ACC-PRJ-SYNC-001"

# ----------------------------------------------------------------- 桩数据
# ⚠️ 形态照 **本机真机实测**（`ops/实测快照/i8-20260916-*.json`）：常用项目 = `{name_full, phid, code}`；
#    仓库 = `{warehouse_name, owner_full_name}`；两张表的关联键 = **项目全名**。

P_ONE = "甲项目(XMCB2025000001)"        # 1 个仓库 ⇒ 可直接建（带真实仓库名）
P_TWO = "乙项目(TBLX2025000002)"        # 2 个仓库 ⇒ 不自动建（要人选）
P_NONE = "丙项目(TBLX2025000003)"       # 0 个仓库 ⇒ 落占位行
P_EXIST = "丁项目(TBLX2025000004)"      # 已在档案 ⇒ 归集、不重复建
P_SHELL = "第四工程公司2026年小微项目(TBLX2025000005)"   # 含「小微」⇒ 壳（不写仓库名）
P_NOPHID = "戊项目(TBLX2025000006)"     # 只在仓库侧出现、**不在常用项目** ⇒ 缺 phid


def _common() -> list[dict]:
    return [
        {"name_full": P_ONE, "phid": "ph-1", "code": "C1", "ab": ""},
        {"name_full": P_TWO, "phid": "ph-2", "code": "C2", "ab": ""},
        {"name_full": P_NONE, "phid": "ph-3", "code": "C3", "ab": ""},
        {"name_full": P_SHELL, "phid": "ph-5", "code": "C5", "ab": ""},
    ]


def _warehouses() -> list[dict]:
    return [
        {"warehouse_name": "甲仓", "owner_full_name": P_ONE},
        {"warehouse_name": "乙仓A", "owner_full_name": P_TWO},
        {"warehouse_name": "乙仓B", "owner_full_name": P_TWO},
        {"warehouse_name": "壳下仓", "owner_full_name": P_SHELL},      # ⇒ 具体小微（不自动建）
        {"warehouse_name": "戊仓", "owner_full_name": P_NOPHID},        # ⇒ 仓库侧有、常用项目侧无
    ]


def _plan(common=None, warehouses=None, existing=(), taken=()):
    return A.plan_archive(
        common_rows=common if common is not None else _common(),
        warehouse_rows=warehouses if warehouses is not None else _warehouses(),
        existing=existing,
        taken_names=taken,
    )


def _by_name(items, name) -> dict:
    got = [i for i in items if i["name_full"] == name]
    assert got, f"{name} 不在 {[i['name_full'] for i in items]}"
    return got[0]


# ----------------------------------------------------------------- 001-01
@acc(CASE, "001-01")
def test_来源两表同一次同步取齐():
    plan = _plan()
    assert len(A.warehouses_by_owner(_warehouses())) == 4        # 归集出口存在且键 = 项目全名
    assert A.warehouses_by_owner(_warehouses())[P_TWO] == ["乙仓A", "乙仓B"]
    # 两表都参与了计划：既有 create（靠 phid）、也有 no_phid（靠仓库侧才有的人）
    assert plan["create"] and plan["no_phid"]


# ----------------------------------------------------------------- 001-02
@acc(CASE, "001-02")
def test_唯一仓库的普通项目带真实仓库名():
    row = _by_name(_plan()["create"], P_ONE)
    assert row["warehouse_name"] == "甲仓"        # ⭐ 真实仓库名
    assert row["project_type"] == TYPE_NORMAL
    assert row["phid"] == "ph-1"
    assert not row["warehouse_name"].startswith("未建仓-")


# ----------------------------------------------------------------- 001-03
@acc(CASE, "001-03")
def test_多仓库不自动建并显式列出():
    plan = _plan()
    assert not [c for c in plan["create"] if c["name_full"] == P_TWO]
    row = _by_name(plan["manual"], P_TWO)
    assert "仓库" in row["reason"] and "选" in row["reason"]      # 理由要能指导人操作


# ----------------------------------------------------------------- 001-04
@acc(CASE, "001-04")
def test_零仓库落占位行且全名仍是全名():
    row = _by_name(_plan(taken={"未建仓-1", "未建仓-2"})["create"], P_NONE)
    assert row["warehouse_name"] == "未建仓-3"      # 取号要跳过已占用的
    assert row["name_full"] == P_NONE               # ⭐ 全名仍写全名（扶正的钥匙）
    # 下一个号不撞车
    nxt = _by_name(_plan(taken={"未建仓-1", "未建仓-2", "未建仓-3"})["create"], P_NONE)
    assert nxt["warehouse_name"] == "未建仓-4"


# ----------------------------------------------------------------- 001-05
@acc(CASE, "001-05")
def test_含小微建壳且不写仓库名():
    row = _by_name(_plan()["create"], P_SHELL)
    assert row["project_type"] == TYPE_SHELL
    assert row["warehouse_name"] in (None, "")      # 壳没有仓库
    assert DEFAULT_SMALL_KEYWORD in row["name_full"]   # 判定依据 = 关键词（唯一出口）


# ----------------------------------------------------------------- 001-06
@acc(CASE, "001-06")
def test_壳下仓库即具体小微不自动建():
    plan = _plan()
    assert not [c for c in plan["create"] if c["name_full"] == P_SHELL
                and c["project_type"] != TYPE_SHELL]
    assert not [c for c in plan["create"] if c["name_full"] == "壳下仓"]
    row = _by_name(plan["manual"], P_SHELL)
    assert "小微" in row["reason"] and "关键词" in row["reason"]

    # ⭐ **壳已在档 ≠ 壳下小微也结束了** —— 「显式列出」与壳在不在档**无关**。
    #    `001-08` 的"归集结束"只管**不重复建壳**，**不得**把壳下未建档的仓库一并吞掉；
    #    本轮真机实测：`兰考金不换前置车间项目`（挂在已建档的「2026年小微」壳下）就是这样
    #    被静默吞掉的 —— 报表里天天有它，档案里永远没有，提取页默认「在建」还筛不到。
    plan2 = _plan(existing={P_SHELL})
    assert _by_name(plan2["exists"], P_SHELL)                              # 壳照旧归集
    assert not [c for c in plan2["create"] if c["name_full"] == P_SHELL]   # 且不重复建（幂等）
    row2 = _by_name(plan2["manual"], P_SHELL)                              # 但**必须**仍列出
    assert "壳下仓" in row2["reason"] and "关键词" in row2["reason"]

    # 反向：**已经建过行**的小微不再反复催（判据 = 「仓库名是唯一标识」）
    plan3 = _plan(existing={P_SHELL}, taken={"壳下仓"})
    assert not [m for m in plan3["manual"] if m["name_full"] == P_SHELL]


# ----------------------------------------------------------------- 001-07
@acc(CASE, "001-07")
def test_仓库侧有常用项目侧无则不建并报缺phid():
    plan = _plan()
    row = _by_name(plan["no_phid"], P_NOPHID)
    assert row["warehouses"] == ["戊仓"]
    assert "常用项目列表" in row["reason"]           # 链路口径：提示去 i8 加进常用项目
    assert not [c for c in plan["create"] if c["name_full"] == P_NOPHID]


# ----------------------------------------------------------------- 001-08
@acc(CASE, "001-08")
def test_幂等已在档案的全名不再建():
    plan = _plan(existing={P_ONE, P_EXIST})
    assert not [c for c in plan["create"] if c["name_full"] == P_ONE]
    assert _by_name(plan["exists"], P_ONE)["phid"] == "ph-1"
    # 重复同步：计划里的 create 条数稳定（不新增）
    assert len(_plan(existing={P_ONE})["create"]) == len(_plan()["create"]) - 1


# ----------------------------------------------------------------- 001-09
@acc(CASE, "001-09")
def test_新建行状态在建且判定走既有出口():
    from app.mod01_projects.domain import classify_name

    plan = _plan()
    for row in plan["create"]:
        assert row["project_type"] in (TYPE_NORMAL, TYPE_SHELL)
    # 判定结果与唯一出口一致（不另立规则）
    whs = A.warehouses_by_owner(_warehouses())
    for row in plan["create"]:
        assert row["project_type"] == classify_name(row["name_full"], whs.get(row["name_full"], []))
    assert A.NEW_STATUS == STATUS_ACTIVE


# ----------------------------------------------------------------- 001-10
@acc(CASE, "001-10")
def test_回执四类计数且接口不可用不动本地档案():
    from app.mod01_projects import sync_service as S

    class _Loader:
        def __init__(self, rows=None, exc=None):
            self.rows, self.exc, self.calls = rows, exc, 0

        def __call__(self):
            self.calls += 1
            if self.exc:
                raise self.exc
            return self.rows

    good_common, good_wh = _Loader(_common()), _Loader(_warehouses())
    out = S.build_plan(load_common=good_common, load_warehouses=good_wh, existing=set(), taken=())
    # ⚠️ 2026-09-29（`TAIL-190`）：计数**加了两项** —— `manual_multi` / `manual_shell`（「待人工」按**出路**拆）。
    #    ⇒ 本断言从「**恰好等于**四类」改成「**四类一个都不许少** ＋ 两个拆数必须在」：
    #    契约声明的是"四类都要给"，**多给拆数不违反**它；而少了任何一类**才是契约被打穿**。
    assert {"create", "exists", "manual", "no_phid"} <= set(out["counts"]), "四类计数的任何一类都不许缺席"
    assert {"manual_multi", "manual_shell"} <= set(out["counts"]), \
        "「待人工」没按出路拆开 —— 回执就只能报一个总数、只能指一条路（用户会去错地方：`TAIL_190`）"
    # ⭐ 拆数之和必须**回到**总数（这才叫"拆"，⛔ 不是又一处各算一遍）：
    #   `plan_archive` 的三处 `manual.append` 都带 `kind` ⇒ 新计划里必然成立。
    assert out["counts"]["manual_multi"] + out["counts"]["manual_shell"] == out["counts"]["manual"], \
        "按出路拆的两个数加起来不等于「待人工」总数 —— 有 manual 条目**没打 kind**（分类漏了）"
    assert out["counts"]["create"] == len(out["plan"]["create"])
    assert good_common.calls == 1 and good_wh.calls == 1     # 同一次同步各取一次

    boom = _Loader(exc=RuntimeError("i8 不可用"))
    out2 = S.build_plan(load_common=boom, load_warehouses=good_wh, existing=set(), taken=())
    assert out2["degraded"] is True and out2["message"]
    assert out2["plan"] is None                              # ⭐ 不动本地档案（无计划可落）
