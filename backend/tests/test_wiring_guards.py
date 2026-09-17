"""工程守卫自检：**「防回归」断言必须真的被调用**。

⚠️ 为什么有这个文件（2026-09-17，`tools/wiring_audit.py` 抓出来的）：
    `assert_single_external_source()`（`mod02_i8/fetch_task.py`）docstring 自称
    「**防回归**：外部数据源只能是 i8」，但**生产与测试都没人调用它** ⇒ **守卫失效**
    （防了个寂寞：真有人接第二个数据源，它也不会响）。

⭐ 这是「**写好的口径没人接**」的又一种形态 —— 与 `ensure_batch_settled` 同类，
   区别只在：那个是**业务判定**没接进链路，这个是**守卫**没人调用。

⚠️ 本文件是**工程自检**（`@acc()` 显式不绑定）—— 它绿 ≠ 判据点绿；
   它守的是「守卫本身还有人调」这件事。
"""

from app.mod02_i8.fetch_task import EXTERNAL_SOURCES, assert_single_external_source
from tests.acc_plugin import acc


@acc()
def test_外部数据源只能是i8这个守卫真的被调用():
    """`assert_single_external_source` 必须**真的被调用**，否则它是无效守卫。

    ⚠️ 变异验证：把本测试里的 `assert_single_external_source()` 去掉 ⇒
       `tools/wiring_audit.py` 的 `W1` 必须重新报红。
    """
    assert EXTERNAL_SOURCES == ("i8",), (
        "外部数据源被改动了 —— i8 是唯一外部数据源（《说明书》§6.1.2 / NG-13 / DEV-J-05）"
    )
    assert_single_external_source()          # 不抛异常 = 守卫在位
