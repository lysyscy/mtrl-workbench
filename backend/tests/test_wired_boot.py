"""前端壳「启动取数」的契约 —— 性能 **`P2`**（`TAIL-48`）的判据（离线读壳源码，不连库）。

守两件事：

① **分组并行**（`P2` 的落地形态）：`boot()` 不许再"一路一等"（首屏耗时 = 各路延迟**之和**）。
   ⭐ 逐条核过各路**真实数据依赖**后只有一条 —— `reloadM07`（大表的机械 / 焊材·气体列）与
   `reloadM05`（机械欠款）要吃 `reloadMech` ＋ `reloadInv` 的产物 ⇒ 它们必须在**第二组**；
   其余 **11 路互不相干** ⇒ 第一组。⛔ 顺手把某路挪组 = 静默取空（或退回串行），本件盯的就是这个。

② **逐路容错不许破**：每一路都走 `soft()`；坏的那路进 `fails` ⇒ 顶部横幅点名，其余页照常可用
   （`2026-09-17` 实测的假故障：`/api/m06/mech` 404 时**全站空表**、看着像功能没做）。

⚠️ 本件是**形态**判据（`@acc()` 未绑定，不映射判据点）：改了 `boot()` 的分组结构，**同批改这里**
   —— 这正是 `P2` 要防的"悄悄退回串行"。旧形态断言（`await soft(...)`）已按本仓规矩**搬**到新形态：
   `test_wired_m01.py`（待人工指认 / 待人工建档）· `test_wired_m02.py`（i8 执行记录）·
   `test_wired_m07.py`（顺序屏障，改成按**组**证）· `test_wired_m08.py`（逐路覆盖计数）。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
SHELL = (ROOT / "backend" / "app" / "web" / "index.html").read_text(encoding="utf-8")

# 第一组（互不相干；改 `boot()` 时若增减路径，**同批改这里**）
GROUP1 = (
    "付款通知书", "项目档案", "待人工指认", "待人工建档", "i8 执行记录", "修改留痕",
    "付款计划", "机械 6 列", "库存单据", "特殊费用月报表", "规则配置",
)
# 第二组（吃第一组产物 —— 依赖屏障，⛔ 不许挪走）
GROUP2 = ("收发结存与大表", "付款域")


def _boot() -> str:
    """`boot()` 的完整函数体（终点 = 下一个顶层函数）。"""
    i = SHELL.find("async function boot() {")
    assert i >= 0, "壳里找不到 `boot()`"
    j = SHELL.find("function bootErrorBanner()", i)
    assert j > i, "找不到 `boot()` 的终点（`bootErrorBanner`）"
    return SHELL[i:j]


def _groups(boot: str) -> list[str]:
    """`boot()` 里的 `await Promise.all([...])` 各段。"""
    return re.findall(r"await Promise\.all\(\[(.*?)\]\);", boot, re.S)


@acc()
def test_boot分两组并行且每一路都在组内():
    """⭐ `P2` 的正面判据：**两组** `await Promise.all([...])`，且 13 路**全都落在某一组里**
    （落在组外 = 又变成"一路一等"，或漏进 `Promise.all` 之外 —— 两种都要挡）。"""
    boot = _boot()
    groups = _groups(boot)
    assert len(groups) == 2, f"`boot()` 应当是**两组** `await Promise.all([...])`，实得 {len(groups)} 组"
    g1, g2 = groups
    for label in GROUP1:
        assert f"soft('{label}'" in g1, f"「{label}」不在第一组（它与其他路无依赖，应当并发发起）"
    for label in GROUP2:
        assert f"soft('{label}'" in g2, f"「{label}」不在第二组（它要吃 `reloadMech`/`reloadInv` 的产物）"
    # ⛔ 组外不许再出现任何一路（否则那一路仍是串行；且第一组会等它）
    outside = boot.replace(g1, "").replace(g2, "")
    assert "soft('" not in outside, "组外还有 `soft('…')` —— 有一路没进 `Promise.all`（仍是串行）"


@acc()
def test_boot第一组不含吃依赖的两路():
    """⛔ **依赖屏障不许挪**：`reloadM07` / `reloadM05` 进了第一组 ⇒ 与 `reloadMech`/`reloadInv` 并行
    ⇒ 大表机械列与机械欠款**取到空值且不报错**（`test_wired_m07.py` / `test_wired_m06.py` 也钉着）。"""
    groups = _groups(_boot())
    assert len(groups) == 2, "组数不对（先看上面那条）"
    g1, g2 = groups
    for label in GROUP2:
        assert f"soft('{label}'" not in g1, f"「{label}」被挪进第一组 ⇒ 依赖屏障丢了（会取到空值）"
    for label in ("机械 6 列", "库存单据"):
        assert f"soft('{label}'" not in g2, f"「{label}」被挪进第二组 ⇒ 它凭空多等一轮（该并发的被串行）"


@acc()
def test_boot逐路容错未破():
    """`soft()` 的**唯一职责**：吞异常并入 `fails`（顶部横幅点名），⛔ 一路失败不许拖垮全站。"""
    boot = _boot()
    assert "const soft = async (label, fn) =>" in boot, "`boot()` 没有逐路容错出口 `soft()`"
    assert "fails.push(" in boot, "`soft()` 没有把失败**记下来**（横幅就点不了名）"
    assert "BOOT_ERROR = fails.join(" in boot and "if (BOOT_ERROR) bootErrorBanner();" in boot, \
        "失败没有汇总成常驻横幅（只弹 toast 会一闪而过，用户只看到'页面是空的'）"
    assert "render();" in boot, "`boot()` 结尾没有统一渲染"


@acc()
def test_启动期间不补拉():
    """⏳ 性能 `P3`①（2026-09-19）：`boot()` 期间 `m05Sync()` **一律不补拉**。

    **为什么**（实测，不是推测）：`m05Sync()` 挂在 `render` 上，而它的参数里有 `ledCur()`（依赖
    `ledProjs()`）；`boot()` 那 13 路**陆续到位**时每次 `render()` 都看到参数在变
    ⇒ 实测同一页加载里 `/api/m05/{flows,stats,debt}` 各发 **3 次**、`ledger` 2 次（约 **420 ms** 纯重复）。
    ⛔ `m05Refetching` 挡不住这个 —— 它是"串行"、不是"合并"。
    ⭐ 放开必须在**第二组之后**（那里有一次**显式** `reloadM05()`；那时参数已稳定）。
    """
    boot = _boot()
    assert "let BOOTING = true;" in SHELL, "没有 `BOOTING` 标志（启动期的补拉会照旧连发）"
    assert "if (BOOTING || m05Refetching) return;" in SHELL, "`m05Sync()` 没在启动期被拦住"
    i_off = boot.find("BOOTING = false;")
    i_g2 = boot.find("await Promise.all(", boot.find("await Promise.all(") + 1)
    assert i_off > 0, "`boot()` 收尾没有放开补拉（那 `m05` 之后就不刷新了 —— 反向的坑）"
    assert i_g2 > 0 and i_off > i_g2, \
        "放开得太早：必须在**第二组**（含显式 `reloadM05()`）**之后**"

