"""⭐ **留痕范围**（§9.3）的**真实现侧**判据 —— `TAIL-21`（2026-09-29 · 用户选 `A`）。

**为什么值得一条**：`TAIL-21` 台账原话 =「留痕是**判据性口径**（「是否手改」的唯一事实来源），
无判据 ⇒ **静默丢失**」。⚠️ 侦察实测：这条口径原先**只**由**原型** `demo/_smoke.js` 的 `X6` 组
6 条挂着（`guard('X6｜…')`，跑在**原型自己的** `trail` 数据模型上）⇒ **真实现（后端 ＋ 真壳）
侧一条判据都没有**：`ProjectFieldLog` 这个名字在 `backend/tests/` 里 **0 命中**。

**口径原文**（《说明书》§9.3）：留痕**只给** ——
· **项目**：全名 / 状态（＋ `project_type`：人工覆盖三类判定必须有据 · `TAIL-42`）
· **统计金额**：统计结算 / 统计付款（`StatTrace` ⇒ 由 `test_acc_pay_stat.py` 守）
⇒ 其余**一律不留痕**：展示名 · 排序 · 关键词 · 分类 · 集采实际供应商 · 三态标记 · 剔除 · 会话级付款金额。

⚠️ 本件**刻意不绑契约面**（`@acc()` 空参 · 同 `TAIL-192` 的先例）：守的是**工程侧的可操作性**
（"这一改留没留下据"），不对应"用户看得见的行为" ⇒ **四态条数不因此变**（现值看 `acc_report` 输出，⛔ 别手抄数字 —— 手抄必漂，本仓栽过多次）。
⚠️ 反向灵敏度 = `tools/mut/_mut_trailscope.py`（三个靶：往 `set_disp` 里塞留痕 · 摘掉 `rename_full`
的留痕 · 在别处直造 `ProjectFieldLog`）。
"""
from __future__ import annotations

from pathlib import Path

from app.mod01_projects import repository as repo
from app.mod01_projects.models import LOGGED_FIELDS, STATUS_ARCHIVED, Project, ProjectFieldLog
from tests.acc_plugin import acc
from tests.m01_helpers import make_project
from tests.m04_helpers import FakeSession

ROOT = Path(__file__).resolve().parents[2]
REPO_PY = ROOT / "backend" / "app" / "mod01_projects" / "repository.py"


class _WriteSession(FakeSession):
    """在只读桩上加**写**能力（`log_field` 会 `session.add(...)` ＋ `flush()`）。"""

    def __init__(self, by_model: dict) -> None:
        super().__init__(by_model)
        self.added: list = []

    def add(self, row) -> None:  # noqa: ANN001
        self.added.append(row)

    def flush(self) -> None:
        return None


def _sess(*projects: Project) -> _WriteSession:
    return _WriteSession({Project: list(projects)})


def _logs(s: _WriteSession) -> list[ProjectFieldLog]:
    return [r for r in s.added if isinstance(r, ProjectFieldLog)]


@acc()
def test_留痕白名单是_全名_状态_类型_三类():
    """`LOGGED_FIELDS` = 留痕范围的**正源** ⇒ 它**多一类 / 少一类**都必须被人看见。

    ⚠️ 「展示名 / 排序**不在**名单里」那半已由 `test_acc_prj_ord.py`（`ACC-PRJ-ORD-001/001-07`）守着，
    本件**不重复**；这里钉**正向三类** ＋ 另两个"看着像业务字段、其实不在范围里"的（关键词 / 仓库名）。

    ⚠️ **能证伪**：往 `LOGGED_FIELDS` 里加一项（或删一项）⇒ 本件必红。
    """
    assert set(LOGGED_FIELDS) == {"name_full", "status", "project_type"}, (
        "留痕白名单变了 —— 这是**口径**（《说明书》§9.3）、不是实现细节："
        "改它要**同批**改口径与本件（多一类 ⇒ 范围悄悄变大；少一类 ⇒ 该留痕的留不下）"
    )
    for not_logged in ("match_keywords", "warehouse_name"):
        assert not_logged not in LOGGED_FIELDS, (
            f"{not_logged} 不该留痕（§9.3 只给 全名 / 状态 / 类型）")


@acc()
def test_改展示名与关键词不写留痕():
    """展示名 = **显示别名**、关键词 = **匹配用** ⇒ 都不是"业务事实" ⇒ 改它们**不产生留痕**。

    ⚠️ **能证伪**：任一处改成"顺手记一条"（在 `set_disp` / `set_keywords` 里调 `log_field`）⇒
    本件必红（反灵敏度 = `_mut_trailscope.py` 的 `M1`）。
    """
    p = make_project(1, name_full="甲项目", warehouse="甲仓", disp="甲仓")
    s = _sess(p)
    repo.set_disp(s, p, "新展示名")
    repo.set_keywords(s, p, ["石灰窑", "石灰窑", "  窑  "])
    assert _logs(s) == [], (
        "改展示名 / 关键词写了留痕 —— 「修改留痕」卡会被噪声灌满，"
        "而 §9.3 的留痕范围只给 全名 / 状态 / 类型")
    assert p.disp == "新展示名", "展示名没真的改成"
    assert p.match_keywords == ["石灰窑", "窑"], "关键词没去空去重"


@acc()
def test_改全名与状态各写一条留痕且字段名在白名单里():
    """⭐ 「是否手改」的**唯一事实来源 = 留痕** ⇒ 该留痕的两类必须**真留下**，且字段名在白名单里。

    ⚠️ **能证伪**：摘掉 `rename_full` / `set_status` 里的 `log_field` 调用 ⇒ 本件必红
    （反灵敏度 = `_mut_trailscope.py` 的 `M2`）。
    """
    p = make_project(1, name_full="甲项目", warehouse="甲仓", disp="甲仓")
    s = _sess(p)
    repo.rename_full(s, p, "甲项目(XMCB2025080001)", changed_by="u")
    logs = _logs(s)
    assert len(logs) == 1 and logs[0].field == "name_full", "改全名必须留**一条** `name_full` 留痕"
    assert logs[0].field in LOGGED_FIELDS, "留痕的字段名不在白名单里（等于绕开了范围）"
    assert logs[0].old_value == "甲项目" and logs[0].new_value.startswith("甲项目"), "留痕缺改前 / 改后值"
    assert logs[0].changed_by == "u" and logs[0].changed_at is not None, "留痕缺「谁改的 / 什么时候」"

    p2 = make_project(2, name_full="乙项目", warehouse="乙仓")
    s2 = _sess(p2)
    repo.set_status(s2, p2, STATUS_ARCHIVED, changed_by="u")
    logs2 = _logs(s2)
    assert len(logs2) == 1 and logs2[0].field == "status", "归档必须留**一条** `status` 留痕"
    assert logs2[0].new_value == STATUS_ARCHIVED and logs2[0].old_value != STATUS_ARCHIVED, \
        "状态留痕缺改前 / 改后值"


@acc()
def test_ProjectFieldLog只许在唯一出口里构造():
    """绕过白名单**直写**留痕 = 范围失控（今天改一处、明天别处偷偷写）⇒ 构造点只许**一处**。

    ⚠️ **能证伪**：在别的件里直造一个 `ProjectFieldLog(...)`（或在 `log_field` 之外造）⇒ 本件必红
    （反灵敏度 = `_mut_trailscope.py` 的 `M3`）。
    """
    hits: list[str] = []
    for f in sorted((ROOT / "backend" / "app").rglob("*.py")):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            # ⚠️ 收窄（本判据第一版就是这么假红的，别拆）：`models.py` 里那行是**类定义**
            #    （`class ProjectFieldLog(Base):`）—— 它不是"构造点"，不排掉就永远多一处。
            if "ProjectFieldLog(" in line and not line.startswith("class "):
                hits.append(f"{f.relative_to(ROOT).as_posix()}:{i}")
    assert len(hits) == 1, (
        f"`ProjectFieldLog(` 的构造点应**只有** 1 处（`repository.log_field`），实为 {len(hits)} 处：{hits}")
    assert hits[0].startswith("backend/app/mod01_projects/repository.py:"), \
        f"留痕只能在 `repository.log_field` 里构造（唯一出口），如今另有：{hits}"

    lines = REPO_PY.read_text(encoding="utf-8").splitlines()
    start = next(i for i, x in enumerate(lines) if x.startswith("def log_field("))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("def "))
    lineno = int(hits[0].rsplit(":", 1)[1])
    assert start < lineno - 1 < end, \
        f"留痕构造跑到了 `log_field` 之外（第 {lineno} 行）—— 那等于**绕过唯一出口**直写"
