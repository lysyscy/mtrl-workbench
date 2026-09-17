"""`ACC-HOME-TODO-001` —— 看板（默认落地页）= 待办页 · 9 项待办。

判据 → `PRD/验收/验收基线.json` 的 `cases["ACC-HOME-TODO-001"]`。
⚠️ **看板不占模块号**（原型导读）⇒ 本页交互规格主人 = 原型 `V.home`（`demo/`）。

做法：`gather()` 内部是**函数级 import**（每次调用才从各域模块取出口）⇒ 测试用 `monkeypatch`
      替换**各域出口**即可，**不连库、不连 i8**。
"""

from __future__ import annotations

import re

import pytest

from app.home import domain as D
from app.home import service as S
from app.home.view import render_home
from tests.acc_plugin import acc

CASE = "ACC-HOME-TODO-001"


# ----------------------------------------------------------------- 桩件
class _P:
    """假档案行（只带本页用到的字段）。"""

    def __init__(self, pid, ptype, wh="", parent=None):
        self.id, self.project_type, self.warehouse_name, self.parent_shell_id = pid, ptype, wh, parent


class _Sess:
    """极简 Session：只为 `fetch_due` 的**计数查询**服务。"""

    def __init__(self, success_rows=0):
        self._n = success_rows

    def execute(self, *_a, **_k):
        n = self._n

        class _R:
            def scalar_one_or_none(self):
                return n

        return _R()


def _patch_all(monkeypatch, *, notices=None, projects=None, plan_rows=0,
               fetch_fail=0, print_fail=0, success_rows=1):
    monkeypatch.setattr("app.mod03_notice.repository.notices_as_dicts",
                        lambda s, **k: list(notices or []))
    monkeypatch.setattr("app.mod01_projects.repository.all_projects",
                        lambda s: list(projects or []))
    monkeypatch.setattr("app.mod02_i8.repository.recent_fetch_failures",
                        lambda s, *, run_type="fetch", limit=5: [object()] *
                        (print_fail if run_type == "print" else fetch_fail))
    monkeypatch.setattr("app.mod04_plan.repository.list_rows", lambda s: [])

    class _Row:
        def __init__(self):
            self.id = 1

        @property
        def __table__(self):
            class T:
                columns = []

            return T()

    monkeypatch.setattr("app.mod04_plan.repository.list_rows",
                        lambda s: [_Row()] * plan_rows)
    monkeypatch.setattr("app.mod04_plan.service.notice_amounts", lambda s: {})


def _html(rows) -> str:
    return render_home(rows)


def _todos(html: str) -> list[tuple[str, int]]:
    return [(m.group(1), int(m.group(2))) for m in
            re.finditer(r'data-todo="([^"]+)"[^>]*data-n="(\d+)"', html)]


# ----------------------------------------------------------------- 001-01
@acc(CASE, "001-01")
def test_九项待办把手齐全不重不漏():
    keys = D.todo_keys()
    assert len(keys) == 9 and len(set(keys)) == 9
    assert keys == ("ntUnapproved", "ownership", "planUnmatched", "jcPending", "dfPending",
                    "placeholder", "fetchDue", "fetchFail", "printFail")
    html = _html(D.dashboard({}))
    got = [k for k, _ in _todos(html)]
    assert got == list(keys), f"页面把手 = {got}"          # 顺序也是契约
    assert html.count('data-todo="') == 9


# ----------------------------------------------------------------- 001-02
@acc(CASE, "001-02")
def test_把手数字与可见数字一致(monkeypatch):
    _patch_all(monkeypatch, projects=[_P(1, "normal", "未建仓-1"), _P(2, "normal", "未建仓-2")])
    out = S.gather(_Sess())
    rows = D.dashboard(out["counts"])
    assert out["counts"]["placeholder"] == 2               # 数字来自域出口（不是本页自证）
    html = _html(rows)
    # ⭐ 同一行里：`data-n` 与可见 `<div class="v">` 必须同值（把手与显示同源）
    for seg in re.findall(r'data-todo="[^"]+"[^>]*>.*?</a>', html, re.S):
        n = int(re.search(r'data-n="(\d+)"', seg).group(1))
        v = int(re.search(r'<div class="v">(\d+)</div>', seg).group(1))
        assert n == v, seg[:80]


# ----------------------------------------------------------------- 001-03
@acc(CASE, "001-03")
def test_九项都可点击跳到对应页():
    html = _html(D.dashboard({}))
    for m in re.finditer(r'<a class="todo[^"]*" href="([^"]+)"[^>]*data-act="go"', html):
        assert m.group(1).startswith("/m"), m.group(1)
    assert len(re.findall(r'data-act="go"', html)) == 9


# ----------------------------------------------------------------- 001-04
@acc(CASE, "001-04")
def test_抓取到期与失败取自执行记录(monkeypatch):
    _patch_all(monkeypatch, fetch_fail=2, success_rows=0)
    out = S.gather(_Sess(success_rows=0))
    assert out["counts"]["fetchFail"] == 2
    assert not out["errors"], f"取数有错被吞：{out['errors']}"      # ⛔ 不许静默吞错
    assert out["counts"]["fetchDue"] == 1                  # 本月无成功记录 ⇒ 提示
    out2 = S.gather(_Sess(success_rows=3))                 # 有成功记录 ⇒ 不提示
    assert out2["counts"]["fetchDue"] == 0


# ----------------------------------------------------------------- 001-05
@acc(CASE, "001-05")
def test_打印失败取自打印执行记录(monkeypatch):
    _patch_all(monkeypatch, print_fail=3, fetch_fail=0)
    out = S.gather(_Sess())
    assert out["counts"]["printFail"] == 3
    assert out["counts"]["fetchFail"] == 0                 # 两种记录**不混用**


# ----------------------------------------------------------------- 001-06
@acc(CASE, "001-06")
def test_未审批只计有效且未审批(monkeypatch):
    notices = [
        {"approve_status": "未批", "excluded": False, "i8_revoked": False},   # ✅ 计
        {"approve_status": "已批", "excluded": False, "i8_revoked": False},   # ✗ 已批
        {"approve_status": "未批", "excluded": True, "i8_revoked": False},    # ✗ 已剔除
        {"approve_status": "未批", "excluded": False, "i8_revoked": True},    # ✗ 已撤单
    ]
    _patch_all(monkeypatch, notices=notices)
    assert S.gather(_Sess())["counts"]["ntUnapproved"] == 1


# ----------------------------------------------------------------- 001-07
@acc(CASE, "001-07")
def test_归属待判定计壳且未定具体小微(monkeypatch):
    projects = [
        _P(10, "shell"),                       # ✅ 壳下无具体小微 ⇒ 计
        _P(11, "shell"),                       # ✗ 下面有具体小微
        _P(12, "small", parent=11),
        _P(13, "normal", "甲仓"),
    ]
    _patch_all(monkeypatch, projects=projects)
    assert S.gather(_Sess())["counts"]["ownership"] == 1


# ----------------------------------------------------------------- 001-08
@acc(CASE, "001-08")
def test_计划未匹配走本域审查出口(monkeypatch):
    _patch_all(monkeypatch, plan_rows=3)
    out = S.gather(_Sess())
    assert out["counts"]["planUnmatched"] >= 0
    assert "planUnmatched" not in out["errors"]            # 取数没坏（口径在 MOD-04）
    src = (S.gather.__doc__ or "") + open(S.__file__, encoding="utf-8").read()
    assert "audit_rows" in src, "计划审查必须调 MOD-04 的审查出口，不得本页另算"


# ----------------------------------------------------------------- 001-09
@acc(CASE, "001-09")
def test_未实现域记零并显式标注():
    assert set(D.UNIMPLEMENTED) == {"jcPending", "dfPending"}
    html = _html(D.dashboard({}))
    assert html.count("该域未实现") == 2                    # ⛔ 不隐藏、不臆造
    rows = {r["key"]: r for r in D.dashboard({"jcPending": 5})}
    assert rows["jcPending"]["count"] == 0 and rows["jcPending"]["unsupported"] is True


# ----------------------------------------------------------------- 001-10
@acc(CASE, "001-10")
def test_占位行按占位前缀计(monkeypatch):
    projects = [
        _P(1, "normal", "未建仓-1"), _P(2, "normal", "未建仓-2"),
        _P(3, "normal", "甲仓"), _P(4, "shell", ""),
    ]
    _patch_all(monkeypatch, projects=projects)
    assert S.gather(_Sess())["counts"]["placeholder"] == 2
