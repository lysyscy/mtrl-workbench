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
    """「预览不写库」的载具**只许一份**（`preview_store`）—— 三个导入页共用，不各写一份。

    ⚠️ 2026-09-21（`§19` 四个暂留件收口）：落点从「服务端渲染页的路由件」（`import_router.py`）
       改成**JSON API 件**（`import_api.py`）—— 载具与口径**一字未变**，只是形态换了
       （同「形态变、判据不变」的既定做法）。
    """
    import pathlib

    from app.core import preview_store
    from app.mod05_flow import import_api as m05
    from app.mod06_proc import import_api as m06
    from app.mod08_inv import import_api as m08

    for module in (m05, m06, m08):
        src = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        assert "preview_store" in src, f"{module.__name__} 没走统一载具"
    assert callable(preview_store.save) and callable(preview_store.load)
