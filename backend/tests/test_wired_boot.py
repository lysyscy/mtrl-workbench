"""前端壳「启动 ＋ 按需取数」的契约 —— 性能 **`P2`**（分组并行）＋ **`P3`**（页级按需取数）。

守五件事：

① **进哪页拉哪页**（`P3` 主体）：`PAGE_LOAD` 表写死「页 → 它要的取数路」；`boot()` 只拉**初始视图**那一格、
   `go(k)` 拉 `k` 那一格 ⇒ 打开页面**不再**把 13 路全量拉一遍（实测：首屏请求 **18 → 3**，到数据可用 **216 → 88 ms**）。
② **依赖屏障**：`收发结存与大表` / `付款域` 要吃 `机械 6 列` 的产物 ⇒ 它们进 `LOAD_DEP` 组
   （**组间串行**、组内并发）。⚠️ 顺序写反 ⇒ 大表机械列 / 机械欠款**取到空值，且不报错**。
③ **逐路容错**：每一路都走 `soft()`；坏的那路记入当前 `FAILED` ⇒ 顶部横幅**点名**，其余页照常可用。
④ **没到位就不补拉**：两道闸 —— `BOOTING`（启动期）与 `!LOADED.has('付款域')`（这页还没取过数）。
⑤ `boot()` 里**不许**再出现"全量组"（`Promise.all`）—— 那是改前的形态（`P2` 的产物）。

⚠️ 本件是**形态**判据（`@acc()` 未绑定）：改 `boot()` / `go()` / `PAGE_LOAD` 的结构，**同批改这里**
   —— 这正是 `P3` 要防的"悄悄退回全量拉"。
"""

from __future__ import annotations

from tests.acc_plugin import acc

from tests.shell_load_helpers import (
    DEP, DEP_BEFORE, PAGES, SHELL, loaders, page_load,
)
# ⭐ 2026-10-03（`TAIL-219` 批 2／2b）：函数体与常量项改走壳的语义口径（⛔ 别在本件自造剪刀）
from tests.shell_src import const_items, func_body


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
    boot = func_body("boot")
    assert "loadPaths(PAGE_LOAD[VIEW]" in boot, "`boot()` 没有「只拉初始视图」（又回到全量拉？）"
    assert "Promise.all(" not in boot, "`boot()` 里又出现了全量组（13 路一次拉全 = 退回改前形态）"
    assert "loadPaths(PAGE_LOAD[k]" in SHELL, "`go(k)` 没有按需拉该页的清单"
    assert "loadPaths(" in func_body("loadPaths"), "`loadPaths()` 自己没有取数"


@acc()
def test_依赖路必须等机械():
    """⛔ **依赖屏障不许挪**：`LOAD_DEP` 那两路必须等 `机械 6 列`；
    且**凡清单里出现它们的页，必须同时含前置路**（行为级 —— 比"顺序"断言更强）。"""
    dep = set(const_items("LOAD_DEP"))
    for lbl in DEP:
        assert lbl in dep, f"「{lbl}」不在 `LOAD_DEP` 里（它要吃前置路的产物）"
    pl = page_load()
    for page, labels in pl.items():
        for dep_lbl, needs in DEP_BEFORE.items():
            if dep_lbl in labels:
                for need in needs:
                    assert need in labels, \
                        f"`PAGE_LOAD['{page}']` 要吃「{dep_lbl}」却没列前置的「{need}」（会取到空值且不报错）"
    body = func_body("loadPaths")
    i_pre = body.find("!LOAD_DEP.has(l)")
    i_dep = body.find("LOAD_DEP.has(l)", i_pre + 1)
    assert i_pre > 0 and i_dep > i_pre, "`loadPaths()` 里依赖组没排在后面（组间串行被拆了）"


@acc()
def test_逐路容错未破():
    """逐路容错记录当前失败，加载与启动收尾都同步横幅（含全部恢复）。"""
    assert "const soft = async (label, fn) =>" in SHELL, "没有逐路容错出口 `soft()`"
    assert "FAILED.set(label" in SHELL, "没有按路名记录当前失败"
    sync = func_body("syncBootErrors")
    assert "Array.from(FAILED," in sync and "BOOT_ERROR = fails.join(" in sync
    assert "bootErrorBanner();" in sync and "if (BOOT_ERROR)" not in sync, "全部恢复也须同步移除横幅"
    assert "syncBootErrors();" in func_body("boot") and "syncBootErrors();" in func_body("loadPaths")
    assert "soft('当前登录用户', reloadWho)" in func_body("boot")
    body = func_body("loadPaths")
    assert "soft(l, LOADERS[l])" in body, "`loadPaths()` 没有逐路走 `soft()`（容错被绕过）"


@acc()
def test_跨页写动作后全标脏():
    """⭐⭐ `TAIL-48` 余项 `P3`②（2026-09-24）：**跨页写 ⇒ 全标脏**（唯一出口 `markCrossPageStale()`）。

    证据（写/读两侧到**表级**）= `.codebuddy/work/10-designs/设计-写动作标脏数据流图-20260924.md`：
    壳按 `PAGE_LOAD` 进哪页拉哪页、`LOADED` 记"这路拉过了"，而写动作**只 reload 自己那页**
    ⇒ 别的页读同一批表时**拿着旧数**（= 对真数据说旧话）。⚠️ 与 `TAIL-78`（导入那两处）**同一口径**。

    ⛔ **不许**改成"写动作 → 受影响页"的字面映射表：读侧一改，那张表就开始漏（**双份真源**）；
    ✅ 全标脏 = 下次进哪页拉哪页（多几路 GET），**永不漏拉**。

    ⚠️ 判据钉的是"**写出口**里有标脏、取数路径里没有" —— 少一处 ⇒ 那条写路径之后别人一直看旧数，
       而界面上**全程看不出来**（正是本仓最忌的一类）。
    """
    assert "function markCrossPageStale() { LOADED.clear(); }" in SHELL, \
        "唯一出口 `markCrossPageStale` 被改掉了（标脏口径只此一处）"
    api = SHELL[SHELL.index("const API = {"):SHELL.index("/* ---------- 字段适配")]
    n = api.count("markCrossPageStale();")
    assert n == 6, (f"`API` 写出口里标脏 {n} 处（应为 6：post / send / postForm / postFile / "
                    "fetchNotices / m07Fetch）—— 少一处 ⇒ 那条写路径之后别的页会一直拿着旧数")
    get_body = api[api.index("async get(url)"):api.index("async post(url")]
    assert "markCrossPageStale();" not in get_body, "⛔ 取数路径（`API.get`）里不该标脏"
    # ⭐ `#3`（2026-09-26 用户裁定「写在通用模块里、不必靠自觉」）：`LOADED.clear()` **只许出现在出口里**。
    #    ⚠️ 报障前的形态：`legacy.js` 的导入落库 / 回滚**各自手写了一遍** `LOADED.clear()`（与出口重复）——
    #       重复本身无害，但它**教坏了后来人**："标脏要在业务动作里写"⇒ 新写一个写动作多半会漏
    #       （`TAIL-78` 就是这么漏掉一路的：付款通知书改了统计金额 ⇒ 切回 m03/m05 看旧数）。
    import re as _re                                  # ⚠️ 局部导入：本件别处没用到正则
    # ⚠️⚠️ **必须剥掉块注释再数**：注释里会**引述**这个写法（"原先有三处"、"与 TAIL-78 那两处同一口径"…）
    #     —— 不剥 ⇒ 说明性注释把判据自己判红（本仓踩过多次，见 `test_acc_theme_user.py` 的头注）。
    code = _re.sub(r"/\*.*?\*/", "", SHELL, flags=_re.S)
    # ⭐ `#4`（2026-09-26）：浮层锚点 `pjwrap` 是"浮层**不会被 `.tw` 裁掉**"的唯一保险 ——
    #    漏一个 ⇒ 界面上只表现为"某一格的下拉被裁了一半"（看不出是漏了 wrapper）。
    #    ⇒ 判据钉**两条不变量**（写法只许两种 ＋ 面板必须都有锚点）；把 markup 搬进共用件是纯形态、
    #      零行为收益，那条已在设计件 §四 排队（本判据先保证"漏了会红"）。
    forms = _re.findall(r'class="[^"]*pjwrap[^"]*"[^>]*style="([^"]*)"', code)
    assert forms, "壳里连 `pjwrap` 锚点都没有了 —— 浮层会被 `.tw` 裁掉（本该有一圈 anchor 包装）"
    bad = [f for f in forms if f not in ("position:relative", "position:relative;display:inline-block")]
    assert not bad, (
        f"`pjwrap` 出现了**非标准形态**：{bad} —— 只许两种"
        "（表单格 `position:relative` / 行内 `position:relative;display:inline-block`）")
    n_panel = SHELL.count("projPanel({")
    n_wrap = len(_re.findall(r"pjwrap", code))
    assert n_wrap >= n_panel, (
        f"`projPanel` 调用 {n_panel} 处、`pjwrap` 锚点只有 {n_wrap} 处 —— "
        "少的那几处浮层会被滚动容器裁掉（界面上只是一格错位，看不出根因）")
    hits = code.count("LOADED.clear()")
    assert hits == 1, (
        f"`LOADED.clear()` 全壳出现 {hits} 次 —— **只许 1 次**（在 `markCrossPageStale()` 里）；"
        "业务动作里手写清空 = 两处口径 ⇒ 下一个人会以为必须写，而漏写的人没有任何东西提醒他")


@acc()
def test_项目面板的搜索与归档折叠():
    """⭐⭐ 2026-09-27（用户裁定 ①② · 原话：「项目总会越来越多，不能无限制地让候选数量增加」）。

    做法（都在**壳里唯一那一处** `projPanel`，13 个调用点同时受益）：
      ① **搜索框** —— 按**展示名 / 仓库名**筛这一屏的显示；⛔ **不改候选集合**（§2.7.1 一字不动：
         含归档、排最后、标注、可选性都不变）⇒ 它治的是"**找得到**"；
      ② **归档折叠** —— 归档那一整段（本来就在最后）**默认折成一行**，点开照旧可选 ⇒ 治"不占视线"。

    判词（四条，缺一条就是新坑）：
      ① 面板里有 `data-act="pjSearch"`，且它有**专属的 `input` 委托**（⚠️ ⛔ 不走 `change`：那要等失焦）；
      ② ⛔ 过滤**不许重绘**（重绘重建输入框 ⇒ **焦点与光标一起丢**，壳里踩过）⇒ 必须走
         `applyPjFilters()` 这种"只切 DOM 显示"的路，关键词存 `PJ_TXT`（重绘后回填）；
      ③ 归档折叠行**必须报「已选 k」** —— 多选面板的「全选」含归档（§2.7.1），
         折起来不报就是"**看不见的已选**"（状态不真实可见）；折叠态走 `PJ_OPEN`（⛔ 不许另开一份状态）；
      ④ **有关键词时归档自动展开**（藏在折里 ⇒ "搜不到"是假话）。

    ⚠️ 能证伪：删搜索框 / 改成只认 `change` / 折叠行去掉已选数 / 折叠态改用新变量 ⇒ 本件必红。
    """
    code = SHELL
    # ⚠️ 断言要**写死到标记本身**（`data-act` ＋ `data-pk` ＋ 值回填）——
    #    只查 `'data-act="pjSearch"' in code` 会被**委托层那行**（`closest('[data-act="pjSearch"]')`）
    #    满足 ⇒ 面板里把搜索框删掉/改名它**照样绿**（本件反向灵敏度实测抓到过）。
    assert '<input class="inp" data-act="pjSearch" data-pk="${pk}" value="${esc(PJ_TXT[pk]||\'\')}"' in code, \
        "项目面板里没有「搜索框」这个输入（① 没落地 / 改了标记）"
    assert "document.addEventListener('input'" in code, \
        "没有处理搜索的 `input` 委托（⛔ 只认 change 的话要等失焦才筛）"
    assert "function applyPjFilters()" in code, "过滤/折叠没有唯一出口（`applyPjFilters`）"
    assert "const PJ_TXT = {}" in code and "value=\"${esc(PJ_TXT[pk]||'')}\"" in code, \
        "关键词没存 / 重绘后没回填 —— 勾一个候选搜索词就被清零（多选场景等于没法用）"
    assert 'data-act="pjArcToggle"' in code, "归档段没有折叠行（② 没落地）"
    assert "已归档（${arc.length}${arcSel?` · 已选 ${arcSel}`:''}）" in code, \
        "折叠行**没报已选数** —— 多选面板「全选」含归档 ⇒ 会出现看不见的已选（状态不真实可见）"
    arc=code[code.index('pjArcToggle:t=>{'):code.index('procPjToggle:',code.index('pjArcToggle:t=>{'))]
    assert "const key=String(t.dataset.pk||'')+'Arc'; PJ_OPEN[key]=!PJ_OPEN[key];" in arc, \
        "归档折叠必须继续使用统一的PJ_OPEN状态"
    assert 'replaceFilterPop(w,make())' in arc, "归档折叠缺少浮层局部更新"
    assert "data-pj-none" in code and "没有匹配「" in code, \
        "搜不到时没有空态提示 —— ⛔ 不许只留一片空白（用户会以为面板坏了）"
    assert "arcBlock.hidden = q ? false : !pjIsOpen(" in code, \
        "有关键词时归档段没有自动展开（藏在折里 ⇒「搜得到」成了假话）"


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
    boot = func_body("boot")
    i_load = boot.find("loadPaths(")
    i_off = boot.find("BOOTING = false;")
    assert i_off > 0 and i_load > 0 and i_off > i_load, \
        "`BOOTING` 放开得太早：必须在**自己的取数发起之后**"
