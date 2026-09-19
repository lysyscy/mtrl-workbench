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


def _xlsx_bytes() -> bytes:
    """现造一个**小 xlsx**（⛔ 不依赖任何真实文件）—— 形态照用户台账：大标题 ＋ 表头 ＋ 数据 ＋ 合计。"""
    import io

    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "某项目"
    ws.append(["某项目集中采购台账"])
    ws.append(["序号", "合同日期", "材料名称", "供应商", "合同总价", "发票金额", "结算"])
    ws.append(["1", "20240723", "钢材", "亿管通", "42799.80", "40731.17", "0"])
    ws.append(["2", "20250326", "钢材", "洛阳业祥", "301040.74", "311211.67", "0"])
    ws.append(["", "合计：", "", "", "343840.54", "351942.84", "0"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode()


@acc()
def test_预览给出列名映射与条数_合计行不计():
    from app.mod11_jc.import_service import preview

    d = preview(_xlsx_bytes(), "自检.xlsx")
    assert d["ok"] is True and len(d["sheets"]) == 1
    s = d["sheets"][0]
    assert s["guess"] is True and s["counts"]["data"] == 2, f"合计行不该算数据，实际={s['counts']}"
    assert s["counts"]["skipped"] == 1 and "合计" in s["skipped"][0]["why"]
    assert s["mapping"]["fields"]["contract_amt"] == 4 and s["mapping"]["fields"]["material_name"] == 2
    # ⚠️ 「结算」是**派生**列 ⇒ 必须**明确告诉人"为什么不导"**，⛔ 不是静默丢掉
    assert any(x["label"] == "结算" and "算出来" in x["why"] for x in s["mapping"]["ignored"]), s["mapping"]
    assert s["header"] == {"row1": 2, "row2": 2}, "两级表头同在一行时要认成同一行（1 基给人看）"


@acc()
def test_落库按合同价匹配并更新_且与i8互不覆盖():
    """⭐⭐ **本片核心**（用户 2026-09-20 口径）：**先抓 i8（合同已在库）→ 再导 Excel（补信息）**。

    ⇒ **锚点 = 含税合同价**，在**单个项目内**匹配**已有**合同，**更新它**
      （材料名 / 备注 / 存档三列 ＋ 汇总发票行）。
    ⚠️ 关键断言：**i8 的事实列（合同价 / 供应商）一个字都不许被 Excel 动** = "两者互不覆盖"。
    """
    from decimal import Decimal

    from sqlalchemy import select

    from app.core.db import session_scope
    from app.mod01_projects import repository as pj_repo
    from app.mod01_projects.models import TYPE_NORMAL
    from app.mod11_jc.import_service import commit, preview
    from app.mod11_jc.models import JcContract, JcInvoice

    data = _xlsx_bytes()
    sh = preview(data, "自检.xlsx")["sheets"][0]
    samples = sh["sample"]
    assert len(samples) == 2, f"预览样例要够我建两条锚点，实际={len(samples)}"

    with session_scope() as s:
        p = pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full="__自检_导入项目__",
                                   warehouse_name="__自检仓_导入__", phid="")
        s.flush()
        pid = int(p.id)
        # 先造"i8 抓来的"两条：**金额 = Excel 的金额（= 锚点）**，材料名/供应商**故意与 Excel 不同**
        #   —— 这样才能验出"Excel 到底动了哪些列"。
        anchor_amts = []
        for i, r in enumerate(samples):
            amt = Decimal(str(r["contract_amt"]))
            anchor_amts.append(amt)
            s.add(JcContract(contract_no=f"__自检_IMP_{i}__", project_id=pid,
                             contract_date="2026-01-01", material_name="i8给的材料名",
                             supplier="i8给的供应商", contract_amt=amt, bill_name="i8单据名"))
        s.flush()

        kw = dict(sheet=sh["name"], project_key="__自检仓_导入__")
        res = commit(s, data, "自检.xlsx", **kw)
        assert res["ok"] is True, res
        assert res["updated"] == 2, f"两条都该按合同价匹配上（`updated`=2），实际={res}"
        assert res["unmatched"] == 0 and res["ambiguous"] == 0, res

        rows = list(s.execute(select(JcContract).where(JcContract.project_id == pid)).scalars())
        assert len(rows) == 2, "⛔ **不许新增** —— 锚点匹配到的是已有合同（多出来就是重复建档）"
        for c in rows:
            assert c.material_name != "i8给的材料名", "材料名要被 Excel 覆盖（用户列的字段之一）"
            assert c.supplier == "i8给的供应商", "⛔ 供应商是 **i8 的事实** ⇒ Excel 一个字都不许动"
            assert str(c.contract_no).startswith("__自检_IMP_"), "⛔ 不许换成 Excel 的行"
        assert sorted(Decimal(str(c.contract_amt)) for c in rows) == sorted(anchor_amts), \
            "⛔ 合同价是**锚点本身** ⇒ 更不许被 Excel 改（改了下次就再也匹配不上了）"

        # 汇总发票行：落了一条（用户 2026-09-19 定：台账的发票额落**一条**）
        invs = list(s.execute(select(JcInvoice).where(
            JcInvoice.contract_id == int(rows[0].id))).scalars())
        assert len(invs) >= 1, "发票额要落成汇总行"

        # ⭐ **再导一次**：发票**不许翻倍**（发票子表是一合同 1..N 张，重导会翻倍）
        again = commit(s, data, "自检.xlsx", **kw)
        assert again["ok"] is True, again
        invs2 = list(s.execute(select(JcInvoice).where(
            JcInvoice.contract_id == int(rows[0].id))).scalars())
        assert len(invs2) == len(invs), f"重导**不许**给发票子表翻倍（{len(invs)} -> {len(invs2)}）"
        assert any("已有" in w["why"] for w in again["warn_items"]), \
            f"跳过发票要**报出来**（禁静默），实际={again['warn_items']}"

        # ⭐ **锚点找不到** ⇒ 列进"配不上"，⛔ **不静默新增**
        lone = commit(s, data, "自检.xlsx", sheet=sh["name"],
                      project_key="__自检仓_导入__", mapping=None)
        assert lone["ok"] is True
        # 换一个"库里没有任何合同"的项目 ⇒ 全部配不上、且一条都不许建
        p2 = pj_repo.create_project(s, project_type=TYPE_NORMAL, name_full="__自检_空项目__",
                                    warehouse_name="__自检仓_空__", phid="")
        s.flush()
        empty = commit(s, data, "自检.xlsx", sheet=sh["name"], project_key="__自检仓_空__")
        assert empty["ok"] is True and empty["updated"] == 0, empty
        assert empty["unmatched"] == 2, f"锚点找不到要逐条报出来，实际={empty}"
        assert not list(s.execute(select(JcContract).where(JcContract.project_id == int(p2.id))).scalars()), \
            "⛔ 配不上的行**不许**被静默建成新合同"

        # 列名没对上 ⇒ **明确拒绝**（⛔ 不许"什么都不导"还回成功）
        bad = commit(s, data, "自检.xlsx", sheet=sh["name"], project_key="__自检仓_导入__",
                     mapping={str(i): "" for i in range(7)})
        assert bad["ok"] is False and "列名" in bad["message"], bad
        # 项目不存在 ⇒ 明确拒绝
        noproj = commit(s, data, "自检.xlsx", sheet=sh["name"], project_key="__不存在的仓__")
        assert noproj["ok"] is False and "找不到项目" in noproj["message"], noproj
        s.rollback()


def R_ids(s, project_id: int) -> list:
    from sqlalchemy import select

    from app.mod11_jc.models import JcContract

    return list(s.execute(select(JcContract).where(JcContract.project_id == int(project_id))).scalars())


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
