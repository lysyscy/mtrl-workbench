"""`TAIL-04` 成品文件写出（模板法）—— 收发结存 ＋ **库存单据明细表**两片切片的**离线接线断言**。

- **第一片（收发结存）**：绑 `ACC-X-EXP-001/001-02`（导出文件名用**当前年月**、不得硬编码成某个固定月份）。
- **第二片（库存单据明细表成品 xlsx，含两张真透视）**：
  · 绑 `ACC-X-EXP-001/001-05`（导出**成品形态 / 提示语必须与模板实际形态一致** —— 3 张 sheet =
    `报表1` +「过程资料」透视 +「安全文明施工费」透视；⛔ 不得声称与实例不符的结构）；
  · 绑 `ACC-INV-001/001-12`（**MOD-08 专属**：⭐ **2026-09-29（`TAIL-185` · 用户裁定 `A`）claim 已改** ——
    原写「主表朴素导出与「含数据透视表」**并存互不影响**」，现改为「卡头**只留真入口**：朴素那枚
    **渲染后被 `BIND.m08` 摘除**（点了必然空转 ⇒ 让用户以为坏了）＋ 含透视那份提示与模板实际形态一致」）。
- 其余接线断言用 `@acc()` 显式声明不绑定（避免被"未绑定测试体检"误报）。

⚠️ 这里钉的三件事（都踩过）：
1. **成品名只有一处主人** —— 页面清单（`domain.zip_manifest`）与实际产出的文件名必须**同一个来源**；
   实测踩过：清单写 `…2026-08…`、真产物写 `…2026年8月…`（两处各写一份命名）。
2. **文件名随期间参数变**（⛔ 不许把某个月份写死）。
3. **三种失败都不产出文件、且把中文原因带回**（模板缺失/损坏 · 该月无数据 · 缓存级对账不过）
   —— ⛔ 绝不静默交付一个空文件或数字对不上的文件。

⚠️ 两片都走**离线**（不连 i8、不顶号）：库存单据那片喂的是 i8 源文件**字节**
（优先仓里现成的真机导出件 `artifacts/_diag/inv_2026-09.xlsx`，缺则现造一份）。

真机验证在 `tools/oneoff/_verify_tail04.py`（连库跑 SQL 与成品逐分对账，**第三条独立路径**）与
`tools/probe/_shell_smoke.py`（第 ⑬ 段，走 HTTP 真下载）。
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import openpyxl
import pytest

from app.core.errors import MustReportError
from app.mod07_setl import domain as D
from app.mod07_setl.models import SetlDetail
from app.report_export import kcdj_export as KE
from app.report_export import resources as R
from app.report_export import service as EX
from app.report_export import setl_export as SE
from tests.acc_plugin import acc
from tests.m07_helpers import dataset
from tests.shell_load_helpers import exp_routes

ROOT = Path(__file__).resolve().parents[2]
from tests.shell_src import SHELL, act_entry, with_kernel  # noqa: F401  ← `P4`① 读取点收敛（`with_kernel`：`TAIL-67`）
API = (ROOT / "backend" / "app" / "mod07_setl" / "api.py").read_text(encoding="utf-8")
INV_API = (ROOT / "backend" / "app" / "mod08_inv" / "router.py").read_text(encoding="utf-8")
DIAG_INV = ROOT / "artifacts" / "_diag" / "inv_2026-09.xlsx"

# ⭐ 2026-10-03（`TAIL-219` 批 2b）：本件原先自带剪刀 `_act`（`SHELL.find` ＋ 花括号配平）——
#    已**整把删掉**，取动作条改走壳的语义口径 `act_entry`（定义 = `tools/audit/shell_api.py`）。⛔ 别写回来。


# ============================================================== 001-02


@acc("ACC-X-EXP-001", "001-02")
def test_导出文件名随期间变且不硬编码月份():
    """`001-02` 导出文件名用**当前年月**，⛔ 不得硬编码成某个固定月份。"""
    # ① 随参数变（两个不同月份必须给出两个名字）
    a, b = D.zip_name("2026-08"), D.zip_name("2026-09")
    assert a != b, f"两个月份给出同一个文件名 ⇒ 疑似写死：{a}"
    assert "2026年8月" in a and "2026年9月" in b
    assert D.total_workbook_name("2025-12") == f"{D.ORG_NAME}2025年12月收发结存表.xlsx"

    # ② 非单月 / 空值 ⇒ **原样返回**（⛔ 不臆造一个月份，也不抛）
    assert D.period_label("") == "" and D.period_label("2026") == "2026"
    assert D.period_label("2026-8") == "2026-8", "不干净的单月不该被猜成 `2026年8月`"

    # ③ 端点把「页面所选年月」透传下去（否则永远导出同一个月的成品）
    assert '/api/m07/settlement/export' in API, "后端没挂导出端点"
    assert 'request.query_params.get("period")' in API, "导出端点没读 `period` ⇒ 导出的是固定月份"
    assert "/api/m07/settlement/export?period=" in SHELL, "壳侧没把当前核算年月传给导出端点"


# ============================================================== 接线（不绑判据点）


@acc()
def test_成品名只有一处主人且与实际产出逐字一致():
    """⭐ **清单（页面承诺）与实际产出必须同一个来源** —— 实测踩过两处各写一份命名。"""
    ym = "2026-08"
    rows = dataset((ym,))[SetlDetail]
    # ⚠️ 用**域内核的键名**（`D.WAREHOUSE_KEY`），⛔ 不写死「仓库」——写死就变成第二份键名约定
    manifest = D.zip_manifest([{D.WAREHOUSE_KEY: w} for w in ("甲仓", "乙仓")], ym)
    assert [m["name"] for m in manifest if m["kind"] == "warehouse"] == ["甲仓.xlsx", "乙仓.xlsx"]
    assert manifest[-1]["name"] == D.total_workbook_name(ym)

    import tempfile

    with tempfile.TemporaryDirectory(prefix="t04-name-") as td:
        p = Path(SE.build_zip(rows, Path(td) / "out", D.period_label(ym)))
        assert p.name == D.zip_name(ym), f"产出名 {p.name} != 清单承诺 {D.zip_name(ym)}"
        # 包内总表名也要与清单一致
        members = zipfile.ZipFile(p).namelist()
    assert D.total_workbook_name(ym) in members


@acc()
def test_模板闸门缺失或损坏时显式报错():
    """⭐ `ops/模板法导出-实测结论.md` §五 点名的实现侧硬性：模板缺失 ⇒ **必须显式报错**。"""
    with pytest.raises(MustReportError) as e1:
        R.require_template(R.TEMPLATE_DIR / "__不存在的模板__.xlsx")
    assert "模板缺失" in str(e1.value)

    # 损坏（内容与登记不符）⇒ 也要拒（云同步回退过两次，是真实风险）
    import hashlib
    import tempfile as _tf

    with _tf.TemporaryDirectory(prefix="t04-tpl-") as td:
        fake = Path(td) / "模板_收发结存表.xlsx"
        fake.write_bytes(b"not a real xlsx")
        with pytest.raises(MustReportError) as e2:
            R.require_template(fake)
        assert "登记不符" in str(e2.value)
    # 闸门登记的摘要必须与真实文件一致（否则正常导出会全线被拦）
    for name, want in R.EXPECTED_SHA256.items():
        got = hashlib.sha256((R.TEMPLATE_DIR / name).read_bytes()).hexdigest()
        assert got == want, f"`{name}` 与登记的 SHA256 不符 —— 实现在跑，但闸门会在下次拒做"


@acc()
def test_三种失败都不产出文件且带回中文原因():
    """⭐ 空数据 / 坏期间 ⇒ 显式拒；⛔ 绝不静默产出一个空文件（那会被当成"交付了"）。"""
    import tempfile

    # ① 空数据
    with tempfile.TemporaryDirectory(prefix="t04-empty-") as td:
        out = Path(td) / "out"
        with pytest.raises(MustReportError) as e1:
            SE.build_zip([], out, "2026年8月")
        assert "没有任何收发结存明细" in str(e1.value)
        assert not list(out.glob("*.zip")) if out.exists() else True, "拒做时不该留下 zip"

    # ② 期间格式非法（服务层显式报，⛔ 不猜一个默认月）
    from app.core.db import session_scope

    with session_scope() as s:
        with pytest.raises(MustReportError) as e2:
            EX.export_settlement(s, "九月")
        assert "格式不对" in str(e2.value)


@acc()
def test_壳侧导出按钮已接线且按content_type分流():
    """`zipSfjc` 必须**真下载**（不再只弹"尚未落地"），并按 `content-type` 分流失败原因。

    ⚠️ 断言必须**只钉 `zipSfjc` 这个动作自己的作用域** ——
       「导出尚未落地」那句在**别的页**上是对的（其余页仍走路径①模板填充，属 `TAIL-04` 未完部分），
       把它当全站特征来查 ⇒ 一改别处就误红（实测首跑踩到）。
    """
    act = act_entry("zipSfjc")
    assert "尚未落地" not in act, "`zipSfjc` 还是旧提示 ⇒ 按钮按下去拿不到文件"
    assert "/api/m07/settlement/export?period=" in act, "`zipSfjc` 没打导出端点"
    assert "x-export-filename" in with_kernel(act), "壳侧没读后端带出的文件名（那就是自己拼了一份命名）"
    assert "'application/json'" in with_kernel(act), "没按 `content-type` 分流失败原因"
    _a = with_kernel(act)          # ⭐ `TAIL-67`：下载代码已抽到 `dlExport` 通用件
    assert "dlExport" in act and "createObjectURL" in _a and ".download" in _a, "没真的触发下载（拿不到文件）"
    # 后端两条分支都要在：成功给 zip、失败给 JSON＋中文原因
    assert "application/zip" in API, "成功分支不是 zip"
    assert '"ok": False' in API.replace("'", '"'), "失败分支没回 `ok:false`（壳就分不出流）"


# ============================================================== 库存单据明细表成品（第二片 · ACC-X-EXP-001/001-05）


def _synth_i8_bytes(with_safe: bool = True) -> bytes:
    """造一份**最小 i8 库存单据源**（28 列，两张透视要的分组数据齐）—— 仅当仓里没有 diag 件时用。

    `with_safe=False` ⇒ 一行安全文明施工费都没有 ⇒ `safe_wh` 为**空集**（钉「空集 ≠ 未传」用）。
    """
    import io as _io

    from app.report_export.schema_cols import KCDJ_COLS

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "报表1"
    ws.append(["库存单据明细表"] + [""] * 27)               # 标题行（引擎会跳过）
    ws.append([KCDJ_COLS[i] for i in range(28)])            # 表头行（含「序号」「金额」）

    def _row(seq, qty, amt, prop, direction, wh, cbs):
        r = [""] * 28
        r[0], r[1], r[2] = seq, "2026", "9"
        r[4], r[9], r[10], r[11] = "某项目", "个", "规格", prop
        r[12], r[13], r[14], r[15], r[16] = qty, "1.0", "1.0", amt, amt
        r[17], r[18], r[27] = direction, wh, cbs
        return r

    safe = KE.SAFE_CBS if with_safe else ""      # ⚠️ 值必须与 `kcdj_export.SAFE_CBS` **同一个来源**
    ws.append(_row("1", "10", "100.00", "主材", "入库", "甲仓", safe))
    ws.append(_row("2", "5", "50.00", "辅材", "出库", "甲仓", safe))
    ws.append(_row("3", "20", "200.00", "主材", "入库", "乙仓", ""))
    ws.append(_row("4", "3", "30.00", "辅材", "出库", "乙仓", ""))
    buf = _io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _kcdj_source() -> bytes:
    """离线 i8 源：**优先仓里现成的真机导出件**（`_diag/inv_2026-09.xlsx`），缺则现造一份。"""
    return DIAG_INV.read_bytes() if DIAG_INV.exists() else _synth_i8_bytes()


@acc("ACC-X-EXP-001", "001-05")
def test_库存单据明细表成品形态与模板一致且两张透视齐备():
    """绑 `ACC-X-EXP-001/001-05` —— **导出成品形态 / 提示语必须与模板实际形态一致**。

    判据对应：`验收基线.json` 的 `ACC-X-EXP-001/001-05`
    （「导出提示语必须与模板的实际形态一致（不得声称与实例不符的列 / 工作表结构）」）。
    成品实际那 3 张 sheet = `报表1` ＋「过程资料」透视 ＋「安全文明施工费」透视 —— 断言**真读回的文件**
    （⛔ 不是断言「提示语自称」的形态）。

    ⚠️ **离线**驱动：喂 i8 源文件**字节**（⛔ 不连 i8、不顶号）。
    """
    import tempfile

    with tempfile.TemporaryDirectory(prefix="t04-kcdj-") as td:
        out = Path(KE.build_xlsx(_kcdj_source(), Path(td) / KE.FILE_PREFIX / "2026年9月"))
        # ① 命名规则照素材包不变：`库存单据明细表_<期间标签>.xlsx`
        assert out.name == f"{KE.FILE_PREFIX}_2026年9月.xlsx", f"命名跑偏：{out.name}"

        # ② 两张真透视的部件必须在
        z = zipfile.ZipFile(out)
        parts = z.namelist()
        for part in ("xl/pivotTables/pivotTable1.xml", "xl/pivotTables/pivotTable2.xml"):
            assert part in parts, f"成品缺透视部件：{part}"
        # ③ 结构正确性：`refreshOnLoad` **只在** `pivotCacheDefinition` 上（⛔ 跑上 `pivotTable` = 不合 schema）
        assert "refreshOnLoad" in z.read("xl/pivotCache/pivotCacheDefinition1.xml").decode("utf-8")
        for pt in ("xl/pivotTables/pivotTable1.xml", "xl/pivotTables/pivotTable2.xml"):
            assert "refreshOnLoad" not in z.read(pt).decode("utf-8"), \
                "`refreshOnLoad` 跑到 `pivotTable` 上了（不合 OOXML schema）"
        z.close()

        # ④ 真读回（⚠️ 必须 `read_only=True`，见 `kcdj_export._structural_gate`）
        wb = openpyxl.load_workbook(out, read_only=True, data_only=True)
        try:
            sheets = list(wb.sheetnames)
        finally:
            wb.close()
    for sn in KE.OUTPUT_SHEETS:
        assert sn in sheets, f"成品缺工作表：{sn}（现有：{sheets}）"


@acc("ACC-X-EXP-001", "001-05")
def test_库存单据成品空源硬失败且不带出文件():
    """绑 `ACC-X-EXP-001/001-05`（must-report 侧）：该月**没有明细** ⇒ **显式报中文原因、不产出文件**。

    ⛔ 绝不静默交付一个空文件（它会被当成「交付了」，比不导出更坏）。
    """
    import tempfile

    with tempfile.TemporaryDirectory(prefix="t04-kcdj-empty-") as td:
        out_dir = Path(td) / KE.FILE_PREFIX / "2026年9月"
        with pytest.raises(MustReportError) as e:
            KE.build_xlsx(b"", out_dir)
        assert "内容为空" in str(e.value), f"空源没给中文原因：{e.value}"
        assert not list(out_dir.glob("*.xlsx")) if out_dir.exists() else True, "拒做时不该留下成品"


@acc("ACC-X-EXP-001", "001-05")
def test_壳侧透视导出按钮真下载且端点按content_type分流():
    """绑 `ACC-X-EXP-001/001-05`：`expPivot` 必须**真下载**（不再只弹提示），且**提示语与模板形态一致**。

    ⚠️ 断言**只钉 `expPivot` 这个动作自己的作用域**（`_act` 取花括号配平区间）——
       别处的同名 `toast(...)` 不得喂饱它。
    """
    act = act_entry("expPivot")
    _a = with_kernel(act)          # ⭐ `TAIL-67`：下载代码已抽到 `dlExport` 通用件
    assert "dlExport" in act and "createObjectURL" in _a and ".download" in _a, "没真的触发下载（拿不到文件）"
    assert "/api/m08/inventory/export?period=" in act, "`expPivot` 没打导出端点（拿不到文件）"
    assert "x-export-filename" in with_kernel(act), "壳侧没读后端带出的文件名（那就是自己拼了一份命名）"
    assert "'application/json'" in with_kernel(act), "没按 `content-type` 分流失败原因"
    # ⭐ 提示语必须与**模板实际形态**一致（两张透视名逐字对上；主表那份不受影响）
    for pivot in ("「过程资料」透视", "「安全文明施工费」透视"):
        assert pivot in act, f"壳侧提示缺工作表：{pivot}"
    # ⚠️ 2026-09-27（守则 §3.1 · `TAIL-117` 批次 2）：「路径②」是内部话术 ⇒ 改成「单独的一条通道」，
    #    **这条判据的口径一字未改**（仍要求"写明它是独立通道、主表那份不受影响"）。
    assert "单独的一条通道" in act and "不受影响" in act, "必须写明它是独立通道、主表那份不受影响"

    # 后端两条分支：成功给 xlsx、失败给 JSON＋中文原因
    assert "/api/m08/inventory/export" in INV_API
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in INV_API, "成功分支不是 xlsx"
    assert '"ok": False' in INV_API.replace("'", '"'), "失败分支没回 `ok:false`（壳就分不出流）"
    assert "default_month()" in INV_API, "端点没把「本页默认月」用作期间缺省"


@acc()
def test_库存导出编排落点与期间标签唯一出口(monkeypatch):
    """接线（不绑判据点）：`export_inventory` 的**落点**与**期间标签**都走唯一出口。

    - 落点 = `EXPORT_ROOT / "库存单据明细表" / <期间标签>`；期间标签**唯一出口** = `domain.period_label`。
    - 期间格式非法 ⇒ **显式报错**（⛔ 不猜默认月）。
    - 此处**注入源字节**（`export_bytes`）⇒ ⛔ **不连 i8**。
    """
    import tempfile

    src = _kcdj_source()
    with tempfile.TemporaryDirectory(prefix="t04-inv-orch-") as td:
        monkeypatch.setattr(EX, "EXPORT_ROOT", Path(td))
        from app.core.db import session_scope

        with session_scope() as s:
            p = EX.export_inventory(s, "2026-09", export_bytes=lambda: src)
            assert p.parent.name == D.period_label("2026-09") == "2026年9月"
            assert p.parent.parent.name == KE.FILE_PREFIX, "落点目录名跑偏"
            assert p.name == f"{KE.FILE_PREFIX}_2026年9月.xlsx"
            assert p.exists()
            with pytest.raises(MustReportError) as e:
                EX.export_inventory(s, "九月", export_bytes=lambda: src)
            assert "格式不对" in str(e.value)


# ============================================================== 库存单据：两种导出并存（第二片 · ACC-INV-001/001-12）


def _m08_card_head() -> str:
    """库存单据明细总表那张卡的卡头 `<h4>…</h4>`（含两个导出按钮）——**只取这一段**，防别处同名串喂饱。"""
    i = SHELL.find("库存单据明细总表")
    assert i >= 0, "壳里找不到「库存单据明细总表」卡头"
    a, b = SHELL.rfind("<h4", 0, i), SHELL.find("</h4>", i)
    assert a >= 0 and b > a, "卡头区间取不到"
    return SHELL[a:b]


@acc("ACC-INV-001", "001-12")
def test_库存单据只留真导出且透视提示与模板形态一致():
    """绑 `ACC-INV-001/001-12` —— ⭐ **2026-09-29（`TAIL-185` · 用户裁定 `A`）claim 已改**：
    **卡头只留真入口**（那枚"点了必然空转"的朴素导出**渲染后被 `BIND.m08` 摘除**）；
    「导出（含数据透视表）」那份提示必须与模板实际形态一致（逐字 claim 见 `PRD/验收/验收基线.json`）。

    ⚠️ **诚实边界**：切片 `V.m08` 里那枚朴素导出**源码仍在**（`U1` 逐行对位原件 ⇒ 删行会让后面所有行报漂移）；
    本件钉的是**渲染后它必须不在屏幕上**（`BIND.m08` 的选择器 ＋ `.remove()`）。
    ⛔ 断言**不**声称「朴素那份已出文件」—— 它本来就是空转的那一枚。
    """
    import tempfile

    # ① 切片里两枚都在（⛔ 不许动切片）；但**渲染后**朴素那枚必须被摘掉
    head = _m08_card_head()
    assert head.count('data-act="exp"') == 1, \
        "切片里那枚朴素导出不见了 —— ⛔ 不该动 `V.m08`（`U1` 逐行对位原件）"
    assert head.count('data-act="expPivot"') == 1, "含透视导出按钮缺 / 重复"
    assert "BIND.m08" in SHELL, \
        "壳里没有 `BIND.m08` ⇒ 那枚点了只会说「还没有导出功能」的朴素导出现在还留在屏幕上（用户会以为坏了）"
    _hook = SHELL[SHELL.index("BIND.m08"):SHELL.index("BIND.m08") + 400]
    assert '[data-act="exp"][data-t="库存单据明细总表"]' in _hook and ".remove()" in _hook, \
        "`BIND.m08` 没把朴素导出摘掉（选择器或 `.remove()` 变了）"

    # ② 两者走**不同实现**（"互不影响"的实质）：朴素那份仍走**通用 `exp`**，⛔ 不得被并进 `expPivot`
    # ⭐ 2026-10-04（`TAIL-219` 批 2b 余下 ②）：原先自造剪刀 `_action_text("exp")`（切到"下一个 ACT 条目"）
    #    已换成语义窗口子 `act_entry("exp")` —— 实测那两条断言（`还没有导出功能` / `不假装成功`）换后仍成立。
    exp_act = act_entry("exp")
    pivot_act = act_entry("expPivot")
    # ⚠️ 2026-09-27（守则 §2.2/§3.1 · `TAIL-117` 批次 2）：兜底**措辞换成人话**（原措辞里有内部台账编号
    #    与后端术语）⇒ token 同步；⭐ 但**两件**都还必须在：① 如实说"这页还没有导出功能"；
    #    ② 那句"不假装成功"的底线（⛔ 没有真文件就绝不写「已导出」）。
    assert "还没有导出功能" in exp_act, "通用 `exp` 不再有那条「这页还没有导出功能」的诚实兜底了（被谁改走了？）"
    assert "不假装成功" in exp_act, "兜底里那句「没有真文件就绝不写『已导出』」的底线丢了"
    assert pivot_act != exp_act
    # ⭐⭐ 2026-09-20（`TAIL-04` 收尾）：`exp` 从"一条诚实提示"改成了**按 `data-t` 真分发**
    #    ⇒ 端点串**搬进了分发表 `EXP_ROUTES`**，光看 `exp` 动作体已经**看不出**
    #      "朴素那份有没有被并进透视那份" ⇒ 断言改看**表**。
    #    ⚠️ **形态变了、判据一字未改**：claim 仍是「两者**并存互不影响**」。
    #    ⚠️ 这也是本条断言**唯一**还守得住的地方：`EXP_ROUTES` 是那张表，
    #       谁把「库存单据明细总表」加进去（或指到透视端点），这里当场红。
    routes = exp_routes()
    assert "库存单据明细总表" not in routes, \
        "库存单据明细总表的**朴素**那份被接进了导出分发表 ⇒ 与「含透视」那份（`expPivot`）重复"
    assert "/api/m08/inventory/export" not in routes.values(), \
        "朴素那份被接到了**透视端点** ⇒ 不再是「两种导出并存互不影响」"

    # ③ `expPivot` 那份**真产出文件**（端点 ＋ 壳侧真下载：`content-type` 分流 + `x-export-filename`）
    assert "/api/m08/inventory/export" in INV_API
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in INV_API, "成功分支不是 xlsx"
    _p = with_kernel(pivot_act)       # ⭐ `TAIL-67`：分流与文件名已抽到 `dlExport` 通用件
    assert "'application/json'" in _p and "x-export-filename" in _p
    assert "dlExport" in pivot_act and "createObjectURL" in _p and ".download" in _p, "没真的触发下载"

    # ④ 提示语声明的表 ↔ **真产出**的结构闸门（`kcdj_export.OUTPUT_SHEETS`）对账（⛔ 不是两处各写一份）
    with tempfile.TemporaryDirectory(prefix="t04-inv-x-") as td:
        out = Path(KE.build_xlsx(_kcdj_source(), Path(td) / KE.FILE_PREFIX / "2026年9月"))
        wb = openpyxl.load_workbook(out, read_only=True, data_only=True)
        try:
            real = list(wb.sheetnames)
            header = tuple(next(iter(wb[KE.OUTPUT_SHEETS[0]].iter_rows(values_only=True))))
        finally:
            wb.close()
    # 声明的张数（提示语里「工作表 N」出现次数）== 真产出张数 == OUTPUT_SHEETS 张数
    assert len(re.findall(r"工作表 \d", pivot_act)) == len(KE.OUTPUT_SHEETS) == len(real)
    # 两张透视：**声明名与真产出 sheet 名逐字一致**
    for pivot in KE.OUTPUT_SHEETS[1:]:
        assert pivot in real, f"真产出缺透视表：{pivot}"
        assert pivot in pivot_act, f"提示语声明与实例不符：缺 {pivot}"
    # 数据表：OUTPUT_SHEETS[0]（真名 `报表1`）在提示语里用其**角色「明细」**称它 —— 二者由**真产出表头**钉死
    assert KE.OUTPUT_SHEETS[0] in real
    assert "序号" in header and "金额" in header, "`报表1` 不是「明细」那张（声明与实例不符）"
    assert "明细" in pivot_act, "提示语没说明第 1 张表是明细表"


# ============================================================== 空集 ≠ 未传（缺陷回归）


def _pivot_rows(path, part: str):
    """读回某张透视表 → `(location, axis_items_count, 仓库行项数, rowItems_count, 行项数)`。

    - `axis_items_count` = `<pivotField axis="axisRow">` 里 `<items count="C">` 的 C（含 default）；
    - `仓库行项数` = `<item x="N"/>` 的个数（⛔ 不含 `<item t="default"/>`）；
    - `rowItems_count` = `<rowItems count="C">` 的 C；`行项数` = 其中 `<i…>` 元素个数（含 grand）。
    """
    xml = zipfile.ZipFile(path).read(part).decode("utf-8")
    loc = re.search(r'<location ref="([^"]*)"', xml)
    assert loc, f"{part} 里没有 <location>"
    ax = re.search(r'<pivotField axis="axisRow"[^>]*><items count="(\d+)">(.*?)</items>', xml, re.S)
    assert ax, f"{part} 里没有 axisRow 的 <items>"
    wh_items = len(re.findall(r'<item x="\d+"/>', ax.group(2)))
    ri = re.search(r'<rowItems count="(\d+)">(.*?)</rowItems>', xml, re.S)
    assert ri, f"{part} 里没有 <rowItems>"
    ri_rows = len(re.findall(r"<i[ >]", ri.group(2)))
    return loc.group(1), int(ax.group(1)), wh_items, int(ri.group(1)), ri_rows


@acc()
def test_空集与未传语义相反_空集得0行项未传用全部仓库():
    """⭐ 缺陷回归：`warehouses=set()`（**空集**）≠ `warehouses=None`（**未传**）—— 判据在**真产出**里。

    - **空集** ⇒ 该透视**确实一个仓库都没有** ⇒ pivot2 应 **0 行项**、`location=A3:B4`；
      ⛔ 旧实现用 falsy 判断 ⇒ 空集被当"未传" ⇒ pivot2 凭空冒出**全部**仓库（`A3:B6`）。
    - **未传**（pivot1 无 `warehouses` 键）⇒ 仍用**全部**仓库（护栏：修复别把这条也弄坏）。

    数据源用**受控合成源**（非 diag）⇒ 期望值确定：有安全文明费 ⇒ 仅 `甲仓`（1 行项）；
    无 ⇒ 空集（0 行项）；两张透视的仓库全集都 = `{甲仓, 乙仓}`（2 行项）。
    """
    import tempfile

    with tempfile.TemporaryDirectory(prefix="t04-pivot-sem-") as td:
        p_empty = Path(KE.build_xlsx(_synth_i8_bytes(with_safe=False),
                                     Path(td) / "empty" / "2026年9月"))
        p_safe = Path(KE.build_xlsx(_synth_i8_bytes(with_safe=True),
                                    Path(td) / "safe" / "2026年9月"))

        # ① 空集 ⇒ pivot2 **0 行项**、`A3:B4`（钉死"空集不是未传"）
        loc, ax_c, wh, ri_c, ri_rows = _pivot_rows(p_empty, "xl/pivotTables/pivotTable2.xml")
        assert loc == "A3:B4", f"空集 pivot2 的 location 应为 A3:B4，实得 {loc}（空集被当成未传？）"
        assert wh == 0, f"空集 pivot2 应 0 个仓库行项，实得 {wh}（空集被当成未传 ⇒ 冒出了全部仓库）"
        assert ax_c == wh + 1 and ri_c == wh + 1 and ri_rows == wh + 1, \
            f"空集 pivot2 的行项数不自洽：axis={ax_c} rowItems={ri_c} 行项={ri_rows}"

        # ② 有安全文明费 ⇒ pivot2 只用**有该费用的仓库**（甲仓，1 行项）、`A3:B5`
        loc2, _, wh2, _, _ = _pivot_rows(p_safe, "xl/pivotTables/pivotTable2.xml")
        assert loc2 == "A3:B5" and wh2 == 1, f"有费用时 pivot2 应 1 行项 / A3:B5，实得 {wh2} / {loc2}"

        # ③ **未传** warehouses 的 pivot1 ⇒ 仍用**全部**仓库（两种源都 2 行项、`A3:N9`）
        for p in (p_empty, p_safe):
            locp, _, whp, _, _ = _pivot_rows(p, "xl/pivotTables/pivotTable1.xml")
            assert locp == "A3:N9" and whp == 2, \
                f"未传 warehouses 的 pivot1 应用全部仓库（2 行项 / A3:N9），实得 {whp} / {locp}"


@acc()
def test_安全文明对账_空集明说未验证而非通过():
    """⭐ 缺陷回归：该月**没有**安全文明施工费数据 ⇒ 该条对账必须**明说「未验证 / 不适用」**，
    ⛔ **绝不**因为"空 == 空"就静默报"通过"（最贵的假绿）。

    ⚠️ 用**词边界**正则钉「有没有被报成通过」—— 别让别处的 `…✓ 通过`（如通用的"缓存对账全部通过"）喂饱。
    """
    import io
    import tempfile
    from contextlib import redirect_stdout

    def _log(src: bytes) -> str:
        buf = io.StringIO()
        with tempfile.TemporaryDirectory(prefix="t04-safe-log-") as td:
            with redirect_stdout(buf):
                KE.build_xlsx(src, Path(td) / KE.FILE_PREFIX / "2026年9月")
        return buf.getvalue()

    # ① 空集 ⇒ 明说「未验证 / 不适用」，且**没有**把该条报成「通过」
    empty_log = _log(_synth_i8_bytes(with_safe=False))
    assert re.search(r"未验证\s*/\s*不适用", empty_log), \
        f"空集没明说「未验证 / 不适用」：\n{empty_log}"
    assert not re.search(r"安全文明施工费透视[^\n]{0,16}✓", empty_log), \
        f"空集时把该条对账报成了「通过」⇒ 空 == 空的静默假绿：\n{empty_log}"

    # ② 反向对照（证明 ① 的判据**有区分力**，不是恒绿）：有数据时**必须**报该条「✓ 通过」
    safe_log = _log(_synth_i8_bytes(with_safe=True))
    assert re.search(r"安全文明施工费透视[^\n]{0,16}✓", safe_log), \
        f"有安全文明费时没报该条「✓ 通过」：\n{safe_log}"
