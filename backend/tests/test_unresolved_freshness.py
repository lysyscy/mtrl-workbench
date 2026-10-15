"""`TAIL-41` · **「未命中清单」的新鲜度**（付款侧 · 链路 C 弹窗的数据源）—— 离线断言。

**病**（`TAIL-41` 原文）：`mod03_notice.repository.latest_unresolved` **回溯最近 20 条** `run_type=fetch`
记录、取最新一条 `reason=ownership_unsettled` 的 ⇒ 那条记录会**长期留着** ⇒ 抓取**成功之后**
用户仍可能对着**已经解决**的清单去补词 / 建小微（白干一场，**且会往档案里塞错行**）。

**药**（两条"新鲜度"，与材料侧 `pending` 同一口径）：
① **只认最近一次付款通知书抓取**（靠运行记录里的 `notice_fetch` 标记认人，⛔ 不靠 `target` 猜）；
   它不是"未走完" ⇒ **没有清单**（⛔ 不回溯更早的记录）。
② 清单里每一条还要**按当前档案现算**（`mod03_notice.domain.still_unsettled`）——
   用户刚补过词 / 刚建过小微的那些行**当场不再出现**。

⚠️ 行为（真库 · 三条写侧结局都真的写到记录里）由 `tools/probe/_e2e_unresolved_freshness.py` 覆盖；
   本文件测的是**纯逻辑 ＋ 读侧口径**。
⭐ **判据点**（2026-09-18 用户批「判据补充直接添加、无需再报」）：
   · `ACC-PRJ-OWN-001/001-10` = **只认最近一次**（含反证：最近一次又变未走完 ⇒ 清单回来）
   · `ACC-PRJ-OWN-001/001-11` = **逐条按当前档案现算**（复用链路 C 同一出口 ＋ 读端点必须过它）
"""

from __future__ import annotations

from datetime import datetime

from app.mod01_projects.models import Project
from app.mod02_i8.models import RunRecord
from app.mod03_notice import domain as D
from app.mod03_notice import repository as R
from tests.acc_plugin import acc
from tests.m09_helpers import M09Session

SHELL_FULL = "第四工程公司2026小微项目(TBLX2026070003)"
HIT_DOC = "邹平项目-铝型材结算"          # 含小微关键词「邹平」⇒ **能归属**
MISS_DOC = "某项目-零星材料结算"          # 不含任何关键词 ⇒ **不能归属**


def p(pid, full, wh=None, *, ptype="normal", kw=(), parent=None):
    return Project(id=pid, name_full=full, warehouse_name=wh, disp=wh or "", project_type=ptype,
                   parent_shell_id=parent, match_keywords=list(kw))


def rec(rid, *, marked=True, reason="", items=None, at="2026-09-18 10:00:00", target="2026-09"):
    from app.mod03_notice.repository import fetch_detail

    detail = (fetch_detail(reason=reason, unresolved=list(items or [])) if marked
              else {"created": 1, "updated": 0})
    return RunRecord(id=rid, run_type="fetch", target=target, status="success",
                     detail=detail, started_at=datetime.strptime(at, "%Y-%m-%d %H:%M:%S"))


def item(doc=MISS_DOC, full="甲项目"):
    return {"project_name": full, "doc_name": doc, "bill_no": "B1", "kind": "no_keyword_hit",
            "shell_id": None}


def sess(records):
    return M09Session({RunRecord: list(records)})


# ============================================================ ① 只认最近一次


@acc("ACC-PRJ-OWN-001", "001-10")
def test_抓取成功之后就没有未命中清单了():
    """⭐ `TAIL-41` 的正题：**最近一次**抓取已走完 ⇒ 清单为空（⛔ 不再回溯更早那条"未走完"的）。

    ⚠️ 这条要是回了旧清单，用户就会对着**已经解决**的清单去补词 / 建小微
       —— 白干一场，还可能把关键词塞到别的壳下（往档案里塞错行）。
    """
    old = rec(1, reason="ownership_unsettled", items=[item()])
    new = rec(2, at="2026-09-18 11:00:00")            # 最近一次 = 成功 ⇒ detail 里没有 reason
    assert R.latest_unresolved(sess([old, new])) == [], "抓取成功之后不该再有清单"
    assert R.latest_unresolved(sess([new])) == []


@acc("ACC-PRJ-OWN-001", "001-10")
def test_最近一次未走完就给它的清单():
    old_ok = rec(1)
    new_bad = rec(2, at="2026-09-18 11:00:00", reason="ownership_unsettled", items=[item()])
    got = R.latest_unresolved(sess([old_ok, new_bad]))
    assert len(got) == 1 and got[0]["bill_no"] == "B1"
    assert got[0]["kind"] == "no_keyword_hit", "条目字段原样带出（弹窗要用）"


@acc("ACC-PRJ-OWN-001", "001-10")
def test_只认付款通知书抓取的记录():
    """⭐ 靠运行记录里的 `notice_fetch` 标记认人（⛔ 不看 `target` 猜）：

    材料侧抓取（收发结存 / 库存单据）**晚于**它、且不带标记 ⇒ **跳过**，清单照旧来自付款侧；
    反过来说，也**不会**把材料侧的"待人工"当成付款侧的未命中清单。
    """
    pay = rec(1, reason="ownership_unsettled", items=[item()])
    other = rec(2, marked=False, at="2026-09-18 12:00:00", target="setl 2026-09（3 个项目）")
    assert len(R.latest_unresolved(sess([pay, other]))) == 1, "无标记的记录要跳过"
    # 一条有标记的都没有 ⇒ 空（⛔ 不拿别的记录凑）
    assert R.latest_unresolved(sess([other])) == []


@acc("ACC-PRJ-OWN-001", "001-10")
def test_最近一次要按id判不许信传入顺序():
    """⚠️ 离线桩（`M09Session`）不处理 `order_by` ⇒ 读侧必须**显式按 id 倒序**：

    不排的话，实现会拿"数组里第一条"当最新 —— 离线测起来是绿的、真机才不同（**两条路**）。
    """
    old_bad = rec(1, reason="ownership_unsettled", items=[item()])
    new_ok = rec(9, at="2026-09-18 11:00:00")
    assert R.latest_unresolved(sess([old_bad, new_ok])) == [], "反序喂入也要认出「最近」是 id=9"
    assert R.latest_unresolved(sess([new_ok, old_bad])) == []


@acc("ACC-PRJ-OWN-001", "001-10")
def test_三条结局都要写标记():
    """⭐ **写侧**（`repository.fetch_detail` = 唯一出口）：付款通知书抓取的**三种结局**
    —— i8 取数失败 / 归属未走完 / 抓取成功 —— **都必须带 `notice_fetch` 标记**。

    漏掉任何一条，"最近一次"就指不住（读侧掉回**更早**的记录）⇒ `TAIL-41` 原地复发。

    ⚠️ 这三条在**闭包**里（`get_fetch_executor` 直接 `new I8Client()`、不可注入）⇒ 行为跑不到，
       只能**静态钉住"唯一出口用了几次 ＋ 不许有裸 `detail={`"**；运行时由真机脚本覆盖。
    """
    import inspect

    from app.mod03_notice import router as RO

    src = inspect.getsource(RO.get_fetch_executor)
    # 忽略清单与正常行同事务写入；三种结果的运行行为见 test_notice_fetch_skip.py。
    assert src.count("detail=fetch_detail(") == 2, "取数失败与处理结果都须走写侧唯一出口"
    assert "detail={" not in src, "⛔ 不许有绕过出口的裸 detail 字面量"
    assert R.fetch_detail(reason="x") == {R.FETCH_MARK: True, "reason": "x"}
    assert R.fetch_detail() == {R.FETCH_MARK: True}


# ============================================================ ② 逐条按当前档案现算


@acc("ACC-PRJ-OWN-001", "001-11")
def test_已经补过词的行不再出现在清单里():
    """⭐ 清单是**当时的判定**，真相是**档案现在的样子**（`domain.still_unsettled`）：

    用户按清单去补关键词 / 建小微 ⇒ 那些行**已经能归属了** ⇒ **当场不再出现**。
    """
    projects = [
        p(10, SHELL_FULL, None, ptype="shell"),
        p(11, SHELL_FULL, "邹平铝业项目仓库", ptype="small", kw=["邹平"], parent=10),
    ]
    still = D.still_unsettled([item(MISS_DOC, full=SHELL_FULL), item(HIT_DOC, full=SHELL_FULL)],
                              projects)
    assert len(still) == 1 and still[0]["doc_name"] == MISS_DOC, "能归属的那条（含「邹平」）该消失"
    # 补上关键词之后，原本不能归属的那条**也**该消失（= 用户补完词再看的画面）
    projects[1].match_keywords = ["邹平", "某项目"]
    assert D.still_unsettled([item(MISS_DOC, full=SHELL_FULL)], projects) == []


@acc("ACC-PRJ-OWN-001", "001-11")
def test_还没建档的行照旧留着():
    """安全绳那一条（全名查不到任何行）也是"没走完"⇒ **必须留着**（它要人去同步常用项目列表）。"""
    projects = [p(10, SHELL_FULL, None, ptype="shell")]
    still = D.still_unsettled([item(MISS_DOC, full="还没建档的项目(XMCB2025990001)")], projects)
    assert len(still) == 1
    assert D.still_unsettled([], projects) == [] and D.still_unsettled(None, projects) == []


@acc("ACC-PRJ-OWN-001", "001-11")
def test_读端点必须走现算过滤():
    """⭐ 端点那一层也不许"把记录里那份当时的判定直接端出去" —— 必须过 `still_unsettled`。

    ⚠️ `still_unsettled` 自己测过了，但**端点用没用它**是另一件事（没接上 = 白做）。
    """
    import inspect

    from app.mod03_notice import router as RO

    src = inspect.getsource(RO.unresolved_notices)
    assert "still_unsettled(" in src, "端点必须按当前档案现算过滤"
    assert "still_unsettled(latest_unresolved(session), projects)" in src, \
        "过滤要包在**读清单**外面（⛔ 别读一份、端一份）"


@acc("ACC-PRJ-OWN-001", "001-11")
def test_现算走的是链路C同一个出口():
    """⛔ 不许在读侧另写一份"够不够格"：判定必须就是链路 C 的 `resolve_ownership`。"""
    import inspect

    src = inspect.getsource(D.still_unsettled)
    assert "resolve_ownership" in src, "判定出口必须是链路 C 那一份"
    projects = [p(1, "甲项目", "甲仓")]
    assert D.still_unsettled([item(MISS_DOC, full="甲项目")], projects) == [], \
        "普通项目按全名直接归属 ⇒ settled ⇒ 不该留在清单里"
