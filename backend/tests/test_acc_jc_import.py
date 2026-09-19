"""`M5-8` 集采台账 Excel **解析层**的断言 —— 全部用**构造网格**（纯函数，⛔ 不依赖任何真实文件）。

⚠️ 这里的每一条都对应 2026-09-19 拿用户真台账（`晋江污泥处理项目集采台账.xls`）实测到的**坑**：
   ① 合并格只有左上角有值 ⇒ 不铺 ⇒ 一整支金额**静默丢掉**；
   ② 表头探测若按"命中**单元格**个数"算 ⇒ 会被**重复列名**骗到（实测认成第 3 行）；
   ③ 手作表的合并区**画得不完整** ⇒ 上级为空 ⇒ 拼名与另一列**撞车**；
   ④ **合计行也有金额** ⇒ 不挡 ⇒ 合计**凭空翻倍**；
   ⑤ 用户表里有 `205260323` 这种**手滑**的日子 ⇒ 必须**拒掉并记账**（⛔ 不静默、⛔ 也不猜成别的日子）。
"""

from __future__ import annotations

from decimal import Decimal

from app.mod11_jc.excel_parse import (
    _fill_merges,
    detect_header,
    header_labels,
    looks_like_data_row,
    map_columns,
    parse_rows,
    to_date,
    to_money,
)
from tests.acc_plugin import acc


@acc()
def test_合并格要按真实合并区铺满():
    """⚠️ 不铺 ⇒ `供应商合同总价` / `供应商发票金额` 两列变无名列 ⇒ **整支丢掉且不报错**。"""
    grid = [["供应商", "", "贸易公司", ""], ["合同总价", "发票金额", "合同总价", "发票金额"]]
    merges = [(0, 0, 0, 1), (0, 0, 2, 3)]          # 真实"跨列合并"（闭区间）
    out = _fill_merges(grid, merges)
    assert out[0] == ["供应商", "供应商", "贸易公司", "贸易公司"]
    # ⛔ **不能**退化成无脑向右填充：没被合并的空列必须保持空
    grid2 = [["发票金额", "", "", ""], ["", "", "", ""]]
    assert _fill_merges(grid2, [])[0] == ["发票金额", "", "", ""], "空列不许被填"


@acc()
def test_表头探测按不同词计数_不被重复列名骗():
    """⚠️ 按"命中**单元格**个数"算会被**重复列名**骗 —— 这里的构造**故意**让两种算法分道扬镳：

    | 行 | 命中**单元格**数 | 命中**不同词**数 |
    |---|---|---|
    | 第 1 级 | 4（序号/合同日期/材料名称/供应商） | **4** |
    | 第 2 级 | **5**（合同总价 ×3 ＋ 发票金额 ×2） | 2 |

    ⇒ 数单元格 ⇒ 选第 2 级（**错**）；数不同词 ⇒ 选第 1 级（**对**）。
    ⚠️ 用户真实台账里两级恰好都是 4 格 —— 那种"看不出区别"的用例**证明不了**哪边对，
       所以这里**刻意**把第 2 级拉长（真实表也可能有第三条金额线）。
    """
    grid = [
        ["某项目集中采购台账"],                                                    # 大标题（r0）
        ["序号", "合同日期", "材料名称", "贸易公司", "供应商", "", "", ""],            # 真第 1 级（4 格 / 4 词）
        ["", "", "", "", "", "合同总价", "发票金额", "合同总价", "发票金额", "合同总价"],  # 第 2 级（5 格 / 2 词）
        ["1", "20240723", "钢材", "维萨", "亿管通", "1.00", "2.00", "3.00", "4.00", "5.00"],
    ]
    r1, r2 = detect_header(grid)
    assert (r1, r2) == (1, 2), f"应认出第 1 级 = 第 2 行、二级 = 第 3 行，实际={(r1, r2)}"


@acc()
def test_拼名撞车时取左侧最近的非空上级():
    """⚠️ 手作表合并区常**画得不完整** —— 复刻用户真文件的形态：`供应商` 与 `贸易公司` **各自只跨 2 列**
    ⇒ 两条线**末尾那列**的上级都是空 ⇒ 拼出来**都叫 `发票金额`**（撞名）⇒ 必有一列被当"重复"丢掉。
    """
    grid = [
        ["供应商", "", "贸易公司", ""],                    # 第 1 级（两条线的合并区都没画全）
        ["合同总价", "发票金额", "合同总价", "发票金额"],     # 第 2 级
    ]
    labels = header_labels(grid, row1=0, row2=1)
    assert labels[0] == "供应商合同总价"
    assert labels[2] == "贸易公司合同总价"
    assert labels[1] == "供应商发票金额", f"撞名那列要挂到**左邻的上级**，实际={labels[1]!r}"
    assert labels[3] == "贸易公司发票金额", f"有上级的不许动，实际={labels[3]!r}"
    m = map_columns(labels)
    assert m["dupes"] == [], f"修正之后不该再有重复列（否则那一列会被丢掉），实际={m['dupes']}"
    assert set(m["fields"]) == {"contract_amt", "inv_sum", "trade_contract_amt", "trade_inv_sum"}, m["fields"]


@acc()
def test_合计行必须挡掉_否则合计凭空翻倍():
    """⚠️ 合计行**也有金额** ⇒ 光靠"有金额"挡不住（实测 110,030,834.08 会被当成一条合同）。"""
    grid = [
        ["序号", "合同日期", "材料名称", "供应商", "合同总价", "发票金额"],
        ["1", "20240723", "钢材", "亿管通", "42799.80", "40731.17"],
        ["", "合计：", "", "", "110030834.08", "74495051.84"],       # 合计行
        ["2", "205260323", "钢材", "洛阳业祥", "1.00", "2.00"],       # 手滑的日期
    ]
    labels = header_labels(grid, row1=0, row2=0)
    fields = map_columns(labels)["fields"]
    assert looks_like_data_row(grid[1], fields) is True
    assert looks_like_data_row(grid[2], fields) is False, "合计行不许算数据"
    assert looks_like_data_row(grid[3], fields) is False, "不像日期的日期列 ⇒ 不许算数据（要记账让人看见）"

    pr = parse_rows(grid, row2=0, fields=fields)
    assert len(pr["rows"]) == 1 and pr["rows"][0]["material_name"] == "钢材"
    why = [x["why"] for x in pr["skipped"]]
    assert len(pr["skipped"]) == 2, f"跳过几行就记几行账（⛔ 禁静默），实际={pr['skipped']}"
    assert any("合计" in w for w in why) and any("不像日期" in w for w in why), why


@acc()
def test_金额空是None不是0_日期归一():
    """⚠️ "没填" 与 "填了 0" 是两回事 —— 一律当 0 会把"没填"伪装成"欠款 0"。"""
    assert to_money("") is None and to_money(None) is None and to_money("—") is None
    assert to_money("0") == Decimal("0.00"), "填了 0 要认成 0（与空区分开）"
    assert to_money("1,234.5") == Decimal("1234.50") and to_money("¥ 100 元") == Decimal("100.00")
    assert to_date("20240723") == "2024-07-23", "8 位数字是用户台账里的常见写法"
    assert to_date("2025/3/6") == "2025-03-06"
    assert to_date("205260323") == "205260323", "认不出就**原样**留着（⛔ 不猜成别的日子）"
    assert to_date("") == ""
