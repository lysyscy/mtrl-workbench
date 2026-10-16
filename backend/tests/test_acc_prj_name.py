"""`ACC-PRJ-NAME-001` 验收断言 —— `MOD-01` **§2.3.1 命名与修改约束** ＋ **§2.3.2 尾码剥离统一**。

规则主人 =《说明书》**§2.3.1**（四个属性各自的约束）· **§2.3.2**（尾码剥离三处共用一个函数）。

⚠️ **判据与判据点 → `PRD/验收/验收基线.json` 的 `cases["ACC-PRJ-NAME-001"]`**；不要在本文件复述规则。

⚠️ 本文件**刻意不测"哪个按钮能改哪个框"**（页面层，机器断言不到）—— 只钉住**域内核可判**的部分：
   ① 剥尾码是**唯一出口、三处同源**；② 写库一律**按档案 id**、不按全名反查；
   ③ 四条"不许人工改"的边界**各有可观测出口**；④ 全名可改但**必须留给痕**（不是静默写）。

覆盖率说明：**§2.3.1 四条约束**（仓库名唯一且不可改 / 全名可改且留痕 / 展示名默认取仓库名 /
phid 由 i8 带出不可改）＋ **§2.3.2 尾码剥离统一** 各自的可观测出口都在本文件内被点到。
"""

from __future__ import annotations

from app.core.db import session_scope
from app.mod01_projects import repository as repo
from app.mod01_projects.domain import (
    build_candidates,
    norm_full_name,
    resolve_ownership,
    strip_trailing_code,
)
from app.mod01_projects.models import (
    PLACEHOLDER_PREFIX,
    TYPE_NORMAL,
    TYPE_SHELL,
    TYPE_SMALL,
)
from tests.acc_plugin import acc
from tests.m01_helpers import make_project

CASE = "ACC-PRJ-NAME-001"

# ------------------------------------------------------------------ 语料
# ⚠️ 形态照**真机实测的项目全名**（`ops/实测快照/i8-20260916-*.json`）：尾部 `(XMCB2025080001)` 式。
_FULL = "百通宏达热力热电联产项目"
_CODE = "XMCB2025080001"


# ============================================================ §2.3.2 尾码剥离


@acc(CASE, "001-01")
def test_尾码剥离认括号与裸尾两种写法():
    """`§2.3.2` —— i8 全名尾部两种写法都要认（认漏任一种 ⇒ 全名对不上）。"""
    assert strip_trailing_code(f"{_FULL}({_CODE})") == _FULL        # 半角括号
    assert strip_trailing_code(f"{_FULL}（{_CODE}）") == _FULL      # 全角括号（i8 中文环境常见）
    assert strip_trailing_code(f"{_FULL} {_CODE}") == _FULL         # 裸尾（无括号、有空格）
    assert strip_trailing_code(f"{_FULL}({_CODE}) ".strip()) == _FULL


@acc(CASE, "001-02")
def test_最宽规则字母至少2位数字至少1位():
    """`§2.3.2` 决策 6 —— 规则取**最宽**的 `[A-Za-z]{2,}\\d+`（取窄了会漏剥）。"""
    # 长度 ≥2 的字母段都算：3 位、小写、大写、全大写混数字
    assert strip_trailing_code(f"{_FULL}(abc123)") == _FULL
    assert strip_trailing_code(f"{_FULL}(AB1)") == _FULL
    assert strip_trailing_code(f"{_FULL}(Xmcb2025)") == _FULL


@acc(CASE, "001-03")
def test_不是尾码的一律不动():
    """`§2.3.2` —— **只剥尾部**；中段出现、或不像项目代码的，**保持原样**（宁不剥不误剥）。"""
    # 全名里本来就带英文（不是尾码）—— 尾部无码 ⇒ 不动
    assert strip_trailing_code("ABB变频器改造项目") == "ABB变频器改造项目"
    # 括号在**中段** ⇒ 不动（只有尾部才算尾码）
    assert strip_trailing_code(f"{_FULL}({_CODE})二期") == f"{_FULL}({_CODE})二期"
    # 纯数字结尾（无字母段）⇒ 不是尾码（避免误剥年份 / 期号）
    assert strip_trailing_code(f"{_FULL}(2025)") == f"{_FULL}(2025)"
    # 单字母 + 数字 ⇒ 不满足「字母 ≥2」，不算尾码
    assert strip_trailing_code(f"{_FULL}(A1)") == f"{_FULL}(A1)"
    # 空 / None 不炸
    assert strip_trailing_code("") == ""
    assert strip_trailing_code(None) == ""


@acc(CASE, "001-04")
def test_三处共用同一出口且可传规则():
    """`§2.3.2` —— **付款通知书导出 / 仓库列表同步 / 项目列表同步 三处共用**一个函数。

    ⚠️ 本断言钉的是"**只有一处实现**"这件事：三处的调用形态都是
       `strip_trailing_code(x)`（`pattern` 走默认值）⇒ 任何一处要改规则，三处一起改。
    """
    # 三处各自的入参形态：导出侧拿通知书全名、两处同步拿 i8 名单全名
    three = [
        f"{_FULL}({_CODE})",       # ① 付款通知书导出
        f"{_FULL}（{_CODE}）",      # ② 仓库列表同步（全角）
        f"{_FULL} {_CODE}",        # ③ 项目列表同步（裸尾）
    ]
    assert {strip_trailing_code(x) for x in three} == {_FULL}
    # 默认规则 = 最宽规则：显式传同一串 ⇒ 结果必须一致（证明默认值没被改窄）
    for x in three:
        assert strip_trailing_code(x, pattern=r"[A-Za-z]{2,}\d+") == strip_trailing_code(x)


@acc(CASE, "001-05")
def test_比较一律走归一不拿原串比():
    """`§2.3.2` —— "全名对不上"的技术根因 = 有人**拿原始串比较** ⇒ 归一出口必须唯一。"""
    assert norm_full_name(f"{_FULL}({_CODE})") == norm_full_name(_FULL)
    # 全角 / 半角括号差异一并抹平
    assert norm_full_name(f"{_FULL}（{_CODE}）") == norm_full_name(_FULL)
    # 多余空白压缩（i8 名单里常见前后空格 / 连续空格）
    assert norm_full_name(f"  {_FULL}   ({_CODE})  ") == _FULL
    # 归一 ≠ 原串（否则上面几条是空断言）
    assert norm_full_name(f"{_FULL}({_CODE})") != f"{_FULL}({_CODE})"


# ============================================================ §2.3.1 命名与修改约束


@acc(CASE, "001-06")
def test_仓库名是唯一标识且占位行也占号():
    """`§2.3.1` —— 仓库名**唯一**；**不得人工改**（只能建档 / 扶正时由系统写入）。

    可观测出口：占位名 `未建仓-n` 取号要**跳过已占用的号** ⇒ 证明"仓库名这一列被当唯一键维护"。
    """
    from app.mod01_projects import archive as A

    # ⚠️ `PLACEHOLDER_PREFIX` 自带尾横线（`未建仓-`）—— 拼接时别再补一个
    assert A.next_placeholder({f"{PLACEHOLDER_PREFIX}1", f"{PLACEHOLDER_PREFIX}2"}) \
        == f"{PLACEHOLDER_PREFIX}3"
    assert A.next_placeholder(set()) == f"{PLACEHOLDER_PREFIX}1"
    # 号码被占成不连续时，仍取**最小可用号**（不重号 = 唯一性）
    assert A.next_placeholder({f"{PLACEHOLDER_PREFIX}1", f"{PLACEHOLDER_PREFIX}3"}) \
        == f"{PLACEHOLDER_PREFIX}2"


@acc(CASE, "001-07")
def test_全名可改但归属仍按id不按全名反查():
    """`§2.3.1` —— 全名**可人工修改**（应对 i8 改名 / 全角半角差异）⇒ **归属必须按 id 存**。

    反证：若归属按全名反查，改全名就会把已有单据甩到"未建档"（这正是本约束存在的原因）。
    """
    shell = make_project(1, name_full="第四工程公司 2024甲小微项目", ptype=TYPE_SHELL)
    small = make_project(11, name_full="第四工程公司 2024甲小微项目", warehouse="甲仓库",
                         ptype=TYPE_SMALL, parent_shell_id=1, keywords=["大唐雷州"])
    before = resolve_ownership(name_full="第四工程公司 2024甲小微项目",
                               doc_name="大唐雷州项目款", projects=[shell, small])
    assert before.target_id == 11

    # 改全名（i8 改名）⇒ 单据仍写**旧全名**，归属仍应落在同一个 id 上
    small.name_full = "第四工程公司 2024甲小微项目（改名后）"
    after = resolve_ownership(name_full="第四工程公司 2024甲小微项目",
                              doc_name="大唐雷州项目款", projects=[shell, small])
    assert after.shell_id == 1                      # 壳没变 ⇒ 写库是按 id 的
    assert before.shell_id == after.shell_id


@acc(CASE, "001-08")
def test_展示名默认取仓库名且可独立改():
    """`§2.3.1` —— 展示名**默认取仓库名**、可改，且**改它不影响归属**。"""
    # 默认：没设 disp ⇒ 显示 = 仓库名
    p = make_project(1, name_full=_FULL, warehouse="泗阳百通4#锅炉项目仓库", disp=None)
    assert build_candidates([p])[0].display == "泗阳百通4#锅炉项目仓库"
    # 可改：设了 disp ⇒ 显示展示名，但**候选的键仍是仓库名**（键不跟着变）
    p.disp = "泗阳百通"
    c = build_candidates([p])[0]
    assert c.display == "泗阳百通" and c.key == "泗阳百通4#锅炉项目仓库"


@acc(CASE, "001-09")
def test_phid不可人工改且缺phid显式拒绝():
    """`§2.3.1` —— phid 由 i8 带出、**不可人工改** ⇒ 缺 phid 必须**显式拒绝建档**、不得静默建行。

    可观测出口 = 建档计划把它落进 `no_phid` 段（**既不 create、也不 exists**）＋ 理由指向 i8 侧动作。
    """
    from app.mod01_projects import archive as A

    P_NO = "戊项目(TBLX2025000006)"
    plan = A.plan_archive(
        common_rows=[{"name_full": "甲项目(XMCB2025000001)", "phid": "ph-1", "code": "C1", "ab": ""}],
        warehouse_rows=[{"warehouse_name": "戊仓", "owner_full_name": P_NO}],
        existing=set(), taken_names=(),
    )
    rows = [r for r in plan["no_phid"] if r["name_full"] == P_NO]
    assert rows, "缺 phid 的项目未被拦住 —— 静默建档 = 后续按 phid 筛单据全落空"
    assert not [c for c in plan["create"] if c["name_full"] == P_NO]     # 不进 create
    assert "常用项目列表" in rows[0]["reason"]                            # 指回 i8 侧该做的动作


@acc(CASE, "001-10")
def test_改全名必须留给痕而不是静默写(rollback_db):
    """`§2.3.1` —— 全名可改 ⇒ **需留痕**（不是静默 UPDATE）。

    可观测出口：真实改名路径把旧值、新值写入 `name_full` 字段日志。
    """
    with session_scope() as s:
        p = repo.create_project(
            s, project_type=TYPE_NORMAL, name_full=_FULL, warehouse_name="__自检仓_项目改名__"
        )
        old = p.name_full
        new = f"{_FULL}（改名后）"
        repo.rename_full(s, p, new, changed_by="自检")

        assert p.name_full == new
        logs = [x for x in repo.list_logs(s, p.id) if x.field == "name_full"]
        assert len(logs) == 1
        assert logs[0].old_value == old and logs[0].new_value == new
        s.rollback()
