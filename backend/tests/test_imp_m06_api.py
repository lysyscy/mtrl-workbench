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

    wh = "__自检仓_IMP_M06_" + uuid.uuid4().hex[:8] + "__"
    body["options"] = {"warehouse": wh}
    out = client.post("/api/imp/m06_proc/commit", json=body).json()
    # ⚠️ 2 行（不是 3）：第三行**材料列全空**（只填了机械列）⇒ 按域内口径当空行跳过（见 `_rows()` 的 ⚠️）
    assert out["ok"] and out["report"]["rows"] == 2, out
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
    tip = next((b for t, b in blocks.items() if t.startswith("不导入的行")), None)
    assert tip and any("合计/小计行" in r[0] for r in tip["rows"]), \
        f"合计/小计行没算成「跳过」（提示）—— 它不该混进「落不了库」里：{tip}"
    assert any("说明行" in r[0] for r in tip["rows"]), tip
    # ⚠️ **说明行不许再被报成"必填为空 ⇒ 需处理"**（2026-09-26：同一行两个说法 —— 域说"不导入"、
    #    通用面说"需处理"，用户会去追一条根本不用管的问题。真文件里那行是 Excel 第 7 行）
    assert all(p["row"] != 7 for p in pre["problems"]), \
        f"说明行（Excel 第 7 行）被报成了要处理的问题：{pre['problems']}"

    # ③ 落库：只写能写的那两行，且回执说清少写了一行
    # ⚠️ **批号显式给**：默认批号是 `PROC-<yyyymmddHHMMSS>`（**秒**）—— 同秒两次落库会撞唯一约束
    #    （本件就踩到了：前一条判据刚提交、这条在同一秒里 ⇒ `UniqueViolation`）。那条真缺陷另登了尾巴。
    wh = "__自检仓_ODD_" + uuid.uuid4().hex[:8] + "__"
    out = client.post("/api/imp/m06_proc/commit",
                      json={**body, "token": token,
                            "options": {"warehouse": wh,
                                        "batch": "PROC-ODD-" + uuid.uuid4().hex[:8]}}).json()
    assert out["ok"] and out["report"]["rows"] == 2, out
    assert out["report"]["不写入的行数"] == 1, \
        f"④ 回执没说清少写了几行 —— 用户会以为全导进去了：{out['report']}"
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
def test_schema_不给机械列目标字段(client):
    """⭐ 口径：机械 6 列**全段手录** ⇒ 通用面里根本不给它们字段（界面不会让他们落库）。"""
    sch = client.get("/api/imp/m06_proc/schema").json()
    labels = {f["label"] for f in sch["fields"]}
    assert "核算月" in labels and {"入库主辅材", "出库周转材料"} <= labels
    assert not (labels & {"租分公司设备", "内租设备", "外租零租含税"}), "机械列不许出现在目标字段里"
    assert sch["batch"] is True and "机械 6 列不导入" in sch["keep_note"]


@acc("ACC-IMP-MAP-001", "001-09")
def test_机械列落进明确不采_而不是未认出(client):
    """⭐ 「**认得出但按口径不采**」与「**系统不认识**」必须分开 —— 否则界面上看着像系统漏了列。
    （`B5-0` 实测逼出来的：机械 6 列早先落进"未认出"，用户会一列列去点。）"""
    got = _parse(client).json()
    ignored = {x["src"]: x["why"] for x in got["ignored"]}
    assert "分公司设备" in ignored and "机械 6 列" in ignored["分公司设备"], got["ignored"]
    assert "序号" in ignored, "序号也是「认得出、系统自己编」那一类"
    by_src = {c["src"]: c for c in got["cols"]}
    assert "机械 6 列" in by_src["分公司设备"]["ignored"]
    assert by_src["分公司设备"]["field"] is None, "不采的列不给目标字段"
    assert by_src["时间"]["ignored"] == "" and by_src["时间"]["field"] == "核算月"
