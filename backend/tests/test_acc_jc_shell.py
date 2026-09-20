"""`ACC-JC-FETCH-001` · **壳侧**（抓取入口 / 三态批量勾选）的验收断言。

⚠️ 与 `test_acc_jc_fetch.py`（**库级**：落库 / 幂等 / 不覆盖）分工：本文件只钉**页面形态**。
⚠️ 逐条对应（claim 原文见验收基线）：
   - `001-01` 触发方式写明「人工点击 + 定时自动（一期启用）」，且执行记录含**定时自动**那一条
   - `001-02` 抓取入口打开「**按月抓取**」弹窗（与其它接口入口行为一致）；**无抓取交互的接口**仍走提示
   - `001-04` 未勾选时批量按钮**先禁用**（⛔ 不是点了才拦）
   - `001-06` 全选范围 = **当前筛选结果**；筛选收紧后勾选**被裁剪**
"""

from __future__ import annotations

import pathlib
import re

import app
from tests.acc_plugin import acc


def _index() -> str:
    return (pathlib.Path(app.__file__).resolve().parent / "web" / "index.html").read_text(encoding="utf-8")


def _actions() -> str:
    return (pathlib.Path(app.__file__).resolve().parent / "web" / "shell" / "actions.js").read_text(encoding="utf-8")


def _all_shell() -> str:
    """**整支壳**（`index.html` ＋ `core.js` ＋ `actions.js`）拼起来。

    ⚠️ 判"某个函数有没有被调用"必须用**整支** —— 定义在 `index.html`、调用却散在
       `actions.js` 与 `core.js` 里（`pruneJcPick` 就是：定义 1 处、调用 8 处）。
       ⛔ 只搜一个文件会得出"定义了没调用"的**假结论**（我第一版就这么误判了）。
    """
    d = pathlib.Path(app.__file__).resolve().parent / "web"
    return "\n".join([
        (d / "index.html").read_text(encoding="utf-8"),
        (d / "shell" / "core.js").read_text(encoding="utf-8"),
        (d / "shell" / "actions.js").read_text(encoding="utf-8"),
    ])


def _fn(src: str, anchor: str, end: str) -> str:
    i = src.index(anchor)
    return src[i:src.index(end, i)]


@acc("ACC-JC-FETCH-001", "001-01")
def test_触发方式写明且执行记录含定时自动那条():
    """claim：「**触发方式写明**「人工点击 + 定时自动（一期启用）」，且**执行记录含定时自动触发那一条**」。

    ⚠️ 两半都要钉，而且**要钉在对的接口上**：
       ① 「定时自动」这句是**集采合同（`API-04`）**的口径（§6.4 / 技术栈 `OPEN-T9`）——
          ⛔ 不能"随便哪个接口写了就算"，否则别的接口写一句同一句话就能骗过断言；
       ② 执行记录里要**真的有一条**「定时自动触发」的记录行（⛔ 只有说明文字、没有记录行不算）。
    """
    html = _index()
    api04 = next((ln for ln in html.splitlines() if "'API-04'" in ln), None)
    assert api04, "API 清单里找不到 `API-04`（采购合同信息）这一行 —— 落点变了"
    assert "人工点击 + 定时自动（一期启用）" in api04, (
        "`API-04` 那一行没写明触发方式「人工点击 + 定时自动（一期启用）」——\n"
        f"  实际那一行是：{api04.strip()[:160]}")
    assert "定时自动触发" in html, (
        "执行记录里没有**定时自动触发**那条记录 ⇒ 页面只说了「会定时」，却拿不出跑过的凭据"
        "（claim 后半句要求「执行记录**含**定时自动触发那一条」）")


@acc("ACC-JC-FETCH-001", "001-02")
def test_抓取入口统一走按月抓取_没有落点的如实提示():
    """claim：「抓取入口打开「**按月抓取**」弹窗（**与其它接口入口行为一致**）；
    **无抓取交互的接口**仍走模拟提示」。

    ⚠️ 「行为一致」在这个壳里 = 三个真入口（`API-01`/`02`/`03`）**都**走到各自那个
       「按月抓取」弹窗，⛔ 不许有谁落回一句 toast 就完事（那样同一个"触发"按钮点下去行为不同）。
    ⚠️ 兜底那句**必须如实**（"尚未接通 / ⛔ 不假装成功"）——
       ⛔ 兜底里出现"模拟成功"这类字样就等于**在骗用户**（claim 里"模拟提示"指的是
       **没有抓取交互**的接口，不是"假装抓成功"）。
    """
    body = _fn(_actions(), "fetchOne:", "manualUp:")
    for api, handler in (("API-01", "fetchNt"), ("API-02", "fetchWh"), ("API-03", "fetchIv")):
        assert api in body and handler in body, (
            f"`fetchOne` 没有把 `{api}` 分派到 `{handler}` —— 三个真入口的行为会不一致")
    for api, handler in (("API-05", "m02Sync"), ("API-06", "m02Sync")):
        assert api in body and handler in body, f"`fetchOne` 没有把 `{api}` 分派到真同步 `{handler}`"
    assert "尚未接通" in body, (
        "`fetchOne` 的兜底没写「尚未接通」这类如实提示 —— 无抓取交互的接口会被静默吞掉")
    assert "不假装成功" in body or "⛔" in body, "兜底提示要**如实**（明说没接通），⛔ 不许含糊过去"


@acc("ACC-JC-FETCH-001", "001-04")
def test_批量标记按钮未勾选时先禁用():
    """claim：「**未勾选时批量按钮先禁用**（⛔ **不是点了才拦**）」。

    ⚠️ 「先禁用」和「点了再拦」是**两件不同的事**：后者用户会先点一下、被拒一次，才知道要勾选。
       ⇒ 判据必须钉在**按钮标签本身**（`disabled`）上，⛔ 不能只看 handler 里有没有那句拦截
       （handler 里的拦截是**第二道**保险，两者**都要有**，但**只有前者**满足 claim）。
    """
    html = _index()
    tags = re.findall(r"<button[^>]*data-act=\"jcBatchTag\"[^>]*>", html)
    assert tags, "找不到批量标记按钮（`data-act=\"jcBatchTag\"`）—— 落点变了"
    for tag in tags:
        assert "disabled" in tag, (
            "这个批量标记按钮**没有「先禁用」**（标签里没有 `disabled`）⇒ 用户会先点一下被拒，"
            f"才知道要先勾选：\n  {tag[:150]}")
        assert "jcPick.size?" in tag, (
            "批量按钮的 `disabled` 不是跟着**勾选数**走的 ⇒ 禁用条件大概接错了对象：\n"
            f"  {tag[:150]}")
    body = _fn(_actions(), "jcBatchTag:", "CHG=")
    assert "if(!jcPick.size)" in body, (
        "handler 里少了第二道保险（点了也要拦）—— 按钮禁用是「先禁用」，"
        "但**状态可能被外部改动**，两道都要在")


@acc("ACC-JC-FETCH-001", "001-06")
def test_全选只作用于当前筛选结果且收紧后被裁剪():
    """claim：「**全选范围 = 当前筛选结果**；**筛选收紧后勾选被裁剪，不越界**」。

    ⚠️ 两半：
       ① 全选**只**勾"当前可见"（= 筛选结果）—— ⛔ 不是全量：否则用户筛了"甲仓"再点全选，
          会把**看不见的**行也勾上，之后批量标记就**越界**改了没看见的行；
       ② 筛选**收紧**（可见集变小）后，已经勾上、但现在看不见的行必须**被裁掉**。
       ⚠️ ②尤其要紧：不裁的话"全选 → 改筛选 → 批量标记"会改到**屏幕上根本不存在**的行。
    """
    html = _index()
    acts = _actions()

    # ① 全选 = 当前可见（筛选结果），⛔ 不是全量
    assert "jcVisible()" in _fn(acts, "jcPickAll:", "jcBatchTag"), (
        "全选没有走 `jcVisible()`（= 当前筛选结果）—— 那它勾的就是**全量**，"
        "筛了「甲仓」再点全选会连看不见的行一起勾上，之后批量标记就改了屏幕上没有的行")

    # ② 筛选收紧后裁剪：`pruneJcPick` 拿 `jcVisible()` 做差集，且**真的被调用**
    i = html.index("const pruneJcPick=")
    pruned = html[i:i + 420]                     # ⚠️ 按固定窗口取本行即可：
    assert "jcVisible()" in pruned, (            #    ⛔ 别拿"后面的某个声明"当终止标记 ——
        "`pruneJcPick` 没有拿 `jcVisible()` 做差集 —— 筛选收紧后勾选不会被裁剪，"  # 那可能在它**前面**
        "批量标记会越界改到屏幕上看不见的行")
    assert _all_shell().count("pruneJcPick()") >= 4, (
        "`pruneJcPick()` 的调用点太少 ⇒ 有些筛选变化后根本不会裁剪"
        "（⚠️ 必须搜**整支壳**：定义在 `index.html`、调用散在 `actions.js`/`core.js`）")
