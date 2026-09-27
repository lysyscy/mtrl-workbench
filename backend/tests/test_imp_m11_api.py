"""`m11` 集采台账 · **通用导入面**端到端（`TAIL-75` · `B5b`）—— 第三个真域挂上 `/api/imp/*`。

⭐ 钉三件：
1. **两级表头拼名在通用面上也认得出**（`供应商` › `合同总价` ⇒ `供应商合同总价`）—— 这是真台账的形态；
2. ⭐ **匹配口径复用同一个函数**（`import_service.match_and_apply`）：锚点 = **含税合同价**、范围 = 单个项目
   ⇒ 命中 1 条就更新它 ＋ 补汇总发票行；**同源重跑不翻倍**（已有同 kind 发票行 ⇒ 跳过并报出来）；
3. **项目必填**（不给 ⇒ 显式拒绝）；⭐ `TAIL-98`（2026-09-25）起本域**有** `rollback` 端点
   （整批回滚 · 批次号形如 `JC-YYYYMMDDHHMMSS`）—— 幽灵批次号必须**显式报错**（⛔ 禁静默）。

⚠️ 会**真写库** ⇒ 仓库名取随机值（持久测试库）。
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
# ⚠️ 先注册表（独立 app ⇒ 不导入就有 FK 解析不到的风险）
from app.mod01_projects import models as _pj_models  # noqa: F401
from app.mod11_jc import imp_spec
from tests.acc_plugin import acc
from tests.imp_contract import assert_skipped_contract

#: 真台账形态：r2 一级（`供应商`/`贸易公司` 各合并两列）· r3 二级（合同总价 / 发票金额）
R2 = ["序号", "合同日期", "材料名称", "供应商", "", "贸易公司", "", "详细付款方式", "备注"]
R3 = ["", "", "", "合同总价", "发票金额", "合同总价", "发票金额", "", ""]
MERGES = [("A1", "I1"), ("D2", "E2"), ("F2", "G2")]
AMT = "42799.80"


def _book(rows: list[tuple] | None = None) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "台账"
    ws.append(["晋江污泥处理项目集采台账"])
    ws.append(list(R2))
    ws.append(list(R3))
    for row in (rows if rows is not None else [(1, "20240723", "钢材", AMT, "40731.17",
                                                "42885.40", "40812.62", "电汇", "60±7银行承兑")]):
        ws.append(list(row))
    for a, b in MERGES:
        ws.merge_cells(f"{a}:{b}")
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(imp_api, "current_operator", lambda: "导入自检")
    app = FastAPI()
    app.include_router(imp_api.build_router(imp_spec.SPEC, imp_spec.HOOKS,
                                            store=ProfileStore(tmp_path / "p.json")))
    return TestClient(app)


def _parse(client):
    return client.post("/api/imp/m11_jc/parse",
                       files={"file": ("台账.xlsx", _book(),
                                       "application/vnd.openxmlformats-officedocument"
                                       ".spreadsheetml.sheet")},
                       data={"sheet": ""}).json()


@acc("ACC-IMP-MAP-001", "001-12")
def test_集采台账在通用面端到端_两级拼名认列_锚点匹配_且幂等(client):
    """⭐ 第三个真域：两级拼名认列 → 预览 → 按**合同价锚点**匹配更新 → 再落一次**发票不翻倍**。"""
    from app.core.db import session_scope
    from app.mod01_projects import repository as pj_repo
    from app.mod01_projects.models import TYPE_NORMAL
    from app.mod11_jc.models import JcContract, JcInvoice

    got = _parse(client)
    assert got["ok"] and got["header_rows"] == [2, 3], got
    cols = {c["src"]: c for c in got["cols"]}
    assert cols["供应商合同总价"]["field"] == "供应商合同总价", "两级拼名要认得出（合并格只铺表头行）"
    assert cols["贸易公司发票金额"]["field"] == "贸易公司发票金额"
    assert cols["详细付款方式"]["field"] == "付款方式"
    assert {c["src"] for c in got["cols"] if c["ignored"]} == {"序号"}, "「序号」要显式说明不采"

    wh = "__自检仓_IMP_M11_" + uuid.uuid4().hex[:8] + "__"
    with session_scope() as s:
        p = pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full="__自检_B5b_台账__",
                                   warehouse_name=wh, phid="")
        s.add(JcContract(contract_no="__自检_B5b_C1__", project_id=int(p.id),
                         contract_date="2024-07-23", material_name="i8给的材料名",
                         supplier="i8给的供应商", contract_amt=Decimal(AMT)))
    mapping = {"合同日期": "合同日期", "材料名称": "材料名称", "供应商合同总价": "供应商合同总价",
               "供应商发票金额": "供应商发票金额", "贸易公司合同总价": "贸易公司合同总价",
               "贸易公司发票金额": "贸易公司发票金额", "详细付款方式": "付款方式", "备注": "备注"}
    body = {"token": got["token"], "mapping": mapping, "options": {"project_key": wh}}
    pre = client.post("/api/imp/m11_jc/preview", json=body).json()
    assert pre["ok"] and pre["total"] == 1, pre

    out = client.post("/api/imp/m11_jc/commit", json=body).json()
    assert out["ok"] and out["report"]["updated"] == 1, out
    assert out["report"]["unmatched"] == 0 and out["report"]["ambiguous"] == 0, out["report"]
    # ⭐ 2026-09-26（用户报障「**落库结果可读性比较差**」）：回执还必须**自报人话指标**（`kpis`）——
    #    通用面只画它（⛔ 不再把 `updated`/`undo_rows`/`message` 这些**程序用的键名**铺一排）；
    #    ⚠️ 词必须与 `preview` **完全一样**（配上 / 配不上 / 同价冲突 / 不合格）—— 同一个数不换说法。
    kpi = out["report"]["kpis"]
    assert kpi["配上并更新"] == 1 and kpi["配不上"] == 0, f"回执没自报人话指标：{kpi!r}"
    assert kpi["同价冲突"] == 0 and kpi["不合格"] == 0 and "提醒" in kpi, f"`kpis` 少项：{kpi!r}"
    assert out["report"]["items"][0]["fields"], "要报出这次更新了哪几列（Excel 的地盘）"

    again = client.post("/api/imp/m11_jc/commit", json=body).json()
    assert again["report"]["warned"] >= 1, f"同源重跑必须报「已有发票行 ⇒ 不重复加」：{again['report']}"
    with session_scope() as s:
        inv = s.query(JcInvoice).filter(JcInvoice.contract_id == out["report"]["items"][0]["id"]).count()
    assert inv == 2, f"一合同两张汇总发票行（供应商/贸易公司），重导不翻倍：{inv}"


@acc()
def test_预览就能看到配上几条_且一个字节都不写库(client):
    """⭐⭐ 2026-09-26（`TAIL-106` · 用户裁定）：**③ 预览**就要说出「**能配上几条**」。

    用户原话：「匹配既然凭合同金额／贸易公司合同金额，为什么放到**最后一步**？能否在**选文件时**
    就选定项目、并**立刻显示"匹配上多少"**？」

    ⚠️ 本判据盯**两件**（少一件都会出问题）：
      ① **数对不对**：库里有一条同价合同 ⇒ 那一行配上；另给一行**对不上的价** ⇒ 列进"没配上"；
      ② ⭐ **零写库**：预览走 `match_and_apply(dry_run=True)` —— 它**只分类、不写**
         （`update_contract` / `fill_contract_amt_if_blank` / `_add_invoice` 三处全跳过）。
         实测办法：**预览前后**把那张合同的那 6 列 ＋ **发票行数**各比一遍，必须一模一样。
    """
    from app.core.db import session_scope
    from app.mod01_projects import repository as pj_repo
    from app.mod01_projects.models import TYPE_NORMAL
    from app.mod11_jc import import_service as IS
    from app.mod11_jc.models import JcContract, JcInvoice

    wh = "__自检仓_IMP_PRE_" + uuid.uuid4().hex[:8] + "__"
    with session_scope() as s:
        p = pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full="__自检_预览对号__",
                                   warehouse_name=wh, phid="")
        c = JcContract(contract_no="__自检_预览_C1__", project_id=int(p.id),
                       contract_date="2024-07-23", material_name="i8给的材料名",
                       supplier="i8给的供应商", contract_amt=Decimal(AMT))
        s.add(c)
        s.flush()
        cid = int(c.id)

    def _snap() -> tuple:
        with session_scope() as s:
            row = s.get(JcContract, cid)
            cols = tuple(str(getattr(row, k) or "") for k in IS.EXCEL_COLS + ("contract_amt",))
            inv = s.query(JcInvoice).filter(JcInvoice.contract_id == cid).count()
        return cols + (inv,)

    before = _snap()
    mapping = {"合同日期": "合同日期", "材料名称": "材料名称", "供应商合同总价": "供应商合同总价",
               "供应商发票金额": "供应商发票金额", "详细付款方式": "付款方式", "备注": "备注"}
    # 第二行：合同价与库里那条**不同** ⇒ 必须落进"配不上"（⛔ 不静默新增、⛔ 不猜）
    book = _book([(1, "20240723", "钢材", AMT, "40731.17", "", "", "电汇", "60±7银行承兑"),
                  (2, "20240724", "水泥", "999.00", "", "", "", "", "")])
    got2 = client.post("/api/imp/m11_jc/parse",
                       files={"file": ("台账.xlsx", book,
                                       "application/vnd.openxmlformats-officedocument"
                                       ".spreadsheetml.sheet")},
                       data={"sheet": ""}).json()
    assert got2["ok"], got2
    body = {"token": got2["token"], "mapping": mapping, "options": {"project_key": wh}}
    pre = client.post("/api/imp/m11_jc/preview", json=body).json()
    assert pre["ok"], pre
    assert pre["writable"] == 1, f"「将写入」必须 = **真会更新的条数**（不是解析出的 2 行）：{pre}"
    assert pre["kpis"]["配上"] == 1 and pre["kpis"]["配不上"] == 1, pre.get("kpis")
    # ⭐ 2026-09-26（用户报障「**这些不会落库的行，要在行上直接标**……而不是还要抬头去看文字说明」）：
    #    预览必须**自报逐行名单**（`skipped`）—— 通用面靠它把「不写入」标在**那一行**上。
    #    ⚠️ 本域口径：不写进去的 = **配不上 ＋ 同价冲突 ＋ 不合格**（`提醒` **不算** —— 那些行是写进去的）。
    assert_skipped_contract(pre, expect=(pre["kpis"]["配不上"] + pre["kpis"]["同价冲突"]
                                         + pre["kpis"]["不合格"]))
    miss = [b for b in pre["blocks"] if "没配上" in b["title"]]
    assert miss and len(miss[0]["rows"]) == 1, f"配不上的行要逐条列出来（带原因）：{pre.get('blocks')}"
    assert "999.00" in " ".join(str(x) for x in miss[0]["rows"][0]), miss[0]["rows"][0]
    assert _snap() == before, "⛔ 预览把库改了 —— 预览必须**只查不写**（判据 001-06）"


@acc()
def test_没选项目时预览不给假的配对数(client):
    """⚠️ 台账按项目分存 ⇒ **没选项目**时一条都对不了号；此时**不许**给出"配上 0 条"这种假数。

    ⇒ 判词：预览**不给** `writable`（界面上的「将写入」退回通用面的行数），只回一句"还没选项目"的提示块。
    """
    got = _parse(client)
    pre = client.post("/api/imp/m11_jc/preview",
                      json={"token": got["token"], "mapping": {"合同日期": "合同日期"}}).json()
    assert pre["ok"], pre
    assert "writable" not in pre, f"没选项目却给了「将写入」—— 那是假话：{pre}"
    assert any("还没选" in b["title"] for b in pre["blocks"]), pre.get("blocks")


@acc()
def test_老xls也能读_按魔术字节判类型():
    """⭐ 用户的集采台账是**老 `.xls`** ⇒ 通用面必须两种格式都认（⛔ 且**不靠文件名**）。

    （真 `.xls` 的端到端在实测里验过：两份真台账走通用面各认出 12/11 列、真未认出 0；
      本件钉的是**判型逻辑**——⛔ 别为了"省事"改成看后缀。）
    """
    from app.core.errors import MustReportError
    from app.import_kit.readers import _kind, read_grid

    assert _kind(b"PK\x03\x04rest") == "xlsx"
    assert _kind(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1rest") == "xls"
    assert _kind(b"hello world") == ""
    with pytest.raises(MustReportError) as bad:
        read_grid(b"hello world")
    assert "后缀" in str(bad.value), "非 Excel 的文件要给一句明白话（说的是**按内容判**）"


@acc()
def test_项目必填_且回滚端点已挂并显式报错(client):
    """⚠️ 匹配范围 = 单个项目 ⇒ 不给项目就明确拒绝；⭐ `TAIL-98` 起 rollback 端点**已挂**
    （`SPEC.batch=True` ＋ `HOOKS.rollback` ⇒ 通用面自己挂上），幽灵批次号必须**说人话**。"""
    got = _parse(client)
    out = client.post("/api/imp/m11_jc/commit",
                      json={"token": got["token"], "mapping": {"合同日期": "合同日期"}}).json()
    assert out["ok"] is False and "项目" in out["message"], out
    rb = client.post("/api/imp/m11_jc/rollback", json={"batch": "JC-19700101000000"})
    assert rb.status_code == 200, "端点必须在（通用面按 `hooks.rollback` 挂）"
    body = rb.json()
    assert body["ok"] is False and "找不到批次" in body["message"], body


@acc()
def test_域上下文端点在_且候选项目只给非空键(client):
    """⭐ 2026-09-26（用户报障截图里的 `[object Object]`）：本域的域上下文必须**走通用面**、且只给**候选键**。

    报障链路：本域原先**没有** `options` 钩子 ⇒ 壳只好单开一条**域号分支**去调**域专属读端点**
      `/api/m11/list`（= `repository.project_choices()` 的**对象** `{"key","display"}`），
      而壳里写的是 `(p && p.key) || String(p)` —— `key` 是**空串**（项目没记仓库名，**库里真有 3 条**）
      时落到 `String(对象)` ⇒ 下拉里是 `[object Object]`，**选中即报「找不到项目」**。

    ⇒ 两条一起钉：
      ① 本域的 `/options` **在**、且**只给候选键**（⛔ 不许再给对象 —— 那正是坏选项的土壤）；
      ② 档案里 `key` 为空的那些项目**根本不进候选**（⛔ 不靠壳里兜底：坏值能进到界面，
         就一定会有人选中它）。
    """
    from app.core.db import session_scope
    from app.mod11_jc import repository as R

    r = client.get("/api/imp/m11_jc/options")
    assert r.status_code == 200, "域上下文端点必须在（壳里零域号分支，全靠这一条问上下文）"
    got = r.json()
    assert got["ok"] is True, got
    keys = got.get("projects")
    assert keys, "没给候选项目 ⇒ 通用面上根本选不了项目（可本域落库**必须要**它）"
    bad = [k for k in keys if not (isinstance(k, str) and k.strip())]
    assert not bad, f"候选键里混进了空键 / 非字符串：{bad}（渲染到界面上就是 `[object Object]`）"
    with session_scope() as s:
        choices = R.project_choices(s)
    empties = [c for c in choices if not str(c.get("key") or "").strip()]
    assert len(keys) == len(choices) - len(empties), (
        f"候选该 = 档案里**有仓库名**的那些（实测空键 {len(empties)} 条，一条都不许进候选）")
    assert set(got) - {"ok", "projects"} == set(), \
        f"域上下文只该给候选键（⛔ 别塞 `display` 之类的对象）—— 多给了：{set(got) - {'ok', 'projects'}}"


@acc("ACC-IMP-MAP-001", "001-12")
def test_贸易公司合同凭贸易公司金额对号_供应商价空才填_且能整批回滚(client):
    """⭐⭐ 2026-09-26（用户报障「贸易公司合同落错列」⇒ 他裁定的**方案②**）：

    贸易公司合同的「合同金额」（= 供应商价）在 i8 里**根本没有**、按设计**留空**
    ⇒ 拿它当钥匙**永远配不上**（Excel 里那个真供应商价永远进不来）
    ⇒ 现在改用「**贸易公司合同金额**」当钥匙（对号 Excel 的「贸易公司合同总价」），
    对上后把 Excel 的「**供应商合同总价**」**空才填**进台账「合同金额」。

    ⚠️ **能证伪**：把 `match_and_apply` 的锚点索引改回"只有 `by_amt` 一张表" ⇒ 本条必红（配不上）。
    ⚠️ 一并钉三半：① 空 ⇒ 填；② **已有值 ⇒ ⛔ 不覆盖**（§9.3「人工改过的不被覆盖」）；
       ③ **整批回滚要把它也还原**（回滚点原先只记那 6 列 ⇒ 会"回滚了但金额没回"）。
    """
    from sqlalchemy import select

    from app.core import timing
    from app.core.db import session_scope
    from app.mod01_projects import repository as pj_repo
    from app.mod01_projects.models import TYPE_NORMAL
    from app.mod11_jc.models import JcContract, JcInvoice

    trade_amt, sup, sup2 = "42885.40", "150000.00", "999999.00"
    # ⚠️ **编号必须每次唯一**：`contract_no` 是全库按值查的（`one_by_no`），留个固定串
    #    就会让**上一轮失败运行留下的旧行**被 `.first()` 取到 ⇒ 断言看的是别人的行
    #    （2026-09-26 实测踩到：库里旧行的材料名还是老值 ⇒ 假红）。同仓惯例：自检数据取随机名。
    no = "__自检_B5b_T1_" + uuid.uuid4().hex[:8] + "__"
    mapping = {"合同日期": "合同日期", "材料名称": "材料名称", "供应商合同总价": "供应商合同总价",
               "供应商发票金额": "供应商发票金额", "贸易公司合同总价": "贸易公司合同总价",
               "贸易公司发票金额": "贸易公司发票金额", "详细付款方式": "付款方式", "备注": "备注"}
    wh = "__自检仓_IMP_M11T_" + uuid.uuid4().hex[:8] + "__"
    with session_scope() as s:
        p = pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full="__自检_贸易公司合同__",
                                   warehouse_name=wh, phid="")
        s.add(JcContract(contract_no=no, project_id=int(p.id), contract_date="2025-11-14",
                         material_name="电缆桥架", supplier="江苏万有电气科技有限公司",
                         party_name="洛阳维萨工程技术有限公司", contract_amt=Decimal("0"),
                         trade_co="洛阳维萨工程技术有限公司", trade_contract_amt=Decimal(trade_amt)))

    def run(sup_amt: str, mat: str) -> dict:
        got = client.post("/api/imp/m11_jc/parse",
                          files={"file": ("台账.xlsx", _book([(1, "20251114", mat, sup_amt, "1000",
                                                              trade_amt, "0", "电汇", "")]),
                                          "application/octet-stream")},
                          data={"sheet": ""}).json()
        assert got["ok"], got
        body = {"token": got["token"], "mapping": mapping, "options": {"project_key": wh}}
        return client.post("/api/imp/m11_jc/commit", json=body).json()

    out = run(sup, "电缆桥架")
    assert out["ok"] and out["report"]["updated"] == 1, out
    assert out["report"]["unmatched"] == 0, out["report"]
    assert out["report"]["items"][0]["matched_by"] == "trade", "这一行该是**靠贸易公司金额**对上的"
    with session_scope() as s:
        c = s.execute(select(JcContract).where(JcContract.contract_no == no)).scalars().first()
        assert Decimal(str(c.contract_amt)) == Decimal(sup), "空 ⇒ 把 Excel 的供应商价填进「合同金额」"
        assert Decimal(str(c.trade_contract_amt)) == Decimal(trade_amt), "贸易公司金额不被导入改"
        assert c.supplier == "江苏万有电气科技有限公司", "i8 的事实列一个字不改"
        # ⭐ 新加的发票行：**发票日期 = 操作当天**（2026-09-26 用户裁定：
        #    「新加的发票行的发票日期，**不要用合同日期，用操作时的日期**」）
        inv = s.execute(select(JcInvoice).where(
            JcInvoice.contract_id == int(out["report"]["items"][0]["id"]))).scalars().first()
        assert inv is not None, "「供应商发票金额」那一列要往发票子表**加一张票**"
        assert inv.invoice_date == timing.to_iso(timing.today_cn()), (
            f"发票日期该 = **操作当天**（{timing.to_iso(timing.today_cn())}），实得 {inv.invoice_date!r}")
        assert inv.invoice_date != "2025-11-14", "⛔ 不许再拿合同日期当发票日期"
        assert Decimal(str(inv.amount)) == Decimal("1000")

    out2 = run(sup2, "电缆桥架（改）")            # 第二遍：合同金额**已有值** ⇒ ⛔ 不许覆盖
    assert out2["ok"] and out2["report"]["updated"] == 1, out2
    assert out2["report"]["items"][0]["contract_amt_filled"] is False, "已有值还去写 = 覆盖"
    with session_scope() as s:
        c = s.execute(select(JcContract).where(JcContract.contract_no == no)).scalars().first()
        assert Decimal(str(c.contract_amt)) == Decimal(sup), "⛔ 已有值被覆盖了"
        assert c.material_name == "电缆桥架（改）", "那 6 列照旧能覆盖（口径未变）"

    rb = client.post("/api/imp/m11_jc/rollback",
                     json={"batch": out2["report"]["batch"]}).json()
    assert rb["ok"], rb
    with session_scope() as s:
        c = s.execute(select(JcContract).where(JcContract.contract_no == no)).scalars().first()
        assert Decimal(str(c.contract_amt)) == Decimal(sup), "回滚第二遍：金额回到第一遍之后的值"
        assert c.material_name == "电缆桥架", "那 6 列已还原（原有行为不变）"
