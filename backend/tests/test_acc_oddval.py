"""不标准值的批量修改入口；通用导入原则由现行引擎测试验证。"""

from __future__ import annotations

import pathlib
import re


import app

#: 确实**归不进** §4.4.2 四类的写法（⚠️ 别用「电汇」—— 它是「现汇」的别名，会被认出来）
_ODD_METHODS = ("银行本票", "现金", "微信支付", "ABC")


def test_提供批量修改入口_勾选多行统一改同一字段():
    """§9.6 第 2 行「**提供批量修改入口**」—— ⚠️ claim 括注写明了形态：
    **（勾选多行 ⇒ 统一改同一字段）**。

    ⚠️ 为什么这一条不能只看"有没有一个改分类的入口"：
       单行改分类（在下拉里点一下）**早就有了**，但它**不解决**"不标准值"这个场景 ——
       不标准值往往是**成批**的（一次导进来几十行都认不出），一行一行改就是几十次点击。
       ⇒ 判据必须钉住**"勾选多行 ⇒ 一次改一整批"**这个形态：
         ① 入口按**分类值**逐个给按钮（`enumVals('cat').map`）—— 点一次就说清"改成哪个值"；
         ② 按钮**跟勾选集走**（`pickSet`）—— ⛔ 不是只作用于某一行；
         ③ 未勾选**先禁用**（`disabled`）—— 与全站同款（⛔ 不是点了才拦）。
    """
    web = pathlib.Path(app.__file__).resolve().parent / "web"
    html = (web / "index.html").read_text(encoding="utf-8")
    acts = (web / "shell" / "actions.js").read_text(encoding="utf-8")

    tags = re.findall(r"<button[^>]*data-act=\"batchCatApply\"[^>]*>", html)
    assert tags, "找不到「批量改分类」入口（`data-act=\"batchCatApply\"`）—— 落点变了"
    for tag in tags:
        assert "data-c=" in tag, (
            "批量改分类的按钮没有声明「改成哪个值」（`data-c`）⇒ 那就说不清「统一改成同一个字段」：\n"
            f"  {tag[:140]}")
        assert "disabled" in tag and "pk.length" in tag, (
            "批量按钮没跟**勾选数**走（未勾选先禁用）—— 用户会先点一下被拒才知道要先勾选：\n"
            f"  {tag[:140]}")

    body = acts[acts.index("batchCatApply:"):]
    body = body[:body.index("/* 单行改分类")]
    assert "pickSet" in body, (
        "`batchCatApply` 没有作用于**勾选集**（`pickSet`）—— 那就不是「勾选多行统一改」，"
        "而是单行改（claim 的形态是**批量**）")
    assert "setCategory" in body, "批量改分类没有走后端同一出口（`setCategory`）"

    # ⭐ 反向：单行改分类**仍然要在**（批量不是拿单行换来的）—— 两者是互补，不是替代
    assert "单行改分类" in acts, "单行改分类的入口不见了 —— 批量与单行应当**并存**（互补）"
