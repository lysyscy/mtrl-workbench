"""集采供应商**自动匹配**（§6.6.3）的断言 —— `M5-5` 把判定从壳里搬到后端后的钉子。

⚠️ 为什么值得单独立文件钉它：这套规则里有一条 **"写错不报错、只是悄悄换了语义"** 的
   （`frags_of` 的片段长度 = `6 - level`）—— 壳里**真的写错过一次**（写成 `level + 2`，
   结果"等级越高片段越长"、先长后短的顺序失去意义，而代码照样跑）。
   ⇒ 那种错只有断言钉得住，所以这里连**每条等级的长度**都逐条验。

⚠️ 库级断言**一律非破坏**：端点 `sup-match` **只算不写**（不 commit）⇒ 用例末尾仍 `s.rollback()`。
"""

from __future__ import annotations

from app.core.db import session_scope
from app.mod01_projects import repository as pj_repo
from app.mod01_projects.models import TYPE_NORMAL
from app.mod03_notice.models import PaymentNotice
from app.mod03_notice.notice_api_router import SupMatchIn, api_sup_match
from app.mod03_notice.sup_match import LVL_NAMES, frags_of, match_of, pool_of
from app.mod11_jc.models import JcContract
from tests.acc_plugin import acc

WH = "__自检仓_供应商匹配__"


@acc()
def test_片段长度必须等于6减等级():
    """⚠️ 这条是**反向灵敏度**的重点目标：写错它不报错、只会悄悄改变等级语义。"""
    s = "河南安装集团"
    # ① 全名整体
    assert frags_of(s, 1) == [s], "1 级必须是**全名整体**（⛔ 不是滑窗）"
    # ② 4 字 / ③ 3 字 / ④ 2 字 —— **长度 = 6 - level**
    assert frags_of(s, 2)[0] == "河南安装" and len(frags_of(s, 2)[0]) == 4
    assert frags_of(s, 3)[0] == "河南安" and len(frags_of(s, 3)[0]) == 3
    assert frags_of(s, 4)[0] == "河南" and len(frags_of(s, 4)[0]) == 2
    # 滑窗**逐位平移**、且数量 = len - n + 1（写错区间会少一个/多一个）
    assert frags_of(s, 4) == ["河南", "南安", "安装", "装集", "集团"]
    assert len(frags_of(s, 4)) == len(s) - 2 + 1
    # ⚠️ 长度不足 ⇒ **空**（⛔ 不退化成全名、⛔ 不硬凑）
    assert frags_of("河南", 2) == [], "全名比片段短 ⇒ 该等级天然不可能命中"
    assert frags_of("", 3) == []
    assert LVL_NAMES == ("", "全名", "4 字片段", "3 字片段", "2 字片段"), "等级名与长度必须一一对应"


@acc()
def test_先长后短_高等级一命中就不看低等级():
    """⚠️ "先长后短"是这套算法的**全部意义**：若不这样做，2 字片段会把一堆无关供应商扯进来。"""
    pool = ["河南安装集团", "河南安装", "尚坤建设"]
    doc = "四分晋江污泥项目/主材钢材/尚坤/河南安装集团/27269.82元"
    r = match_of(doc, pool)
    assert r["level"] == 1, "全名整体命中 ⇒ 取 1 级（⛔ 不许退化到 2 字片段）"
    # ⚠️ **前缀关系在 1 级也构成歧义**：`"河南安装"` 是 `"河南安装集团"` 的前缀 ⇒ 两条全名**都**出现在
    #    单据名里 ⇒ 命中集是**两家**。这不是缺陷 —— 正是"多命中必须问人"那道闸要处理的情形。
    assert sorted(r["cands"]) == ["河南安装", "河南安装集团"], "同等级命中集全给出来（人的事，不是算法的事）"

    # ⚠️ 要验"4 字等级"，单据名里**不能出现全名**（否则 1 级就命中、根本轮不到 4 字）——
    #    这就是"反着匹配"的意义：简称在单据名里，全名不在。
    r2 = match_of("四分项目/主材钢材/河南安装/27269.82元", ["河南安装集团", "尚坤建设"])
    assert r2["level"] == 2, "全名不在、4 字片段在 ⇒ 取 2 级"
    assert r2["cands"] == ["河南安装集团"], "命中的是**全名**（人看的、要落库的是全名，不是片段）"

    # ⚠️ **同等级多命中 = 歧义** ⇒ 全给出来（由人定，⛔ 系统绝不取"最像的/第一个"）
    r3 = match_of("单据里有 尚坤 和 中建 两家", ["尚坤建设", "中建八局"])
    assert r3["level"] == 4 and sorted(r3["cands"]) == ["中建八局", "尚坤建设"], "2 字等级的两家都命中"

    assert match_of("", pool) == {"level": 0, "level_name": "", "cands": []}, "没单据名 ⇒ 不匹配"
    assert match_of("毫不相关的内容", pool) == {"level": 0, "level_name": "", "cands": []}, "0 命中"


@acc()
def test_候选池只取本项目且按全名去重():
    """⚠️ 不去重 ⇒ "一家被数成多家" ⇒ 多命中弹窗里出重复项、把"歧义"变成假的。"""
    rows = [
        {"project_key": WH, "supplier": "业祥"},
        {"project_key": WH, "supplier": "业祥"},          # 同供应商第二份合同 ⇒ 必须只算一次
        {"project_key": WH, "supplier": " 尚坤 "},        # 两侧空白要去掉
        {"project_key": WH, "supplier": ""},              # 空供应商 ⇒ 不进池
        {"project_key": "别人家仓", "supplier": "别家供应商"},   # 他项目 ⇒ 不进池
    ]
    pool = pool_of(rows, project_key=WH)
    assert pool == ["业祥", "尚坤"], f"本项目 + 去重 + 去空白，实际={pool}"
    assert pool_of(rows, project_key="") == [], "项目键为空 ⇒ 池为空（⛔ 不回落成「全库」）"


@acc()
def test_端点真跑一次_只算不写():
    """端到端：造 1 项目 + 1 合同 + 1 通知书 ⇒ 真调端点 ⇒ 命中并给出候选。"""
    with session_scope() as s:
        p = pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full=f"{WH}项目",
                                   warehouse_name=WH, phid="")
        s.flush()
        s.add(JcContract(project_id=int(p.id), contract_date="2026-09-19",
                         material_name="钢材", supplier="业祥建设"))
        # ⚠️ 单据名称在 `fields["BillName"]`（表无独立列）—— 端点也读这里，两边必须一致。
        n = PaymentNotice(ph_id="__自检_ph_供应商匹配__", doc_date="2026-09-18",
                          fields={"BillName": "四分自检项目/主材钢材/业祥/河南安装/100元"},
                          category="jc", ownership_id=int(p.id))
        s.add(n)
        s.flush()

        d = api_sup_match(SupMatchIn(notice_id=int(n.id)), session=s)
        assert d["ok"] is True and d["project_key"] == WH
        assert d["pool"] == ["业祥建设"], "池 = 本项目合同的供应商"
        assert d["cands"] == ["业祥建设"] and d["level_name"], f"应命中全名，实际={d}"

        # ⚠️ **只算不写**：本端点不得改动任何字段（落库一律走 jc-supplier）
        assert str(n.jc_supplier or "") == "", "端点不许顺手落库（预填须经人「采用」）"
        s.rollback()


@acc()
def test_写入集采实际供应商_列表必须读得回同一个值():
    """⭐ 2026-10-08 BUG 钉子（往返）：`jc-supplier` 写进去的值，**列表必须原样读回**。

    ⚠️ 为什么这条必须钉：`NoticeRow` 曾经**漏装** `jc_supplier` ⇒ `_row_dict` 的
    `getattr(..., "")` 兜底把缺口**静默变成空串** ⇒ 页面上那一格恒空、点「采用」反而清空，
    而后端全部回 `ok:true`、所有既有判据照样绿。
    ⇒ 这里既验「写得进」，也验「读得回」；`_row_dict` 已改为**直取**（漏装会当场红，不再兜空）。
    """
    from app.mod03_notice.notice_api_router import JcSupplierIn, api_jc_supplier, get_notice_list

    def _list(s):
        """走**真实列表端点**（前端那一格就是从它来的）—— 参数显式给全，⛔ 不吃 `Query(...)` 默认值。
        ⚠️ `period=""` = **全部时间**（`None` 会落"当月"默认值，判据会被日期漂移带偏）。"""
        return get_notice_list(period="", project=[], category="", approve_status="",
                               pay_status="", sort="", dir=0, session=s)["items"]

    nid = 0
    with session_scope() as s:
        p = pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full=f"{WH}往返项目",
                                   warehouse_name=WH, phid="")
        s.flush()
        n = PaymentNotice(ph_id="__自检_ph_供应商往返__", doc_date="2026-09-18",
                          fields={"BillName": "四分自检项目/主材钢材/业祥/100元"},
                          category="jc", ownership_id=int(p.id))
        s.add(n)
        s.commit()
        nid = int(n.id)

    try:
        # ① 写：走真实端点（`category="jc"` ⇒ `jc_supplier_problem` 放行）
        with session_scope() as s:
            w = api_jc_supplier(JcSupplierIn(notice_id=nid, supplier="  业祥建设  "), session=s)
        assert w["ok"] is True and w["supplier"] == "业祥建设", f"写入失败或没去空白：{w}"

        # ② 读：走**列表端点**（前端那一格就是从它来的）
        with session_scope() as s:
            items = _list(s)
        got = next((i for i in items if int(i["notice_id"]) == nid), None)
        assert got is not None, "刚写的那条没出现在列表里"
        assert got["jc_supplier"] == "业祥建设", \
            f"列表读回来的集采实际供应商不对（实际={got['jc_supplier']!r}）—— 这一格在页面上恒空就是它造成的"

        # ③ 清空也要读得回空串（否则「不采用」清不掉）
        with session_scope() as s:
            assert api_jc_supplier(JcSupplierIn(notice_id=nid, supplier=""), session=s)["ok"] is True
        with session_scope() as s:
            items = _list(s)
        got = next(i for i in items if int(i["notice_id"]) == nid)
        assert got["jc_supplier"] == "", f"清空后列表仍回 {got['jc_supplier']!r}"
    finally:
        # ⚠️ 本条**故意落库**（要跨会话往返）⇒ 自己收拾干净，⛔ 不能留给下一个用例
        with session_scope() as s:
            row = s.get(PaymentNotice, nid)
            if row is not None:
                s.delete(row)
            for r in list(s.query(pj_repo.Project).filter(
                    pj_repo.Project.warehouse_name == WH)):
                s.delete(r)
            s.commit()
