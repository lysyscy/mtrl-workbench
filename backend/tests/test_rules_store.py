"""`MOD-14` 剔除规则落库（`TAIL-40`）—— **后端侧**断言。

⚠️ 本文件只钉**后端**：命中值结构与分隔符 · 「库 → 出厂默认」语义 · 幂等初始化 ·
   **抓取管线保持纯读** · 依赖单向（不给 `mod03` 引 `mod14`）· 端点已注册。
   **页面侧的 5 个判据点**（`ACC-CFG-RULE-001/001-01…05`）要等壳接线完再绑 —— 见 §16 实施顺序。

⚠️ 库级断言**一律非破坏**（本机测试会连到**同一个库**）：
   ⛔ 不删、不清空、不假设"库是空的" —— 只做**幂等**与**读一致性**的核对。
"""

from __future__ import annotations

import re
from pathlib import Path

from app.mod03_notice import classify
from app.mod03_notice import rules_repository as RR
from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT / "backend" / "app" / "mod03_notice" / "rules_repository.py"
ROUTER = ROOT / "backend" / "app" / "mod03_notice" / "router.py"
RULES_API = ROOT / "backend" / "app" / "mod14_config" / "rules_api.py"


# ============================================================== 1 · 命中值结构与分隔符


@acc()
def test_命中值分隔符全角为主_半角也认():
    """§4.2.2 表内写法 = **全角 `｜`**（与原型演示常量同款）；手输常见的**半角 `|` 也必须认**。

    ⚠️ 这条不是"格式洁癖"：解析认不出分隔符 ⇒ 一条规则会被当成**一个超长命中值**
       ⇒ 那一类规则**永远不命中**，而且**不报错**（静默失效）。
    """
    full = "水费｜电费｜房租"
    half = "水费|电费|房租"
    mixed = "水费|电费｜房租"
    assert RR.split_values(full) == ("水费", "电费", "房租")
    assert RR.split_values(half) == ("水费", "电费", "房租")
    assert RR.split_values(mixed) == ("水费", "电费", "房租")
    # 去空 + 去重（同一个值写两遍没有意义，且会让回执难看）
    assert RR.split_values("水费||电费|水费|  ") == ("水费", "电费")
    # 写入一律**规整成全角**（唯一写法 —— 免得同一个值两种写法各存一份）
    assert RR.join_values(("水费", "电费")) == "水费｜电费"
    assert RR.SEP == "｜"


@acc()
def test_库行转判定值时对象是_excludeRule():
    """库行 → `classify.ExcludeRule`（判定用的**不可变值对象**）—— `meaning` **不参与判定**。"""

    class _Row:
        kind = "bill_name"
        values = "水费|电费"
        meaning = "期间费用，非材料/机械"

    rule = RR.to_rule(_Row)  # type: ignore[arg-type]
    assert isinstance(rule, classify.ExcludeRule)
    assert rule.kind == "bill_name" and rule.values == ("水费", "电费")
    assert rule.label == "单据名称关键字"


# ============================================================== 2 · 「库 → 出厂默认」语义


@acc()
def test_库空回落到出厂默认():
    """⭐ 用户 2026-09-18 裁定：**库里有 ⇒ 以库为准；库空 ⇒ 回落 `DEFAULT_RULES`（＝ §4.2.2 那张表）**。

    ⚠️ 用**空库替身**测（`all_rows` 打桩返回 `[]`）—— ⛔ 不去清空真库（库级断言必须非破坏）。
    ⛔ 若把回落去掉（库空 ⇒ 空规则集），首装行为会**静默偏离 §4.2.2** —— 这条就是钉它的。
    """
    from app.core.db import session_scope

    with session_scope() as s:
        got = RR.effective_rules(s)
        expect_db = tuple(RR.to_rule(r) for r in RR.all_rows(s))
    assert got and all(isinstance(r, classify.ExcludeRule) for r in got), "生效规则集为空 / 类型不对"
    if expect_db:
        assert got == expect_db, "库非空时没有以库为准"

    orig = RR.all_rows
    try:
        RR.all_rows = lambda _s: []          # type: ignore[assignment]
        with session_scope() as s:
            empty = RR.effective_rules(s)
        assert empty == tuple(classify.DEFAULT_RULES), "库空时没有回落到出厂默认"
    finally:
        RR.all_rows = orig                    # type: ignore[assignment]


@acc()
def test_幂等初始化不会重复落库():
    """`ensure_seeded` 只在**库空**时写一次；库非空时**返回 0 且一行不加**（幂等）。

    ⚠️ 非破坏：库非空（本机现状）⇒ 只断言"没动它"。
    """
    from app.core.db import session_scope

    with session_scope() as s:
        before = len(RR.all_rows(s))
        if before:
            assert RR.ensure_seeded(s) == 0, "库非空还写入 ⇒ 幂等破了（会重复灌出厂默认）"
            assert len(RR.all_rows(s)) == before
        else:
            n = RR.ensure_seeded(s)
            assert n == len(classify.DEFAULT_RULES)
            assert RR.ensure_seeded(s) == 0, "第二次调用还在写 ⇒ 幂等破了"


@acc()
def test_出厂默认本身必须合法():
    """出厂默认要过同一份校验（§4.2.2 的四类 / 不得按收款单位 / 命中值非空）。

    ⚠️ 若默认值本身不合法 ⇒ 一旦被灌进库，**改都改不动**（每次保存都被自己的校验拒）。
    """
    classify.validate_rules(classify.DEFAULT_RULES)
    from app.mod03_notice.rules_repository import _validate

    for rule in classify.DEFAULT_RULES:
        _validate(kind=rule.kind, values=rule.values)


# ============================================================== 3 · 抓取管线保持纯读 + 依赖单向


@acc()
def test_抓取管线读到规则并同时喂给两处():
    """⭐ **一处读取、两处同一份**：`rows_needing_ownership`（挑需校验的行）与
    `apply_fetched_row`（落库时打剔除标记）必须用**同一批**规则 ——
    ⛔ 两处各读一次会让"这批到底按哪份规则判的"说不清；⛔ 更不许在编排层另写一份剔除判定。
    """
    src = ROUTER.read_text(encoding="utf-8")
    assert "rules = effective_rules(session)" in src, "抓取管线没读生效规则集"
    assert "rows_needing_ownership(rows, rules)" in src, "挑行那处没拿到规则"
    assert "rules=rules" in src, "落库那处没拿到规则（两处会分叉）"
    # 落库函数内部也不许各自现读一次
    assert "effective_rules(" not in src.split("def apply_fetched_row")[1].split("def ")[0], \
        "`apply_fetched_row` 自己又读了一次规则（同一批要保证判据一致）"


@acc()
def test_抓取管线不得调幂等初始化():
    """⛔ **抓取路径必须保持纯读**：`ensure_seeded`（会写库）只许由**配置页**触达。

    否则"抓一次"会顺手改配置表 —— 排查问题时谁都想不到那儿会变。
    """
    router = ROUTER.read_text(encoding="utf-8")
    assert "ensure_seeded" not in router, "抓取管线里出现了写库的初始化"
    assert "ensure_seeded" in RULES_API.read_text(encoding="utf-8"), "配置页端点没做初始化"


@acc()
def test_付款域不反向依赖配置域():
    """依赖方向**单向** `mod14_config → mod03_notice`（§4.2.2：规则本身属付款域）。

    ⛔ 反过来（`mod03` 引 `mod14`）会与"配置页引付款域仓储"**成环** ⇒ 循环 import。

    ⚠️ 断言只看**导入行** —— 只写 `"mod14" not in 源码` 是**假绿**：本文件头的**说明文字**里
       就写着 `mod14_config`（实测：第一版断言被自己的注释喂饱）。
    """
    repo = REPO.read_text(encoding="utf-8")
    bad = [ln.strip() for ln in repo.split("\n")
           if re.match(r"\s*(from|import)\s+app\.mod14", ln)]
    assert not bad, f"付款域的规则仓储**导入**了配置域 ⇒ 有循环 import 风险：{bad}"
    assert "from app.mod03_notice" in RULES_API.read_text(encoding="utf-8"), \
        "配置页端点没走付款域的规则仓储（那数据主人就分叉了）"


# ============================================================== 4 · 端点已注册


@acc()
def test_规则端点已注册且写侧恒200():
    """4 个端点齐；写侧**恒 HTTP 200 ＋ `ok` 标志**（拒绝是可预期的，那句中文必须给用户看）。"""
    from app.main import create_app

    paths = create_app().openapi()["paths"]
    assert ("GET", "POST") == tuple(sorted(m.upper() for m in paths["/api/m14/rules"]))
    assert ("DELETE", "PUT") == tuple(sorted(m.upper() for m in paths["/api/m14/rules/{rule_id}"]))
    api = RULES_API.read_text(encoding="utf-8")
    assert "MustReportError" in api, "写侧没接住规则校验的拒绝（会变成一句 HTTP 500/400，原因丢失）"
    assert not re.search(r"status_code\s*=\s*4\d\d", api), "写侧不该返回 4xx（约定：恒 200 ＋ ok 标志）"
