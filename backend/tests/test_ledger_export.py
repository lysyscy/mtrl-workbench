# -*- coding: utf-8 -*-
"""台账成品（`TAIL-04` 路径① **片 2＋3 合体**）—— 一本工作簿 / 三个 sheet 的离线断言。

形态（唯一主人 = 交付面 `demo/模板/模板清单.md` §二 · §5.1 · §5.2）：
`辅材` / `机械`（序号 ｜ 月份 ｜ 其他支出金额 ｜ 付款 ｜ 欠款 ｜ 备注 ＋ R19「合计：」尾块）＋
`特殊费用月报表`（数据项 ｜ `<M>月份` ｜ 合计；**月份列按当前核算月生成**）。

⭐ 断言分五类覆盖维度（各自独立成档 —— 一条红了就知道哪一维坏的）：
① **三张表齐**（⛔ 只填两个就交付 = 第三张会留模板里**别的项目**的示例数据，`TAIL-43` 同族）；
② **逐格独立复算**（台账 6 列 / 特殊费用 3 列，期望**手写**、不问实现）；
③ **月份文本口径**（期初行 = `截止 YYYY 年 M 月底`、其余 = `YYYY-MM`；含**数字格式 = 文本**）；
④ **尾块随行数派生**（合计行 = 各数据行之和；尾块紧随、下面不留行）；
⑤ **标题替换**（模板那句写着**别的项目名** ⇒ 一律整格换掉，且**展示名不带「项目」二字**）。

⚠️ 跑法照旧：`PYTHONIOENCODING=utf-8` ＋ 子进程 `CODEBUDDY_SAFE_DELETE_ENABLED=0`。
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from app.core.errors import MustReportError
from app.mod01_projects.models import Project
from app.mod03_notice.models import PaymentNotice
from app.mod05_flow.models import (
    CATEGORY_MATERIAL,
    CATEGORY_MECH,
    LedgerRemark,
    OpeningBalance,
)
from app.mod08_inv.models import InvDetail
from app.mod09_fee.models import FeeManualItem
from app.report_export import ledger_export as LX
from tests.acc_plugin import acc
from tests.m05_helpers import make_notice_row, make_opening, make_project
from tests.m09_helpers import M09Session, make_inv, make_item

YM = "2026-09"                     # 报告月（台账止月 = 特殊费用月报表的月份列，**必须同一个**）
OPEN_YM = "2026-06"                # 期初截止月 ⇒ 台账从 `2026-07` 起逐月出行
WH_A, WH_B = "甲仓库", "乙仓库"
DISP_A = "甲公司项目"

#: 手写期望（**独立复算**，⛔ 不问实现）：台账两侧各 4 行 = 期初 ＋ 07/08/09（空月也出行）
LEDGER_EXPECT: dict[str, list[tuple]] = {
    "material": [
        ("1", "截止 2026 年 6 月底", "100.00", "0.00", "100.00", ""),
        ("2", "2026-07", "0.00", "0.00", "0.00", ""),
        ("3", "2026-08", "0.00", "0.00", "0.00", ""),
        ("4", "2026-09", "1000.00", "200.00", "800.00", ""),
    ],
    "mechanical": [
        ("1", "截止 2026 年 6 月底", "50.00", "0.00", "50.00", ""),
        ("2", "2026-07", "0.00", "0.00", "0.00", ""),
        ("3", "2026-08", "0.00", "0.00", "0.00", ""),
        ("4", "2026-09", "0.00", "300.00", "-300.00", ""),
    ],
}

#: 手写期望：特殊费用月报表 = 1 自动项（安文费 800）＋ 2 手填项；**单月列 ⇒ 合计 = 该月值**
FEE_EXPECT: list[tuple] = [
    ("安全文明施工费（按 CBS 分类）", "800.00", "800.00"),
    ("油卡", "100.00", "100.00"),
    ("运费", "200.00", "200.00"),
]

SHEET_MAT, SHEET_MECH, SHEET_FEE = "辅材", "机械", "特殊费用月报表"


def dataset() -> dict:
    """一份**口径自洽**的小样本（全部落在报告月 `2026-09`）。

    ⚠️ 桩要 honor `where`（见下 `session()`）：否则多项目场景会把**别的项目**的期初行也混进来。
    """
    return {
        Project: [make_project(11, WH_A, DISP_A), make_project(12, WH_B, "乙公司项目")],
        # 通知书：辅材（2026-09：结算 1000 / 付款 200）＋ 机械（2026-09：付款 300、无结算）
        PaymentNotice: [
            make_notice_row(101, doc_date="2026-09-05", category=CATEGORY_MATERIAL,
                            settle="1000", paid="200", ownership_id=11),
            make_notice_row(102, doc_date="2026-09-06", category=CATEGORY_MECH,
                            settle="0", paid="300", ownership_id=11),
        ],
        OpeningBalance: [
            make_opening(201, category=CATEGORY_MATERIAL, project_id=11, cutoff_ym=OPEN_YM,
                         settle="100", paid="0"),
            make_opening(202, category=CATEGORY_MECH, project_id=11, cutoff_ym=OPEN_YM,
                         settle="50", paid="0"),
        ],
        LedgerRemark: [],
        InvDetail: [make_inv(YM, WH_A, "出库", "CBS-安文费", "800.00", rid=301)],
        FeeManualItem: [
            make_item(401, YM, 11, "油卡", "100.00"),
            make_item(402, YM, 11, "运费", "200.00"),
        ],
    }


def session() -> M09Session:
    """⭐ 复用 **honor 等值过滤** 的那个桩（`m05_helpers.FakeSession` **忽略 where** ——
    多项目场景下它会把别的项目的期初行一起返回，正好把"取数按项目"这条判据变成**假绿**）。"""
    return M09Session(dataset())


def build(tmp_path, *, display: str = DISP_A, ym: str = YM) -> tuple[str, dict]:
    """跑一遍真链路（取数 → 装配 → 落盘）⇒ `(成品路径, 返回的对账计划)`。"""
    from app.mod05_flow import service as M5
    from app.mod09_fee import service as M9

    s = session()
    sides = {x["category"]: x for x in M5.build_ledger(s, project_id=11, end_ym=ym)["sides"]}
    sections = {cat: sides.get(cat) for cat in LX.SHEET_OF_CATEGORY}
    sections[LX.SHEET_FEE] = M9.build_page_data(s, {"ym": ym, "pj": WH_A})
    plan = {"sections": sections}
    path = LX.build_xlsx(sections, tmp_path, display=display, ym=ym)
    plan["path"] = path
    return path, plan


def sheet(path: str, name: str) -> list[list]:
    wb = openpyxl.load_workbook(path, data_only=False)
    try:
        ws = wb[name]
        return [[ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
                for r in range(1, ws.max_row + 1)]
    finally:
        wb.close()


def txt(v) -> str:
    """格值 → 文本：`None` ⇒ 空串（其余原样、不美化）。"""
    return "" if v is None else str(v).strip()


def dec(v) -> Decimal:
    """格值 → 金额（`None` / 空串 ⇒ `0`）。"""
    return Decimal(str(v)) if v not in (None, "") else Decimal("0")


def row_matches(got: list, want: tuple, *, money: tuple[int, ...]) -> str:
    """逐格比对，返回**第一条差异**的说明（`''` = 全同）。

    ⭐ 金额列按**数值**比 —— Excel 存回来的整数金额是 `int`（`800`）、带小数的是 `float`（`1000.0`），
       ⛔ 按字符串比会把**正确的实现判成错的**（实测踩到：`800` ≠ `800.00`）。
    """
    for i, (g, w) in enumerate(zip(got, want)):
        if i in money:
            if dec(g) != dec(w):
                return f"第 {i + 1} 列（金额）：{g!r} ≠ {w!r}"
        elif txt(g) != str(w).strip():
            return f"第 {i + 1} 列：{g!r} ≠ {w!r}"
    return ""


def cells(rows: list[list], r: int, n: int) -> list:
    """第 `r` 行（1 基）取前 `n` 列的**原值**。"""
    return list(rows[r - 1][:n])


# ============================================================ ① 三张表齐


@acc()
def test_三个sheet都在一个都不少(tmp_path):
    """⭐ **要么都填、要么不交付**：只填两个 sheet 就交付，第三张会把模板里别的项目的示例数据留下。"""
    path, _ = build(tmp_path)
    wb = openpyxl.load_workbook(path)
    try:
        assert wb.sheetnames == [SHEET_MAT, SHEET_MECH, SHEET_FEE], f"工作表不对：{wb.sheetnames}"
    finally:
        wb.close()


@acc()
def test_模板示例数据一格不留(tmp_path):
    """`TAIL-43` 同族：模板里那些**别的项目**的示例格不得出现在成品里。"""
    path, _ = build(tmp_path)
    hits = []
    for name in (SHEET_MAT, SHEET_MECH, SHEET_FEE):
        for row in sheet(path, name):
            for v in row:
                if "龙源纸业" in str(v or ""):
                    hits.append((name, v))
    assert not hits, f"成品里还留着模板的示例数据：{hits[:5]}"


# ============================================================ ② 逐格独立复算


@acc()
def test_台账两侧逐格等于手写期望(tmp_path):
    """台账 6 列逐格 = **手写期望表**（期初行 / 空月出行 / 当月值 / 欠款 = 其他支出 − 付款）。"""
    path, _ = build(tmp_path)
    rows_all = {}
    for cat, want in LEDGER_EXPECT.items():
        name = LX.SHEET_OF_CATEGORY[cat]
        rows = rows_all.setdefault(name, sheet(path, name))
        for i, exp in enumerate(want):
            diff = row_matches(cells(rows, 3 + i, 6), exp, money=(2, 3, 4))
            assert not diff, f"[{name}] 第 {i + 1} 行 · {diff}"


@acc()
def test_特殊费用月报表逐格等于手写期望(tmp_path):
    """特殊费用 3 列逐格 = 手写期望（1 自动项 ＋ N 手填项；**合计列 = 该月值**）。"""
    path, _ = build(tmp_path)
    rows = sheet(path, SHEET_FEE)
    for i, exp in enumerate(FEE_EXPECT):
        diff = row_matches(cells(rows, 3 + i, 3), exp, money=(1, 2))
        assert not diff, f"第 {i + 1} 行 · {diff}"


# ============================================================ ③ 月份文本口径


@acc()
def test_期初行的月份是页面文本不是YYYY_MM(tmp_path):
    """⭐ `模板清单` §四-4 裁定「**按页面文本**」：期初行 = `截止 YYYY 年 M 月底`（⛔ 不是 `2026-06`）。"""
    path, _ = build(tmp_path)
    for cat in LEDGER_EXPECT:
        got = txt(sheet(path, LX.SHEET_OF_CATEGORY[cat])[2][1])
        assert got == "截止 2026 年 6 月底", f"[{LX.SHEET_OF_CATEGORY[cat]}] 期初行月份 = {got!r}"


@acc()
def test_月份列的数字格式是文本(tmp_path):
    """⭐ 同一条裁定的**另一半**：模板那列原本是日期/数值格式 ⇒ 写文本前必须先设成文本，
    否则 Excel 会把 `2026-07` 按日期吃掉（页面文本就再也看不见了）。"""
    path, _ = build(tmp_path)
    wb = openpyxl.load_workbook(path)
    try:
        for cat in LEDGER_EXPECT:
            ws = wb[LX.SHEET_OF_CATEGORY[cat]]
            fmts = {ws.cell(row=r, column=2).number_format for r in range(3, 7)}
            assert fmts == {LX.TEXT_FMT}, f"[{ws.title}] 月份列数字格式 = {fmts}（应为 {LX.TEXT_FMT!r}）"
    finally:
        wb.close()


# ============================================================ ④ 尾块随行数派生


@acc()
def test_合计行等于各数据行之和且紧随其后(tmp_path):
    """⭐ 模板的合计行**死在一个固定行号**上 ⇒ 必须随行数派生：合计 = 各数据行之和、且**紧随**最后一行。"""
    path, _ = build(tmp_path)
    for cat, want in LEDGER_EXPECT.items():
        name = LX.SHEET_OF_CATEGORY[cat]
        rows = sheet(path, name)
        n = len(want)
        assert len(rows) == 2 + n + 1, f"[{name}] 行数 = {len(rows)}（应 = 表头 2 ＋ 数据 {n} ＋ 合计 1）"
        tail = cells(rows, 3 + n, 6)
        exp = [sum(Decimal(w[i]) for w in want) for i in (2, 3, 4)]
        assert txt(tail[1]) == "合计：", f"[{name}] 尾块首格被改掉了：{tail[1]!r}"
        assert [dec(tail[i]) for i in (2, 3, 4)] == exp, \
            f"[{name}] 合计 != 各数据行之和：实得 {tail[2:5]} 期望 {exp}"
        assert txt(tail[0]) == "" and txt(tail[5]) == "", f"[{name}] 合计行的序号 / 备注格应留空：{tail}"


@acc()
def test_特殊费用月报表的单月列由报告月生成(tmp_path):
    """⭐ `模板清单` §5.2 裁定①丙：`3月份`…`8月份` 只是示例 ⇒ 压成**报告月那一列** ＋ 合计（共 3 列）。"""
    path, _ = build(tmp_path)
    rows = sheet(path, SHEET_FEE)
    assert [txt(v) for v in cells(rows, 2, 3)] == ["数据项", "9月份", "合计"], f"表头不对：{rows[1]}"
    assert all(len(r) == 3 for r in rows), f"列数多于 3：{rows[:2]}"


@acc()
def test_特殊费用月报表的行数随数据项派生(tmp_path):
    """行数也随数据项派生：1 自动 ＋ N 手填，下面不留空壳行。"""
    path, _ = build(tmp_path)
    rows = sheet(path, SHEET_FEE)
    assert len(rows) == 2 + len(FEE_EXPECT), f"行数 = {len(rows)}（应 = 表头 2 ＋ 数据 {len(FEE_EXPECT)}）"


# ============================================================ ⑤ 标题 / 拒做 / 打包


@acc()
def test_标题用展示名且不带项目二字(tmp_path):
    """⭐ 用户 2026-09-18 裁定：标题 = **展示名 ＋ 模板后缀**（**不带「项目」二字**）。
    ⚠️ 模板那句 `龙源纸业项目辅材欠款` 里写着**别的项目名** ⇒ 必须整格换掉。"""
    path, _ = build(tmp_path)
    wb = openpyxl.load_workbook(path)
    try:
        for name, suffix in ((SHEET_MAT, "辅材欠款"), (SHEET_MECH, "机械费欠款"),
                             (SHEET_FEE, "费用汇总表")):
            got = str(wb[name]["A1"].value or "")
            assert got == f"{DISP_A}{suffix}", f"[{name}] 标题 = {got!r}（应 = {DISP_A}{suffix}）"
    finally:
        wb.close()


@acc()
def test_拿不到报告月就拒做不产出文件(tmp_path):
    """⛔ **拒做**：报告月拿不到 ⇒ 显式报错、**不产出文件**（半成品比不产出更坏）。"""
    with pytest.raises(MustReportError):
        LX.build_xlsx({}, tmp_path, display=DISP_A, ym="")
    assert not list(Path(tmp_path).glob("*.xlsx")), "被拒的导出却留下了文件"


@acc()
def test_项目不在档案里就拒做():
    """⛔ 导出的项目**必须在档案里**（拿不到展示名 ⇒ 拒做，⛔ 不拿仓库名冒充展示名）。"""
    from app.report_export import service as EX

    with pytest.raises(MustReportError):
        EX.export_ledger(session(), [WH_A, "查无此仓"])


@acc()
def test_一个项目都没选就拒做():
    from app.report_export import service as EX

    with pytest.raises(MustReportError):
        EX.export_ledger(session(), [])


@acc()
def test_两个项目打成一个zip(tmp_path):
    """交付形态：每项目一本工作簿；**≥2 个项目 ⇒ 一个 zip**（两本都在、名字带展示名与期间）。"""
    a = tmp_path / LX.file_name("甲公司项目", YM)
    b = tmp_path / LX.file_name("乙公司项目", YM)
    a.write_text("A", encoding="utf-8")
    b.write_text("B", encoding="utf-8")
    z = LX.build_zip([str(a), str(b)], tmp_path, "欠款台账_2026年9月.zip")
    import zipfile

    with zipfile.ZipFile(z) as zf:
        assert sorted(zf.namelist()) == sorted([a.name, b.name]), zf.namelist()


@acc()
def test_成品名含展示名与期间():
    """文件名 = `{展示名}欠款台账_{期间标签}.xlsx`（原型口径：文件名含项目展示名与当前年月）。"""
    assert LX.file_name(DISP_A, YM) == "甲公司项目欠款台账_2026年9月.xlsx"
    assert LX.file_name("乙公司项目", YM) == "乙公司项目欠款台账_2026年9月.xlsx"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-v"]))
