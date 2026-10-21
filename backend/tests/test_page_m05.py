"""`MOD-05` **组装层**的工程自检（离线 · 不连库 · **只读数据出口**）。

⚠️ 2026-09-19（`TAIL-27` · `§19` **批 3**）：本文件原先用 `TestClient` 打**四个旧服务端页**
   （`/m05` · `/m05/debt` · `/m05/ledger` · `/m05/stats`）来守"页面装配"这一层；旧页整体删除
   （授权 `D18`）⇒ **改守同一批事实的"数据出口"那一面** —— 页面原先也只是印它们 ✓：
   `service.build_flows` / `build_debt` / `build_ledger` / `build_stats`（＋ `domain` 的口径）。
   ⛔ 判据（本文件 8 条 `@acc()` **未绑定**守卫，非判据点）没删；**UI 形态**里仍然有意义的那几条
   （台账两侧共用一个选择器 / 机械侧无手填 / 空态跨列由表头派生 / 撤销入口只在生效行）已搬到
   `tests/test_wired_m05.py`（新壳侧 ✓）。

⚠️ 本文件**不绑定 `ACC-*` 判据点**（`@acc()` 显式声明）—— `ACC-FLOW-{LIST,PST,DEBT,LED}-001` 的判据
在 `test_acc_flow_*.py` 里已由**纯函数**钉住；本文件守的是**组装**这层。
"""

from __future__ import annotations

from app.mod05_flow.service import (
    build_debt, build_flows, build_ledger, build_stats, order_project_ids,
)
from tests.m05_helpers import TODAY, FakeSession, dataset

PROJECT_ID = 11


def _flows(**kw):
    return build_flows(FakeSession(dataset()), **kw)


def _debt():
    return build_debt(FakeSession(dataset()))


def _ledger():
    return build_ledger(FakeSession(dataset()), project_id=PROJECT_ID)


def _stats():
    # ⚠️ 2026-10-01：`today` **必须显式传**（桩里现成的 `TODAY`）；否则走 `date.today()` ⇒
    #    默认"本季度 ＋ 本窗口"会随真实日历漂 —— 实测 10-01 当天（Q4 第一周）窗口里
    #    **一条 9 月数据都没有** ⇒ 左栏空 ⇒ 假红（09-30 跑则正常）。
    return build_stats(FakeSession(dataset()), today=TODAY)


def test_导出总欠款的行序_选了项目就按用户给的顺序():
    """⭐ 2026-09-28（用户口径）：**总欠款导出也能自己选项目 ＋ 定顺序**（像月度会大表那样）。

    行序口径（`service.order_project_ids`）：
      · **没选** ⇒ 按**项目展示名**升序（＝原来的行为，⛔ 不改变老用户看到的东西）；
      · **选了** ⇒ **严格按给它的顺序**；只保留"真有数"的项目（`cand`）；重复只取一次；
        解析不到的脏名字**跳过**（⛔ 别让一个脏名字把整张表顶掉）。
    """
    cand, by_wh = {11, 22, 33}, {"仓A": 11, "仓B": 22, "仓C": 33}
    label = {11: "B项目", 22: "A项目", 33: "C项目"}.__getitem__
    assert order_project_ids(cand, by_wh, [], label) == [22, 11, 33], "没选项目时应按展示名升序"
    assert order_project_ids(cand, by_wh, ["仓C", "仓A"], label) == [33, 11], "选了就按用户给的顺序"
    assert order_project_ids(cand, by_wh, ["仓A", "仓A", "不存在的仓"], label) == [11], \
        "重复的只取一次；解析不到的跳过"
    assert order_project_ids(cand, by_wh, ["仓B", "不存在的仓", "仓C"], label) == [22, 33], \
        "脏名字只跳过它自己，⛔ 不许把后面的都丢掉"


def test_期初行在欠款与台账两侧必须给同一个id():
    """⭐ 2026-09-28（用户走查：「期初占位行录入后点删除没反应」）。

    壳里「删除期初行」按钮挂在**台账行**上（拿的是 `ledger.sides[].opening_id`），而它要去
    `/api/m05/debt` 的 `openings[]` 那一侧取金额与项目 ⇒ **两侧必须给同一个 id**。
    ⚠️ 原来 `debt.openings[]` **根本不返回 id** ⇒ 壳只能填假值 `''` ⇒ 删除按钮**恒匹配不上 + 静默 return**
    = 用户看到的"点了没反应"。（同源缺陷的壳侧断言在 `tests/test_wired_m05.py`。）
    """
    led = _ledger()["sides"][0]
    ids = [o.get("id") for o in _debt()["openings"]]
    assert led.get("opening_id"), "台账侧没有 `opening_id` —— 删除按钮拿不到 id"
    assert led["opening_id"] in ids, (
        f"欠款侧 `openings[].id` 与台账 `opening_id` 对不上：{ids} vs {led['opening_id']}"
        " ⇒ 壳「删除期初行」会静默点不动")


def test_四份组装件都带自己的口径与指标区():
    """旧页的"五段骨架"是**页面形态**（随页消失）；它守的**实质**是"每份组装件都把口径 / 指标带上"
    —— 这一面在这里钉住：流水带 `kpis`、统计带 `layout`（左右栏口径）、欠款带三类、台账带两侧。"""
    assert _flows()["kpis"], "流水缺指标区"
    assert _stats()["layout"] == {"left": "by_project", "right": "timeline"}, "统计缺左右栏口径"
    assert [c["category"] for c in _debt()["by_category"]] == ["material", "mechanical", "jc"]
    assert [s["category"] for s in _ledger()["sides"]] == ["material", "mechanical"]


def test_台账两侧共用同一个项目选择器且无切换口径按钮():
    led = _ledger()
    assert led["shared_project_selector"] is True, "两侧没共用同一个项目选择器"
    assert led["has_switch_caliber_button"] is False, "出现了「切换口径」按钮（口径在域内核就是 False）"


def test_台账机械侧没有手填入口_辅材侧有():
    by = {s["category"]: s for s in _ledger()["sides"]}
    assert by["material"]["has_manual_input"] is True, "辅材侧少了手填入口"
    assert by["mechanical"]["has_manual_input"] is False, "机械侧不该有手填入口（「其他支出金额」是派生只读）"


def test_台账首行是期初且空月也出行():
    rows = _ledger()["sides"][0]["display_rows"]             # 页面与导出的统一行集合
    assert rows[0]["is_opening"] is True, "首行不是期初行"
    assert rows[0]["month"] == "2026-06" == _ledger()["sides"][0]["opening_default"]["cutoff_ym"]
    months = [r["month"] for r in rows if not r["is_opening"]]
    assert len(months) == len(set(months)), "月份重复"
    assert months == sorted(months), "月份不连续（空月必须也出行）"
    assert months[0] <= "2026-07" and "2026-08" in months, f"本桩应含空月 2026-08：{months}"


def test_流水默认走全部月份且撤销只对生效行有意义():
    """旧页那半（"默认当月" / "撤销表单只在生效行"）是**页面形态** ⇒ 搬到壳；这里钉**数据侧**：
    不传筛选 = 全部月份（约定 `year_month=""`）、不翻页、且每行都带 `status`（「生效 / 已撤销」由它定）。"""
    f = _flows(year_month="", status=None)
    assert f["paginated"] is False, "付款流水**不分页**（列表一次给全）"
    assert f["rows"], "没取到流水行"
    statuses = {r["status"] for r in f["rows"]}
    assert statuses <= {"effective", "revoked"} and "effective" in statuses, f"行的状态取值不对：{statuses}"


def test_统计页左右栏都在且默认按周():
    data = _stats()
    assert data["granularity"] == "week"                  # 默认**按周**
    assert data["layout"] == {"left": "by_project", "right": "timeline"}
    assert data["buckets"] and data["left"] and data["right"]


def test_流水列表不分页_空态那半在壳侧():
    data = build_flows(FakeSession({}), year_month="", status=None)   # ""=全部月份（约定）
    assert data["paginated"] is False
    assert data["rows"] == [], "空桩不该有行"
    # ⚠️ 2026-09-19（`§19` 批 3）：原先还断言空态行的 `colspan = 表头列数`（页面形态）；
    # 旧页删除（`D18`）后那半搬到壳 —— `test_wired_m05.py` 的空态断言 ✓。


def test_欠款页把三类与按项目都渲染出来():
    d = _debt()
    assert [c["label"] for c in d["by_category"]] == ["辅材", "机械", "集采"]
    assert d["total"] is not None
    keys = [p["label"] for p in d["by_project"]]
    assert any("未判定" in k for k in keys), "无归属的行必须**单列**（不并入任何小微）"
