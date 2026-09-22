"""`TAIL-45` · 链路 A ③-b「全名对应 ≥2 个仓库 ⇒ **选定一个**建行」—— 离线断言。

**病**（`TAIL-45` 原文）：这条分支**只做到"列出"** —— 系统把它列进**同步回执**的 `manual` 清单里，
**页面一刷新就没了** ⇒ `m01` 上没有任何可点的入口 ⇒ 用户按回执**看得见、却无处可点**。

**药**（与 `pending.py`（链路 B · 待人工指认）**同一套做法**）：
① 清单随**同步那条运行记录**落进 `detail`（原先 `_persist_fetch` **写死 `detail={}`**）；
② `m01` 从**最近一次成功同步**读回，并**逐条按当前档案现算**（已建行 / 候选不足两条的当场丢掉）；
③ 人选定一个仓库 ⇒ 走 `create_project`（**唯一建档出口**）就地建行。

⭐ **两条口径与链路 B 恰好相反，别照抄**（都写进断言）：
   `pending`（链路 B）是「**抓取成功即清空**」⇒ 它要求**三种结局都写标记**；
   本模块是「**失败不改档案 ⇒ 清单照旧有效**」⇒ 它**跳过没带清单的记录**，认的是**最近一次成功**那次。

⚠️ 真机（真库 ＋ 真端点）由 `tools/probe/_e2e_m01_archpick.py` 覆盖；本文件测**纯逻辑 ＋ 读侧口径 ＋ 守卫**。
"""

from __future__ import annotations

import inspect
from datetime import datetime

from app.mod01_projects import archive_pending as AP
from app.mod01_projects.models import TYPE_NORMAL, Project
from app.mod02_i8.models import RunRecord
from tests.acc_plugin import acc
from tests.m01_helpers import make_project
from tests.m09_helpers import M09Session

FULL = "甲项目(XMCB2025000001)"
AT = "2026-09-18 10:00:00"


def item(full=FULL, warehouses=("甲仓", "乙仓"), phid="ph-1"):
    return {"name_full": full, "phid": phid, "warehouses": list(warehouses),
            "reason": f"挂 {len(warehouses)} 个仓库 —— 需人工选一个再建"}


def rec(rid, *, items=None, has_key=True, target=AP.TARGET_OF_SYNC, at=AT):
    """一条 `sync` 运行记录：`has_key=False` ⇒ 模拟**失败那次**（没带清单）。"""
    detail = AP.record_detail(items if items is not None else []) if has_key else {}
    return RunRecord(id=rid, run_type="sync", target=target, status="success",
                     detail=detail, started_at=datetime.strptime(at, "%Y-%m-%d %H:%M:%S"))


def sess(records=(), projects=()):
    return M09Session({RunRecord: list(records), Project: list(projects)})


# ============================================================ ① 只认「最近一次成功同步」


@acc("ACC-PRJ-SYNC-001", "001-12")
def test_没带清单的同步记录要跳过():
    """⭐ **失败那次不改档案 ⇒ 它不换清单**：跳过没带清单的记录，认**最近一次成功**那次。

    ⚠️ 这条口径**恰与链路 B 相反**（那边"抓取成功即清空"⇒ 三种结局都要写标记）。照抄那边 ⇒
      同步失败一次，用户的待办**凭空消失**（而档案一行没变）—— 静默丢待办。
    """
    bad = rec(2, has_key=False, at="2026-09-18 11:00:00")       # 失败那次（较新）
    ok = rec(1, items=[item()])                                 # 成功那次（较旧）
    got = AP.latest_pending(sess([bad, ok]))
    assert got["found"] and len(got["items"]) == 1, "失败那次不该把清单抹掉"
    assert AP.latest_pending(sess([ok, bad]))["items"] == got["items"], "反序喂入也要认（显式按 id 倒序）"


@acc("ACC-PRJ-SYNC-001", "001-12")
def test_最近一次成功同步清单为空就没有待办():
    """成功同步**就会换新**（哪怕换成一纸空清单）⇒ ⛔ 不回溯更早那条有内容的（`TAIL-41` 同族）。"""
    old = rec(1, items=[item()])
    new = rec(2, items=[], at="2026-09-18 11:00:00")
    assert AP.latest_pending(sess([old, new]))["items"] == []
    assert AP.live_items(sess([old, new])) == []


@acc("ACC-PRJ-SYNC-001", "001-12")
def test_只认常用项目列表那条同步记录():
    """仓库名单那条 `sync`（`target=仓库列表`）**不是**建档清单的出处 ⇒ 跳过；一条都没有 ⇒ `found=False`。"""
    other = rec(2, items=[item()], target="仓库列表", at="2026-09-18 12:00:00")
    assert AP.latest_pending(sess([other]))["found"] is False, "⛔ 不拿别的同步记录凑"
    assert AP.live_pending(sess([other]))["items"] == []
    assert AP.live_pending(sess([]))["found"] is False


# ============================================================ ② 逐条按当前档案现算


@acc("ACC-PRJ-SYNC-001", "001-12")
def test_已经建过行的当场丢掉():
    """清单是**当时的判定**，真相是**档案现在的样子**：该全名已经有行了 ⇒ 这条**当场消失**。

    ⚠️ 两种形态都要测，且**第一种才是关键**：那行挂的仓库**不在候选里**（如人工建档时挑了别的仓库）
       ⇒ 只有「已有行」这一条能拦住它；第二种（挂的就是候选里的一个）**两条判据都会拦** ——
       只测第二种 ⇒ 把「已有行」那条判据改坏，断言**照样绿**（反向灵敏度实测到的"变异打偏"）。
    """
    s0 = sess([rec(1, items=[item()])], [make_project(7, name_full=FULL, warehouse="别的仓库")])
    assert AP.live_items(s0) == [], "已有行（仓库不在候选里）也该当场消失"

    s = sess([rec(1, items=[item()])], [make_project(7, name_full=FULL, warehouse="甲仓")])
    assert AP.live_items(s) == [], "已建过行还摆着 ⇒ 用户对着已解决的清单白干"
    assert AP.live_pending(s)["dropped"] == 1, "丢了几条要如实报（⛔ 不静默）"


@acc("ACC-PRJ-SYNC-001", "001-12")
def test_候选不足两条的当场丢掉():
    """那条同步记录里的仓库清单，**只剩 1 个没被占用** ⇒ 下次同步系统**自己就建了**（不必打扰人）。"""
    projects = [make_project(7, name_full="别的项目", warehouse="乙仓")]   # 乙仓被别行占了
    s = sess([rec(1, items=[item(warehouses=("甲仓", "乙仓"))])], projects)
    assert AP.live_items(s) == []
    # 两个都还空着 ⇒ 才列出来（对照组：证明上面不是因为"永远为空"才过）
    s2 = sess([rec(1, items=[item(warehouses=("甲仓", "乙仓"))])], [])
    assert len(AP.live_items(s2)) == 1


@acc("ACC-PRJ-SYNC-001", "001-12")
def test_候选里不含已占用的仓库名():
    """界面能选的候选 = **i8 名单里那条** 减去**已被占用的**（仓库名是唯一标识）。"""
    projects = [make_project(7, name_full="别的项目", warehouse="乙仓")]
    s = sess([rec(1, items=[item(warehouses=("甲仓", "乙仓", "丙仓"))])], projects)
    it = AP.live_items(s)[0]
    assert it["warehouses"] == ["甲仓", "丙仓"], "被占用的仓库名不该还让人选"
    assert it["stored_warehouses"] == ["甲仓", "乙仓", "丙仓"], "当时那份要留痕（看得见'少了谁'）"


@acc("ACC-PRJ-SYNC-001", "001-12")
def test_同步写侧必须真的把清单落进记录():
    """⭐ 光有读侧没用 —— **写侧**必须真把清单写进那条同步记录（原先写死 `detail={}`）。

    ⚠️ 这三件在真机/壳上都看不出来（清单照旧从回包回执里显示），只有**换页重进**才露 ——
       所以钉在**源码**上：`sync_common_projects` 走 `detail=archive_detail(...)`；
       `_persist_fetch` 不再写死空 detail；两边的「哪条记录」字面必须一致（防改名后静默指不住）。
    """
    from app.mod02_i8 import router as M2

    src = inspect.getsource(M2.sync_common_projects)
    assert "detail=archive_detail(" in src, "同步没有把「待人工建档」清单写进运行记录"
    assert f'object_desc="{AP.TARGET_OF_SYNC}"' in src, "两边认定的同步记录不是同一条（字面不一致）"
    # ⚠️ 按**整行**比，⛔ 不用 `in 全文` —— `_persist_fetch` 的**文档注释**里就写着
    #    「原先这里写死 `detail={}`」⇒ 子串比会把说明文字当成代码喂饱（本仓实测踩过一次）。
    body = [ln.strip() for ln in inspect.getsource(M2._persist_fetch).split("\n")]
    assert "detail=detail or {}," in body, "`_persist_fetch` 没把调用方给的清单传下去"
    assert "detail={}," not in body and "detail={}" not in body, \
        "`_persist_fetch` 还在写死空 detail ⇒ 调用方给的清单会被丢掉"


# ============================================================ ③ 选定一个仓库 ⇒ 建行（含三条守卫）


@acc("ACC-PRJ-SYNC-001", "001-13")
def test_选定一个仓库就建行():
    """正题：候选里选一个 ⇒ 就地建行（普通项目 · 带**真实仓库名** · 类型判定走后端唯一出口）。"""
    s = sess([rec(1, items=[item(warehouses=("甲仓", "乙仓"))])])
    row = AP.pick_row(s, full_name=FULL, warehouse_name="乙仓")
    assert row.project_type == TYPE_NORMAL and row.warehouse_name == "乙仓"
    assert row.name_full == FULL and row.phid == "ph-1", "phid 要带上（建档的钥匙）"
    assert row.status == "active" and row.disp == "乙仓", "新建行 = 在建；展示名跟随仓库名"
    assert row in s.added, "必须真的落库（走 create_project 唯一出口）"


@acc("ACC-PRJ-SYNC-001", "001-13")
def test_建完就从清单里消失():
    """建完那一条**即从清单消失**；且同一项目的**其余仓库不再建行**（决策 2：普通项目 ↔ 仓库 = 1 : 1）。"""
    s = sess([rec(1, items=[item(warehouses=("甲仓", "乙仓"))])])
    AP.pick_row(s, full_name=FULL, warehouse_name="甲仓")
    assert AP.live_items(s) == [], "建完还在清单里 ⇒ 用户会重复建"
    assert len([p for p in s.by_model[Project]]) == 1, "只建选中的那一个（其余仓库不再建行）"


@acc("ACC-PRJ-SYNC-001", "001-13")
def test_不在清单里的一律拒且不落库():
    """守卫①：不在「待人工」清单的（已经建过行 / 压根没报过）⇒ 拒，且**一行都不许落**。"""
    import pytest

    from app.core.errors import MustReportError

    # 已经有行了 ⇒ live 清单里没有它 ⇒ 拒（决策 2，也防"别人刚挑过"）
    s = sess([rec(1, items=[item()])], [make_project(7, name_full=FULL, warehouse="甲仓")])
    with pytest.raises(MustReportError):
        AP.pick_row(s, full_name=FULL, warehouse_name="乙仓")
    assert s.added == [], "被拒之后居然落了行"

    # 压根没这条 ⇒ 同样拒
    s2 = sess([rec(1, items=[])])
    with pytest.raises(MustReportError):
        AP.pick_row(s2, full_name=FULL, warehouse_name="甲仓")
    assert s2.added == []


@acc("ACC-PRJ-SYNC-001", "001-13")
def test_手填或已被占用的仓库名都拒():
    """守卫②：仓库名**只能来自 i8 名单**（§9.4）—— 手打一个 / 已被别行占用，**都**拒且给一句人话。

    ⚠️ 这两种情形在**读侧**就已经被现算拦掉了（手填的不进候选；被占用的不进候选）⇒ 本层只负责
       **报成一句能读懂的话**（⛔ 不再各写一遍判据 —— 那种"守卫"永远到不了，是**死代码**）。
    """
    import pytest

    from app.core.errors import MustReportError

    for wh, why in (("丁仓", "手填的（不在 i8 名单里）"), ("乙仓", "已被别的档案行占用")):
        # ⚠️ 场景必须是**三个仓库、被占一个** —— 若只有两个且被占一个，候选只剩一条 ⇒ 整条已被
        #    现算丢掉 ⇒ 报的是"已不在清单里"（那走的是另一条守卫，验不到这一句）。
        s = sess([rec(1, items=[item(warehouses=("甲仓", "乙仓", "丙仓"))])],
                 [make_project(7, name_full="别的项目", warehouse="乙仓")])
        assert AP.live_items(s)[0]["warehouses"] == ["甲仓", "丙仓"], "场景没搭对（候选应是甲/丙）"
        with pytest.raises(MustReportError) as e:
            AP.pick_row(s, full_name=FULL, warehouse_name=wh)
        assert "候选" in str(e.value) and "i8 名单" in str(e.value), f"{why} 的拒绝理由没说清：{e.value}"
        assert s.added == [], f"{why} 被拒之后居然落了行"
