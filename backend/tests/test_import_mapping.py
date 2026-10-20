"""映射引擎 `import_kit.mapping` / `import_kit.profile_store` 的行为判据（`TAIL-75` B1）。

⭐ 断言里的素材**全部取自用户 2026-09-22 给的真文件**（见
`10-designs/设计-识别样本-真实模板-20260922.md`）—— ⛔ 不用编的列名，否则测的是想象。

⚠️ 判据**占号**（进验收基线）留到 B1 收口时做（本仓纪律：**不预先占号**）。
"""

from __future__ import annotations

from app.import_kit.mapping import (
    IGNORE, Field, apply, dupes, guess, join_levels, level_of, looks_like_data, normalize, profile,
    secondary, serial_hint,
)
from app.import_kit.profile_store import MIN_JACCARD, ProfileStore, fingerprint, jaccard

# —— 真文件里的字段声明（片段）——
M06_FIELDS = [
    Field("ym", "核算月", aliases=("时间", "核算年月", "月份"), type="ym", required=True),
    Field("in_main", "入库主辅材", aliases=("线上入库（不含税）主辅材",), type="amount"),
    Field("out_main", "出库主辅材", aliases=("线下出库（不含税）主辅材",), type="amount"),
    Field("rent_branch", "租分公司设备", aliases=("分公司设备",), type="amount"),
]
M11_FIELDS = [
    Field("supplier", "供应商", type="text", required=True),
    Field("contract_amt", "供应商合同总价", aliases=("供应商›合同总价",), type="amount"),
    Field("inv_sum", "供应商发票金额", aliases=("供应商›发票金额",), type="amount"),
]


# ------------------------------------------------------------------ 归一化（只用于比较）
def test_归一化_去空白全半角与大小写():
    assert normalize("  付款 方式 ") == "付款方式"
    assert normalize("ＡＢＣ") == "abc"
    assert normalize("合计\n金额") == "合计金额"


def test_归一化_只剥单位括号_语义括号必须留():
    """⭐ 真文件逼出来的：`金额（元）` 该剥；`线上入库（不含税）` **剥了就与「含税」撞车**。

    ⚠️ `NFKC` 会把全角括号转半角（`（）`→`()`）—— 这是**统一**，不是语义丢失；
    所以断言只看**语义**（含不含"不含税"、两者是否还区分得开），⛔ 不钉具体字形。
    """
    assert normalize("金额（元）") == "金额"
    assert normalize("合同总价（万元）") == "合同总价"
    assert "不含税" in normalize("线上入库（不含税）")            # 语义括号还在
    assert normalize("线上入库（不含税）") != normalize("线上入库（含税）")
    assert normalize(" 金额(元) ") == normalize("金额（元）")        # 全半角/空白等价


def test_次要键_剥通用后缀词():
    assert secondary("材料名称") == "材料"
    assert secondary("供应商编号") == "供应商"
    assert secondary("供应商") == "供应商"       # ⛔ 不能把「供应商」剥空


def test_两级拼名_两种顺序都要出():
    """慧能那份把「含税/不含税」放上级、把「外租设备（零租）」放下级 —— 与另两份**互换**。"""
    a, b = join_levels("外租机械（含税）", "零租")
    assert a == normalize("外租机械（含税）") + "零租"
    assert b == "零租" + normalize("外租机械（含税）")
    c, d = join_levels("含税", "外租设备（零租）")
    assert c == "含税" + normalize("外租设备（零租）")
    assert d == normalize("外租设备（零租）") + "含税"
    assert set(join_levels("外租机械（含税）", "零租")) == {"外租机械(含税)零租", "零租外租机械(含税)"}
    assert join_levels("", "零租") == ("零租", "零租")      # 缺一级 ⇒ 退化为单级


# ------------------------------------------------------------------ 内容画像（用值说话）
def test_画像_真文件里的六种形态():
    assert profile(["5,006.98", "595", "0"]) == "金额"             # 有千分位 ⇒ 金额
    assert profile(["797726.5", "28922"]) == "金额"                # 有小数点 ⇒ 金额
    assert profile(["2025-12-03", "2026-04-01"]) == "日期"
    assert profile(["20250901", "20240723"]) == "日期"             # 慧能/晋江台账的合同日期
    assert profile(["9月11号", "9月15号"]) == "年月"               # 付款计划里的中文月日
    assert profile(["202508", "202507"]) == "年月"
    assert profile(["FKTZS2025120365", "CL2026090012"]) == "编号"
    assert profile(["电汇", "承兑", "电汇"]) == "枚举"
    assert profile([None, "", "  "]) == "空列"
    assert profile(["#REF!", ""]) == "文本"                        # 公式残值 ⇒ 不是金额


def test_画像_纯整数不判金额_交给序列号提示由域裁():
    """⭐ 真文件的核心歧义：`45444` 既可能是金额也可能是 Excel 序列号 ⇒ 画像只敢说「数字」。"""
    vals = ["45444", "45475", "45507"]                             # 晋江那份的「时间」列
    assert profile(vals) == "数字" and serial_hint(vals) is True
    assert serial_hint(["797726.5", "28922"]) is False             # 金额列不是序列号
    # ⚠️ 月份非法（`00`）⇒ 再像也不是年月（否则 `400000` 也会被当成年月）
    assert profile(["400000", "300000"]) == "数字"


# ------------------------------------------------------------------ 建议（三档 · 只出建议）
def test_建议_三档阈值():
    assert level_of(1.00) == "auto" and level_of(0.90) == "auto"
    assert level_of(0.89) == "confirm" and level_of(0.70) == "confirm"
    assert level_of(0.69) == "blank"


def test_建议_真列名命中_自动档且可解释():
    got = {s.src: s for s in guess(["核算月", "入库主辅材"], M06_FIELDS)}
    assert got["核算月"].field == "核算月" and got["核算月"].level == "auto"
    assert "归一化后相同" in got["核算月"].why                 # 依据必须写出来（可解释）
    assert got["入库主辅材"].field == "入库主辅材"


def test_建议_拼名写法也能命中():
    """模板列是两级拼名（`线上入库（不含税）› 主辅材`），页面列叫「入库主辅材」—— 必须认得。"""
    key, _ = join_levels("线上入库（不含税）", "主辅材")
    got = guess([key], M06_FIELDS)[0]
    assert got.field == "入库主辅材" and got.level == "auto", got


def test_建议_认不出就留空_不猜():
    got = guess(["审批状态", "制单人", "（首列无名）"], M06_FIELDS)
    assert all(s.field is None and s.level == "blank" for s in got), got
    assert all("留给你选" in s.why for s in got)


def test_建议_类型不符要降档并写明():
    """列名叫「付款时间」但整列是「电汇/承兑」⇒ 降 0.20 并标"值像枚举与字段类型 date 不符"。"""
    got = guess(["付款时间"], [Field("pay_date", "付款时间", type="date")],
                samples={"付款时间": ["电汇", "承兑", "电汇"]})[0]
    assert got.conf == 0.80 and got.level == "confirm", got
    assert "不符" in got.why


def test_建议_文本列的弱画像不许把精确命中降档():
    """⭐ 回归：类型校验的方向（第一版写反 ⇒ **所有列**都被降权，"项目"这种精确命中也掉 confirm）。

    口径：`数字`/`文本` 是**弱证据**（值少、有歧义）⇒ 接受所有类型、⛔ 不降权；
    `枚举` 才是强证据（数值列到不了这一档）。"""
    got = guess(["项目"], [Field("pj", "项目", type="text")],
                samples={"项目": ["灵宝二期", "灵宝二期", "灵宝二期"]})[0]
    assert got.conf == 1.00 and got.level == "auto", got
    got2 = guess(["分公司设备"], [Field("rent", "分公司设备", type="amount")],
                 samples={"分公司设备": ["1,100.00", "1,100.00"]})[0]
    assert got2.conf == 1.00 and got2.level == "auto", got2      # 金额画像 ＋ amount ⇒ 不降权


def test_建议_相似但类型不符要掉到留空档():
    """⭐ `_CONF_CONFIRM` 的边界靠它守：0.82 再被类型降权 ⇒ 0.62 ⇒ **不许预选**（留空让人选）。"""
    got = guess(["分公司设备台账"], [Field("rent", "租分公司设备", type="amount")],
                samples={"分公司设备台账": ["已存档", "已存档", "已存档"]})[0]
    assert got.conf < 0.70 and got.field is None and got.level == "blank", got


def test_建议_同字段被多列认领要暴露出来():
    """台账/流水里「项目名称」与「项目」并存 ⇒ 记 `dupes`，⛔ 不自动裁决（域内才懂）。"""
    sugs = guess(["项目名称", "项目"], [Field("pj", "项目", type="text")])
    assert dupes(sugs) == {"项目": ["项目名称", "项目"]}


# ------------------------------------------------------------------ 取行（未映射 ⇒ 原样保留）
def test_取行_未映射与忽略的列都原样保留():
    headers = ["项目", "审批状态", "该流程金额"]
    rows = [["灵宝二期", "已审批", "797,726.5"]]
    mapping = {"项目": "项目", "该流程金额": "该流程金额", "审批状态": IGNORE}
    rec = apply(rows, headers, mapping)[0]
    assert rec["项目"] == "灵宝二期" and rec["该流程金额"] == "797,726.5"
    assert rec["raw"] == {"审批状态": "已审批"}          # ⭐ 原样保留（⛔ 不丢、不报错）
    assert "审批状态" not in rec


def test_取行_行比表头短不炸():
    rec = apply([["只有一格"]], ["a", "b"], {"a": "A"})[0]
    assert rec["A"] == "只有一格" and rec["raw"] == {"b": None}


# ------------------------------------------------------------------ 记忆（按表头指纹）
def test_指纹_同表同指纹_换顺序不同():
    h1 = ["项目", "付款时间", "该流程金额"]
    assert fingerprint(h1) == fingerprint(["项目", "付款时间", "该流程金额"])
    assert fingerprint(h1) != fingerprint(["项目", "该流程金额", "付款时间"])


def test_记忆_指纹命中_预填并可改(tmp_path):
    st = ProfileStore(tmp_path / "p.json")
    h = ["项目", "材料：其他支出付资产处/贸易公司（编号）", "该流程金额"]
    st.save("m04", h, {"项目": "项目", "该流程金额": "该流程金额"}, source_label="项目付款计划")
    hit = st.prefill("m04", h)
    assert hit and hit[2] == 1.0 and "来自记忆" in hit[1] and "可改" in hit[1]
    assert hit[0]["项目"] == "项目"


def test_记忆_表头大改就不用_小改用相似(tmp_path):
    """⭐ `MIN_JACCARD = 0.60`：表换了别拿旧映射硬套 —— 宁可空白让人选。"""
    st = ProfileStore(tmp_path / "p.json")
    st.save("m04", ["项目", "付款时间", "该流程金额", "付款方式", "备注"], {"项目": "项目"})
    old = ["项目", "付款时间", "该流程金额", "付款方式", "备注"]
    assert st.find("m04", ["项目", "付款时间"]) is None              # 大改 ⇒ 够不着
    hit = st.find("m04", ["项目", "付款时间", "该流程金额", "付款方式", "备注", "制单人"])
    assert hit and hit[2] == "相似" and hit[1] >= MIN_JACCARD        # 小改 ⇒ 相似命中
    assert jaccard(old, ["项目", "付款时间", "该流程金额", "付款方式", "备注"]) == 1.0
    assert jaccard(old, ["项目", "付款时间"]) < MIN_JACCARD          # 大改 ⇒ 够不着
    assert jaccard(old, ["项目", "付款时间", "该流程金额", "付款方式", "备注", "制单人"]) >= MIN_JACCARD


def test_记忆_落盘是原子写_且坏文件不炸(tmp_path):
    p = tmp_path / "p.json"
    st = ProfileStore(p)
    st.save("m11", ["序号", "合同日期", "供应商"], {"供应商": "供应商"})
    assert p.exists() and not p.with_suffix(p.suffix + ".tmp").exists()
    assert ProfileStore(p).count("m11") == 1          # 重开能读回
    p.write_text("{ 这不是 json", encoding="utf-8")     # 记忆件坏了
    assert ProfileStore(p).count() == 0               # ⇒ 当空处理，⛔ 不让它卡死导入


def test_记忆_可删可数_且按域隔离(tmp_path):
    st = ProfileStore(tmp_path / "p.json")
    st.save("m04", ["项目", "付款时间"], {"项目": "项目"})
    st.save("m11", ["序号", "供应商"], {"供应商": "供应商"})
    assert st.count() == 2 and st.count("m04") == 1
    assert st.find("m11", ["项目", "付款时间"]) is None      # ⛔ 别域的记忆不许套用
    assert st.drop("m04", ["项目", "付款时间"]) is True
    assert st.count("m04") == 0


def test_记忆_默认落点与cwd无关(tmp_path, monkeypatch):
    """⭐ 2026-09-24（真故障修）：默认落点必须是**工程根的绝对路径**。

    ⚠️ 改坏的样子 = 写回相对路径 `"artifacts/import_profiles.json"` ⇒ 落点跟 **cwd** 走：
    NSSM 服务的 `AppDirectory = backend/`（见 `ops/nssm_install.ps1`）⇒ 服务把记忆写进
    `backend/artifacts/…`，而工具 / pytest（cwd = 仓根）读写**根** `artifacts/…`
    ⇒ **同一份「导入映射记忆」分裂成两份**（页面上刚确认过的映射，跑测试时看不见 —— 2026-09-24 实测两份都在）。
    """
    monkeypatch.chdir(tmp_path)                    # ⭐ 把 cwd 挪走：相对路径必然落错
    st = ProfileStore()
    assert st.path.is_absolute(), f"默认落点必须是绝对路径，实为 {st.path}"
    assert st.path.parts[-2:] == ("data", "import_profiles.json"), st.path


# ---------------------------------------------------- 像数据吗（`TAIL-129` 表头定位的硬门槛）


def test_像数据的行不许当表头():
    """⭐⭐ 2026-09-27 **用户报障的最小回归**：「**最后落库的单据号大多都变成供应商名**了」。

    ⚠️ 起因：挑表头时把「表头第 2 行 ＋ **紧跟的第一行数据**」拼成了"两级表头"
       ⇒ 列名成了 `收款单位**资产处集中采购**` ⇒ 别名「资产处」被"包含词命中"抢走这一列
       ⇒ 收款单位（供应商名）落成了单据号。
    ⇒ 本条钉两半：① 真·数据行（编号/日期/金额/纯数字）**必须**判成"像数据"；
       ② 真·表头续行（`外租机械：付款通知书（编号）`）**不许**被判成"像数据"
       （⛔ 判严了会把正当的两级表头一起否掉）。
    """
    # ① 真表的**第一行数据**（就是它被误当成了子表头）
    row = ["灵宝二期", "", "2025-12-03 00:00:00", "FKTZS2025120365", "资产处集中采购",
           797726.5, 397726.5, 400000, "", "9月11号", "承兑", "循环水管道（唐山泽盈）"]
    assert looks_like_data(row) is True

    # ② 表头续行 / 表头本身 ⇒ **不是**数据（否则两级表头会被误杀）
    assert looks_like_data(["", "", "", "外租机械：付款通知书  （编号）", "", "", "", "", ""]) is False
    assert looks_like_data(["项目", "科目", "费用日期", "收款单位", "该流程金额", "备注"]) is False
    assert looks_like_data([]) is False and looks_like_data(["", ""]) is False

    # ③ 门槛**故意不严**：表头里偶尔出现一格年份/数字不算数据（≥2 格且占比 ≥50% 才算）
    assert looks_like_data(["项目", "2025", "备注"]) is False
