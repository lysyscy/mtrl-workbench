"""前端壳「启动 ＋ 按需取数」的契约 —— 性能 **`P2`**（分组并行）＋ **`P3`**（页级按需取数）。

守五件事：

① **进哪页拉哪页**（`P3` 主体）：`PAGE_LOAD` 表写死「页 → 它要的取数路」；`boot()` 只拉**初始视图**那一格、
   `go(k)` 拉 `k` 那一格 ⇒ 打开页面**不再**把 13 路全量拉一遍（实测：首屏请求 **18 → 3**，到数据可用 **216 → 88 ms**）。
② **依赖屏障**：`收发结存与大表` / `付款域` 要吃 `机械 6 列` ＋ `库存单据` 的产物 ⇒ 它们进 `LOAD_DEP` 组
   （**组间串行**、组内并发）。⚠️ 顺序写反 ⇒ 大表机械列 / 机械欠款**取到空值，且不报错**。
③ **逐路容错**：每一路都走 `soft()`；坏的那路进 `fails` ⇒ 顶部横幅**点名**，其余页照常可用。
④ **没到位就不补拉**：两道闸 —— `BOOTING`（启动期）与 `!LOADED.has('付款域')`（这页还没取过数）。
⑤ `boot()` 里**不许**再出现"全量组"（`Promise.all`）—— 那是改前的形态（`P2` 的产物）。

⚠️ 本件是**形态**判据（`@acc()` 未绑定）：改 `boot()` / `go()` / `PAGE_LOAD` 的结构，**同批改这里**
   —— 这正是 `P3` 要防的"悄悄退回全量拉"。
"""

from __future__ import annotations

from tests.acc_plugin import acc

from tests.shell_load_helpers import (
    DEP, DEP_BEFORE, PAGES, SHELL, boot_body, load_dep, load_paths_body, loaders, page_load,
)


@acc()
def test_按需取数表覆盖每一页且标签都在LOADERS():
    """⭐ `P3` 的正面判据：**十一页都有清单**（十页 `WIRED` ＋ `home`），且清单里的每个标签都在 `LOADERS` 里。

    ⚠️ 这一条是"标签不许拼错/漏登记"的守卫 —— 拼错一个 ⇒ 那一路**永远拉不到**（且不报错）。
    """
    pl, ls = page_load(), loaders()
    for page in PAGES:
        assert page in pl, f"`PAGE_LOAD` 里没有 `{page}`（那页进不去数据）"
        assert pl[page], f"`PAGE_LOAD['{page}']` 是空的"
    for page, labels in pl.items():
        for label in labels:
            assert label in ls, f"`PAGE_LOAD['{page}']` 里的「{label}」在 `LOADERS` 里没有对应取数函数"
    assert len(ls) >= 13, f"`LOADERS` 只剩 {len(ls)} 路 —— 有取数口被删了？"


@acc()
def test_boot只拉初始视图而go按需拉():
    """⭐ 核心：`boot()` **只**拉初始视图那一格；进哪页由 `go(k)` 拉 ⇒ 首屏不再全量。

    ⛔ `boot()` 里**不许**再有 `Promise.all([...])` 的那种"全量组"（改前形态）。
    """
    boot = boot_body()
    assert "loadPaths(PAGE_LOAD[VIEW]" in boot, "`boot()` 没有「只拉初始视图」（又回到全量拉？）"
    assert "Promise.all(" not in boot, "`boot()` 里又出现了全量组（13 路一次拉全 = 退回改前形态）"
    assert "loadPaths(PAGE_LOAD[k]" in SHELL, "`go(k)` 没有按需拉该页的清单"
    assert "loadPaths(" in load_paths_body(), "`loadPaths()` 自己没有取数"


@acc()
def test_依赖路必须等机械与库存():
    """⛔ **依赖屏障不许挪**：`LOAD_DEP` 那两路必须等 `机械 6 列`＋`库存单据`；
    且**凡清单里出现它们的页，必须同时含前置两路**（行为级 —— 比"顺序"断言更强）。"""
    dep = load_dep()
    for lbl in DEP:
        assert lbl in dep, f"「{lbl}」不在 `LOAD_DEP` 里（它要吃前置路的产物）"
    pl = page_load()
    for page, labels in pl.items():
        for dep_lbl, needs in DEP_BEFORE.items():
            if dep_lbl in labels:
                for need in needs:
                    assert need in labels, \
                        f"`PAGE_LOAD['{page}']` 要吃「{dep_lbl}」却没列前置的「{need}」（会取到空值且不报错）"
    body = load_paths_body()
    i_pre = body.find("!LOAD_DEP.has(l)")
    i_dep = body.find("LOAD_DEP.has(l)", i_pre + 1)
    assert i_pre > 0 and i_dep > i_pre, "`loadPaths()` 里依赖组没排在后面（组间串行被拆了）"


@acc()
def test_逐路容错未破():
    """`soft()` 的**唯一职责**：吞异常并入 `fails`（顶部横幅点名），⛔ 一路失败不许拖垮全站。"""
    assert "const soft = async (label, fn) =>" in SHELL, "没有逐路容错出口 `soft()`"
    assert "fails.push(" in SHELL, "`soft()` 没有把失败**记下来**（横幅就点不了名）"
    assert "BOOT_ERROR = fails.join(" in SHELL and "if (BOOT_ERROR) bootErrorBanner();" in SHELL, \
        "失败没有汇总成常驻横幅（只弹 toast 会一闪而过，用户只看到'页面是空的'）"
    body = load_paths_body()
    assert "soft(l, LOADERS[l])" in body, "`loadPaths()` 没有逐路走 `soft()`（容错被绕过）"


@acc()
def test_没到位就不补拉():
    """⏳ `P3`① ＋ `P3` 主体的两道闸，防"启动期把 m05 那几路白白拉一遍"。

    （实测：`m05Sync()` 挂在 `render` 上、参数含 `ledCur()`（依赖 `ledProjs()`）⇒ 各路数据陆续到位时
      参数在变 ⇒ 同一页加载里 `/api/m05/{flows,stats,debt}` 各发 **3 次**、`ledger` 2 次。
      `BOOTING` 挡启动期；`!LOADED.has('付款域')` 挡"这页还没取过数"（同时避免与 `loadPaths` 并发重复）。
    """
    assert "let BOOTING = true;" in SHELL, "没有 `BOOTING` 标志（启动期的补拉会照旧连发）"
    assert "if (BOOTING || m05Refetching || !LOADED.has('付款域')) return;" in SHELL, \
        "`m05Sync()` 的两道闸不在了（会重复拉 / 或在别的页上白拉）"
    boot = boot_body()
    i_load = boot.find("loadPaths(")
    i_off = boot.find("BOOTING = false;")
    assert i_off > 0 and i_load > 0 and i_off > i_load, \
        "`BOOTING` 放开得太早：必须在**自己的取数发起之后**"
