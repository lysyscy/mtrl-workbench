"""`m12` 差异登记（`MOD-12` · M6 跨域第一片）**前端壳接线**断言（离线 · 静态）。

**这一页接的是什么**：原型里 `DFs` 是 5 行**演示数组**（`DF01`…`DF05`，硬编码在 HTML 里）
⇒ 接线后 `DFs` 由 `GET /api/m12/list` 原地填充，**演示数组已删**。
写动作（登记 / 删除 / 标记已核对）原先全是**本地 `push` / `splice`**（刷新就没了）⇒ 现在走真接口。

⚠️ **本文件测不了什么**：这些是**静态检查**（壳里有没有那些接线点），**不证明运行时真的调通**；
   运行时由壳真机自检（`tools/_shell_smoke.py`）＋ 后端 `tests/test_acc_dif_reg.py` 覆盖。

⭐ 其中两条是**反向**断言：⛔ 不许再有"本地改 `DFs` 冒充落库"，⛔ 不许壳里再算一份编号。
"""

from __future__ import annotations

from tests.acc_plugin import acc

from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛


def _fn(name: str, end: str) -> str:
    """取壳里某段（`name` 起、`end` 止）—— 段内断言用，避免全文件宽松命中。"""
    body = SHELL[SHELL.index(name):]
    return body[:body.index(end)]


# ---------------------------------------------------------------- 接线点（正向）


@acc("ACC-DIF-REG-001", "001-01")
def test_数据源接到后端_注册齐():
    """四处注册缺一不可（照 `test_wired_m11` 的同款清单）。

    ⚠️ 少一处就是**静默失效**：漏 `PAGE_LOAD` ⇒ 进页不拉数（表是空的，且不报错）；
       漏 `WIRED` ⇒ 侧栏还标「原型态」（用户会以为这一页是假的）。
    """
    assert "API.m12List" in SHELL and "/api/m12/list" in SHELL, "取数没走 `/api/m12/list`"
    assert "async function reloadM12" in SHELL, "没有 `reloadM12()`"
    assert "'差异登记': reloadM12" in SHELL, "`LOADERS` 要认这一路（否则进页面不拉）"
    assert "m12: ['差异登记']" in SHELL, "`PAGE_LOAD` 要登记（`P3` 的按需取数靠它）"
    assert "'m12'" in SHELL, "`WIRED` 要加 `m12`（侧栏与顶栏据此不标「原型态」）"


@acc("ACC-DIF-REG-001", "001-01")
def test_手工清单不由别处自动生成行():
    """⭐ 判据原文：「本页为**手工清单**：有登记入口、可增、可删，**不由库存单据 / 过程资料自动生成行**」。

    ⚠️ 「不自动生成」这条**没有正向代码可查**（"没写"是看不见的）⇒ 只能**反向钉**：
       全壳里写 `DFs` 内容的地方**只能有一处**（`reloadM12` 的原地填充）——
       多出第二处（比如某个 `reloadM08` 顺手往 `DFs` 里塞一行）就**破了这条口径**。
    """
    reload = _fn("async function reloadM12() {", "\n}\n")
    assert "DFs.length = 0" in reload and "DFs.push" in reload, \
        "`reloadM12` 没原地填充 `DFs`（⚠️ `DFs` 是 const，只许改内容）"
    assert SHELL.count("DFs.push") == 1, \
        f"壳里有 {SHELL.count('DFs.push')} 处写 `DFs` —— 只许 `reloadM12` 这一处（手工清单，⛔ 不自动生成行）"
    assert "DFs.splice" not in SHELL, "⛔ 还有本地 `splice` 冒充删除（刷新就没了）"
    # 演示数据必须删净（留着就是"看起来有数据"的假绿）
    # ⚠️ 判据要挑**代码**形态：`DFs=DF.map(` —— ⛔ 别用裸 `DF.map(`，
    #    我自己写的那段说明注释里就引了 `DF.map(r=>O(r,DF_COLS))`，裸串会**自己撞自己**。
    assert "DFs=DF.map(" not in SHELL, "⛔ `DFs` 还从演示数组 `DF` 起手（本页数据一律来自后端）"
    assert "const DF = [" not in SHELL, "⛔ 演示数组 `DF` 还留在壳里"
    # ⚠️ 同样挑代码形态（`const nextDfId=`）—— 说明注释里会提到这个名字，裸串自己撞自己
    assert "const nextDfId=" not in SHELL, "⛔ 壳里还在自己算编号 —— 那就是**第二个编号主人**（会撞号）"


# ---------------------------------------------------------------- 写动作（正向 + 反向）


@acc("ACC-DIF-REG-001", "001-02")
def test_三个写动作都走真接口且先判ok():
    """登记 / 删除 / 标记已核对 —— **一律**发请求、**先判 `ok`**、再刷本页。

    ⚠️⚠️ **先判 `ok`** 这条是用户 2026-09-20 刚教的（`M5-9b` 假成功清扫）：
       `/api/m12/*` 的写动作**恒 HTTP 200 ＋ `ok` 标志**（同 `m03`/`m07`/`m09`/`m14`）
       ⇒ **只靠 `try/catch` 挡不住**（失败不抛）⇒ 不判 `ok` 就会**把失败说成成功**。
    """
    # ⚠️ 段尾必须取**下一个动作名**：取 `"\n"` 会当场截断（函数签名后面就是换行）——
    #    这正是"断言写得太松 ⇒ 假绿"的一种，写的时候就得堵住。
    for start, end, api in (("dfOk:async", "dfAdd:", "API.m12Status"),
                            ("dfSave:async ()", "dfDel:async", "API.m12Create"),
                            ("dfDel:async", "dfFilter:", "API.m12Delete")):
        body = _fn(start, end)
        assert api in body, f"`{start}` 段里没走 `{api}`"
        assert "ok === false" in body, f"`{start}` 没判 `ok`（失败恒 200 ⇒ 会把失败说成成功）"

    save = _fn("dfSave:async ()", "dfDel:async")
    # ⚠️ 失败**不清草稿**：人刚填的一整行不能丢（`dfClear` 必须在成功分支里）
    assert save.index("ok === false") < save.index("dfClear()"), \
        "`dfSave` 在判 `ok` **之前**就清了草稿 ⇒ 失败时用户填的一整行会丢"
    # ⛔ 反面：壳里不许再自己校验（判定唯一主人 = 后端 `domain.validate`）
    assert "badMoney(" not in save and "请先选「核算月」" not in save, \
        "壳里还留着一份本地校验 —— 同一个口径两处实现，迟早分叉"
    # 定位必须用后端主键（业务编号可读、但不该当写定位键）
    assert "_dbId" in save or "_dbId" in _fn("dfDel:async", "dfFilter"), \
        "写动作没按后端主键定位（§9.8.2-5「写操作按 id 定位」）"


@acc("ACC-DIF-REG-001", "001-02")
def test_适配层把后端字符串金额转成数字():
    """⚠️ 后端金额出**字符串**（`numeric(18,2)` 精度保护）⇒ 适配层必须过 `N0()`
    （漏了会让本页合计变**字符串拼接**、合计安静地错 —— 「接后端时必查三件」那条）。"""
    body = _fn("function adaptDf(x)", "\n}\n")
    assert "amount: N0(x.amount)" in body, "`adaptDf` 没把金额转数字"
    # ⚠️ `id` 必须 String：原型到处 `d.id===t.dataset.id`，而 dataset 出来**永远是字符串**
    assert "id: String(" in body, "`adaptDf` 的 `id` 必须转字符串（否则按钮点了静默没反应）"
    assert "type: x.owner" in body, "归属字段名对不上（后端叫 `owner`、原型列叫 `type`）"
