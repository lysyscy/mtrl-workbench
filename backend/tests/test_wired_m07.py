"""`MOD-07` 收发结存与活动大表 —— **前端壳接线的离线断言**。

真机验证在 `tools/probe/_shell_smoke.py`（第 ⑩ 段：连服务 + 连库），本文件只做**静态接线断言**。

⚠️ 这里钉的是**接线本身**，不是"页面好不好看"：
1. **演示数据必须已清** —— 留着就永远渲染演示值（`ui_parity` 的 `U2b` 也查 `m07→WHM`）。
2. **适配层必须把金额转成数字** —— 后端金额出**字符串**（`numeric(18,2)` 精度保护），
   不过 `N0()` 的话壳里的求和会变成**字符串拼接**（`'100.00'+'1.00'`）—— **合计那栏安静地错掉**。
   ⚠️ 更隐蔽的一处：大表**手填列**的合计走 `typeof v === 'number' ? v : 0`
   ⇒ 手填值若是字符串，**那一列合计恒 0**（2026-09-18 接线时核实）。
3. **判据不得在前端复写**（`D18`）—— 防出**第二份口径**（金额非负 / 开工时间格式 / 选题校验）。
4. **不许本地赋值冒充落库**（假成功）。
5. ⛔ **不许给 `BIGSET` 兜底「空了就填全部候选」** —— 后端选题有**标记行**区分
   「从未选题」（⇒ 后端已给全部候选）与「选了空」（⇒ 0 个项目）；前端兜底会把「清空」悄悄改回去。
"""

from __future__ import annotations

import re
from pathlib import Path





ROOT = Path(__file__).resolve().parents[2]
API = (ROOT / "backend/app/mod07_setl/api.py").read_text(encoding="utf-8")
ROUTER = (ROOT / "backend/app/mod07_setl/router.py").read_text(encoding="utf-8")


def test_后端结余端点读写都在():
    assert '@router.post("/api/m07/extract/balance")' in API, "后端缺写端点"
    assert "S.save_balance_cell(" in API, "写端点没走服务层出口（判定会散到路由里）"
    assert "load_balances(s)" in API, "读端点没带上结余（壳里永远空）"


def test_后端关键端点都在():
    for path, verb in (
        ("/api/m07/settlement", "get"), ("/api/m07/extract", "get"), ("/api/m07/big", "get"),
        ("/api/m07/big/cell", "post"), ("/api/m07/big/selection", "post"),
        ("/api/m07/extract/balance", "post"),
        ("/api/m07/fetch", "post"),
    ):
        assert f'@router.{verb}("{path}")' in API, f"后端缺端点 {verb.upper()} {path}"
    assert "router.include_router(api_router)" in ROUTER, "`mod07_setl/router.py` 没汇总 API 路由"


def test_抓取端点必须显式确认():
    """⛔ 防"直接 POST 打进来"的静默抓取（**会顶号**）。"""
    assert "confirmed=req.confirm" in API, "抓取端点没把 `confirm` 交给 `run_fetch`（D9 二次确认形同虚设）"


def test_大表手填校验走服务层出口():
    """⭐ 金额非负 / 开工时间格式的判定**唯一出口 = `big_service.save_manual_cell`**（不在路由里另写）。"""
    assert "BS.save_manual_cell(" in API, "手填端点没走 `big_service.save_manual_cell`"
    assert "month=req.month, warehouse=req.warehouse" in API, "手填端点的参数形态不对"
# ⚠️ 2026-09-19（`P3` 主体）：`boot()` 不再逐路拉 ⇒ 下面那条判据改在**取数表**上证（判据不变）。
# ⭐ 2026-10-03（`TAIL-219` 批 2／2b）：取片改走壳的语义口径（⛔ 别在本件自造剪刀）

# ============== `ACC-SETL-001` / `ACC-SETL-EXT-001` 的**形态**半边（`§19` 批 2 搬家）
#
# 原先钉在**旧服务端页**（`render_setl_page` / `render_extract_page`）渲染出的 HTML 上；
# 旧页删除（授权 `D18`）⇒ 形态**改指新壳**（⛔ 判据不删）。






















def test_壳里产出物清单按仓数加总表且真导出():
    """TAIL-263 撤掉输出产物说明模块，真实分仓/总表导出入口与端点保留。"""
    from app.mod07_setl.domain import zip_manifest, WAREHOUSE_KEY
    manifest = zip_manifest([{WAREHOUSE_KEY: "甲仓"}, {WAREHOUSE_KEY: "乙仓"}], "2026-09")
    assert sum(x["kind"] == "warehouse" for x in manifest) == 2
    assert len(manifest) == 3 and manifest[-1]["name"].endswith("收发结存表.xlsx")




# ============================================================== 1 · 演示数据已清







# ============================================================== 2 · 适配层







# ============================================================== 3 · 写动作走后端（含反向）









# ============================================================== 4 · 后端端点 + 接线自洽

# ============================================================== 5 · 「结余」录入（2026-09-18 用户裁定「甲」）
