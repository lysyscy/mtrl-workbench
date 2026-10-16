"""`ACC-HOME-TODO-001` —— 看板（默认落地页）= **待办页**（项数**以 `KEYS` 为准**，⛔ 别在文案里写死个数；用户增减待办项是常态）。

判据 → `PRD/验收/验收基线.json` 的 `cases["ACC-HOME-TODO-001"]`。
⚠️ **看板不占模块号**（原型导读）⇒ 本页交互规格主人 = 原型 `V.home`（`demo/`）。

⭐⭐ **2026-09-21 判据搬家（`§19` 批 5 · 看板接真数据）**：看板原先有**服务端渲染页**
   （`app/home/view.py` ＋ `home/domain.py` ＋ `home/service.gather`），10 点全钉在那半边。
   看板现已进壳（`WIRED` 含 `home`）⇒ 旧页与那三个出口**已于 2026-09-21 删除**，
   断言**改指新壳**（⛔ 判据一条不删、编号不变 —— 这就是"形态变、判据不变"）：

| 点 | 现在的落点 |
|---|---|
| `001-01` `001-02` `001-03` `001-06` `001-07` `001-08` `001-09` `001-10` | 壳 `index.html` 的 `V.home` 切片（**A 段**） |
| `001-04` `001-05` | 后端 `GET /api/home/run-counts`（`app/home/service.py::run_counts`，**B 段**） |

⭐ **为什么 ⑦⑬⑭ 那两点落在后端**（不是偷懒）：`run_record` 是**流水表**
   （2026-09-21 实测 5 天 49 条 ≈ **10 条/天** ⇒ 一个月 ≈300 条），而记录端点是**窗口**
   （`limit ≤ 200`）⇒「本月有没有成功抓取」在窗口里**会漏**、**而且漏了不报错**
   （症状 = 看板说"本月未抓" ⇒ 用户照着去重抓 ⇒ **白顶一次 i8 的号**）。
   ⇒ 判据要求"取自执行记录"，那就必须**跨全表** ⇒ 只有后端能答。

⚠️ 只读壳源码（`SHELL`）；A 段的断言一律在 **`V.home` 切片**里找 ——
   不到全文里撞（`data-todo` / `tile(` 这类写法在别的页也有 ⇒ 会**假命中**）。
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from tests.acc_plugin import acc
from tests.shell_src import SHELL  # noqa: F401  ← `P4`① 读取点收敛

from app.home import service as S

CASE = "ACC-HOME-TODO-001"

#: 8 项把手（**顺序也是契约** —— 看板按此序展示）
#: ⭐ `TAIL-97`（2026-09-25）：`jcPending`（集采合同待确认）**已撤** ⇒ 9 项 ⇒ 8 项。
# ⚠️ 2026-09-28（用户口径 · 看板清账）：删掉 4 个瓦片 —— `ntUnapproved` / `dfPending` /
#    `fetchFail` / `printFail`（用户判「全无用」）。⭐ **claim 不变**：「留下的每一项」都必须
#    **有本域出口 · 能点去对应页 · 不许写死数字」。⛔ 删除已登记，别把这几项加回来。
#: ⭐ 2026-09-28（用户口径「**AB 做吧**」· 看板补两项真待办）：加 `jcUnlinked`（集采未关联合同 ⇒
#:    **付不了款**）与 `voidJoint`（i8 已撤单但仍有牵涉 ⇒ 账不准）。⭐ **claim 不变**：
#:    每一项都必须**有本域出口 · 能点去对应页 · 不许写死数字**。
#: ⚠️ 顺序即契约（= 页面渲染顺序）：两个新把手**插在 `fetchDue` 之前** —— 前面几项都是「有具体东西要办」，
#:    而「本月抓取」更像**例行状态**（已抓就绿）。⛔ 改顺序要**同批改壳里的瓦片顺序**，否则本件必红。
KEYS = ("ownership",
        "placeholder", "jcUnlinked", "voidJoint", "fetchDue")

#: 每项的去向页（`data-k`）—— 新加两项都去 `m03`（付款通知书页：关联合同 / 撤销付款 / 解绑都在那）
DEST = {"ownership": "m03",
        "placeholder": "m01", "fetchDue": "m02",
        "jcUnlinked": "m03", "voidJoint": "m03"}
# ⚠️ 上面这张表里若还留着已删瓦片的条目（如 `ntUnapproved`），那是**惰性残留** —— 001-03 只按
#    `KEYS` 逐项核对，多余的键不会生效；下次动本件时顺手清掉即可。


def _home() -> str:
    """`V.home` 的**推导段**（口径表达式 ＋ 各瓦片，**个数以 `KEYS` 为准**）—— 到 `return \\`` 为止。"""
    i = SHELL.find("V.home=()=>{")
    assert i >= 0, "壳里找不到 `V.home`"
    j = SHELL.find("  return `", i)
    assert j > i, "找不到 `V.home` 推导段的终点（`  return \\``）"
    return SHELL[i:j]


def _calls(block: str) -> dict[str, str]:
    """9 个瓦片调用的**实参串**：`{把手: "键,数,色,标题,显示值,说明,去向,链接文字"}`。

    ⚠️ 按行取（每个瓦片调用都独占一行、以 `),` 收尾）；⚠️ 实参里**不含逗号**
       （说明文字里用的都是 `、` / `·`）⇒ 直接 `split(',')` 就是 8 段 ——
       谁哪天往说明里塞了个逗号，本函数**当场报错**（⛔ 不静默错位）。
    """
    out: dict[str, str] = {}
    for m in re.finditer(r"^\s*(?:run)?[Tt]ile\('(\w+)',(.+)\),?\s*$", block, re.M):
        key, args = m.group(1), f"'{m.group(1)}',{m.group(2)}"
        parts = args.split(",")
        assert len(parts) == 8, f"{key} 的实参切成了 {len(parts)} 段（应为 8）：{args[:90]}"
        out[key] = args
    return out


# ================================================================ A 段 · 壳（`V.home`）


# ----------------------------------------------------------------- 001-01
@acc(CASE, "001-01")
def test_待办把手齐全不重不漏():
    """⭐ 把手集合固定、**顺序即契约**（`TAIL-97` 撤掉 `jcPending`；2026-09-28 看板清账又撤 4 项）。

    ⚠️ 数量**以 `KEYS` 为准** —— ⛔ 别把个数写死在断言里：用户增减待办项是常态，
       写死个数会让"用户删一个无用的待办"变成一串假红（本会话实测踩到）。
    """
    block = _home()
    got = [m.group(1) for m in re.finditer(r"(?:run)?[Tt]ile\('(\w+)',", block)]
    assert got == list(KEYS), f"页面把手 = {got}"
    assert len(set(got)) == len(KEYS), "把手有重复"
    assert set(_calls(block)) == set(KEYS)


# ----------------------------------------------------------------- 001-02
@acc(CASE, "001-02")
def test_每项数字都来自数据源不得写死():
    """⭐ 数字 = **对应数据域的出口**（⛔ 不写死、⛔ 不拿本页自己自证）。

    ⚠️ 断言方式：逐项钉住「**把手 → 用来算它的那个表达式**」。
       把数字改成字面量、或把口径改到别处 ⇒ **当场变红**。
    """
    block = _home()
    calls = _calls(block)
    # ①–⑥ 与 ⑤ 的表达式名（每一行都是**该域的出口**，不是本页另算的中间量）
    # ⚠️ 2026-09-28（看板清账）：`ntUnapproved` / `dfPending` 两个瓦片已删 ⇒ 从本表去掉；
    #    claim 不变：**留下的每一项**都取自本域出口（⛔ 不许本页另算中间量）。
    want_expr = {
        "ownership": "nOwn",
        "placeholder": "ph.length",
        "jcUnlinked": "nNoLink", "voidJoint": "nVoidJ",
    }
    for key, expr in want_expr.items():
        assert calls[key].split(",")[1] == expr, f"{key} 的数不是取自 {expr}：{calls[key][:70]}"
    # ⑦⑬⑭ 走 `runTile`（后端取数）—— 数字必须引 `fDone` / `fFail` / `pFail`，⛔ 不写死
    assert "fDone?0:1" in calls["fetchDue"]
    # ⚠️ 2026-09-28（看板清账）：`fetchFail` / `printFail` 两个瓦片已删 ⇒ 那两条形态断言随之去掉；
    #    claim 不变：**留下的**这一项仍必须引后端取数的量（`fDone`），⛔ 不许写死。
    # ⭐ 逐条钉住**口径表达式本身**（谁把口径改了/换成写死的数 ⇒ 红）
    for line in (
        "nUn=NO.filter(n=>ntLive(n)&&n.astat==='未批').length;",
        "const nOwn=NO.filter(n=>ntLive(n)&&isShellFull(n.proj)&&!ntProjKey(n)).length;",
        "const nAdj=IVs.filter(iv=>adjOf(iv)).length;",
        "const ph=PJs.filter(p=>p.name.startsWith('未建仓-'));",
        # ⭐ 2026-09-28 新增两项：口径**必须**走本域唯一出口（`ntJcUnlinked` / `ntVoidJoint`），
        #    ⛔ 不许本页另写判定（改口径 ⇒ 本行必红）。
        # ⚠️ 变量名**刻意不含 `nJc`** —— 001-09 那条旧墓碑写着"看板不许再数 `nJc`（集采待确认，TAIL-97 已撤）"，
        #    命名撞子串会让它**假红**（本次实测踩到）⇒ 这里用 `nNoLink`。
        "const nNoLink=NO.filter(n=>ntLive(n)&&ntJcUnlinked(n)&&statOf(n)!=='已付清').length;",
        "const nVoidJ=NO.filter(ntVoidJoint).length;",
    ):
        assert line in block, f"口径表达式的唯一出口不见了：{line}"
    # ⚠️ 反向：这些瓦片的数字**不得**出现字面量写法（`tile('x',3,` 这种）
    for key, args in calls.items():
        assert not re.fullmatch(r"\d+", args.split(",")[1]), f"{key} 的数字像是写死的：{args[:60]}"


# ----------------------------------------------------------------- 001-03
@acc(CASE, "001-03")
def test_八项都可点击跳到对应页():
    """⭐ 每一项都能**点进去处理**（不是只读展示）＋ 键盘可达（R13 无障碍）。"""
    block = _home()
    calls = _calls(block)
    for key in KEYS:
        pg = calls[key].split(",")[6]
        assert pg == f"'{DEST[key]}'", f"{key} 的去向 = {pg}（应为 'm{DEST[key][1:]}'）"
    # 瓦片出口必须**自带**可点三件套（否则 9 个瓦片全是死块）
    tmpl = block[block.find("const tile=(k,n,cls,t,v,s,pg,tx)=>"):]
    for bit in ('data-act="go"', 'data-k="\'+pg+\'"', 'tabindex="0"', 'role="button"'):
        assert bit in tmpl[:400], f"瓦片出口缺「可点」要件：{bit}"


# ----------------------------------------------------------------- 001-06
@acc(CASE, "001-06")
def test_未审批只计有效且未审批():
    """⭐ 「未审批」= **有效且未审批**（撤单 / 剔除行不计）—— 出口是 `ntLive`（唯一判据）。"""
    assert "nUn=NO.filter(n=>ntLive(n)&&n.astat==='未批').length;" in _home()


# ----------------------------------------------------------------- 001-07
@acc(CASE, "001-07")
def test_归属待判定计壳且未定具体小微():
    """⭐ 「归属待判定」= 壳全名 且 **尚未指定具体小微**（`isShellFull` ＋ `ntProjKey`）。"""
    assert "const nOwn=NO.filter(n=>ntLive(n)&&isShellFull(n.proj)&&!ntProjKey(n)).length;" in _home()


# ----------------------------------------------------------------- 001-08


# ----------------------------------------------------------------- 001-09
@acc(CASE, "001-09")
def test_集采与差异各取本域出口且不臆造不隐藏():
    """⭐ 2026-09-21 重写口径：两项**都已实现**，各自取本域出口；⛔ 不臆造、⛔ 不把项藏起来。

    ⚠️ 原文写的是「该域**未实现时**记 0 并标注」—— 那个条件现在**不成立**了：
       · 「集采待确认」自 `M5` 起就是**真数**（`JCs` 三态，`m11` 已接线）；
       · 「差异」自 `MOD-12` 撤页后**载体 = 库存单据的调整单**（§5.8.3）⇒ 数 = 有调整单的行数。
       ⛔ 别退回"恒 0 ＋ 该域未实现"（那会让看板去谎报一个不存在的待办）。
    """
    block = _home()
    assert "const nAdj=IVs.filter(iv=>adjOf(iv)).length;" in block
    # ⭐ `TAIL-97`：`jcPending`（集采待确认）**已撤** ⇒ ④ 号那条口径出口**不许再出现**
    assert "nJc" not in block, "看板又数起了「集采待确认」（该待办已撤）"
    # ⛔ **已撤页的数据源不许长回来**（`DFs` 是 m12 的留痕残留、恒空 ⇒ 拿它当"待核对"就是谎报）
    assert "DFs" not in block, "看板又读起了 `DFs`（那是已撤的 `m12` 的残片，恒空）"
    assert "待核对" not in block, "看板又写起了「差异待核对」（该状态已无载体）"
    # ⚠️ 2026-09-28（看板清账）：`dfPending` 瓦片已删（用户判无用）⇒ 原「两项都在」不再适用；
    #    claim 改成**反向**保留：已撤的东西⛔ 不许长回来（下面那条 `jcPending` 就是同款）。
    calls = _calls(block)
    assert "jcPending" not in calls, "看板的「集采待确认」瓦片已撤（TAIL-97）"


# ----------------------------------------------------------------- 001-10
@acc(CASE, "001-10")
def test_占位行按占位前缀计():
    """⭐ 「占位行」= 仓库名以占位前缀开头（`未建仓-`）的档案行数。"""
    assert "const ph=PJs.filter(p=>p.name.startsWith('未建仓-'));" in _home()


# ================================================================ B 段 · 后端（记账端点）


class _Sess:
    """极简 Session：只为 `fetch_due` 的**计数查询**服务（与旧断言同款桩件）。"""

    def __init__(self, success_rows=0):
        self._n = success_rows

    def execute(self, *_a, **_k):
        n = self._n

        class _R:
            def scalar_one_or_none(self):
                return n

        return _R()


class _Rec:
    """假执行记录（`run_record_out` 只读属性 ⇒ 鸭子类型即可）。"""

    def __init__(self, run_type="fetch", target="付款通知书", status="failed"):
        self.id, self.run_type, self.target, self.status = 1, run_type, target, status
        self.success_count, self.fail_count = 0, 1
        self.error_message = "i8 接口超时"
        self.started_at = datetime(2026, 9, 14, 9, 12, 7)
        self.finished_at = datetime(2026, 9, 14, 9, 12, 38)


def _patch(monkeypatch, *, fetch_fail=0, print_fail=0):
    """按 `run_type` 分别给失败记录（⛔ 两类**不得混用**）。"""
    monkeypatch.setattr(
        "app.mod02_i8.repository.recent_fetch_failures",
        lambda s, *, run_type="fetch", limit=5:
            ([_Rec(run_type)] if (print_fail if run_type == "print" else fetch_fail) else []),
    )


# ----------------------------------------------------------------- 001-04
@acc(CASE, "001-04")
def test_抓取到期与失败取自执行记录(monkeypatch):
    """⭐ 「本月尚未抓取」＝ 本月**有没有成功**的抓取；「最近一次抓取失败」＝ 最近那条失败记录。

    ⚠️ 判据原文要求「含**表名与时间**」⇒ 端点必须把**那条记录**带回来（⛔ 不只是给个 0/1）。
    """
    _patch(monkeypatch, fetch_fail=2)
    out = S.run_counts(_Sess(success_rows=0))
    assert out["counts"]["fetchFail"] == 1                      # 0/1 待办数
    assert out["counts"]["fetchDue"] == 1                       # 本月无成功记录 ⇒ 提示
    assert not out["errors"], f"取数有错被吞：{out['errors']}"    # ⛔ 不许静默吞错
    rec = out["latest"]["fetchFail"]
    assert rec is not None and rec.target and rec.started_at, "失败记录没带回来（判据要「表名 ＋ 时间」）"

    out2 = S.run_counts(_Sess(success_rows=3))                  # 有成功记录 ⇒ 不提示
    assert out2["counts"]["fetchDue"] == 0

    # ⭐ 结构：壳必须**问后端**（⛔ 不许在壳里扫记录窗口 —— 那会漏，且漏了不报错）
    # ⚠️⚠️ **必须钉「代码行」而不是钉关键词** —— 本节三条断言第一版就是栽在这：
    #    · `'看板计数' in SHELL` ⇒ 把 `LOADERS` 的键改名、而 `PAGE_LOAD` 里那个字符串还在 ⇒ **仍是绿的**；
    #    · `'runFailInfo' in SHELL` ⇒ 改名成 `runFailInfoX` 后**子串仍命中** ⇒ **仍是绿的**；
    #    · `'/api/home/run-counts' in SHELL` ⇒ 注释里也写着这个串 ⇒ **仍是绿的**。
    #    ⇒ 三条全落空（`tools/mut/_归档-20261009/_mut_home_wired.py` 的 M5/M6/M7 实测无区分力）。
    for line in ("  homeRunCounts: () => API.get('/api/home/run-counts'),",
                 "  '看板计数': reloadHome,",
                 "function runFailInfo(rec) {"):
        assert line in SHELL, f"壳里少了这条代码（⛔ 注释里写着不算）：{line}"
    assert "RUNLOG" not in _home(), "`V.home` 又读起了写死的演示记录数组"
    assert "home: ['付款通知书', '项目档案', '看板计数']," in SHELL, \
        "看板没把记账这一路加进取数表"
    # ⚠️ **补盲区**：上面两条用的是 `_Sess` 桩件，而桩件的 `execute()` **直接返一个数**
    #    ⇒ 那句 SQL（按 run_type / status / **本月**筛）在桩件下**永远是对的**。
    #    这里按结构再钉一遍：三个条件一个都不能少（去掉「本月」那句 ⇒ 看板会拿旧月份报"已抓"）。
    _svc = Path(S.__file__).read_text(encoding="utf-8")
    for bit in ("RunRecord.run_type == RUN_FETCH", 'RunRecord.status == "success"',
                'datetime.strptime(ym + "-01", "%Y-%m-%d")'):
        assert bit in _svc, f"记账端点的 SQL 少了这条条件：{bit}"


class _BadSess:
    """取数就炸的 Session（只为走**失败路径**）。"""

    def execute(self, *_a, **_k):
        raise RuntimeError("boom")


# ----------------------------------------------------------------- 001-04（反面）
@acc(CASE, "001-04")
def test_取数失败必须如实报错不许静默吞(monkeypatch):
    """⛔ **反面用例**（没有它，`assert not out["errors"]` 就是一句空话 —— 永远为真）。

    铁律「禁静默」：某一路取不到 ⇒ **记 0 ＋ 把原因说出来**（看板那三格据此显「—」），
    ⛔ 不是悄悄当成"没有待办"（那会让用户以为本月抓过了）。
    """
    out = S.run_counts(_BadSess())
    assert out["errors"].get("fetchDue"), f"本月抓取那一路取数失败被吞了：{out['errors']}"
    assert out["counts"]["fetchDue"] == 0, "取不到数时不该凭空报 1"

    monkeypatch.setattr(
        "app.mod02_i8.repository.recent_fetch_failures",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    out2 = S.run_counts(_Sess())
    assert set(out2["errors"]) == {"fetchFail", "printFail"}, f"两路失败都被吞了：{out2['errors']}"
    assert out2["latest"]["fetchFail"] is None and out2["latest"]["printFail"] is None


# ----------------------------------------------------------------- 001-05
@acc(CASE, "001-05")
def test_打印失败取自打印执行记录(monkeypatch):
    """⭐ 「打印投递失败」取自**打印**记录 —— 与抓取**不混用**（§4.6）。"""
    _patch(monkeypatch, print_fail=3, fetch_fail=0)
    out = S.run_counts(_Sess())
    assert out["counts"]["printFail"] == 1
    assert out["counts"]["fetchFail"] == 0                      # 两种记录**不混用**
    assert out["latest"]["printFail"].run_type == "print"
    assert out["latest"]["fetchFail"] is None
    # ⚠️ 时间必须与 m02 页同一展示口径（`T` 换空格），且**标签走 `m02LabelOf`**（同一个出口）
    #    ⇒ ⛔ 只写 `"runFailInfo" in SHELL` 是**假绿**：改名成 `runFailInfoX` 子串照样命中（实测 M6 未命中）。
    for line in ("function runFailInfo(rec) {",
                 "  return { obj: m02LabelOf({ type: rec.run_type, target: rec.target }),",
                 "           at: String(rec.started_at || '').replace('T', ' ') };"):
        assert line in SHELL, f"壳里少了这条代码（⛔ 注释里写着不算）：{line}"


# ================================================================ 附 · 旧渲染出口的坟


@acc()
def test_旧看板渲染层不得复活():
    """⛔ 旧的服务端渲染看板（`render_home`，已于 2026-09-21 删除）不许长回来。

    ⚠️ 这不是"多此一举"：本页曾经**整块存在过**（`home/view.py` 68 行），
       而壳接管之后它若再出现，就会出现"两个看板、数还不一样"。
       `T8` 那张 `CANCELLED` 表也登记了同一个名字（每次跑批都会端到面前）。
    """
    home_dir = Path(__file__).resolve().parents[1] / "app" / "home"
    assert not (home_dir / "view.py").exists(), "旧看板渲染页 `view.py` 又回来了"
    assert not (home_dir / "domain.py").exists(), "旧看板的 8 项口径出口 `domain.py` 又回来了"


@acc()
def test_看板只保留待办():
    """用户 2026-10-08 撤掉三块说明，防止后续恢复干扰内容。"""
    from tests.shell_src import page_slice
    page = page_slice('home')
    for text in ('怎么看这一页', '只列「需要你处理的事」', '状态一览'):
        assert text not in page, f'看板又出现已撤掉内容：{text}'
    assert 'todoTiles.join' in page and 'todo-grid' in page
