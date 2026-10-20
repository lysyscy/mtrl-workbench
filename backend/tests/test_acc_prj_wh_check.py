"""`ACC-PRJ-OWN-001` —— 链路 C **兜底前先跑一次 i8 仓库名单**（`TAIL-39`）验收断言。

用户 2026-09-18 口述裁定的原话：「**在兜底前，系统的设计里应该有去仓库跑了一环这个逻辑，
而且如果跑完没结果要在界面上提醒用户**」。

**病根**：兜底 = **手填仓库名**新建具体小微 ⇒ 用户**凭猜**填 ⇒ 留下与 i8 不符的**假档案行**；
日后 i8 真建了这个仓库 ⇒ 系统**再建一行**（重复）。⇒ **建之前先问 i8**。

⚠️ 本文件**不连 i8**：取数件由参数注入（桩）；端点**直接调函数**（不起服务）。
⚠️ **判据点** `ACC-PRJ-OWN-001` 的加点 = 按该用例（说明书 `MOD-01` 能力 5/11 挂它）⇒ 可绑。
"""

from __future__ import annotations

import inspect

from app.mod01_projects.domain import i8_warehouse_lookup
from app.mod02_i8 import wh_cache
from app.mod03_notice import router as m03r
from app.mod03_notice.schemas import WarehouseCheckRequest

ROWS = [
    {"warehouse_name": "兰考金不换前置车间项目", "owner_full_name": "第四工程公司2026年小微项目"},
    {"warehouse_name": "沭阳仓库", "owner_full_name": "第四工程公司2026年小微项目"},
    {"warehouse_name": "沭阳仓库", "owner_full_name": "四分公司2019年小微项目"},       # 同名挂两条全名
]


def _stub(rows=ROWS, *, seen=None):
    """取数桩（记录收到的 `allow_kick`，不连 i8）。"""
    def _load(allow_kick=False, client=None):
        if seen is not None:
            seen.append(allow_kick)
        return rows
    return _load


def _call(name, rows=ROWS, allow_kick=False, seen=None):
    return m03r.warehouse_check(
        WarehouseCheckRequest(warehouse_name=name, allow_kick=allow_kick),
        wh_loader=_stub(rows, seen=seen),
    )


# --------------------------------------------------------------- 1 · 判定（唯一出口）


def test_查名单的三态_命中_没命中_同名多主():
    """⚠️ 三种结果必须**分得开**：命中 ⇒ 给出所属全名；没命中 ⇒ 如实"没有"；同名多主 ⇒ 全给（⛔ 不替选）。"""
    hit = i8_warehouse_lookup("兰考金不换前置车间项目", ROWS)
    assert hit["found"] is True and hit["owners"] == ["第四工程公司2026年小微项目"]
    assert hit["total"] == 3, "名单条数要如实（用户看得到「这次跑回来几条」）"

    miss = i8_warehouse_lookup("不存在的仓库", ROWS)
    assert miss["found"] is False and miss["owners"] == [], "没命中就**不许编**一个所属全名"

    multi = i8_warehouse_lookup("沭阳仓库", ROWS)
    assert multi["found"] is True and len(multi["owners"]) == 2, \
        "同名挂两条全名要**全给**（与 needs_confirm 同一类事实：⛔ 不替用户选一个）"

    empty = i8_warehouse_lookup("兰考金不换前置车间项目", None)
    assert empty["found"] is False and empty["total"] == 0, \
        "取不到名单 ⇒ 只是「没查到」，⛔ 不是「没有」（由调用方区分）"


def test_仓库名比较是精确的白名单不剥尾码():
    """⛔ **不许把项目全名那套尾码剥离（§2.3.2）用到仓库名上**：仓库名是唯一标识 / 候选键（§2.7.4），
    剥了尾码就会**认错行**（把 "A仓(XM2)" 当成 "A仓"）。"""
    assert i8_warehouse_lookup("兰考金不换前置车间项目", ROWS)["found"] is True
    assert i8_warehouse_lookup("兰考金不换前置车间项目(TBLX2026070003)", ROWS)["found"] is False, \
        "带尾码的名字**不**命中 ⇒ 证明没有拿全名的剥离规则来比仓库名"
    assert i8_warehouse_lookup("  沭阳仓库  ", ROWS)["found"] is True, "首尾空白要去掉（人工输入常见）"


# --------------------------------------------------------------- 2 · 端点（只读 · 禁静默）


def test_端点没命中时把后果说清():
    """没命中 ⇒ 回执要讲**后果**（将来 i8 建了会再建一行）＋ 要求**显式确认**（⛔ 不静默建）。"""
    miss = _call("不存在的仓库")
    assert miss.found is False and miss.degraded is False, "这是「取到了名单、名单里没有」，不是降级"
    assert "没有" in miss.message and "再建一行" in miss.message and "显式确认" in miss.message

    hit = _call("沭阳仓库")
    assert hit.found is True and len(hit.owners) == 2, \
        "同名多主要如实带出（壳侧据此提醒「先确认是不是同一个壳」）"
    assert "不替选" in hit.message


def test_取不到名单必须降级且不许说成没有(monkeypatch, tmp_path):
    """⭐ **禁静默的核心**：「没取到名单」和「名单里没有」是**两回事** —— 取不到必须 `degraded=True`
    并在话里点明「**不等于**名单里没有」（否则用户会以为 i8 里真没有这个仓库）。

    ⚠️ **隔离缓存**（`wh_cache.CACHE_DIR` 指到临时目录）—— 本机若已有缓存，就会走"用上次名单"那条路
    （那是另一条断言），这条专测**连缓存都没有**时的降级。
    """
    monkeypatch.setattr(wh_cache, "CACHE_DIR", tmp_path / "wh")

    def boom(allow_kick=False, client=None):
        raise RuntimeError("i8 登录失败")

    bad = m03r.warehouse_check(WarehouseCheckRequest(warehouse_name="沭阳仓库"), wh_loader=boom)
    assert bad.degraded is True and bad.found is False
    assert "不等于" in bad.message and "没查到" in bad.message, f"要把两件事分开说：{bad.message}"

    blank = _call("   ")
    assert blank.degraded is True and "先填" in blank.message, "空名字要当场提示（⛔ 别拿空串去查 i8）"


def test_取不到名单但有上次缓存时用缓存并说清是几点的(monkeypatch, tmp_path):
    """⭐ 照交付面素材包 `warehouse_sync` 的 `save_cache`：名单**留一份快照**，
    查名单取不到（i8 不可用）时**接着判** —— ⛔ 但必须把「这是几点抓的」**说出来**
    （缓存是**上一次的快照**，不是刚抓的；`wh_cache` 纪律 2）。"""
    monkeypatch.setattr(wh_cache, "CACHE_DIR", tmp_path / "wh")
    wh_cache.save(ROWS, source="自检")

    def boom(allow_kick=False, client=None):
        raise RuntimeError("i8 登录失败")

    hit = m03r.warehouse_check(WarehouseCheckRequest(warehouse_name="沭阳仓库"), wh_loader=boom)
    assert hit.from_cache is True and hit.found is True and len(hit.owners) == 2
    assert hit.cached_at, "必须带出缓存的抓取时间"
    assert "没取到" in hit.message and hit.cached_at in hit.message, \
        f"要说清这次没抓到、用的是几点的缓存：{hit.message}"
    assert hit.degraded is False, "有上次名单可用 ⇒ 不该算「完全没结果」（但来源已如实说明）"

    miss = m03r.warehouse_check(WarehouseCheckRequest(warehouse_name="不存在的仓库"), wh_loader=boom)
    assert miss.from_cache is True and miss.found is False and "没有" in miss.message


def test_名单缓存只读写文件且空名单不覆盖上一份(monkeypatch, tmp_path):
    """`wh_cache` 是**优化**（照本仓 `cookie_store` 的样板）：空名单**不许**覆盖上一份好的，
    路径走**唯一出口** `cache_path()`。"""
    monkeypatch.setattr(wh_cache, "CACHE_DIR", tmp_path / "wh")
    assert wh_cache.load() == (None, ""), "没写过 ⇒ 无缓存（不抛）"
    assert wh_cache.save([]) is None and wh_cache.load() == (None, ""), "空名单不写、也不当缓存"

    p = wh_cache.save(ROWS, source="自检")
    assert p == wh_cache.cache_path() and p.exists()
    items, at = wh_cache.load()
    assert len(items) == 3 and at, "要带 fetched_at（用它的地方必须把时间说出来）"
    assert wh_cache.clear() is True and wh_cache.load() == (None, ""), "清得掉、清完当无缓存"


def test_端点只读且判定走唯一出口():
    """⭐ ① **只读**：不落库、不建档（名单本身也不留档）—— 所以不碰 session / 仓储；
    ② 判定走 `domain.i8_warehouse_lookup`（**唯一出口**）—— 端点里⛔ 别自己写一份比较。"""
    src = inspect.getsource(m03r.warehouse_check)
    for forbidden in ("session_scope", "create_project", "set_keywords", "all_projects"):
        assert forbidden not in src, f"查名单这一环不许写库（发现有 {forbidden}）"
    assert "i8_warehouse_lookup(" in src, "判定要走唯一出口"


def test_强踢授权默认关且原样透传():
    """`D9`：查名单**要登录 i8**、可能**强踢**在线用户 ⇒ `allow_kick` **默认 False**，
    且用户显式授权时**原样**传给取数件（⛔ 不许壳里悄悄替用户打开）。"""
    assert WarehouseCheckRequest(warehouse_name="x").allow_kick is False, "默认必须是关的"
    seen: list[bool] = []
    _call("沭阳仓库", allow_kick=True, seen=seen)
    assert seen == [True], "显式授权要原样传下去"
    seen2: list[bool] = []
    _call("沭阳仓库", seen=seen2)
    assert seen2 == [False], "不给就是不给（⛔ 别默认踢人）"
