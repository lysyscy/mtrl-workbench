"""`MOD-14` 规则配置 —— **前端壳接线的离线断言**（绑 `ACC-CFG-RULE-001` 的 5 个判据点）。

真机验证在 `tools/_shell_smoke.py`（第 ⑫ / ⑫b 段：连服务 + 连库，含**写路径往返**，
跑完库回原样）；本文件只做**静态接线断言**。

⚠️ 这里钉的是**接线本身**（`TAIL-40` 后半），不是"页面好不好看"：
1. **演示常量必须已清** —— `RULE_EX` 原先硬编码 4 条演示规则；接线后它只能由
   `reloadM14()` 从 `/api/m14/rules` 填（`ui_parity` 的 `U2b` 也查 `m14→RULE_EX`）。
2. **增 / 删 / 改必须真的落到规则数据** —— ⛔ 不许本地改数组冒充落库
   （改完一刷新就回原样，而页面还回「已新增」= 假成功）。
3. **规则类别必须是后端认的 key** —— 原型是一个自由文本输入框；而 §4.2.2 只有四类，
   填「收款单位」后端会拒、填错别字更看不出问题 ⇒ 改成**后端 `kinds` 撑起来的下拉**。
4. **卡头条数必须是算出来的**（`RULE_EX.length`），⛔ 不许写死。
5. **分类规则表只读 / 规则与说明表不可排序 / 关键词编辑入口在项目行** ——
   这三条是判定顺序的归属边界（可编辑 = 允许就地改业务口径）。

⚠️ **`001-04` 刻意不断言「几条命中值」** —— 该判据点原文即「条数在此不复述」
   （条数的主人 =《说明书》§4.2.2 那张表，抄一份到测试里必然静默过期）。
   它查的是**结构**：四类齐、每类有值、`收款单位`不在有效类别里。
"""

from __future__ import annotations

import re
from pathlib import Path

from tests.acc_plugin import acc

ROOT = Path(__file__).resolve().parents[2]
from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛
RULES_API = (ROOT / "backend" / "app" / "mod14_config" / "rules_api.py").read_text(encoding="utf-8")
REPO = (ROOT / "backend" / "app" / "mod03_notice" / "rules_repository.py").read_text(encoding="utf-8")
CLASSIFY = (ROOT / "backend" / "app" / "mod03_notice" / "classify.py").read_text(encoding="utf-8")

#: 切片切法**必须与 `tools/ui_parity.py` 一致**（`V.<名>=` 起，到下一个顶层声明止）
_END_RE = re.compile(r"^(?:V\.|BIND\.|const |let |function )")


def _vslice(name: str) -> str:
    """取壳里 `V.<名>=` 起、到下一个顶层声明止的切片。"""
    out: list[str] = []
    cur = False
    for ln in SHELL.replace("\r\n", "\n").split("\n"):
        if re.match(rf"^{re.escape(name)}\s*=", ln):
            cur = True
            out.append(ln)
            continue
        if cur:
            if _END_RE.match(ln):
                break
            out.append(ln)
    assert out, f"壳里找不到 `{name}=`"
    return "\n".join(out)


def _balanced(start: int, *, limit: int = 4000) -> str:
    """从 `start` 处第一个 `{` 起做**花括号配平**（⛔ 不用"下一个同名键"当终点）。"""
    depth, k = 0, SHELL.find("{", start)
    assert k > 0, "找不到起始花括号"
    while k < len(SHELL):
        if SHELL[k] == "{":
            depth += 1
        elif SHELL[k] == "}":
            depth -= 1
            if depth == 0:
                break
        k += 1
    body = SHELL[start:k + 1]
    assert len(body) < limit, f"取到 {len(body)} 字符 —— 配平可能跑偏"
    return body


def _fn(name: str) -> str:
    """取壳里 `function <名>(…)` 的函数体。"""
    i = SHELL.find(f"function {name}(")
    assert i >= 0, f"壳里找不到 `function {name}(`"
    return _balanced(i)


def _act(name: str) -> str:
    """取壳里 `ACT` 的某个动作（`\\n <名>:` 起，花括号配平）。"""
    i = SHELL.find(f"\n {name}:")
    assert i >= 0, f"壳里找不到动作 `{name}:`"
    return _balanced(i)


# ============================================================== 001-01


@acc("ACC-CFG-RULE-001", "001-01")
def test_剔除规则真增删改且改动落到规则数据():
    """`001-01` 剔除规则真「增 / 删 / 改」：改动落到规则数据，且**卡头条数实时算**（不得写死）。"""
    # ① 三个动作都必须**调后端**（⛔ 不本地改数组冒充落库）
    save, dele = _act("ruleSave"), _act("ruleDel")
    assert "API.m14RuleAdd(" in save, "`ruleSave` 的新增没走后端"
    assert "API.m14RuleSet(" in save, "`ruleSave` 的修改没走后端"
    assert "API.m14RuleDel(" in dele, "`ruleDel` 没走后端"
    # ② 本地改演示表的写法必须**一处不剩**
    for name, body in (("ruleSave", save), ("ruleDel", dele)):
        for bad in ("RULE_EX.push(", "RULE_EX.splice(", "RULE_EX[i]="):
            assert bad not in body, f"`{name}` 还在本地改 `RULE_EX`（{bad}）⇒ 一刷新就回原样 = 假成功"
    # ③ 改动要**看得见**：写完必须重拉
    for name, body in (("ruleSave", save), ("ruleDel", dele)):
        assert "await reloadM14()" in body, f"`{name}` 写完没重拉（改了看不见）"
    # ④ 规则数据的**唯一来源**必须是后端：演示常量已清 ⇒ 只能由 `reloadM14()` 填
    #    （⛔ 只查「写了 `reloadM14()`」不够 —— 填不进去的话表格恒空，而上面几条照样通过）
    reload_body = _fn("reloadM14")
    assert "RULE_RAW = d.rules" in reload_body, "`reloadM14()` 没把后端规则行落定到 `RULE_RAW`"
    assert "RULE_EX = RULE_RAW.map(" in reload_body, \
        "`reloadM14()` 没把后端规则行转成 `RULE_EX`（切片会渲染空表）"
    # ⑤ 卡头条数必须是**算出来的**
    assert "RULE_EX.length" in _vslice("V.m14"), "卡头条数没跟着规则条数走（写死了）"
    # ⑥ 后端：三个端点都在，且**都走仓储**（判定不另写一套）
    for ep, fn in (("@router.post(\"/api/m14/rules\")", "def api_rule_add("),
                   ("@router.put(\"/api/m14/rules/{rule_id}\")", "def api_rule_update("),
                   ("@router.delete(\"/api/m14/rules/{rule_id}\")", "def api_rule_delete(")):
        assert ep in RULES_API, f"后端缺 `{ep}`"
        assert fn in RULES_API, f"后端缺 `{fn}`"
    assert "RR.add_row(" in RULES_API and "RR.update_row(" in RULES_API and "RR.delete_row(" in RULES_API, \
        "写端点没走 `rules_repository`（规则的主人分叉了）"
    # ⑦ ⚠️ **改规则不重算历史**（§4.2.2）—— 写侧一处都不许出现重算调用
    for bad in ("decide_placement", "upsert_month", "recompute"):
        assert bad not in RULES_API, f"写侧出现了 `{bad}` ⇒ 改规则触发了历史重算（§4.2.2 禁止）"


# ============================================================== 001-02


@acc("ACC-CFG-RULE-001", "001-02")
def test_分类规则表只读不渲染编辑入口():
    """`001-02` 分类规则表**保持只读**，不渲染编辑入口（判定顺序 = 业务口径，可编辑 = 允许改口径）。"""
    sl = _vslice("V.m14")
    i = sl.find("RULE_CA.map")
    assert i > 0, "`V.m14` 里找不到分类规则表的 `RULE_CA.map(...)`"
    # ⚠️ 只取**分类规则那一行**的 map 段（⛔ 别把整页 `in` —— 上方的剔除规则表本来就有按钮）
    seg = sl[i:i + 700]
    for bad in ("button", "data-act", "input"):
        assert bad not in seg, f"分类规则表的渲染段里出现了 `{bad}` ⇒ 它被做成了可编辑（§4.2.3 只读）"


# ============================================================== 001-03


@acc("ACC-CFG-RULE-001", "001-03")
def test_规则与说明表不得被标为可排序():
    """`001-03` 规则 / 说明表不得被标为可排序（`data-sort` 是数据表的属性，不是配置表的）。"""
    sl = _vslice("V.m14")
    assert "data-sort" not in sl, "`V.m14` 里有表被标了 `data-sort` ⇒ 配置 / 说明表被当成可排序数据表"


# ============================================================== 001-04


@acc("ACC-CFG-RULE-001", "001-04")
def test_命中值结构与口径一致():
    """`001-04` 剔除规则的命中值**结构与 §4.2.2 一致**。

    ⚠️ **刻意不断言条数** —— 该判据点原文即「条数在此不复述」（条数的主人 =《说明书》§4.2.2）。
    查的是结构：四类齐 / 每类有值 / `收款单位`**不在有效类别**（只能识别并拒绝）。
    """
    from app.mod03_notice import classify

    for k in (classify.KIND_BIZ_TYPE, classify.KIND_PROJECT_NAME,
              classify.KIND_BILL_NAME, classify.KIND_INPUT_BY):
        assert k in classify.KIND_LABELS, f"口径四类里缺 `{k}`"
        assert classify.KIND_LABELS[k].strip(), f"`{k}` 没有中文名（页面会显示 key）"
    assert all(r.values for r in classify.DEFAULT_RULES), "出厂默认里有规则没有任何命中值"

    # ⛔ 「收款单位」不得出现在**可选类别**里（后端 `effective_payload` 负责剔除）
    assert "if k != classify.KIND_PAYEE" in REPO, "后端 `kinds` 没把「收款单位」排除 ⇒ 页面上能选它"
    # 壳侧：类别下拉来自后端（与真数据同源），⛔ 不是前端硬编码的类别表
    assert "RULE_KINDS = d.kinds" in _fn("reloadM14"), "`reloadM14()` 没从后端落定可选类别"
    assert "RULE_KINDS.map(" in _act("ruleForm"), "规则类别没用后端给的类别做下拉（硬编码了类别）"


# ============================================================== 001-05


@acc("ACC-CFG-RULE-001", "001-05")
def test_关键词编辑入口在项目行本页只读():
    """`001-05` 小微识别关键词的编辑入口在**项目行**（`MOD-01`），本页只作**只读展示**。"""
    sl = _vslice("V.m14")
    i = sl.find("PJs.filter(p=>p.type==='small')")
    assert i > 0, "`V.m14` 里找不到小微识别关键字表"
    seg = sl[i:i + 900]
    for bad in ("input", "button", "data-act"):
        assert bad not in seg, f"本页的关键词表里出现了 `{bad}` ⇒ 越权可编辑（入口该在项目行）"
    # 真入口确实在 `m01` 的项目行上（丢了它 = 关键词哪儿都改不了）
    # ⚠️ 必须**连属性名一起钉**（`data-act="editKw"`）—— 只查 `editKw` 会被 `editKwX`
    #    / `editKwOk` 这类同前缀标识符**喂饱**（反向灵敏度实测：改成 `editKwX` 照样绿）。
    m01 = _vslice("V.m01")
    assert 'data-act="editKw"' in m01, "项目行（`m01`）里没有关键词编辑入口 `data-act=\"editKw\"`"
    # ⛔ 反向：本页也**不得**出现那个入口（题眼是"入口在项目行"，不是"两处都有"）
    assert 'data-act="editKw"' not in _vslice("V.m14"), "`m14` 也渲染了关键词编辑入口（越权）"
