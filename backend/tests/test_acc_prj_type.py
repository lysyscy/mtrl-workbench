"""`ACC-PRJ-OWN-001` 的**人工覆盖三类判定**（`TAIL-42`）验收断言。

**这件事的根因**（现网事实）：三类判定（§2.2.1）里"是不是壳"**只看全名里有没有「小微」**
（`domain.classify_name`）⇒ **有的壳的全名不含「小微」** ⇒ 被误判成**普通项目**；
材料侧再遇到它名下的仓库时，就会按普通项目那条路重复处理（`m01` 上看着是"同名的几条普通项目"）。

**三件事**（= 说明书 `MOD-01` 能力 5「三类项目自动判定（双轨 ＋ **人工可覆盖**）」缺的那半）：
1. 人能把一条行在「普通项目 ⇄ 小微壳」之间纠正（**唯一出口** ＋ 留痕）；⛔ `small` 不受理。
2. **人工覆盖要"粘住"** —— 该全名已在档案里是壳 ⇒ 之后同步给同族仓库建行时**按壳处理**。
3. 仓库名的规矩：普通项目**必须**挂仓库名、壳**不挂**；行下有具体小微不许改类型（§2.7.2）。

⚠️ 库级断言**一律非破坏**：本机测试连的是**同一个库** ⇒ 每个用例末尾 `s.rollback()`（一行不留）。
"""

from __future__ import annotations

import pytest

from app.core.db import session_scope
from app.core.errors import MustReportError
from app.mod01_projects import repository as repo
from app.mod01_projects.archive import plan_archive
from app.mod01_projects.models import TYPE_NORMAL, TYPE_SHELL, TYPE_SMALL

_SHELL_NO_KEYWORD = "第四工程公司 2024 前置车间项目"      # ⚠️ **全名不含「小微」** = 那条根因
_SHELL_WITH_KEYWORD = "第四工程公司 2024小微项目"


def _new_row(s, *, ptype=TYPE_NORMAL, name=_SHELL_NO_KEYWORD, wh="__自检仓_类型纠正__"):
    """造一条**自检行**（用完 `rollback` ⇒ ⛔ 不留痕、不占名）。"""
    row = repo.create_project(s, project_type=ptype, name_full=name, warehouse_name=wh, phid="")
    s.flush()
    return row


# --------------------------------------------------------------- 1 · 人工纠正（唯一出口）


def test_被误判成普通项目的壳可以人工纠正成壳():
    """⭐ 根因那条：错误判成普通项目的行 ⇒ 人工改成壳（**并通过留痕留下介入痕迹**）。"""
    with session_scope() as s:
        row = _new_row(s, ptype=TYPE_NORMAL, wh="__自检仓_改壳__")
        pid = row.id
        assert row.project_type == TYPE_NORMAL and row.warehouse_name == "__自检仓_改壳__"

        repo.set_type(s, row, TYPE_SHELL, changed_by="自检")

        assert row.project_type == TYPE_SHELL
        assert row.warehouse_name is None, "壳**不挂仓库** ⇒ 改类型时要把仓库名让出来（否则唯一约束会挡）"
        logs = [x for x in repo.list_logs(s, pid) if x.field == "project_type"]
        assert len(logs) == 1, "人工介入判定必须留痕（否则日后看不出这行为什么跟同名的别行不一样）"
        assert logs[0].old_value == "normal" and logs[0].new_value == "shell"
        s.rollback()                                        # ⛔ 非破坏


def test_具体小微不由人工指定且重复纠正被拒():
    """⛔ `small` 不受理（它得挂壳下 ＋ 占仓库名，由链路产生）；已是该类型 ⇒ 明确拒（不写空留痕）。"""
    with session_scope() as s:
        row = _new_row(s, ptype=TYPE_NORMAL)
        with pytest.raises(MustReportError) as e:
            repo.set_type(s, row, TYPE_SMALL, changed_by="自检")
        assert "具体小微" in str(e.value) and "由链路产生" in str(e.value), \
            f"拒绝理由要说清「为什么不能人工指定」：{e.value}"
        with pytest.raises(MustReportError) as e2:
            repo.set_type(s, row, TYPE_NORMAL, changed_by="自检")
        assert "已经是" in str(e2.value)
        assert row.project_type == TYPE_NORMAL and row.warehouse_name == "__自检仓_类型纠正__"
        s.rollback()


# --------------------------------------------------------------- 2 · "粘住"（覆盖要一直算数）


def test_人工纠正过的壳_同族仓库在建行时按壳处理():
    """⭐ 根因的**后果**：纠正过一次之后，同族的仓库不该再被当成普通项目建出来。

    做法：该全名（**不含「小微」**）在档案里已是壳 ⇒ `plan_archive` 要按壳判
    （**走判定唯一出口的 `manual_override`**，⛔ 不是在这儿另写一条规则）。

    ⚠️ 两种仓库数都要试，因为**没有人工覆盖时它们判的不是一回事**：
    挂 1 个仓库 ⇒ 按关键字判成**普通项目**（根因本体）；
    挂 ≥2 个 ⇒ 判成 `needs_confirm`（既不建也归集，甩给人工）—— **人工一句"它是壳"就把这条悬案定死**。
    """
    def rows(*whs):
        return {
            "common_rows": [{"name_full": _SHELL_NO_KEYWORD, "phid": "P1"}],
            "warehouse_rows": [{"owner_full_name": _SHELL_NO_KEYWORD, "warehouse_name": w} for w in whs],
        }

    one = rows("前置车间-1号仓")
    plain1 = plan_archive(**one)
    assert [c["project_type"] for c in plain1["create"]] == [TYPE_NORMAL], \
        "先确认这就是那条根因：全名不含「小微」＋ 刚好 1 个仓库 ⇒ 被判成**普通项目**"
    sticky1 = plan_archive(**one, shell_names_in_archive={_SHELL_NO_KEYWORD})
    assert [c["project_type"] for c in sticky1["create"]] == [TYPE_SHELL], \
        "人工纠正过的全名 ⇒ 同族仓库也按壳处理（否则下次同步又建一条普通项目）"
    assert sticky1["create"][0]["warehouse_name"] is None, "壳不挂仓库"
    assert sticky1["manual"], "壳下的仓库 = 具体小微 ⇒ 要**显式列出**走人工（⛔ 不静默跳过）"

    two = rows("前置车间-1号仓", "前置车间-2号仓")
    plain2 = plan_archive(**two)
    assert plain2["create"] == [], "≥2 个仓库 ⇒ 原口径**不自动建**（悬着）"
    assert len(plain2["manual"]) == 1 and "选一个" in plain2["manual"][0]["reason"], \
        "≥2 个仓库 ⇒ 进人工（原话「需人工选一个再建」），这正是人工要介入的那条路"
    sticky2 = plan_archive(**two, shell_names_in_archive={_SHELL_NO_KEYWORD})
    assert [c["project_type"] for c in sticky2["create"]] == [TYPE_SHELL], \
        "⭐ 人工纠正过 ⇒ ≥2 仓库这条**悬案当场定死**（按壳建 ＋ 壳下仓库进人工）"
    assert sticky2["manual"], "壳下的两个仓库仍要显式列出（具体小微得人配关键词）"


def test_粘住只认壳不认普通项目():
    """反向看住：`shell_names_in_archive` 只喂**壳**的全名 —— 别把普通项目的全名也算成壳。
    （`sync_and_archive` 里那条筛选就是按 `project_type == TYPE_SHELL` 取的。）"""
    rows = {
        "common_rows": [{"name_full": _SHELL_WITH_KEYWORD, "phid": "P2"}],
        "warehouse_rows": [{"owner_full_name": _SHELL_WITH_KEYWORD, "warehouse_name": "小微仓A"}],
    }
    assert [c["project_type"] for c in plan_archive(**rows)["create"]] == [TYPE_SHELL], \
        "含「小微」的全名本来就判壳（与人工覆盖无关）—— 这条不变量不许被这次改动带歪"
    build_rows = {
        "common_rows": [{"name_full": _SHELL_NO_KEYWORD, "phid": "P3"}],
        "warehouse_rows": [{"owner_full_name": _SHELL_NO_KEYWORD, "warehouse_name": "手动覆盖仓A"}],
    }
    from app.mod01_projects.sync_service import build_plan
    out = build_plan(load_common=lambda: build_rows["common_rows"],
                     load_warehouses=lambda: build_rows["warehouse_rows"],
                     shells={_SHELL_NO_KEYWORD})
    assert [c["project_type"] for c in out["plan"]["create"]] == [TYPE_SHELL], \
        "`build_plan` 要把 `shells` 透传给计划（这一路断了 ⇒ 人工覆盖就粘不住）"



# --------------------------------------------------------------- 3 · 仓库名的规矩 / 不变式


def test_壳改回普通项目必须给出仓库名():
    """⚖️ 反方向：普通项目**必须**挂一个仓库名（候选键 §2.7.4），壳没有 ⇒ **要求显式给出**。
    ⛔ 不给就拒、被占用也拒 —— 不许猜一个填上。"""
    with session_scope() as s:
        shell = _new_row(s, ptype=TYPE_SHELL, wh=None)
        with pytest.raises(MustReportError) as e:
            repo.set_type(s, shell, TYPE_NORMAL, changed_by="自检")
        assert "必须给出" in str(e.value) and "不猜" in str(e.value), f"得说清为什么拒：{e.value}"

        busy = _new_row(s, ptype=TYPE_NORMAL, wh="__自检仓_已占用__")
        with pytest.raises(MustReportError) as e2:
            repo.set_type(s, shell, TYPE_NORMAL, warehouse_name=busy.warehouse_name, changed_by="自检")
        assert "已被占用" in str(e2.value), f"仓库名是唯一标识：{e2.value}"

        repo.set_type(s, shell, TYPE_NORMAL, warehouse_name="__自检仓_壳改普通__", changed_by="自检")
        assert shell.project_type == TYPE_NORMAL and shell.warehouse_name == "__自检仓_壳改普通__"
        s.rollback()


def test_行下有具体小微时不许改类型():
    """§2.7.2 的壳 ⇄ 小微不变式：壳改成别的类型会把名下的小微**变成孤儿** ⇒ 先处理它们。"""
    with session_scope() as s:
        shell = _new_row(s, ptype=TYPE_SHELL, wh=None)
        child = repo.create_project(s, project_type=TYPE_SMALL,
                                    name_full=_SHELL_NO_KEYWORD, warehouse_name="__自检仓_小微子行__",
                                    phid="", parent_shell_id=shell.id)
        s.flush()
        with pytest.raises(MustReportError) as e:
            repo.set_type(s, shell, TYPE_NORMAL, warehouse_name="__自检仓_改坏了__", changed_by="自检")
        assert "具体小微" in str(e.value) and "__自检仓_小微子行__" in str(e.value), \
            f"要说清是哪个小微挡住的：{e.value}"
        assert shell.project_type == TYPE_SHELL
        s.rollback()


def test_反向_不许在别处直接写project_type():
    """⛔ 反向：改类型**只有一条路**（`repository.set_type`）——
    别处直接 `xxx.project_type = ...` 就会绕过仓库名一致性与留痕。"""
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "app"
    offenders = []
    for p in src.rglob("*.py"):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            s = line.strip()
            if ".project_type = " not in s or s.startswith("#"):
                continue
            if p.name == "repository.py" or s.startswith("project.project_type ="):
                continue                                     # 唯一出口内部（含建行）
            offenders.append(f"{p.relative_to(src)}:{i}: {s[:80]}")
    assert not offenders, "有人绕过唯一出口直接写类型：" + "；".join(offenders)
