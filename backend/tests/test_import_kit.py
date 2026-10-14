"""统一导入底座 `import_kit`（`TAIL-69` · 2026-09-22 设计）的工程自检（离线 · 不连库）。

⚠️ `@acc()` 显式不绑定判据点（域导入判据在各域测试里）；本文件守**底座本身**：
统一解析出口（金额禁 float / 日期多格式）· 找表头（不猜列位）· 暂存往返 · 问题清单。
"""

from __future__ import annotations

import io
import json
from decimal import Decimal

import pytest

from app.core import preview_store
from app.import_kit.parse import amount, date_text, text
from app.import_kit.readers import find_header, read_grid
from app.import_kit.validators import Problems
from tests.acc_plugin import acc


@pytest.fixture(autouse=True)
def isolated_previews(tmp_path, monkeypatch):
    monkeypatch.setattr(preview_store, "PREVIEW_DIR", tmp_path / "previews")


def _grid(*rows: tuple) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(list(r))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ------------------------------------------------------------ parse（统一解析出口）


@acc()
def test_金额解析_禁float直传_空给零():
    assert amount("1,234.50") == Decimal("1234.50")          # 千分位
    assert amount(" 100 ") == Decimal("100")
    assert amount(None) == Decimal("0") and amount("") == Decimal("0")
    assert amount(12.3) == Decimal("12.3"), "float 也先转字符串再归一（⛔ 直传）"


@acc()
def test_日期文本_datetime取ISO_字符串原样():
    from datetime import date, datetime

    assert date_text(datetime(2026, 9, 15)) == "2026-09-15"
    assert date_text(date(2026, 9, 15)) == "2026-09-15"
    assert date_text("2026/9/15") == "2026/9/15", "字符串**原样交域内校验**（⛔ 底座不猜格式）"
    assert text(None) == ""


# ------------------------------------------------------------ readers（找表头）


@acc()
def test_读grid与前N行找表头():
    grid, name = read_grid(_grid(("备注", "x"), ("项目", "金额", "付款时间"), ("甲", 1, "d")))
    assert name and grid[0][0] == "备注"
    hit = find_header(grid, lambda c: {"项目": "p", "金额": "m", "付款时间": "d"}.get(str(c).strip() if c else ""))
    assert hit is not None
    idx, mapping = hit
    assert idx == 1 and mapping["p"] == 0 and mapping["m"] == 1


@acc()
def test_表头行_找不到给None_报错话术归调用方():
    grid, _ = read_grid(_grid(("a", "b"), ("1", "2")))
    assert find_header(grid, lambda c: None) is None          # ⛔ 底座不发明报错文案


@acc()
def test_读表的格子都装得进载具_但数字仍是数字():
    """⭐ 2026-09-26 用户报障（**真上传课表.xlsx ⇒ 界面「解析失败：TypeError: Object of type
    time is not JSON serializable」**）—— **能证伪**：把 `read_grid` 的 xlsx 分支改回
    "原样返回 openpyxl 原生值" ⇒ 本件必红（`datetime.time` 一进载具就抛）。

    ⚠️ 崩的是**载具**：`core.preview_store.save` 落盘是 `json.dumps`，而通用面的 `/parse`
       把读表给的 `grid_rows` **原样**塞进这个载荷 ⇒ 读表出口必须**装得进 JSON**。
    ⚠️⚠️ 但**不能连数字一起文本化**：序列号 / 金额的换算靠"值的类型"判（`parse.date_text`
       认 `int/float` 的序列号、`m06._ym_from_number` 同）—— 真把 `45444` 变成 `"45444"`，
       `m06` 的「核算月」会被**静默认不出**。本条把这两半一起钉住（假绿/假红都不许）。
    """
    from datetime import date, datetime, time

    grid, _ = read_grid(_grid(("项目", "上课时间", "金额", "日期", "核算月"),
                              ("甲", time(8, 30), 174.0, date(2026, 9, 15), 45444),
                              ("乙", datetime(2026, 9, 15, 8, 30), Decimal("12.30"), "2026/9/15", 45444)))
    assert grid[1][1] == "08:30:00", "时间格要给文本（课表那种「上课时间」列）"
    assert grid[1][3] == "2026-09-15" and grid[2][1] == "2026-09-15", "日期 / 日期时间按 ISO 给"
    assert grid[1][2] == 174.0 and grid[1][4] == 45444, \
        "⛔ 数字**原样**（序列号/金额的换算按类型判：文本化会让「核算月」静默认不出）"
    json.dumps(grid, ensure_ascii=False)
    token = preview_store.save({"grid_rows": grid})         # ← 报障时**炸的就是这一句**
    assert preview_store.load(token)["grid_rows"] == grid, "所见即所落（重启后预览还在）"


# ------------------------------------------------------------ preview_store（唯一载具）


@acc()
def test_暂存往返_所见即所落():
    token = preview_store.save({"year_month": "2026-09", "rows": [{"a": "1"}]})
    assert token and len(token) >= 16
    assert preview_store.load(token) == {"year_month": "2026-09", "rows": [{"a": "1"}]}


@acc()
def test_暂存_坏token显式报错():
    from app.core.errors import MustReportError

    with pytest.raises(MustReportError):
        preview_store.load("not-hex-token!!")               # 防路径穿越 ＋ 显式报错


# ------------------------------------------------------------ validators（问题清单）


@acc()
def test_问题清单_保留原值与行号():
    ps = Problems()
    ps.add(7, "金额", "abc", "不是数字")
    ps.add(9, "项目", None, "必填")
    assert len(ps) == 2 and bool(ps)
    assert ps.as_list()[0] == {"row": 7, "column": "金额", "raw": "abc", "reason": "不是数字"}
    assert ps.as_list()[1]["raw"] == "", "None 原值显示为空串（⛔ 不猜成 0）"
    assert not Problems()
