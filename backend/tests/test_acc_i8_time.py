"""`ACC-I8-TIME-001`（核算年月 / 时间口径）7 个判据点的验收断言。

⚠️ 时间口径是 **`MOD-01` · `MOD-02` 共用** 的（实现落在 `app/core/period.py`）；
⭐ 它的**前端对侧** = 壳里的业务时钟 `SYS_YM` / `SYS_TODAY` ＋ 唯一出口 `bjMonth()`（见 `001-07` 后半）。
"""

from __future__ import annotations

import re
from datetime import date

import pytest

from app.core.errors import MustReportError
from app.core.period import (
    ALL_MODES,
    GLOBAL_PERIOD,
    MODE_ALL,
    MODE_MONTH,
    MODE_SPAN,
    MODE_YEAR,
    PERIOD_COMPONENT,
    default_period,
    export_filename,
    in_period,
    parse_period,
    period_capabilities,
    period_range,
)
from tests.acc_plugin import acc
from tests.shell_src import SHELL   # ⚠️ 壳源码的唯一出口（⛔ 别直接读 index.html）


@acc("ACC-I8-TIME-001", "001-01")
def test_全站统一核算年月组件且无全局年月控件():
    # 全站唯一组件 + 四种模式；**不设「全局核算期」**（顶栏不再有全局年月控件）
    assert PERIOD_COMPONENT["id"] == "acc-period"
    assert PERIOD_COMPONENT["modes"] == ALL_MODES
    assert GLOBAL_PERIOD is None


@acc("ACC-I8-TIME-001", "001-02")
def test_能力由调用点声明():
    # 列表页给 4 种模式
    assert period_capabilities("notice") == ALL_MODES
    # 抓取弹窗 / 期初截止年月**只声明「月」** ⇒ 不渲染模式切换条
    assert period_capabilities("fetch") == (MODE_MONTH,)
    assert period_capabilities("opening") == (MODE_MONTH,)


@acc("ACC-I8-TIME-001", "001-03")
def test_跨月两击选区间且闭区间生效():
    mode, value = parse_period("2026-01~2026-06")
    assert mode == MODE_SPAN and value == "2026-01~2026-06"
    start, end = period_range("2026-01~2026-06")
    assert (start, end) == ("2026-01-01", "2026-06-30")
    # **闭区间**：两端各自命中
    assert in_period("2026-01-01", "2026-01~2026-06")
    assert in_period("2026-06-30", "2026-01~2026-06")
    assert not in_period("2026-07-01", "2026-01~2026-06")
    assert not in_period("2025-12-31", "2026-01~2026-06")


@acc("ACC-I8-TIME-001", "001-04")
def test_年模式命中全年各月():
    assert parse_period("2026") == (MODE_YEAR, "2026")
    assert period_range("2026") == ("2026-01-01", "2026-12-31")
    for m in range(1, 13):
        assert in_period(f"2026-{m:02d}-15", "2026")


@acc("ACC-I8-TIME-001", "001-05")
def test_全部模式下发到付款流水与付款计划():
    # 「全部」不再是某一页独有 —— 付款通知书声明的它，同样下发到付款流水与付款计划
    for ctx in ("notice", "flow", "plan"):
        assert MODE_ALL in period_capabilities(ctx)


@acc("ACC-I8-TIME-001", "001-06")
def test_各表默认年月各按口径():
    fixed = date(2026, 9, 15)
    # 付款侧（通知书 / 计划 / 流水）= 当月
    assert default_period("notice", fixed) == "2026-09"
    assert default_period("plan", fixed) == "2026-09"
    assert default_period("flow", fixed) == "2026-09"
    # 材料报表类 = 上月（月度报表做的是上一个月）
    assert default_period("process", fixed) == "2026-08"
    assert default_period("inventory", fixed) == "2026-08"
    # 跨年：1 月的上月 = 去年 12 月
    assert default_period("process", date(2026, 1, 5)) == "2025-12"


@acc("ACC-I8-TIME-001", "001-07")
def test_不设全局核算期且导出文件名用当前年月():
    assert GLOBAL_PERIOD is None
    # 单月 ⇒ 用该月
    assert export_filename("付款通知书", "2026-03") == "付款通知书-2026-03"
    # 非单月 ⇒ 用**当前年月**（不得硬编码固定月）
    from datetime import datetime

    assert export_filename("付款通知书", "", now=datetime(2026, 9, 15)) == "付款通知书-2026-09"
    assert export_filename("付款通知书", "2026", now=datetime(2026, 9, 15)) == "付款通知书-2026-09"
    with pytest.raises(MustReportError):
        parse_period("2026/03")   # 非法形态 ⇒ 显式报错


@acc("ACC-I8-TIME-001", "001-07")
def test_壳的业务时钟取自北京时间而非写死():
    """⭐ `TAIL-51`：壳的**业务时钟**（全站默认年月的唯一源头）必须由**当前时间**派生。

    ⚠️ 为什么必须钉：`SYS_YM` / `SYS_TODAY` 原先写死 `'2026-09'` / `'2026-09-12'` —— 当时
    **恰好**是 2026-09 ⇒ **看不出来**；一过月，全站**默认年月**就指到**空月份**
    （材料域取上月 ⇒ 更早空），看板「本月抓取」还会照着假月份判 ⇒ 界面对真数据说假话。

    ⛔ 原型（`demo/`）那边**固定时钟是有意的**（它是演示快照）⇒ 本断言只扫壳（`SHELL`）。
    """
    # ① 初值**不得是日期字面量** —— 谁把时钟写回去，这条就变红（本断言的全部价值）
    for name in ("SYS_YM", "SYS_TODAY"):
        m = re.search(rf"^(?:const|let|var)\s+{name}\s*=\s*([^\r\n]+);", SHELL, re.M)
        assert m, (f"壳里找不到 `{name}` 的声明 —— 全站默认年月的**唯一时钟符号**没了"
                   "（⛔ 别改成各页各写一个）")
        init = m.group(1).strip()
        assert not re.fullmatch(r"'\d{4}-\d{2}(?:-\d{2})?'", init), (
            f"`{name}` 的初值是**写死的日期字面量** `{init}` —— "
            "一过月全站默认年月就指到空月份（`TAIL-51`）；必须由「当前时间」派生")

    # ② 取值来源必须是**北京时间**（`Asia/Shanghai`）—— ⛔ 不是"本机时区"、也不是别的时区
    #    ⚠️ 认的是**时区参数本身**（`timeZone:'Asia/Shanghai'`），⛔ 不是"壳里出现过这串字" ——
    #       注释里也会写它，只查出现与否会被**注释喂饱**（2026-09-21 反向灵敏度实测：
    #       把参数改成 `timeZone:'UTC'` 而注释还在 ⇒ 断言照绿 = 假绿）。
    m_tz = re.search(r"timeZone\s*:\s*['\"]Asia/Shanghai['\"]", SHELL)
    assert m_tz, ("壳里没有把**时区参数**设成 `Asia/Shanghai` —— 业务时钟的时区口径丢了"
                  "（《说明书》§9.2：取北京时间）。⚠️ 只在注释里写一句**不算**")
    assert m_tz.start() < SHELL.find("const SYS_YM"), (
        "时区参数没出现在 `SYS_YM` **之前** ⇒ 时钟不是由它派生的"
        "（别用 `new Date()` 直接取 —— 那取的是**本机时区**）")

    # ③ 老内核的**兜底路径**：必须按 **UTC 算固定 +8 小时**（⛔ 不得退到本机时区 ——
    #    那取的是「这台机的时间」，口径要的是北京时间；中国无夏令时 ⇒ 恒定 UTC+8）
    for tok in ("getUTCFullYear()", "getUTCMonth()", "getUTCDate()"):
        assert tok in SHELL, (f"兜底路径没有按 UTC 取（缺 `{tok}`）⇒ 很可能退到了**本机时区**，"
                              "而口径要的是北京时间")
    assert "8*3600*1000" in SHELL, "兜底路径的 +8 小时偏移没了（口径 = `Asia/Shanghai` = UTC+8）"

    # ④ 「调用点一处都不用动」那半还得成立：`bjMonth` 仍是唯一出口、仍从 `SYS_YM` 拆
    assert "const bjMonth = (off=0)=>{" in SHELL, "`bjMonth` 的形态变了 —— 全站默认年月的唯一出口"
    assert "SYS_YM.split('-')" in SHELL, "`bjMonth` 不再从 `SYS_YM` 拆 ⇒ 时钟符号与出口脱钩了"
