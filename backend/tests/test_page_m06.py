"""`MOD-06` **页面 / 组装层 ＋ 两条写路径**的工程自检（离线 · 不连库）。

⚠️ 本文件**不绑定 `ACC-*` 判据点**（`@acc()` 显式声明）：判据在 `test_acc_proc_001/002.py` 里
由纯函数钉住；本文件守的是**这一层新加的东西** ——
**机械手录区块**（§5.2.5 ③）与**历史导入三步**（§5.2.5 ①②）的页面形态、写路径与暂存载具。
"""

from __future__ import annotations

import copy
import re
from decimal import Decimal

import pytest

from app.core import preview_store
from app.core.errors import MustReportError
from app.mod06_proc import domain as D
from app.mod06_proc import importer, mech_ui, repository as repo
from app.mod06_proc.models import ProcHistoryBatch, ProcHistorySnapshot
from app.mod06_proc.service import build_page_data, build_import_data, parse_state
from app.mod08_inv.models import InvDetail
from tests.acc_plugin import acc
from tests.m06_helpers import (
    CUTOFF_YM,
    WAREHOUSE,
    FakeSession,
    dataset_sections,
    make_batch,
    make_snapshot,
    xlsx_bytes,
)

MAT_HEADER = ("核算月", "入库主辅材", "出库工具", "租分公司设备", "备注")


def _sess() -> FakeSession:
    return FakeSession(copy.deepcopy(dataset_sections()))


# ⚠️ 2026-09-18（`§19` 批 2）：`_page()`（取旧页 html）已随过程资料页删除 ⇒ 整件移除
#    （它只被上面那两条页面形态用例用过）。


def _by_month(s: FakeSession) -> dict[str, dict]:
    return {r["ym"]: r for r in build_page_data(s, parse_state({"pj": WAREHOUSE}))["rows"]}


def _xlsx(rows: list[list], header=MAT_HEADER) -> bytes:
    return xlsx_bytes(rows, header)


# ============================================================ 机械手录（§5.2.5 ③）
#
# ⚠️ 2026-09-18（`TAIL-27` · `§19` **批 2**）：过程资料页半边已删（授权 `D18`）——
#    · 「机械手录区块只给机械列输入框」＝**页面形态** ⇒ 搬壳：`test_wired_m06.py` 的
#      「机械录入口只送 mech 键 / 材料列没有输入面」；
#    · 「回执条必须转义」＝**旧页 PRG 的提示文案形态** ⇒ 随页作废（壳的 toast 一律过 `esc()`，
#      另有全站口径在守；这条旧页形态没有独立 claim）；
#    · 「历史导入入口在页面上」⇒ 归**仍在的**导入页那一段（见下方「历史导入」小节 ✓）。
#    保留下来的两条只碰**入参解析/落库**（与页面无关）✓。


@acc()
def test_机械手录入参解析_空按零_负数与非数字报错():
    """⚠️ 原先这条还借旧页 html 看「核算月带回 / 现值预填」；那是页面形态，旧页删后随之删掉，
    留下的**入参解析（空按 0 / 负数与非数字报错）与月份归一**是与页面无关的实质。"""

    zeros = {f"mech_{i}": Decimal("0.00") for i in range(len(D.MECH_COLUMNS))}
    assert mech_ui.parse_mech_values({}) == zeros, "空框按 0（0 是合法录入值）"
    assert mech_ui.parse_mech_values({"mech_0": "12.5"})["mech_0"] == Decimal("12.50")
    with pytest.raises(ValueError):
        mech_ui.parse_mech_values({"mech_0": "-1"})
    with pytest.raises(ValueError):
        mech_ui.parse_mech_values({"mech_0": "abc"})
    # 月份归一（唯一出口 = domain）
    assert D.normalize_ym("2026/8") == D.normalize_ym("202608") == "2026-08"
    assert D.normalize_ym("2026-13") == "" and D.normalize_ym("八月") == ""


@acc()
def test_机械手录落库后表内取到_且重抓重导都不覆盖():
    s = _sess()
    repo.save_mech(s, ym="2026-09", warehouse=WAREHOUSE,
                   values={**{f"mech_{i}": Decimal("0") for i in range(len(D.MECH_COLUMNS))},
                           "mech_0": Decimal("55.00")})
    assert _by_month(s)["2026-09"]["mech_0"] == Decimal("55.00")

    # ① 重抓 i8（库存单据整批改数）⇒ 手录值不动
    for r in s.by_model[InvDetail]:
        r.amount = Decimal("77777.00")
    assert _by_month(s)["2026-09"]["mech_0"] == Decimal("55.00"), "重抓不得动机械手录"
    # ② 重导历史（新批次快照）⇒ 手录值仍不动
    s.by_model[ProcHistoryBatch].append(make_batch("H-02"))
    s.by_model[ProcHistorySnapshot].append(make_snapshot(399, ym="2026-09", ins="1.00",
                                                        batch_no="H-02"))
    assert _by_month(s)["2026-09"]["mech_0"] == Decimal("55.00"), "重导不得动机械手录"
    # ③ ⭐ 2026-09-26 改口径（`TAIL-107`）：**历史段（2026-06 ≤ 截止月）不许手录**
    #    （那一格以"过程资料导入"的值为准）—— 改前这条断言是"历史段也照常可录"。
    assert not any(D.column_editable(k, ym="2026-06", cutoff_ym=CUTOFF_YM) for k in D.MECH_KEYS)
    assert all(D.column_editable(k, ym="2026-09", cutoff_ym=CUTOFF_YM) for k in D.MECH_KEYS), \
        "正式段仍可手录（用户原话：「机械费手录仅限于正式启用系统后」）"


# ⚠️ 原先还有一条 `test_机械手录回执条必须转义`（旧页 PRG 的 `msg` 参数反射）—— 随页作废：
#    壳的提示一律过分 `esc()`（全站口径），那条是**旧页形态专用**的回归，没有独立 claim。


# ============================================================ 历史导入（§5.2.5 ①②）


def _plan():
    rows = [
        ["2026-03", "1000.00", "20.00", "888.00", "原始台账"],
        ["2026-04", "2000.00", "", "999.00", ""],
    ]
    return importer.parse_sheet(_xlsx(rows))


@acc()
def test_历史导入按表头认列_机械列也导_异常行必报():
    """⭐ 2026-09-26（`TAIL-107`）**改口径**：**机械 6 列也导入**（进历史段快照）。

    ⚠️ 改前这条叫"机械列不导入"（口径：机械全段手录、导入只提示）—— 那条已作废；⛔ 别再改回去。
    """
    plan = _plan()
    assert plan.months == ["2026-03", "2026-04"] and plan.writable == 2
    assert plan.rows[0]["in_主辅材"] == Decimal("1000.00")
    assert plan.rows[0]["out_工具"] == Decimal("20.00")
    # ⭐ 机械列**进快照**（表头「租分公司设备」⇒ `mech_0`）
    assert plan.rows[0]["mech_0"] == Decimal("888.00")
    assert plan.rows[1]["mech_0"] == Decimal("999.00")
    # 认不出的列只提示、不算错（「备注」不属那 17 列）
    assert plan.unknown_headers == ["备注"]
    # 列序打乱也认得出（**不依赖位置**）
    shuffled = importer.parse_sheet(_xlsx([["20.00", "2026-03", "888", "1000.00"]],
                                          header=("出库工具", "核算月", "租分公司设备", "入库主辅材")))
    assert shuffled.rows[0]["in_主辅材"] == Decimal("1000.00")
    assert shuffled.rows[0]["mech_0"] == Decimal("888.00"), "机械列也一样不依赖位置"

    # 异常行逐条列出：月份认不出 / 金额非数字
    # ⚠️ **2026-09-22 用户裁定 ④**（"空行就是没数据"）：原第 3 行（只有核算月、无金额）**不再算异常**
    #    ⇒ 改判为"空行 ⇒ 跳过 ＋ 一条提示"（`ACC-PROC-IMPORT-001/001-05`）；异常由 3 行变 **2 行**。
    with pytest.raises(MustReportError) as bad:
        importer.parse_sheet(_xlsx([
            ["八月", "1.00", "", "", ""],
            ["2026-05", "—", "", "", ""],
            ["2026-06", "", "", "", ""],
        ]))
    assert "2 行异常" in str(bad.value) and "行 2" in str(bad.value), "报错要带上行号与原因"
    # 「空行 ⇒ 跳过」也要**看得见**（提示里点出行号），⛔ 不静默
    empty_plan = importer.parse_sheet(_xlsx([["2026-06", "", "", "", ""],
                                             ["2026-07", "5.00", "", "", ""]]))
    assert empty_plan.writable == 1 and not empty_plan.anomalies
    assert any("空行" in n and "行 2" in n for n in empty_plan.notes), empty_plan.notes

    # 一列材料列都没有 ⇒ 整份拒绝
    with pytest.raises(MustReportError):
        importer.parse_sheet(_xlsx([["2026-03", "1"]], header=("核算月", "备注")))


@acc()
def test_历史导入只写历史段_正式段与机械手录都不动():
    s = _sess()
    before_formal = _by_month(s)["2026-07"]["in_主辅材"]
    before_mech = _by_month(s)["2026-07"]["mech_0"]
    out = importer.commit(s, _plan(), warehouse=WAREHOUSE, batch="PROC-T1",
                          operator="科室用户", cutoff_ym=CUTOFF_YM)
    rows = _by_month(s)
    assert out["rows"] == 2 and out["cutoff_ym"] == CUTOFF_YM
    assert rows["2026-03"]["section"] == D.SECTION_HISTORY
    assert rows["2026-03"]["in_主辅材"] == Decimal("1000.00")
    assert rows["2026-04"]["out_工具"] is None or rows["2026-04"]["out_工具"] == Decimal("0.00")
    # 正式段与机械手录一格没动
    assert rows["2026-07"]["in_主辅材"] == before_formal
    assert rows["2026-07"]["mech_0"] == before_mech
    assert rows["2026-07"]["section"] == D.SECTION_FORMAL, "截止核算月被顺手挪了"


@acc()
def test_历史导入整批回滚后不再计入但不物理删():
    s = _sess()
    importer.commit(s, _plan(), warehouse=WAREHOUSE, batch="PROC-T2",
                    operator="科室用户", cutoff_ym=CUTOFF_YM)
    assert _by_month(s)["2026-03"]["in_主辅材"] == Decimal("1000.00")
    count = importer.rollback(s, batch_no="PROC-T2")
    assert count == 2
    assert "2026-03" not in _by_month(s), "回滚后该月连行都不该再有（历史段不回落 i8）"
    kept = [x for x in s.by_model[ProcHistorySnapshot] if x.batch_no == "PROC-T2"]
    assert len(kept) == 2, "回滚**不物理删**（留痕）"


@acc()
def test_核对报告列出不回落i8的月份():
    s = _sess()
    # 2026-05 在 i8 里有数据（9999）、快照里也有 ⇒ 不算空；把 2026-05 从快照里去掉再看
    s.by_model[ProcHistorySnapshot] = [r for r in s.by_model[ProcHistorySnapshot]
                                       if r.ym != "2026-05"]
    report = importer.check_report(s, warehouse=WAREHOUSE, batch_no="H20260916-01",
                                   cutoff_ym=CUTOFF_YM)
    assert report["count"] == 1 and report["rows"] == ["2026-05"]
    assert report["months"] == ["2026-06"], "报告里的「本批月份」= 生效批次覆盖到的月份"


# ============================================================ 暂存载具（两个导入页共用）


@acc()
def test_预览暂存不落库且两个导入页共用同一载具():
    token = preview_store.save({"rows": [{"ym": "2026-03"}]})
    assert preview_store.load(token)["rows"] == [{"ym": "2026-03"}]
    # ⚠️ 「取不到」这条分支要用**形态合法但不存在**的 token 才测得到 ——
    #    用中文串 / 带斜杠的串会**先被 token 形态校验拦掉**，测的其实是别的东西（反向灵敏度揪出来的）
    with pytest.raises(MustReportError):
        preview_store.load("deadbeefdeadbeef")
    with pytest.raises(MustReportError):
        preview_store.load("../etc/passwd")            # 路径穿越 ⇒ 直接拒
    # `MOD-05` 的付款导入走**同一个**载具（此前是它自己的一份 `_dump/_load`）
    # ⚠️ 2026-09-21（`§19` 四个暂留件收口）：编排函数搬进 `import_api.py`；
    # ⭐ 2026-09-23（`TAIL-75` `B5b` 第三步 · **用户裁定 `B`**）：`import_api.py` **连件删除**、
    #    壳 `V.m05imp` **已下架** ⇒ 付款导入改由**通用面**承接 ⇒ **判词不变**（"付款导入走同一个载具、
    #    ⛔ 不自带一份暂存"），只把落点换成通用面那一份 —— 后端这半钉两件：
    #    ① 域钩子确实挂在通用面上（有 `preview` ⇒ 预览也走通用面）；
    #    ② 域内判定仍是**纯函数**、不依赖会话写（`_plan_of` 可离线跑；`known_notices` 是只读出口）。
    from tests.shell_src import SHELL                     # noqa: PLC0415

    from app.mod05_flow import imp_spec
    from app.mod05_flow import importer as m05

    assert imp_spec.HOOKS.preview is not None and imp_spec.HOOKS.commit is not None, \
        "付款域必须挂在通用面上（否则它就没有导入入口了）"
    assert "/api/imp/" in SHELL and "impDomain" in SHELL, "壳的付款导入口没接上通用面"

    plan = imp_spec._plan_of([{"_row": 2, "单据号": "FKTZS2026090466", "付款金额": "3000.00",
                              "付款时间": "2026-08-05", "付款方式": "现汇", "备注": ""}])
    assert plan.rows[0].amount == Decimal("3000.00")
    assert plan.rows[0].bill_no == "FKTZS2026090466"
    assert m05.known_notices(FakeSession({})) == {}


# ============================================================ 导入页（三步）


@acc()
def test_历史导入页三步齐备且带项目与截止月():
    """导入页**齐全**：三步（选文件 → 预览 → 确认）＋ 项目（键 = 仓库名）＋ 当前截止核算月 ＋ 列说明。

    ⚠️ 2026-09-21（`§19` 四个暂留件收口）：页面搬进新壳 ⇒ 分两半钉住（同「形态变、判据不变」）：
      ① **后端给的数据**（项目候选 / 截止核算月 / 列说明）—— 来自 `service.build_import_data`
         ＋ `import_api`（⛔ 壳里不许另算一份）；
      ② **壳把三步与这些数据都画出来**、且上传走**通用导入面**的 `/api/imp/m06_proc/parse`
         （⛔ 2026-09-23 `B5c-2`：`/api/m06/import/*` 五条旧端点已退休）。
    """
    from tests.shell_src import SHELL            # noqa: PLC0415  ← `P4`① 读取点收敛

    s = _sess()
    data = build_import_data(s, warehouse=WAREHOUSE)
    assert data["warehouse"] == WAREHOUSE, "项目（键 = 仓库名）没带出来"
    assert data["cutoff_ym"] == CUTOFF_YM, "当前截止核算月要显示出来"

    # ⚠️ 2026-09-23（`TAIL-75` `B5c-2`）：`import_api.api_meta()` 随五条旧端点**一起退休** ⇒
    #    「材料列清单 / 不采哪些列」改从**域声明**（`imp_spec.SPEC`）出 —— 判词不变
    #    （"列清单从域口径出，⛔ 壳里不许另抄一份"），只是**唯一出口**换成了通用面的那一份。
    #    ⭐ 2026-09-26（`TAIL-107`）：**机械列从"不采"挪到"目标字段"**（要导）——「不采」只剩「序号」。
    from app.mod06_proc import imp_spec

    mats = [f.label for f in imp_spec.FIELDS if f.key in D.MATERIAL_KEYS]
    assert "入库主辅材" in mats, "材料列清单要从域口径出（壳里不许另抄一份）"
    # ⭐ 2026-09-26（`TAIL-107`）**改口径**：机械 6 列**要导**（进历史段快照）⇒ 它们是**目标字段**，
    #    ⛔ 不再落在「明确不采」里。改前这条断言恰是 `set(D.MECH_COLUMNS) <= ignored`。
    fields = {f.label for f in imp_spec.FIELDS}
    assert set(D.MECH_COLUMNS) <= fields, "机械 6 列要从域口径出（它们现在是目标字段）"
    ignored = {lb for lb, _ in imp_spec.SPEC.ignored}
    assert not (set(D.MECH_COLUMNS) & ignored), "机械 6 列不许再出现在「明确不采」里（那是旧口径）"
    assert ignored == {"序号"}, "「明确不采」现在只剩「序号」（行号，系统自己编）"

    # ⚠️ 2026-09-22（`TAIL-75` `B5c`）：画这三步的**是「数据导入」页**（通用导入面），旧 `V.m06imp` 已下架 ——
    #    **判词不变**（"壳把三步与后端给的数据都画出来"），落点换到通用面：
    assert "/api/imp/" in SHELL and "impDomains" in SHELL, "壳的上传口没接上通用导入面"
    assert "/api/imp/${encodeURIComponent(domain)}/parse" in SHELL, "上传口要指到通用面的 parse"
    # ⚠️ 2026-09-26（`TAIL-103`）：「项目」从**自造的原生下拉**（`data-act="impPj"`）换成
    #    **共用面板 `projPanel`（单选）**，且那一栏改成**按域声明的键渲染**（`IMP.hasCut`）——
    #    **判词不变**（"壳把项目与截止核算月都画出来"），落点换成面板的展开动作。
    assert 'data-act="impPjToggle"' in SHELL and 'id="impCut"' in SHELL, "项目（仓库名）与截止核算月没画出来"
    for must in ("选域与文件", "列映射", "预览校验", "确认落库"):
        assert must in SHELL, f"壳的导入流程少了这一步：{must}"


# ============================================================ 机械 6 列的有效值（`TAIL-107`）


@acc()
def test_接口按分界月给机械值_历史段读快照():
    """⭐⭐ 2026-09-26（`TAIL-107`）：`GET /api/m06/mech` 给的是机械 6 列的**有效值**（**按段切来源**）。

    ⚠️ 为什么必须钉住它：壳里十几处都吃这一份（过程资料 17 列 / 活动大表 / **机械结算 = `m05` 欠款** /
    台账候选）⇒ 它给错，用户看到的机械费就错。
    ⚠️ 改前它只回**手录值**（旧口径"全段手录"）—— 而历史段的手录值**页面根本不读**（读快照）
      ⇒ 那种"录了却不显示"的错配，正是本届口径要堵的。
    ⭐ 判据里刻意塞了一条**历史段的旧手录行**（99.00，绕过挡板直接写模型，模拟改口径之前留下的数据）
      ⇒ 读到的必须是**快照值 11.00**，⛔ 不是 99.00（"以导入值为准"不是口号）。
    """
    import uuid

    from sqlalchemy import select as _sel

    from app.core.db import session_scope
    from app.mod06_proc import repository as repo
    from app.mod06_proc.models import ProcCutoff, ProcHistoryBatch, ProcHistorySnapshot, ProcMechManual
    from app.mod06_proc.router import api_mech

    h = "__自检仓_MECHAPI_H_" + uuid.uuid4().hex[:6] + "__"       # 历史段（有快照值 ＋ 一条旧手录）
    f = "__自检仓_MECHAPI_F_" + uuid.uuid4().hex[:6] + "__"       # 正式段（只有手录）
    ym_h, ym_f = "2026-05", "2026-09"
    try:
        with session_scope() as s:
            repo.import_snapshot(s, warehouse=h, rows=[{"ym": ym_h, "mech_0": Decimal("11.00")}],
                                 batch_no="PROC-API-" + uuid.uuid4().hex[:6], operator="自检",
                                 cutoff_ym="2026-06")
            repo.save_mech(s, ym=ym_f, warehouse=f, values={"mech_0": Decimal("22.00")})
            s.add(ProcMechManual(ym=ym_h, warehouse_name=h, mech_0=Decimal("99.00")))  # 旧口径遗留
            s.flush()

        got = api_mech()
        assert got["mech"][h][ym_h][0] == 11.0, \
            f"历史段要读**快照值**（那条 99.00 的旧手录不该被读到）：{got['mech'][h]}"
        assert got["mech"][f][ym_f][0] == 22.0, "正式段要读**手录值**"
        assert got["sections"][h][ym_h] == D.SECTION_HISTORY, "段要如实给（壳据此拦住历史段手录）"
        assert got["sections"][f][ym_f] == D.SECTION_FORMAL
    finally:
        with session_scope() as s:
            for r in list(s.execute(_sel(ProcHistorySnapshot)).scalars()):
                if r.warehouse_name == h:
                    s.delete(r)
            for r in list(s.execute(_sel(ProcHistoryBatch)).scalars()):
                if r.warehouse_name == h:
                    s.delete(r)
            for r in list(s.execute(_sel(ProcCutoff)).scalars()):
                if r.warehouse_name == h:
                    s.delete(r)
            for r in list(s.execute(_sel(ProcMechManual)).scalars()):
                if r.warehouse_name in (h, f):
                    s.delete(r)
