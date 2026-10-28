"""现行三项看板待办及已退出看板的运行计数端点兼容性。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


from app.home import service as S

CASE = "ACC-HOME-TODO-001"

# 用户2026-10-20确认的待办集合与显示顺序。
KEYS = ("ownership",
        "jcUnlinked", "voidJoint")

#: 每项的去向页（`data-k`）—— 新加两项都去 `m03`（付款通知书页：关联合同 / 撤销付款 / 解绑都在那）
DEST = {"ownership": "m03",
        "jcUnlinked": "m03", "voidJoint": "m03"}
# ⚠️ 上面这张表里若还留着已删瓦片的条目（如 `ntUnapproved`），那是**惰性残留** —— 001-03 只按
#    `KEYS` 逐项核对，多余的键不会生效；下次动本件时顺手清掉即可。






# ================================================================ A 段 · 壳（`V.home`）


# ----------------------------------------------------------------- 001-01


# ----------------------------------------------------------------- 001-02


# ----------------------------------------------------------------- 001-03


# ----------------------------------------------------------------- 001-06


# ----------------------------------------------------------------- 001-07


# ----------------------------------------------------------------- 001-08


# ----------------------------------------------------------------- 001-09


# ----------------------------------------------------------------- 001-10


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
        self.triggered_by = ""
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

    # 记账端点保持兼容，看板不再展示或请求运行状态。
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
def test_打印失败取自打印执行记录(monkeypatch):
    """⭐ 「打印投递失败」取自**打印**记录 —— 与抓取**不混用**（§4.6）。"""
    _patch(monkeypatch, print_fail=3, fetch_fail=0)
    out = S.run_counts(_Sess())
    assert out["counts"]["printFail"] == 1
    assert out["counts"]["fetchFail"] == 0                      # 两种记录**不混用**
    assert out["latest"]["printFail"].run_type == "print"
    assert out["latest"]["fetchFail"] is None



# ================================================================ 附 · 旧渲染出口的坟


def test_旧看板渲染层不得复活():
    """⛔ 旧的服务端渲染看板（`render_home`，已于 2026-09-21 删除）不许长回来。

    ⚠️ 这不是"多此一举"：本页曾经**整块存在过**（`home/view.py` 68 行），
       而壳接管之后它若再出现，就会出现"两个看板、数还不一样"。
       `T8` 那张 `CANCELLED` 表也登记了同一个名字（每次跑批都会端到面前）。
    """
    home_dir = Path(__file__).resolve().parents[1] / "app" / "home"
    assert not (home_dir / "view.py").exists(), "旧看板渲染页 `view.py` 又回来了"
    assert not (home_dir / "domain.py").exists(), "旧看板的 8 项口径出口 `domain.py` 又回来了"
