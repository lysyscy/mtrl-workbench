"""`TAIL-298`：`m11` 的列**有身份** —— 列清单一个主人（`domain.JC_COLUMNS`）、导出由它派生。

⭐ 为什么要这一件（不做会怎样）：改一次列序要人肉同步五处 —— 壳的**表头字面量**、导出的**列字面量**、
  壳里两处**列号**常量、切片行 —— **漏一处不报错**（悄悄隐藏错列 / 钉错列 / 导出的表头漂了）。
⇒ 本件钉三件（**导出 / 域内核**侧那半）：
  ① **导出列 = 域内核派生**：`jc_export.COLUMNS` 不再自写一份 —— 列集 = `JC_COLUMNS − PAGE_ONLY_KEYS`、
     表头字 = `export_label`（缺省 = `label`）、合计列 = `SUM_KEYS`；
  ② **序号列键名三者同名**：元数据（`JC_COLUMNS`）/ 行字典（`build_list`）/ 导出（`SEQ_KEY`）都是
     `project_seq`；
  ③ ⭐ **值级缺口**：导出列引用的每个键都必须真的出现在**行字典**里 —— `r.get(key)` 拿到空**不报错**
     ⇒ 那是"永远空着一列"的静默病（本仓最贵的一族）。

⚠️ 壳侧那半在 `tests/test_ux_pages.py::001-61`（行为表按 id ＋ 渲染后量宽）与
  `tests/test_acc_jc_shell.py`（空态跨列由表头派生）；真机那半（渲染出的表头列数 = 1 ＋ 列清单长度）
  在 `tools/probe/_shell_jcpin.py`（㉝）。
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.core.db import session_scope
from app.mod01_projects import repository as pj_repo
from app.mod01_projects.models import TYPE_NORMAL
from app.mod11_jc import domain as D
from app.mod11_jc import service as SV
from app.mod11_jc.models import TAG_IN, JcContract
from app.report_export import jc_export as J
from tests.acc_plugin import acc

#: 屏幕注解（屏内文字，⛔ 不进 Excel 表头）——**只许这三列**：多一列就该显式改本件（见下）。
SCREEN_ONLY = ("settle", "debt", "method")

WH = "__自检仓_集采列身份__"


def _project(s, wh: str):
    """造一个自检档案行（键 = 仓库名 · §2.7.4；用完 rollback ⇒ ⛔ 不留痕）。"""
    row = pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full=f"{wh}项目",
                                 warehouse_name=wh, phid="")
    s.flush()
    return row


def _contract(s, *, project_id: int):
    row = JcContract(project_id=int(project_id), contract_date="2026-10-01", material_name="自检材料",
                     supplier="自检供应商", contract_amt=Decimal("100.00"), tag=TAG_IN)
    s.add(row)
    s.flush()
    return row


# ============================================================== ① 导出列 = 域内核派生


@acc()
def test_导出列逐列等于域内核那张清单():
    """导出列**不是**在 `jc_export` 里"设计"的 —— 它必须**逐列等于** `domain.JC_COLUMNS` 去掉屏幕专用列。

    ⚠️ 为什么这条最重要：屏幕与导出各抄一份 ⇒ 加一列 / 改列序时**总有一边忘改**，而且**不报错**
       （表与屏幕对不上号、Excel 里多一列空列都是这类）。`TAIL-298` 起**只有一个主人**。
    """
    want = tuple((c.get("export_label") or c["label"], c["key"])
                 for c in D.JC_COLUMNS if c["key"] not in D.PAGE_ONLY_KEYS)
    assert J.COLUMNS == want, (
        "导出列与域内核那张清单不一致了 —— 两边必须逐列同名同序：\n"
        f"  导出   = {J.COLUMNS}\n  期望   = {want}")
    assert len(J.COLUMNS) == len(D.JC_COLUMNS) - len(D.PAGE_ONLY_KEYS)
    assert len(D.JC_COLUMNS) == 20 and len(J.COLUMNS) == 19, "主表 20 列 / 导出 19 列（去掉「操作」）"
    # 合计列 = 域内核的 `SUM_KEYS`（页面 `sumRowOf` 求的就是那几列）
    assert J.MONEY_KEYS == frozenset(D.SUM_KEYS), "导出合计列必须来自 `domain.SUM_KEYS`"
    assert J.MONEY_KEYS <= {k for _, k in J.COLUMNS}, "合计列必须都在导出的列里"


@acc()
def test_导出表头的字与键名对齐_屏幕注解只许那三列():
    """屏幕带「（自动）」「（自由文本）」这类**屏内注解**，Excel **不带**（`export_label` 缺省 = `label`）。

    ⚠️ 注解的**白名单**写死在 `SCREEN_ONLY`：多一列带注解 ⇒ 本件红 ⇒ 那一刻人得自己判断
       "这列在 Excel 里到底该叫什么"（⛔ 别让它悄悄漂）。
    """
    screen = {c["key"]: c["label"] for c in D.JC_COLUMNS}
    excel = {k: label for label, k in J.COLUMNS}
    for k in SCREEN_ONLY:
        assert "（" in screen[k], f"「{screen[k]}」是本件认定的**屏幕带注解**列 —— 注解没了就同批改本件"
        assert "（" not in excel[k], f"「{k}」的 Excel 表头带了屏内注解：{excel[k]!r}"
    others = [k for k in screen if k not in SCREEN_ONLY and k not in D.PAGE_ONLY_KEYS]
    assert {k: screen[k] for k in others} == {k: excel[k] for k in others}, (
        "除白名单那三列外，屏幕与 Excel 的表头字必须**逐字相同** —— 差异只许是显式声明的")


@acc()
def test_序号列键名元数据行字典导出三者同名():
    """⭐ `TAIL-298`：序号列**一个键名走到底** = `project_seq`（⛔ 不再有 `idx` 这种只在元数据里存在的名字）。"""
    assert D.JC_COLUMNS[0]["key"] == "project_seq", "元数据（域内核列清单）首列的键必须是 `project_seq`"
    assert J.SEQ_KEY == "project_seq", "导出读序号的键 = `project_seq`"
    assert J.COLUMNS[0][1] == "project_seq", "导出首列（序号）必须接在这个键上"
    keys = [c["key"] for c in D.JC_COLUMNS]
    assert len(keys) == len(set(keys)), "列 id 必须唯一（壳的行为表按 id 定位，重 id = 永远打到第一列）"
    ops = {k for _, k in J.COLUMNS}
    assert "ops" not in ops and "ops" in keys, "「操作」列只在屏幕上成立（`PAGE_ONLY_KEYS`）"


# ============================================================== ③ 值级缺口（真实行字典）


@acc()
def test_导出列每个键都出现在真实行字典里(monkeypatch: pytest.MonkeyPatch):
    """⭐ **值级缺口**：导出列引用的每个键，必须真的出现在 `service.build_list` 产的**行字典**里。

    ⚠️ 病：`naive_export` 取值走 `r.get(key)` —— 键名漂了**不报错**，只是那一列**永远空着**
       （本仓最贵的一族：看着正常的错表）。
    ⚠️ **造数走真库**（`session_scope` ＋ 自检仓/合同，末尾 rollback）：⛔ 别拿 `COLUMNS` 自己造一行
       再自证 —— 那种"样例行"永远是全的，等于没验（`test_naive_export_parity.py` 的 `_rows` 就是自造）。
    ⚠️ 打桩的是**内核**（`jc_export.build_xlsx`）：走的是真端点那条路
       （`service.export_xlsx` → `build_list` → 按 id 挑 → 交内核）⇒ 截下来的就是**真行**。
    """
    captured: dict = {}

    def _capture(rows):
        captured["rows"] = rows
        return b""                      # 只要行，不真要一本书（⛔ 不在判据里写盘）

    monkeypatch.setattr(J, "build_xlsx", _capture)
    with session_scope() as s:
        p = _project(s, WH)
        c = _contract(s, project_id=p.id)
        blob = SV.export_xlsx(s, ids=[c.id])
        s.rollback()                    # ⭐ 库级断言非破坏：一行不留
    assert blob == b"" and captured.get("rows"), "没截到行 —— 导出这条路变了（⛔ 别让它静默通过）"
    row = captured["rows"][0]
    missing = sorted(k for _, k in J.COLUMNS if k not in row)
    assert not missing, (
        "导出的这些列在**行字典**里根本不存在 ⇒ `r.get(key)` 拿到空、那一列永远空着（且不报错）：\n  "
        + "\n  ".join(missing)
        + "\n  ⇒ 键名以 `domain.JC_COLUMNS` / `repository.list_contracts` 为准，同批改对（⛔ 别改断言）。")
