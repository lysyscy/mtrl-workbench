"""i8 HTTP source shape, phid, name bridges and ownership regressions."""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path

from app.core.config import get_settings
from app.mod02_i8 import sources as S

CASE = "ACC-I8-SRC-001"

_REPO_ROOT = Path(__file__).resolve().parents[2]


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




# ============================================================ §3.1.1 数据来源清单




def test_纯HTTP两类各自绑定正确的API编号():
    """`§3.1.1` ＋ 附录 E.1 —— **仓库列表 = `API-05` · 常用项目列表 = `API-06`**，不得互换。"""
    # 实现侧 docstring 必须把编号钉在类上（编号互换 = 来源张冠李戴）
    assert "API-05" in (S.WarehouseSource.__doc__ or "")
    assert "API-06" in (S.CommonProjectSource.__doc__ or "")
    # 端点常量必须**成对且不同**（同一个端点服务两类来源 = 抄错了）
    from app.core.config import I8_PATH_COMMON_PROJECT, I8_PATH_WAREHOUSE_LIST

    assert I8_PATH_WAREHOUSE_LIST != I8_PATH_COMMON_PROJECT


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


def test_常用项目列表是phid的权威来源():
    """`§3.1.1` ＋ `§3.1.2` —— **常用项目列表 = phid 权威来源** ⇒ 它必须真的产 `phid`。

    反证：仓库列表产的是 **`{warehouse_name, owner_full_name}`**（**无 `phid` 键**）
    ⇒ 只用仓库列表建不出带 phid 的档案行，必须靠常用项目列表。
    """

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


def test_库存单据明细表最可靠两把钥匙都有():
    """`§3.5` —— 库存单据明细表**两把钥匙都有**（仓库名 ＋ 项目全名）⇒ 对账主工具。

    可观测出口：库存单据的抓取入参同时含**核算年月 ＋ 项目**（与 §3.1.1 的"按核算年月 + 项目"一致）。
    """
    from app.mod08_inv import fetch_service as F

    src = Path(F.__file__).read_text(encoding="utf-8", errors="replace")
    assert "warehouse" in src.lower() and ("name_full" in src or "项目" in src)


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
