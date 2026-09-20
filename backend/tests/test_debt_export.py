"""**总欠款表导出**（用户 2026-09-20 定）的验收断言 —— 三条，全部对应同一判据点
`ACC-FLOW-DEBT-001/001-06`：

> 总欠款可**整表导出**：每个项目一行（A 序号 · B 项目展示名 · C 集采 · D 辅材 · E 机械）；
> 与页面/看板的欠款**同源**（同一份口径，⛔ 不得各算一套）；金额为**数值**（可再求和）；
> 口径缺口（如「机械费结算」未接通）须**在文件内显式说明**

⚠️ 一条 claim 拆成三条断言，是因为它管的是**四个互不相干的失效模式**：列序被改 / 字数变文本 /
   说明没落进文件 / 口径分叉。⛔ 合成一条会让人排不出到底是哪件坏了。
"""

from __future__ import annotations

import inspect
from decimal import Decimal
from pathlib import Path

import openpyxl

from app.mod05_flow import debt_export as X
from app.mod05_flow import service as S
from tests.acc_plugin import acc


@acc("ACC-FLOW-DEBT-001", "001-06")
def test_总欠款表的列序是用户指定的():
    """**A 序号 · B 项目展示名 · C 集采 · D 辅材 · E 机械** —— 用户原话指定的顺序。

    ⚠️ 钉住它：这种"看着还能更好"的列序，最容易被后来的人**顺手优化**成「辅材 / 机械 / 集采」，
       而用户是**按这个列序**在用（他多半还要往下接公式 / 透视图）。
    """
    assert X.COLUMNS == ("序号", "项目", "集采", "辅材", "机械")


@acc("ACC-FLOW-DEBT-001", "001-06")
def test_总欠款表写出形态_金额是数值且带表尾说明(tmp_path: Path):
    """产出形态三件：① 表头 → 数据 → **合计**；② 金额是**数值**；③ 机械说明**写进文件**。

    ⚠️ ② 尤其要紧：写成**字符串**的话，用户在 Excel 里自己 `Σ` 会**静默得 0**
       （本项目在别处踩过"文本数字"的坑）—— 而"表里明明有数、加起来是 0"没人能立刻反应过来。
    ⚠️ ③ 机械欠款**不含机械费结算**（来源未接通）⇒ 文件一旦离开页面，读到的人还得知道这件事
       ⇒ 那句说明**必须落进文件**，⛔ 不能只挂在页面提示上。
    """
    items = [
        {"index": 1, "project": "甲项目", "jc": Decimal("10.5"), "material": Decimal("20"),
         "mech": Decimal("-30")},
        {"index": 2, "project": "乙项目", "jc": Decimal("0"), "material": Decimal("1.25"),
         "mech": Decimal("0")},
    ]
    out = X.build_xlsx(items, tmp_path, mark_mech=True)
    rows = list(openpyxl.load_workbook(out).active.iter_rows(values_only=True))

    assert rows[0] == X.COLUMNS, "表头要逐字一致（用户指定的那五个词）"
    assert rows[1][:5] == (1, "甲项目", 10.5, 20, -30), "序号要从 1 起、项目取展示名、三列金额就位"
    assert rows[2][:5] == (2, "乙项目", 0, 1.25, 0)
    # ② 金额必须是**数值**（⛔ 字符串会让用户的 Σ 静默变 0）
    assert all(isinstance(r[c], (int, float)) for r in rows[1:3] for c in (2, 3, 4)), \
        "三列金额必须是数值，不是字符串"
    # 合计行：只对三列金额求和，⛔ 不把"合计"写进项目列以外的地方
    assert rows[3][1] == "合计"
    assert (rows[3][2], rows[3][3], rows[3][4]) == (10.5, 21.25, -30)
    # ③ 说明落进文件
    assert any(X.FOOTNOTE in str(c or "") for r in rows for c in r), "机械口径说明必须写进文件"

    # `mark_mech=False` ⇒ 不写（= 将来机械结算接通后该有的样子）
    out2 = X.build_xlsx(items, tmp_path, mark_mech=False)
    rows2 = list(openpyxl.load_workbook(out2).active.iter_rows(values_only=True))
    assert not any(X.FOOTNOTE in str(c or "") for r in rows2 for c in r)


@acc("ACC-FLOW-DEBT-001", "001-06")
def test_导出返回的是Path而不是str(monkeypatch):
    """⚠️⚠️ **2026-09-20 真机实测踩到**：`export_total_debt` 回的是 **`str`**，
    而端点那边写的是 `path.name` ⇒ 一调就 `AttributeError: 'str' object has no attribute 'name'`
    ＋ **HTTP 500**。

    ⚠️ 为什么当时三条断言**全绿**：它们都在测 `debt_export.build_xlsx`（**纯函数**），
       **没有一条跨过「实现 → 端点」那道缝** —— 这正是"接缝处最容易漏测"的典型样子。
    ⇒ 这条钉住那个**类型契约**：必须回 `Path`（端点要用 `.name` / `.suffix` 决定文件名与媒体类型）。
    """
    monkeypatch.setattr(S, "total_debt_rows", lambda _s: {
        "items": [{"index": 1, "project": "自检项目", "jc": Decimal("1"),
                   "material": Decimal("2"), "mech": Decimal("3")}],
        "jc_skipped": 0, "mech_settle_ready": False,
    })
    path, note = S.export_total_debt(None)          # ⚠️ 会话已被打桩，不需要真库
    assert isinstance(path, Path), (
        "端点要 `path.name` ⇒ 实现必须回 `Path`；回 `str` 会 **HTTP 500**（真机踩过）")
    assert path.name.endswith(".xlsx")
    assert path.is_file(), "要真写出文件（端点直接把它流给浏览器）"
    assert note["rows"] == 1 and note["mech_settle_ready"] is False


@acc("ACC-FLOW-DEBT-001", "001-06")
def test_总欠款的口径与页面同源():
    """⚠️ `total_debt_rows` **必须**用现场那两个出口算，⛔ 不许自己另写一套算钱的。

    ⚠️ 为什么这条值得一个**源码级**断言（本项目少见，但这里值）：
       这张表是**外部交付物** —— 一旦它与页面上的欠款**对不上**，用户手上就是**两份都"看着对"的数**，
       而他**没有任何办法**判断该信哪一份。⇒ 把"**同源**"钉死，比断言几个具体数字更有价值
       （数字会随口径演进而变，"同源"这件事不该变）。
    """
    src = inspect.getsource(S.total_debt_rows)
    assert "dom.debt_by_category" in src, "辅材 / 机械要走付款域**那个**出口（与页面同一份口径）"
    assert "build_list" in src, "集采要走集采台账**那个**出口（与集采页同一个数）"
    # ⚠️ 反例守卫：⛔ 不许在本函数里自己累加 `settle / pay`（那就是第二份口径）
    assert "settle_stat" not in src and "pay_stat" not in src, \
        "本函数只许**转交**给域内核，⛔ 不许自己算欠款"
