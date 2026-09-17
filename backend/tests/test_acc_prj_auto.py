"""`ACC-PRJ-AUTO-001` —— **材料侧自动扶正（链路 B）**（`MOD-01` 能力 4）。

判据点与判据 → `PRD/验收/验收基线.json` 的 `cases["ACC-PRJ-AUTO-001"]`。
规则主人 =《说明书》**§2.4.2**（B 材料侧扶正）· **§2.5**（找不到 = 陌生仓库 ⇒ 触发建档/扶正）
＋《全自动建档-实施计划》**§三 链路 B** · **§1.2 安全绳**。

⚠️ 本用例 2026-09-17 新建：`MOD-01` 能力 4 原挂 `ACC-PRJ-LIST-001`，而那个用例 7 点全是
   「候选 / 展示名」口径、**无一条讲扶正** ⇒ 属**幽灵判据**（沿用通法：**独立的能力独立成档**）。
⚠️ **验收先行**：本文件与实现同轮落地；`@acc(CASE, "001-0N")` **成对声明**。
"""

from __future__ import annotations

from app.core.errors import MustReportError

from app.mod01_projects import recovery as R
from app.mod01_projects.models import (
    STATUS_ARCHIVED,
    TYPE_NORMAL,
    TYPE_SHELL,
    TYPE_SMALL,
)
from app.mod01_projects.repository import all_projects, promote_placeholder
from tests.acc_plugin import acc
from tests.m08_helpers import FakeSession

CASE = "ACC-PRJ-AUTO-001"

SHELL = "第四工程公司2026年小微项目(TBLX2026070003)"


def _p(pid, name_full, warehouse=None, *, ptype=TYPE_NORMAL, parent=None,
       disp=None, phid="", status="active"):
    from app.mod01_projects.models import Project

    return Project(id=pid, name_full=name_full, warehouse_name=warehouse,
                   disp=disp if disp is not None else (warehouse or ""),
                   project_type=ptype, parent_shell_id=parent, phid=phid, status=status)


def _wh(*pairs) -> list[dict]:
    """仓库名单桩（`API-05`）：`(仓库名, 所属项目全名)`。"""
    return [{"warehouse_name": w, "owner_full_name": o} for w, o in pairs]


def _recover(projects, *, unknown, wh):
    """跑一次编排（`wh` 传 callable ⇒ 可注入**会抛**的 loader 测降级）。"""
    s = FakeSession({_model(): list(projects)})
    loader = wh if callable(wh) else (lambda: wh)
    return s, R.recover_unknown_warehouses(s, unknown_wh=unknown, load_warehouse_rows=loader)


def _model():
    from app.mod01_projects.models import Project

    return Project


# ----------------------------------------------------------------- 001-01
@acc(CASE, "001-01")
def test_遇陌生仓库自动跑一次同步并建档():
    """⭐ 「无感」的判据 = **自动**（不是让用户去点），且**只跑一次**。"""
    calls: list[int] = []

    def loader():
        calls.append(1)
        return _wh(("乙仓", "甲项目"))

    s = FakeSession({_model(): [_p(1, "甲项目", "未建仓-1", disp="未建仓-1")]})
    out = R.recover_unknown_warehouses(s, unknown_wh=["乙仓"], load_warehouse_rows=loader)
    assert calls == [1], "必须**自动**跑一次仓库名单同步（且只一次）"
    assert out["degraded"] is False
    assert out["promote"] == 1
    assert all_projects(s)[0].warehouse_name == "乙仓", "跑完就该在档案里落地"


# ----------------------------------------------------------------- 001-02
@acc(CASE, "001-02")
def test_能扶正就扶正占位行换成真实仓库名():
    s, out = _recover([_p(1, "甲项目", "未建仓-3", disp="未建仓-3")],
                      unknown=["乙仓"], wh=_wh(("乙仓", "甲项目")))
    assert (out["promote"], out["create"], out["unresolved"]) == (1, 0, 0)
    row = all_projects(s)[0]
    assert row.warehouse_name == "乙仓"
    assert row.disp == "乙仓", "展示名沿用占位名 ⇒ 必须一并跟着换（否则屏幕一直挂「未建仓-3」）"
    assert "未建仓-3" in out["promoted"][0] and "乙仓" in out["promoted"][0], "结果要逐条说出来"


# ----------------------------------------------------------------- 001-03
@acc(CASE, "001-03")
def test_扶不了就新建壳下建具体小微且关键词留空():
    s, out = _recover([_p(10, SHELL, None, ptype=TYPE_SHELL, phid="ph-9")],
                      unknown=["兰考金不换前置车间项目"], wh=_wh(("兰考金不换前置车间项目", SHELL)))
    assert (out["create"], out["promote"], out["unresolved"]) == (1, 0, 0)
    small = [p for p in all_projects(s) if p.warehouse_name == "兰考金不换前置车间项目"][0]
    assert small.project_type == TYPE_SMALL
    assert small.parent_shell_id == 10, "具体小微必须挂回它的壳"
    assert list(small.match_keywords or []) == [], "材料侧不需要关键词 ⇒ 留空、不臆造"
    assert "关键词待补" in out["created"][0], "留空不阻塞，但回执要注明"


# ----------------------------------------------------------------- 001-04
@acc(CASE, "001-04")
def test_判不了的一律列出不臆造():
    # ① 仓库名单里查不到它的所属项目
    _, a = _recover([_p(1, "甲项目", "甲仓")], unknown=["乙仓"], wh=_wh(("丙仓", "丙项目")))
    assert a["unresolved"] == 1 and not (a["promote"] or a["create"])
    # ② 全名还没建档（安全绳：i8 侧要先加入「常用项目列表」并同步）
    _, b = _recover([_p(1, "甲项目", "甲仓")], unknown=["乙仓"], wh=_wh(("乙仓", "乙项目")))
    assert b["unresolved"] == 1 and "没建档" in b["unresolved_items"][0]["reason"]
    assert not (b["promote"] or b["create"]), "未建档不得自动建（挡住历史老项目污染）"
    # ③ 同一全名命中 ≥2 条非壳档案（疑似「名字没带小微的壳」）
    _, c = _recover([_p(1, "甲项目", "甲仓"), _p(2, "甲项目", "甲仓2")],
                    unknown=["乙仓"], wh=_wh(("乙仓", "甲项目")))
    assert c["unresolved"] == 1 and "疑似" in c["unresolved_items"][0]["reason"]
    # ④ 已有真实仓库名、与本次不符（普通项目 ↔ 仓库 = 1 : 1）
    _, d = _recover([_p(1, "甲项目", "甲仓")], unknown=["乙仓"], wh=_wh(("乙仓", "甲项目")))
    assert d["unresolved"] == 1 and "1 : 1" in d["unresolved_items"][0]["reason"]
    # 三类都要给（禁静默 —— 判不了时也必须给出"哪一类是空、哪一类有"）
    assert all({"promote", "create", "unresolved"} <= set(x) for x in (a, b, c, d))


# ----------------------------------------------------------------- 001-05
@acc(CASE, "001-05")
def test_只对已建档项目名下的仓库建档():
    """全名在档案里找不到任何行 ⇒ **不建**（那属"先同步常用项目列表"，不是链路 B 的活）。"""
    s, out = _recover([_p(1, "甲项目", "甲仓")], unknown=["乙仓"], wh=_wh(("乙仓", "乙项目")))
    assert [p.warehouse_name for p in all_projects(s)] == ["甲仓"], "一行都不许新增"
    assert out["unresolved"] == 1


# ----------------------------------------------------------------- 001-06
@acc(CASE, "001-06")
def test_人工不得改仓库名扶正只认占位行():
    s = FakeSession({_model(): [_p(1, "甲项目", "甲仓")]})
    real = all_projects(s)[0]
    with __import__("pytest").raises(MustReportError):
        promote_placeholder(s, real, "乙仓")
    assert real.warehouse_name == "甲仓", "被拒后**一个字都不许改**"
    # 占位行才放行
    s2 = FakeSession({_model(): [_p(1, "甲项目", "未建仓-7", disp="未建仓-7")]})
    ok = all_projects(s2)[0]
    promote_placeholder(s2, ok, "乙仓")
    assert (ok.warehouse_name, ok.disp) == ("乙仓", "乙仓")


# ----------------------------------------------------------------- 001-07
@acc(CASE, "001-07")
def test_建档失败不得拖垮抓取():
    # ① 取不到仓库名单 ⇒ 降级（**不抛**），并说清"可稍后重抓"
    def boom():
        raise RuntimeError("i8 502")

    s = FakeSession({_model(): [_p(1, "甲项目", "甲仓")]})
    out = R.recover_unknown_warehouses(s, unknown_wh=["乙仓"], load_warehouse_rows=boom)
    assert out["degraded"] is True and out["unresolved"] == 1
    assert "可稍后重抓" in out["message"]
    # ② 单条建不了（壳已归档）⇒ 只该条进 unresolved，**其余照建**
    s2, out2 = _recover(
        [_p(10, "第四工程公司 2024小微项目(XMCB2024030001)", None, ptype=TYPE_SHELL, status=STATUS_ARCHIVED),
         _p(11, SHELL, None, ptype=TYPE_SHELL)],
        unknown=["大唐雷州发电项目", "兰考金不换前置车间项目"],
        wh=_wh(("大唐雷州发电项目", "第四工程公司 2024小微项目(XMCB2024030001)"),
               ("兰考金不换前置车间项目", SHELL)))
    assert out2["create"] == 1 and out2["unresolved"] == 1, out2
    assert out2["created"][0].startswith("兰考")
    assert "大唐雷州发电项目" == out2["unresolved_items"][0]["warehouse_name"]
    # ③ 汇总文案：扶正/新建/待人工三段都要能出现在回执里
    txt = R.summary_text(out2)
    assert "自动建档 1 行" in txt and "待人工 1 条" in txt
    assert R.summary_text({}) == "" and R.summary_text(None) == ""
