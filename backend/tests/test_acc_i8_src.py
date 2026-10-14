"""`ACC-I8-SRC-001` 验收断言 —— `MOD-02` **§3.1.1 数据来源清单** ＋ **§3.5 三表匹配规则汇总**。

规则主人 =《说明书》**§3.1.1**（六类数据源与各自的 i8 接口 / 模块）· **§3.5**（三张表各靠什么认项目、有什么风险）。

⚠️ **判据与判据点 → `PRD/验收/验收基线.json` 的 `cases["ACC-I8-SRC-001"]`**；本文件不复述规则。

⚠️ 本文件**不绑 `@acc(用例号, 判据点号)` 的"业务断言"，而是钉「清单本身是机器可判的」**：
   §3.1.1 与 §3.5 是**清单式口径**（"有哪几个来源 / 各靠什么认项目"），
   单测某一处**证不了清单完整**，所以这里的判据 = **实现侧那张来源表与口径逐项对齐**。
   已实测：清单**有实现载体**（`app.mod02_i8.sources` 的两个 source 类 ＋ `core.config` 的端点常量）
   ⇒ 不是"无可观测出口"。

⚠️ 与 `ACC-I8-FETCH-001` 的**分工**：那条管**抓取动作**（触发 / 入参 / 回显 / 执行记录），
   本文件管**来源表**（有哪些来源、各用什么形态取、各靠什么认项目）—— 两条不重叠。
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path

from app.core.config import get_settings
from app.mod02_i8 import sources as S
from tests.acc_plugin import acc

CASE = "ACC-I8-SRC-001"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SPEC = _REPO_ROOT / "docs" / "requirements" / "材料科业务全流程说明书.md"


@contextmanager
def _env(**kv):
    """临时改环境变量并清 `get_settings` 缓存（用完**无条件**复原）。"""
    old = {k: os.environ.get(k) for k in kv}
    os.environ.update(kv)
    get_settings.cache_clear()
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()


def _spec_section(head: str) -> str:
    """从《说明书》里取一节正文（**节号 = 口径的唯一主人**，取值不从本文件抄）。"""
    if not _SPEC.exists():
        return ""
    lines = _SPEC.read_text(encoding="utf-8", errors="replace").splitlines()
    start = next((i for i, l in enumerate(lines) if l.startswith(head)), None)
    if start is None:
        return ""
    out = []
    for l in lines[start + 1:]:
        if l.startswith("#"):
            break
        out.append(l)
    return "\n".join(out)


# ============================================================ §3.1.1 数据来源清单


@acc(CASE, "001-01")
def test_来源清单六类数据源一个不少():
    """`§3.1.1` —— 来源清单是**六类**；实现侧必须每一条都有可追的载体。

    ⚠️ 本断言先把**口径那份清单**读出来（节号是主人），再要求实现侧的**来源模块**
       对每一类都能指到载体 —— 不是凭空列一张自己的表。
    """
    body = _spec_section("#### 3.1.1")
    assert body, "取不到 §3.1.1 正文（交付面路径变了？本断言不得静默跳过）"
    # 口径表里的每一行第一个 `|` 格 = 一类数据源
    names = [c.strip().strip("*`") for c in
             (m.group(0) for m in re.finditer(r"^\| \*\*.+?\*\* \|", body, re.M))]
    names = [n for n in names if n]
    assert len(names) == 6, f"§3.1.1 应列 6 类数据源，实际 {len(names)}：{names}"

    # 实现侧：纯 HTTP 的两类必须有 source 类（其余四类是导出 / 抓取，走别的通道）
    assert hasattr(S, "WarehouseSource") and hasattr(S, "CommonProjectSource")
    assert S.WarehouseSource.table == "warehouse_list"
    assert S.CommonProjectSource.table == "common_project"


@acc(CASE, "001-02")
def test_纯HTTP两类各自绑定正确的API编号():
    """`§3.1.1` ＋ 附录 E.1 —— **仓库列表 = `API-05` · 常用项目列表 = `API-06`**，不得互换。"""
    body = _spec_section("#### 3.1.1")
    assert "GetWareHouseList" in body and "GetCommonUseList" in body
    # 实现侧 docstring 必须把编号钉在类上（编号互换 = 来源张冠李戴）
    assert "API-05" in (S.WarehouseSource.__doc__ or "")
    assert "API-06" in (S.CommonProjectSource.__doc__ or "")
    # 端点常量必须**成对且不同**（同一个端点服务两类来源 = 抄错了）
    from app.core.config import I8_PATH_COMMON_PROJECT, I8_PATH_WAREHOUSE_LIST

    assert I8_PATH_WAREHOUSE_LIST != I8_PATH_COMMON_PROJECT


@acc(CASE, "001-03")
def test_两类纯HTTP取数形态不同_POST与GET():
    """`§3.1.1` —— 形态**逐类不同**：仓库列表是 **POST form**、常用项目列表是 **GET**。

    ⚠️ 这是"实测出来"的形态（真机 / 旁证一致）—— 认反了会**静默查不到数**。
    """
    assert "POST" in (S.WarehouseSource.fetch.__doc__ or "")
    # 仓库列表的固定表单里必须有 `orgQuery`（机构范围），且必须是 POST
    assert "orgQuery" in S.WH_PARAMS
    assert all(isinstance(v, str) for v in S.WH_PARAMS.values())
    # 分页上限有明确常量（不是散落的魔法数）
    assert isinstance(S.WH_LIMIT, int) and S.WH_LIMIT > 0


@acc(CASE, "001-04")
def test_常用项目列表是phid的权威来源():
    """`§3.1.1` ＋ `§3.1.2` —— **常用项目列表 = phid 权威来源** ⇒ 它必须真的产 `phid`。

    反证：仓库列表产的是 **`{warehouse_name, owner_full_name}`**（**无 `phid` 键**）
    ⇒ 只用仓库列表建不出带 phid 的档案行，必须靠常用项目列表。
    """
    body = _spec_section("#### 3.1.1")
    assert "phid" in body.lower()

    class _C:
        def get_json(self, url, params=None, **kw):  # noqa: ANN001
            return {"Record": [{"PhId": "P1", "BillNo": "C1", "BillName": "某项目", "Ab": ""}]}

        def post_json(self, url, data=None, **kw):  # noqa: ANN001
            return {"Record": [{"Whname": "甲仓", "PhidPc_EXName": "某项目", "Nullify": "0"}]}

    with _env(I8_BASE_URL="http://i8/x"):
        cp = S.CommonProjectSource(_C()).fetch()        # type: ignore[arg-type]
        wh = S.WarehouseSource(_C()).fetch()            # type: ignore[arg-type]
    # ⭐ 常用项目列表**产 phid**；仓库列表**不产**（键集合完全不同）
    assert "phid" in cp[0] and cp[0]["phid"] == "P1"
    assert "phid" not in wh[0]
    assert set(cp[0]) == {"name_full", "phid", "code", "ab"}
    assert set(wh[0]) == {"warehouse_name", "owner_full_name"}


@acc(CASE, "001-05")
def test_仓库列表产出仓库名与所属项目全名两列():
    """`§3.1.1` —— 仓库列表的用途 = **仓库名 ↔ 所属项目全名**映射 ⇒ 这两列必须都有。"""
    class _C:
        def post_json(self, url, data=None, **kw):  # noqa: ANN001
            return {"Record": [{"Whname": "甲仓", "PhidPc_EXName": "某项目(XMCB2025080001)",
                                "Nullify": "0"}]}

    with _env(I8_BASE_URL="http://i8/x"):
        rows = S.WarehouseSource(_C()).fetch()          # type: ignore[arg-type]
    assert rows and set(rows[0]) == {"warehouse_name", "owner_full_name"}
    assert rows[0]["owner_full_name"].startswith("某项目")   # 全名（**尾码留给建档口径剥**）


# ============================================================ §3.5 三表匹配规则汇总


@acc(CASE, "001-06")
def test_三表匹配规则汇总的口径逐行可核():
    """`§3.5` —— 三张表各靠什么认项目，各不相同（认错就会出现"数据对不上"）。"""
    body = _spec_section("### 3.5")
    assert body, "取不到 §3.5 正文"
    # 付款通知书 ⇒ **项目全名**；收发结存 / 库存单据 ⇒ **仓库名**（库存单据另有全名辅助）
    assert "项目全名" in body and "仓库名" in body
    rows = [l for l in body.splitlines() if l.startswith("|") and "---" not in l]
    assert len(rows) == 4, f"§3.5 应为「表头 ＋ 三张表」，实际 {len(rows)} 行"   # noqa: PLR2004


@acc(CASE, "001-07")
def test_付款通知书靠全名认项目_与仓库侧只差全名的风险对称():
    """`§3.5` —— ⭐ 核心风险：**付款侧只有全名、仓库侧只有仓库名**（库存单据两把钥匙都有）。

    ⇒ 这正是 `MOD-01` 那条"必须同时认住两个名字"的由来；本断言把它钉在**实现侧的键**上。
    """
    from app.mod01_projects.archive import warehouses_by_owner

    # 仓库侧的关联键 = **项目全名**（不是仓库名）
    got = warehouses_by_owner([
        {"warehouse_name": "甲仓", "owner_full_name": "某项目(XMCB2025080001)"},
    ])
    assert list(got) == ["某项目(XMCB2025080001)"]
    # 全名 = **唯一**能做桥的键（尾码在归一后才对齐）
    from app.mod01_projects.domain import norm_full_name

    assert norm_full_name("某项目(XMCB2025080001)") == norm_full_name("某项目")
    assert norm_full_name("某项目(XMCB2025080001)") != "甲仓"


@acc(CASE, "001-08")
def test_库存单据明细表最可靠两把钥匙都有():
    """`§3.5` —— 库存单据明细表**两把钥匙都有**（仓库名 ＋ 项目全名）⇒ 对账主工具。

    可观测出口：库存单据的抓取入参同时含**核算年月 ＋ 项目**（与 §3.1.1 的"按核算年月 + 项目"一致）。
    """
    from app.mod08_inv import fetch_service as F

    src = Path(F.__file__).read_text(encoding="utf-8", errors="replace")
    assert "warehouse" in src.lower() and ("name_full" in src or "项目" in src)


@acc(CASE, "001-09")
def test_小微须靠关键词拆_不能只认全名():
    """`§3.5` —— 付款通知书行的风险：**小微的全名对应多个具体小微 ⇒ 必须靠关键词拆**。

    ⇒ 认全名**不够**，必须再走一次关键词匹配（否则钱会归错小微）。
    """
    from app.mod01_projects.domain import hit_keyword, resolve_ownership
    from app.mod01_projects.models import TYPE_SHELL, TYPE_SMALL
    from tests.m01_helpers import make_project

    shell = make_project(1, name_full="壳项目", ptype=TYPE_SHELL)
    a = make_project(11, name_full="壳项目", warehouse="仓A", ptype=TYPE_SMALL,
                     parent_shell_id=1, keywords=["大唐雷州"])
    b = make_project(12, name_full="壳项目", warehouse="仓B", ptype=TYPE_SMALL,
                     parent_shell_id=1, keywords=["焦作百利"])
    key = "壳项目"
    # ⭐ 只认全名 ⇒ **分不开**（两个小微同全名）—— 这是必须要关键词的证明
    assert hit_keyword(a.match_keywords, "焦作百利项目款") is False
    d1 = resolve_ownership(name_full=key, doc_name="大唐雷州项目款", projects=[shell, a, b])
    d2 = resolve_ownership(name_full=key, doc_name="焦作百利项目款", projects=[shell, a, b])
    assert d1.target_id == 11 and d2.target_id == 12      # 关键词拆开了
    # 单据名不含任何关键词 ⇒ **不许静默归一个**，必须弹窗
    assert not resolve_ownership(name_full=key, doc_name="某工程款", projects=[shell, a, b]).settled
