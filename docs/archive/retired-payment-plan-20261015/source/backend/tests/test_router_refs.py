"""**全站路由静态引用守卫** —— 走 `/api` 之前先把「引用了不存在的域出口」揪出来。

⚠️ 本文件**不绑定 `ACC-*` 判据点**（`@acc()` 显式声明）：它守的是**一类错**，不是某条判据。
⚠️ 为什么必须有它：这类错**离线断言天生看不见** —— 断言都直接调函数、不走 HTTP，
   而路由里写错别名只有**真机请求**才会 500（2026-09-17 活动大表实测一次，见 `开发计划` §6 与交接 §⑥）。
⚠️ **按 glob 发现路由**（⛔ 不逐份列清单）：逐份列会让**新加的路由件漏网不被查**。
"""

from __future__ import annotations

from tests.acc_plugin import acc
from tests.router_refs import broken_refs, router_modules


@acc()
def test_全站所有模块路由引用的域出口都真实存在():
    modules = router_modules()
    # ① 守卫本身不许退化成"什么都没扫"（发现不到路由 = 这个自检失效了）
    #    ⚠️ 2026-09-21：扫描面加宽到 `*api*.py`（四个暂留件收口后新加 `settings_api.py` /
    #       `import_api.py` 等件）—— 实际件数**只会变多**；这里的下限只作"发现逻辑坏了"的信号。
    assert len(modules) >= 15, f"只扫到 {len(modules)} 个路由件 —— 发现逻辑坏了"
    # ② 逐个核对 `别名.属性`
    bad: list[str] = []
    for rel, module in modules:
        for item in broken_refs(module):
            bad.append(f"{rel}：{item}")
    assert not bad, "路由引用了不存在的出口 —— 真机请求会 500：\n" + "\n".join(bad)


@acc()
def test_导入类页面引用的暂存载具是同一份():
    """「预览不写库」的载具**只许一份**（`preview_store`）—— 导入页共用，不各写一份。

    ⚠️ 2026-09-21（`§19` 四个暂留件收口）：落点从「服务端渲染页的路由件」（`import_router.py`）
       改成**JSON API 件**（`import_api.py`）—— 载具与口径**一字未变**，只是形态换了
       （同「形态变、判据不变」的既定做法）。
    ⚠️ 2026-09-22：**m08 的手动导入已按用户裁定删除** ⇒ 只剩 m05 / m06 两家
       （m11 集采台账导入自带解析暂存，不占 `preview_store` —— 别把它错并进来）。
    ⚠️ 2026-09-23（`TAIL-75` `B5c-2`）：m06 的**专属导入端点已退休** ⇒ 它那半边改由
       **通用导入面**（`import_kit.api`）代表 —— 通用面同样必须走这**同一份**载具
       （⛔ 通用层若自带一份暂存 ⇒ "预览不写库"这条就裂了）。
    ⭐ 2026-09-23（`TAIL-75` `B5b` 第三步 · 用户裁定 `B`）：m05 的专属导入端点（`import_api.py`）
       **也连件删除** ⇒ 现在**全站导入只剩通用面一条路** ⇒ 本守卫的落点收敛成**一处**：
       通用面（`import_kit.api`）走 `preview_store`，且**各域不得自带暂存**（下面第二半按域扫）。
    """
    import pathlib

    from app.core import preview_store
    from app.import_kit import api as impkit
    # ⚠️ 别名**别叫 `imp05` / `imp06`** —— 那两个名字是**已撤项**（旧页的壳侧动作，
    #   见 `audit_common.CANCELLED`）⇒ `T8` 会把这条测试当成"复活"报红（自测踩到）。
    from app.mod04_plan import imp_spec as spec04
    from app.mod06_proc import imp_spec as spec06

    src = pathlib.Path(impkit.__file__).read_text(encoding="utf-8")
    assert "preview_store" in src, f"{impkit.__name__} 没走统一载具"
    # ⭐ 各域只许**声明 ＋ 钩子**：⛔ 谁在域里**另起一份暂存**，这条就红（"预览不写库"会裂成两处真源）。
    # ⚠️ 只认**真用法**（`import preview_store` / `preview_store.xxx`）—— 文件里**提到这个名字**很正常
    #   （注释在解释"载具只有这一份"），按字符串匹配会把好注释判红（自测踩到）。
    for spec in (spec04, spec06):
        text = pathlib.Path(spec.__file__).read_text(encoding="utf-8")
        assert "import preview_store" not in text and "preview_store." not in text, \
            f"{spec.__name__} 自带了暂存 —— ⛔ 载具只许一份"
    assert callable(preview_store.save) and callable(preview_store.load)
