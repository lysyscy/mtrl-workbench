"""`TAIL-36` · 项目三小件的**唯一实现**（防再抄）。

**口径**：《材料科业务全流程说明书》**§2.7.4** —— 项目**归并键 = 仓库名**
（不是项目全名、不是 id）；仓库名缺失（壳）时退化为 `#id`，**不猜**。

**为什么值得单独立断言**：这三件原本在 `mod04_plan/service.py` 与 `mod05_flow/service.py`
**各有一份**（第 2 份是接 `m05` 时「本模块没有 ⇒ 又抄一份」）⇒ 重复件最易分叉：
改一处忘另一处 ⇒ 前端「按仓库名归并 / 点条目筛流水」这类联动**静默失配**（不报错、数字就是不对）。
现在唯一实现 = `app/core/projects.py`；⛔ 后续模块（含材料域 `m06/m07/m08`）一律 import 它。

⚠️ **本文件不测调用点**（那是各模块自己的判据）；它只钉两件：**只有一份实现** ＋ **口径**。
"""

from __future__ import annotations

from tests.acc_plugin import acc

from app.core import projects as C
from app.mod01_projects.models import Project
from app.mod04_plan import service as S4
from app.mod05_flow import service as S5

THREE = ("project_key", "project_label", "project_index")


# --------------------------------------------------------------- 唯一实现（防倒退）


@acc()
def test_三件是同一个函数对象而不是各自包一层():
    """⭐ 最强的防倒退断言：钉**身份**（`is`），不是"两边都能调"。

    ⚠️ 只断「两边都能调」是**假绿** —— 各自包一层
       （`def project_key(p): return core.project_key(p)`）照样能过，而**改动仍会分叉**。
    """
    for n in THREE:
        assert getattr(S4, n) is getattr(C, n), f"mod04_plan 的 {n} 不是 core 的那一份"
        assert getattr(S5, n) is getattr(C, n), f"mod05_flow 的 {n} 不是 core 的那一份"


@acc()
def test_业务模块源码里不得再出现这三件的定义():
    """反向守卫：谁再抄一份 `def project_key` 回业务模块 ⇒ **红**（不靠自觉）。"""
    import inspect

    for mod in (S4, S5):
        src = inspect.getsource(mod)
        for n in THREE:
            assert f"def {n}(" not in src, f"{mod.__name__} 里又出现 `def {n}(` —— 口径要分叉了"


# --------------------------------------------------------------- 归并键口径（§2.7.4）


@acc()
def test_归并键就是仓库名():
    p = Project(id=1, warehouse_name="某仓库", name_full="某项目全名特别长", disp="展示名")
    assert C.project_key(p) == "某仓库"
    assert C.project_key(p) not in (p.name_full, "1")


@acc()
def test_仓库名缺失时退化为id而不猜():
    """壳的 `warehouse_name` 为 NULL ⇒ `#id`；⛔ **不许拿全名 / 展示名顶上**（不猜）。"""
    p = Project(id=7, warehouse_name=None, name_full="甲项目全名", disp="甲")
    assert C.project_key(p) == "#7"


@acc()
def test_展示名不参与归并_改展示名不得改变归并键():
    """展示名可改、会变 ⇒ 拿它当键，键就漂了（前端联动会静默失配）。"""
    a = Project(id=1, warehouse_name="W", disp="旧名")
    b = Project(id=1, warehouse_name="W", disp="新名")
    assert C.project_key(a) == C.project_key(b) == "W"


# --------------------------------------------------------------- 显示名口径（§2.3.1）


@acc()
def test_显示名优先级为展示名到仓库名到全名到id():
    assert C.project_label(Project(id=1, warehouse_name="W", name_full="F", disp="D")) == "D"
    assert C.project_label(Project(id=1, warehouse_name="W", name_full="F", disp="")) == "W"
    assert C.project_label(Project(id=1, warehouse_name=None, name_full="F", disp="")) == "F"
    assert C.project_label(Project(id=9, warehouse_name=None, name_full="", disp="")) == "#9"


@acc()
def test_项目为None时一律空串不抛异常():
    """未归属行（`project_id` 为空 ⇒ 传 None）⇒ 空串；调用方据此判「没归属」。"""
    assert C.project_key(None) == ""
    assert C.project_label(None) == ""


# --------------------------------------------------------------- project_index 形状


class _FakeResult:
    def __init__(self, rows: list) -> None:
        self._rows = rows

    def scalars(self) -> _FakeResult:
        return self

    def all(self) -> list:
        return self._rows


class _FakeSession:
    """只够 `select(Project)` 用（本断言不连库）。"""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    def execute(self, _stmt) -> _FakeResult:
        return _FakeResult(self._rows)


@acc()
def test_项目索引以id为键():
    a = Project(id=3, warehouse_name="A")
    b = Project(id=5, warehouse_name="B")
    idx = C.project_index(_FakeSession([a, b]))
    assert idx == {3: a, 5: b}, f"索引形状变了：{idx}"
