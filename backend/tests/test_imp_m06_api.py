"""`m06` 过程资料 · **通用导入面**端到端（`TAIL-75` · `B5-0`）—— 第一个真域挂上 `/api/imp/*`。

⭐ 本件钉三件事：
1. **端到端能跑**：`schema → parse（挑表/认列）→ preview → commit → rollback`；
2. **落库口径 = 既有出口**：钩子只是把 records 装成 `ImportPlan` 再调 `importer.commit`
   （→ `repository.import_snapshot`）⇒ 历史段行数说得清、整批可回滚；
3. ⭐ **统一面上三条老口径不许走样**：**空 ≠ 0**（没填的不写）· **负数照收**（`D25` ①）·
   **机械 6 列不导入**（`FIELDS` 里就没有它们 ⇒ 界面不会给出可落库的目标字段）。

⚠️ 落库会**真写库**（走真 `session_scope`）⇒ 用**随机仓库名**（持久测试库，写死会撞唯一约束）+ 跑完整批回滚。
"""

from __future__ import annotations

import io
import uuid
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.import_kit import api as imp_api
from app.import_kit.profile_store import ProfileStore
from tests.imp_contract import assert_skipped_contract
# ⚠️ 必须先把 `project` 等表导进来：本件用的是**独立 FastAPI app**（不经过 `app.main`）⇒
#    少一次导入，`proc_history_snapshot.project_id` 的外键就解析不到表（`NoReferencedTableError`，实测踩到）。
from app.mod01_projects import models as _pj_models  # noqa: F401
from app.mod06_proc import imp_spec
from tests.acc_plugin import acc

#: 两级表头（r2 分组头 ＋ r3 叶子）；`时间` = 核算月（真文件里那列叫「时间」）
R2 = ["序号", "时间", "线上入库（不含税）", "", "", "", "线下出库（不含税）", "", "", "",
      "分公司设备"]
R3 = ["", "", "主辅材", "工具", "劳保", "周转材料", "主辅材", "工具", "劳保", "周转材料", ""]
MERGES = [("C2", "F2"), ("G2", "J2")]


def _book(rows: list[tuple] | None = None) -> bytes:
    """真文件形态：r1 标题 / r2 分组头（合并格）/ r3 叶子 / r4 起数据。"""
    wb = Workbook()
    ws = wb.active
    ws.title = "汇总表"
    ws.append(["项目材料设备工机具采购、消耗汇总表"])
    ws.append(list(R2))
    ws.append(list(R3))
    for row in (rows if rows is not None else _rows()):
        ws.append(list(row))
    for a, b in MERGES:
        ws.merge_cells(f"{a}:{b}")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _rows():
    """三行：正常行 · 含**负数**（红字/冲销，`D25` ①）· 材料列**全空**（= 没填，不是 0）。

    ⚠️ 第三行（`45507` 那一行）**只填了机械列**、材料 10 列全空 —— 2026-09-26 起它**不进快照**
    （按域内口径当「空行」跳过：`material 一行都没有 ⇒ 没有可落库的数据`）⇒ 落库 **2 行**、
    「默认截止核算月」也跟着变成 **2024-07**（被跳过的那个月不再参与"最大月"的推断）。
    ⛔ **别只写"只有月份"的空行**：那会在历史段里**凭空多一个全 0 的月份**（"空 ≠ 0"）。
    ⭐ `TAIL-107`（机械费也要从过程资料导入）落地后，这一行**会重新变成数据**（它有机械金额）——
       届时本件这两处期望要**同批**改回 3 行 / `2024-08`，那正是"机械列有值就算数据"的判据。
    """
    return [
        (1, 45444, 5006.98, 595, 5994, "", 12000, 100, 200, "", 1100),
        (2, 45475, "1125913.87", "-7579.56", "27668.13", "", "1600986.05", "173286", "29840.7",
         "", "9748.83"),
        (3, 45507, "", "", "", "", "", "", "", "", ""),          # 只填了机械列 ⇒ 材料全空
    ]


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(imp_api, "current_operator", lambda: "导入自检")
    app = FastAPI()
    app.include_router(imp_api.build_router(imp_spec.SPEC, imp_spec.HOOKS,
                                            store=ProfileStore(tmp_path / "p.json")))
    return TestClient(app)


def _parse(client, sheet: str = "", book: bytes | None = None):
    """解析一份表（默认 `_book()`；`book` 给了就用它 —— 见下面"不合规核算月"那条判据）。"""
    return client.post("/api/imp/m06_proc/parse",
                       files={"file": ("汇总表.xlsx", _book() if book is None else book,
                                       "application/vnd.openxmlformats-officedocument"
                                       ".spreadsheetml.sheet")},
                       data={"sheet": sheet})


@acc("ACC-IMP-MAP-001", "001-08")
def test_通用面端到端_认列到落库再到回滚(client):
    """⭐ 第一个真域挂上通用面：挑表 / 认列（两级拼名 ＋ 序列号核算月）/ 预览 / 落库 / 整批回滚。"""
    got = _parse(client).json()
    assert got["ok"] and got["sheet"] == "汇总表" and got["header_row"] == 2, got
    cols = {c["src"]: c for c in got["cols"]}
    assert cols["时间"]["field"] == "核算月", "真模板里那列叫「时间」"
    assert cols["线上入库（不含税）主辅材"]["field"] == "入库主辅材", "两级拼名要认得出"
    assert not any(c["field"] and "外租" in c["field"] for c in got["cols"]), "机械列不给目标字段"

    body = {"token": got["token"],
            "mapping": {"时间": "核算月", "线上入库（不含税）主辅材": "入库主辅材",
                        "线下出库（不含税）主辅材": "出库主辅材"}}
    pre = client.post("/api/imp/m06_proc/preview", json=body).json()
    assert pre["ok"] and pre["total"] == 3, pre
    first = pre["preview"][0]
    assert first["核算月"] == "2024-06", "Excel 序列号 45444 ⇒ 2024-06"
    assert first["出库主辅材"] == "12000.00"
    # ⭐ 2026-09-26（用户报障「**这些不会落库的行，要在行上直接标**……而不是还要抬头去看文字说明」）：
    #    预览必须**自报逐行名单**（`skipped` = 行号 ＋ 人话原因）—— 通用面靠它把「不写入」标在**那一行**上。
    #    ⚠️ 契约三条（m04/m05/m11 同款）：是 list · **条数与 `不写入的行` 一致** · 每项带行号与人话原因。
    assert_skipped_contract(pre,
                            expect_bad=pre["kpis"]["不写入的行"],
                            expect_skip=pre["kpis"]["本来就跳过（合计/说明/空行）"])

    wh = "__自检仓_IMP_M06_" + uuid.uuid4().hex[:8] + "__"
    body["options"] = {"warehouse": wh}
    out = client.post("/api/imp/m06_proc/commit", json=body).json()
    # ⚠️ 2 行（不是 3）：第三行**材料列全空**（只填了机械列）⇒ 按域内口径当空行跳过（见 `_rows()` 的 ⚠️）
    assert out["ok"] and out["report"]["rows"] == 2, out
    # ⭐ 2026-09-26（用户报障「**落库结果可读性比较差**」）：回执还必须**自报人话指标**（`kpis`）——
    #    通用面只画它（⛔ 不再把 `cutoff_ym` 这类**程序用的键名**铺一排给用户看）。
    kpi = out["report"]["kpis"]
    assert kpi["写入行数"] == 2 and kpi["不写入的行数"] == 0, f"回执没自报人话指标：{kpi!r}"
    assert out["report"]["cutoff_ym"] == "2024-07", \
        "默认截止核算月 = **能落库的那些**里最大那个（被跳过的那一行不参与）"

    back = client.post("/api/imp/m06_proc/rollback",
                       json={"batch": out["report"]["batch"]}).json()
    assert back["ok"] and back["report"]["revoked"] == 2, back


@acc()
def test_统一面上三条老口径不许走样(client):
    """⭐ **空 ≠ 0**（没填的不落库）· **负数照收**（`D25` ①）—— 通用面与域内必须一致。"""
    got = _parse(client).json()
    body = {"token": got["token"], "mapping": {"时间": "核算月", "线上入库（不含税）主辅材": "入库主辅材",
                                              "线上入库（不含税）工具": "入库工具"}}
    pre = client.post("/api/imp/m06_proc/preview", json=body).json()
    rows = pre["preview"]
    assert rows[1]["入库工具"] == "-7579.56", "负数照收（红字/冲销是定稿事实）"
    assert rows[2]["入库主辅材"] == "", "**没填**就回空串（⛔ 不是 0.00 —— 那是凭空多一笔）"
    assert "不是数字" not in " ".join(p["reason"] for p in pre["problems"]), pre["problems"]


@acc()
def test_缺项目选项要显式报错_不静默落库(client):
    """⚠️ 过程资料按项目分存 ⇒ 没选项目就**明确拒绝**（⛔ 不许落到"没项目"的桶里）。"""
    got = _parse(client).json()
    out = client.post("/api/imp/m06_proc/commit",
                      json={"token": got["token"],
                            "mapping": {"时间": "核算月", "线上入库（不含税）主辅材": "入库主辅材"}}).json()
    assert out["ok"] is False and "项目" in out["message"], out


@acc()
def test_每个项目的截止月各给一份_换项目不会串():
    """⭐ 2026-09-26（**真缺陷修复**）：界面上的「截止核算月」**按项目存**（`repository.load_cutoff`），
    而落库会把它**写进所选项目**（`importer.commit` → `import_snapshot(cutoff_ym=…)`）。

    ⚠️ 症状（改之前）：域上下文**只在进域那一刻**取一次（取的是"候选人里的第一个"）
    ⇒ 用户**换成别的项目时那个框不跟着换** ⇒ **A 项目的分界被写给 B，而且不报错**。
    ⇒ 修法：域上下文**把每个项目的那一格都给出来**（`cutoffs`），壳按当前选中项取。
    本判据点钉的就是"这张表**逐项目**都在"（⛔ 只给一格 = 缺陷会复发）。
    """
    from sqlalchemy import select

    from app.core.db import session_scope
    from app.mod06_proc import imp_spec as spec
    from app.mod06_proc import repository as repo
    from app.mod06_proc.models import ProcCutoff

    a = "__自检仓_CUT_A_" + uuid.uuid4().hex[:6] + "__"
    b = "__自检仓_CUT_B_" + uuid.uuid4().hex[:6] + "__"
    with session_scope() as s:
        repo.set_cutoff(s, warehouse=a, cutoff_ym="2026-05")
        repo.set_cutoff(s, warehouse=b, cutoff_ym="2026-07")
        s.flush()
        opts = spec.options(s)                     # ⭐ 域钩子 = 壳唯一能看到的那一份
        assert opts["cutoffs"].get(a) == "2026-05", opts.get("cutoffs")
        assert opts["cutoffs"].get(b) == "2026-07", "两个项目必须各给一份（⛔ 不是只给「当前那个」）"
        assert repo.load_cutoffs(s).get(b) == "2026-07"
        for r in list(s.execute(select(ProcCutoff)).scalars()):   # 持久测试库：随手清干净
            if r.warehouse_name in (a, b):
                s.delete(r)


@acc()
def test_截止核算月认不出要拒_含糊写法归一(client):
    """⭐ 2026-09-26（用户报「**截止核算月的格式要求一下吧**」）—— 要求写清了，就得**有人执行**：

    ⚠️ 改前这一格**原样入库**（`cutoff_ym` 直接写进 `proc_cutoff`）—— 写个 `八月` 也能静默存进去，
      而**分段是按字符串比的**（`ym <= cutoff`）⇒ 分段会悄悄错（表现成"某个月莫名其妙算到另一段"）。
    判词两半：① 认不出的**当场拒**（说清要什么形态）；② 含糊但能认的（`2026/8`）**照收并归一**成 `2026-08`。
    """
    from sqlalchemy import select as _sel

    from app.core.db import session_scope
    from app.mod06_proc.models import ProcCutoff, ProcHistoryBatch, ProcHistorySnapshot

    mapping = {"时间": "核算月", "线上入库（不含税）主辅材": "入库主辅材"}
    whs = ["__自检仓_CUT_X_" + uuid.uuid4().hex[:6] + "__",
           "__自检仓_CUT_Y_" + uuid.uuid4().hex[:6] + "__"]

    def _commit(cut, wh):
        g = _parse(client).json()                       # ⚠️ 每次提交用**自己的 token**（token 是一次性的）
        return client.post("/api/imp/m06_proc/commit",
                           json={"token": g["token"], "mapping": mapping,
                                 "options": {"warehouse": wh, "cutoff_ym": cut,
                                             "batch": "PROC-CUT-" + uuid.uuid4().hex[:8]}}).json()

    try:
        bad = _commit("八月", whs[0])
        assert bad["ok"] is False, bad
        assert "YYYY-MM" in bad["message"] and "截止核算月" in bad["message"], \
            f"拒绝要说清「要什么形态」（守则 §5.5）：{bad['message']}"
        ok = _commit("2026/8", whs[1])
        assert ok["ok"], ok
        assert ok["report"]["cutoff_ym"] == "2026-08", \
            f"含糊写法要**归一**成 YYYY-MM 再入库：{ok['report']['cutoff_ym']}"
    finally:
        with session_scope() as s:
            for model in (ProcHistorySnapshot, ProcHistoryBatch, ProcCutoff):
                for r in list(s.execute(_sel(model)).scalars()):
                    if getattr(r, "warehouse_name", "") in whs:
                        s.delete(r)


@acc()
def test_同一秒两次落库各自拿到批号(client):
    """⭐ 2026-09-26（`TAIL-108`）：默认批号 = `PROC-<yyyymmddHHMMSS>`（**秒**）⇒ **同一秒两次落库**
    会撞 `proc_history_batch.batch_no` 的唯一约束，用户看到 `导入失败：IntegrityError …重复键违反唯一约束`
    （**天书**；守则 §5.5 不让这么报）。

    ⚠️ 诱因很自然：**连点两次「④ 确认落库」** —— 壳侧同批加了"提交期间禁用 ④"，但**脚本 / 接口绕得过界面**
      ⇒ 后端也要兜（`imp_spec._batch_no`：撞了就补 `-2`）。
    判词：**不显式给批号**、连着提交两次 ⇒ **两次都成功**、且批号**不同**。
    """
    g1 = _parse(client).json()
    g2 = _parse(client).json()
    mapping = {"时间": "核算月", "线上入库（不含税）主辅材": "入库主辅材"}
    wh = "__自检仓_TAIL108_" + uuid.uuid4().hex[:8] + "__"
    out1 = client.post("/api/imp/m06_proc/commit",
                       json={"token": g1["token"], "mapping": mapping,
                             "options": {"warehouse": wh}}).json()
    out2 = client.post("/api/imp/m06_proc/commit",
                       json={"token": g2["token"], "mapping": mapping,
                             "options": {"warehouse": wh}}).json()
    assert out1["ok"] and out2["ok"], (out1, out2)
    b1, b2 = out1["report"]["batch"], out2["report"]["batch"]
    assert b1 and b2 and b1 != b2, f"同一秒两次落库拿到同一个批号（会撞唯一约束）：{b1} / {b2}"
    back = client.post("/api/imp/m06_proc/rollback", json={"batch": b2}).json()
    assert back["ok"], back


@acc()
def test_机械列导入落进历史段_并能被读到(client):
    """⭐⭐ 2026-09-26（`TAIL-107`）**端到端**：机械 6 列从 excel **导进来** ⇒ 落**历史段快照** ⇒ 读得到。

    用户原话：「导入过程资料，**机械费也要导进去**，机械费手录仅限于正式启用系统后，
    历史机械费都填在过程资料 excel 里」—— 本件钉的就是这条链**通了**（改前机械列被过滤掉，
    导进来的只有材料 10 列）。
    """
    from app.core.db import session_scope
    from app.mod06_proc import repository as repo

    got = _parse(client).json()
    # 「分公司设备」= 机械第一列（`mech_0`）的别名之一 —— 它现在**是目标字段**
    by_src = {c["src"]: c for c in got["cols"]}
    assert by_src["分公司设备"]["field"] == "租分公司设备", by_src["分公司设备"]
    body = {"token": got["token"],
            "mapping": {"时间": "核算月", "线上入库（不含税）主辅材": "入库主辅材",
                        "分公司设备": "租分公司设备"}}
    wh = "__自检仓_MECH_" + uuid.uuid4().hex[:8] + "__"
    out = client.post("/api/imp/m06_proc/commit",
                      json={**body, "options": {"warehouse": wh,
                                                "batch": "PROC-MECH-" + uuid.uuid4().hex[:8]}}).json()
    assert out["ok"], out
    with session_scope() as s:
        rows = [r for r in repo.load_history(s) if r.get("warehouse") == wh]
        assert rows, "历史段快照里没有这一批"
        assert any(r.get("mech_0") for r in rows), \
            f"机械列**没落进快照** —— 用户要导的机械费丢了：{rows}"
        assert [r["mech_0"] for r in rows if r.get("mech_0")], "机械第一列的值要对上"
        # 清干净（持久测试库：随手删掉本件造的批次与快照）
        from app.mod06_proc.models import ProcHistoryBatch, ProcHistorySnapshot, ProcCutoff
        from sqlalchemy import select as _sel
        for r in list(s.execute(_sel(ProcHistorySnapshot)).scalars()):
            if r.warehouse_name == wh:
                s.delete(r)
        for r in list(s.execute(_sel(ProcHistoryBatch)).scalars()):
            if r.warehouse_name == wh:
                s.delete(r)
        for r in list(s.execute(_sel(ProcCutoff)).scalars()):
            if r.warehouse_name == wh:
                s.delete(r)


@acc()
def test_合计与说明行跳过_不合规核算月不收_且在预览就报出来(client):
    """⭐⭐ 2026-09-26（用户报障收口 · 原话「**不合规的核算月文本不收**，我说了正式导入的时候会改成
    标准格式」＋「**合计说明行跳过**」）。

    ⭐ 这条判据钉的是**用户那次"走到最后才知道"**的真因：④ 报「第 19 行的核算月认不出」，
       而 ③ 预览**一个字都没说**（只报了一条无关的行）⇒ 预览与落库**必须是同一个函数**
       （`importer.plan_rows`）算出来的数。

    判词（三半，缺一半都不算）：
      ① ③ 就要给出「**能写入几行**」＋ 把**落不了库的行（行号 ＋ 原因）**列出来；
      ② **合计/小计行 · 说明行**算"跳过"（**提示**），⛔ 不算"落不了库"（否则用户以为是自己填错了）；
      ③ ④ 落库**只写能写的那些**，回执里也要说清**少写了几行**（⛔ 不许只在 ③ 说过）。
    ⚠️ **反向灵敏度**：把那条文本月换成标准写法 ⇒ 它就得能写（证明拦的是"认不出"，不是"有合计行"）。
    """
    rows = [
        (1, 45444, 5006.98, 595, 5994, "", 12000, 100, 200, "", 1100),        # 合规
        (2, "2025年9月（一标）", 100, "", "", "", 200, "", "", "", 0),           # ✗ 核算月不是标准格式
        ("", "小计", 5106.98, 595, 5994, "", 12200, 100, 200, "", 1100),       # 合计/小计行 ⇒ 跳过
        ("", "说明：6月总出库也多了53.54", "", "", "", "", "", "", "", "", ""),   # 说明行 ⇒ 跳过
        (3, 45507, 700, "", "", "", "", "", "", "", ""),                      # 合规
    ]
    body = {"token": "", "mapping": {"时间": "核算月", "线上入库（不含税）主辅材": "入库主辅材",
                                     "线下出库（不含税）主辅材": "出库主辅材"}}

    def _prev(book):
        got = _parse(client, book=book).json()
        assert got["ok"], got
        return client.post("/api/imp/m06_proc/preview",
                           json={**body, "token": got["token"]}).json(), got["token"]

    pre, token = _prev(_book(rows))
    assert pre["ok"] and pre["total"] == 5, pre
    assert pre.get("writable") == 2, (
        f"能写入的应只有**两行合规行**（合计/说明行不许算进去）—— 拿到 {pre.get('writable')!r}；"
        "③ 没给这个数 = 域的预览钩子没接上（用户又只能走到 ④ 才知道）")
    blocks = {b["title"]: b for b in pre["blocks"]}
    bad = next((b for t, b in blocks.items() if t.startswith("⚠️ 落不了库的行")), None)
    assert bad, f"③ 没报出「落不了库的行」—— 用户又要走到 ④ 才知道：{list(blocks)}"
    assert [r[0] for r in bad["rows"]] == [5], f"落不了库的行号不对（应是 Excel 第 5 行）：{bad['rows']}"
    assert "核算月认不出" in bad["rows"][0][1]
    tip = next((b for t, b in blocks.items() if t.startswith("本来就跳过的行")), None)
    assert tip, f"③ 没报出「本来就跳过的行」—— 那几行在表里就没标记：{list(blocks)}"
    assert [r[0] for r in tip["rows"]] == [6, 7], \
        f"跳过行的**行号**不对（小计 = 第 6 行 · 说明 = 第 7 行）：{tip['rows']}"
    assert all("不用你改" in r[1] for r in tip["rows"]), \
        f"跳过行的原因必须说清「不用你改」（否则用户以为是自己文件的问题）：{tip['rows']}"
    # ⭐⭐ 2026-09-27（用户报障 · 原话「**请将所有不写入输出的行也进行标注**」）：**逐行**名单里
    #    这两类都要有，且**分开**（壳按 `kind` 给两种标记 —— 合成一种，用户会以为合计行也要自己改）。
    sk = {(x["row"], str(x.get("kind") or "bad")) for x in pre["skipped"]}
    assert (5, "bad") in sk, f"落不了库的那一行（第 5 行）要带 `kind=bad`：{sorted(sk)}"
    assert (6, "skip") in sk and (7, "skip") in sk, \
        f"合计/小计行与说明行（第 6、7 行）要带 `kind=skip`（**也要在行上标**）：{sorted(sk)}"
    assert pre["kpis"]["本来就跳过（合计/说明/空行）"] == 2, (
        f"「本来就跳过」的数与 `skipped` 对不上（守则 §4.7：同一页同一个数不换说法）：{pre['kpis']}")
    # ⚠️ **说明行不许再被报成"必填为空 ⇒ 需处理"**（2026-09-26：同一行两个说法 —— 域说"不导入"、
    #    通用面说"需处理"，用户会去追一条根本不用管的问题。真文件里那行是 Excel 第 7 行）
    assert all(p["row"] != 7 for p in pre["problems"]), \
        f"说明行（Excel 第 7 行）被报成了要处理的问题：{pre['problems']}"

    # ③ 落库：只写能写的那两行，且回执说清少写了一行
    # ⚠️ 这里**不显式给批号**（2026-09-26 `TAIL-108` 修好后不必再绕）—— 同秒撞批号由
    #    `imp_spec._batch_no` 兜（撞了自动补 `-2`）；那条缺陷的判据见本件末尾。
    wh = "__自检仓_ODD_" + uuid.uuid4().hex[:8] + "__"
    out = client.post("/api/imp/m06_proc/commit",
                      json={**body, "token": token, "options": {"warehouse": wh}}).json()
    assert out["ok"] and out["report"]["rows"] == 2, out
    assert out["report"]["不写入的行数"] == 1, \
        f"④ 回执没说清少写了几行 —— 用户会以为全导进去了：{out['report']}"
    assert out["report"]["本来就跳过的行数"] == 2, \
        f"④ 回执要把「本来就跳过」（合计/说明行）**分开**报（与 ③ 同一个数）：{out['report']}"
    # ⚠️ 顶上那句数字**必须是真写进去的行数**（原来是"解析出多少行"：5 行里只写 2 行，却说"已导入 5 行"）
    assert "已导入 2 行" in out["message"], \
        f"回执头一句的数字不是**真写入**的行数（实测晋江那份：写 24 行却说「已导入 32 行」）：{out['message']}"
    assert any(b["title"].startswith("⚠️ 落不了库的行") for b in out["report"].get("blocks") or []), \
        "④ 回执里没有「落不了库的行」—— 只在 ③ 说过的信息，到落库后就断了"
    back = client.post("/api/imp/m06_proc/rollback",
                       json={"batch": out["report"]["batch"]}).json()
    assert back["ok"] and back["report"]["revoked"] == 2, back

    # ⭐ 反向灵敏度：把那条文本月换成标准写法 ⇒ 三行全能写（拦的是"认不出"，不是别的）
    ok_rows = [rows[0], (2, 45475, 100, "", "", "", 200, "", "", "", 0)] + rows[2:]
    pre2, _ = _prev(_book(ok_rows))
    assert pre2["writable"] == 3, f"改成标准写法后应能写 3 行：{pre2.get('writable')}"
    assert not [b for b in pre2["blocks"] if b["title"].startswith("⚠️ 落不了库的行")], \
        "标准写法下不该再有「落不了库的行」"


@acc()
def test_schema_机械列也是目标字段(client):
    """⭐⭐ 2026-09-26（`TAIL-107`）**改口径**：机械 6 列**也是目标字段**（要落进历史段快照）。

    ⚠️ 改前这条断言是**反的**（"不给机械列目标字段" —— 旧口径"机械全段手录"），那条已作废；
       ⛔ 别再用"机械列不许出现在目标字段里"当判据（那会把用户要导的东西挡在门外）。
    """
    sch = client.get("/api/imp/m06_proc/schema").json()
    labels = {f["label"] for f in sch["fields"]}
    assert "核算月" in labels and {"入库主辅材", "出库周转材料"} <= labels
    assert {"租分公司设备", "内租设备", "外租零租含税", "外租包月含税",
            "外租零租不含税", "外租包月不含税"} <= labels, "机械 6 列要在目标字段里（它们要导）"
    assert sch["batch"] is True
    assert "序号" in sch["keep_note"], "「不采」那一栏现在只剩「序号」这类"
    assert "机械 6 列不导入" not in sch["keep_note"], "还留着旧口径那句话（机械列现在要导）"


@acc("ACC-IMP-MAP-001", "001-09")
def test_序号落进明确不采_机械列是目标字段(client):
    """⭐ 「**认得出但按口径不采**」与「**系统不认识**」必须分开 —— 否则界面上看着像系统漏了列。

    ⭐ 2026-09-26（`TAIL-107`）**改口径**：**机械列从"不采"挪到"目标字段"**（要导）；
      「不采」那一档现在只剩 `序号`（行号，系统自己编）—— 这条判据的**形态**没变、**成员**变了。
    """
    got = _parse(client).json()
    ignored = {x["src"]: x["why"] for x in got["ignored"]}
    assert "序号" in ignored, "序号是「认得出、系统自己编」那一类"
    assert not [x for x in got["ignored"] if "机械" in x["why"]], \
        f"机械列**不许**再落进「不采」（它们要导）：{got['ignored']}"
    by_src = {c["src"]: c for c in got["cols"]}
    assert by_src["序号"]["field"] is None, "不采的列不给目标字段"
    assert by_src["分公司设备"]["field"] == "租分公司设备", "机械列现在是**目标字段**（要落库）"
    assert by_src["时间"]["ignored"] == "" and by_src["时间"]["field"] == "核算月"


@acc()
def test_导入候选要能选到只有档案行的项目_页面口径不许跟着改(client):
    """⭐⭐ 2026-09-27（用户裁定 · `TAIL-114`）——**两处候选口径刻意不同**（⛔ 别再合并成一处）：

    · **导入页**（`build_import_data` ⇒ `GET /api/imp/m06_proc/options`）＝ **项目档案里的全部
      （含归档）∪ 有数据的**。为什么：**"导历史资料"这件事本身**才是给项目造历史段的手段 ——
      若候选只看「库存单据里出现过的仓库名」，**一个还没有任何数据的项目永远选不到 ⇒ 它的历史
      永远导不进去**（自我锁死＝鸡生蛋；实测 17 个有仓库名的档案项目里 **8 个选不到**）。
    · **过程资料页**（`projects_of`）＝ 仍只列**有数据的**（用户原话：「过程资料**本身**可以只显示
      仓库有数据项目没问题」）⇒ 那条口径**不许**跟着改。

    ⚠️ 反证：把 `build_import_data` 里的 `import_projects(s)` 写回 `projects_of(...)` ⇒ 本件必红
      （那正是 2026-09-27 改前的形态）。
    """
    from sqlalchemy import select

    from app.core.db import session_scope
    from app.mod01_projects.models import Project
    from app.mod06_proc import service as SV
    from app.mod06_proc.repository import load_history, load_inv_rows

    wh = "__自检仓_导入候选_" + uuid.uuid4().hex[:8] + "__"          # 随机名：持久测试库，写死会撞
    with session_scope() as s:
        s.add(Project(project_type="normal", warehouse_name=wh, name_full=wh,
                      disp="导入候选自检", status="active"))
    try:
        with session_scope() as s:
            imp = SV.build_import_data(s, warehouse="")["projects"]
            page = SV.projects_of(load_inv_rows(s), load_history(s))
        assert wh in imp, (
            "**导入页**的候选里没有「只有档案行、没有任何数据」的项目 —— 那正是本条的病："
            "导历史本身就是给它造数据的手段 ⇒ 候选只看'有数据的'就**永远锁死**（`TAIL-114`）")
        assert wh not in page, (
            "**过程资料页**的候选把它也带上了 —— 用户 2026-09-27 明确「过程资料本身可以只显示"
            "仓库有数据的项目没问题」⇒ 页面那条口径**不许**跟着改（两处**刻意**不同）")
        got = client.get("/api/imp/m06_proc/options").json()
        assert wh in (got.get("projects") or []), (
            f"通用导入面的 `options` 没给全候选（{len(got.get('projects') or [])} 个）—— "
            "导入页选不到它，历史资料就永远导不进去")
    finally:
        with session_scope() as s:
            row = s.execute(select(Project).where(Project.warehouse_name == wh)).scalar_one_or_none()
            if row is not None:
                s.delete(row)
