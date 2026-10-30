"""`MOD-09` 特殊费用月报表 —— **前端壳接线的离线断言**。

本文件保留特殊费用后端接口、服务与报表的静态接线断言。

⚠️ 这里钉的是**接线本身**，不是"页面好不好看"：
1. **演示容器必须已清** —— 留着就永远渲染演示值（`ui_parity` 的 `U2b` 也查 `m09→AWF`）。
2. **适配层必须把金额转成数字** —— 后端金额出**字符串**（`numeric(18,2)` 精度保护），
   而原型切片里写着 `r[1].toFixed(2)` ⇒ 不过 `N0()` 会 **TypeError 整页崩**（不报错地坏）。
3. **候选 / 默认项目必须由 `reloadM09()` 落定** —— `PJs` 是**异步填充**的，
   写成加载时求值（`const x = f(异步变量)`）会在取数回来时**早已定死成空**（静默失去候选）。
4. **判据不得在前端复写**（`D18`）—— §5.5 的金额判据唯一出口是后端 `domain.amount_problem`。
5. **不许本地改数据冒充落库**（假成功）。
6. **失败也要看回执** —— 后端对「金额不合法」回 **HTTP 200 ＋ `ok:false`**
   ⇒ 只判 `!r` 不判 `ok === false` 的话，那句"金额不合法…"会被当成成功**吞掉**。
7. ⭐ **自动项取数改用核算年月**（`inv_detail.ym`）：原实现按 `iv.dd`（**单据日期**）前缀算 ——
   口径要的是核算年月（`domain` 顶部已注明），两者在"单据日期跨月"时**不一致**且**不报错**。
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
API = (ROOT / "backend" / "app" / "mod09_fee" / "api.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "backend" / "app" / "mod09_fee" / "router.py").read_text(encoding="utf-8")

# ⭐ 2026-10-03（`TAIL-219` 批 1 **试点**）：本件原先自带三把"剪刀"（`_body` / `_slice` / `_act`：
#    靠 `SHELL.find` ＋ 花括号配平）⇒ 已**全部改走壳的语义口径**
#    `tests.shell_src` 转发的 `func_body` / `page_slice` / `act_entry`
#    （定义 = `tools/audit/shell_api.py` · **认结构**＝跳过字符串/模板串/注释/正则 · 找不到**必抛**）。
#    ⛔ 别在这儿把剪刀写回来（要治的就是"同一件事各处剪一遍"）；⛔ 也别再各写一份。


# ================================ `ACC-FEE-MON-001` 的**形态**半边（`§19` 批 2 搬家）
#
# 原先钉在**旧服务端页** `render_fee_page` 渲染出的 HTML 上；旧页删除（授权 `D18`）⇒ 形态改指新壳
# （⛔ 判据不删）。实质（取数 / 判定 / 独立复算）仍留在 `tests/test_acc_fee_mon.py`。

















# ============================================================== 1 · 演示数据已清





# ============================================================== 2 · 适配层







# ============================================================== 3 · 候选与默认值





# ============================================================== 4 · 写动作走后端











# ============================================================== 5 · 切片与纳管





# ============================================================== 6 · 后端端点

def test_后端m09端点存在且复用service出口():
    """⚠️ 读端点走 `_payload` ⇒ `build_page_data`，写端点**各自**直接调 `SV.act_*`。

    ⚠️ 断言必须**进各自函数体**取切片 —— 只写「文件里含 `SV.act_add(`」是**假绿**：
       同名调用在别处出现时，把端点里那处变异掉**只查全文照样通过**。
    """
    for ep in ('@router.get("/api/m09/fee")', '@router.post("/api/m09/fee/add")',
               '@router.post("/api/m09/fee/name")', '@router.post("/api/m09/fee/amount")',
               '@router.post("/api/m09/fee/delete")'):
        assert ep in API, f"后端缺 `{ep}`"
    for fn, needle in (("def _payload(", "SV.build_page_data("),
                       ("def _payload(", "SV.parse_state("),
                       ("def api_fee(", "_payload("),
                       ("def api_add(", "SV.act_add("),
                       ("def api_rename(", "SV.act_rename("),
                       ("def api_amount(", "SV.act_set_amount("),
                       ("def api_delete(", "SV.act_delete(")):
        i = API.find(fn)
        assert i > 0, f"找不到 `{fn}`"
        j = API.find("\ndef ", i)
        seg = API[i:j if j > i else i + 900]
        assert needle in seg, f"`{fn}` 没走 `{needle}`（判定该与 PRG 端点**同一出口**，不另写一套）"


def test_后端m09端点剔除页面专用列():
    """⚠️ 「操作」列（`ops`）是**页面专用 HTML 占位** ⇒ `/api/*` 必须剔除（`domain.PAGE_ONLY_KEYS`）。

    ⚠️ 断言必须钉在 `_row()` **自己的作用域**里：只写「文件里含 `D.PAGE_ONLY_KEYS`」是**假绿**
       —— 文档注释里那句 `domain.PAGE_ONLY_KEYS` **含 `D.PAGE_ONLY_KEYS` 这个子串**
       （反向灵敏度实测：把实现那行改成 `if False:` **照样绿** —— 子串喂饱，同族坑第二次踩到）。
    """
    from app.mod09_fee import domain as D

    assert D.PAGE_ONLY_KEYS == ("ops",)
    i = API.find("def _row(")
    assert i > 0, "`api.py` 里找不到 `def _row(`"
    j = API.find("\ndef ", i)
    seg = API[i:j if j > i else i + 600]
    assert "if k in D.PAGE_ONLY_KEYS:" in seg, "`_row()` 没剔除 `PAGE_ONLY_KEYS`（操作列会漏进 API）"


def test_后端m09路由已汇总():
    """`main.py` 不用改 —— `mod09` 的页面路由文件负责汇总（同 `mod07` 的做法）。"""
    assert "from app.mod09_fee.api import router as api_router" in ROUTER, \
        "`mod09_fee/router.py` 没汇总 JSON API 路由"
    assert "router.include_router(api_router)" in ROUTER, "没把 api 路由挂上去"
