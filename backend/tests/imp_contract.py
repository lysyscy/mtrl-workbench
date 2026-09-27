"""**通用导入面**的契约断言 —— 供 4 个域的 API 测试共用（`test_imp_m04/m05/m06/m11_api`）。

⭐ 为什么要有本件（2026-09-26 · 用户报障）：③ 预览回执里的 `skipped`（**逐行**"哪几行不会落库"）
是**通用面 ↔ 四个域**之间的契约 —— 通用面按 `row` 把「不写入」标在**那一行**上、把 `why` 挂成
悬停原因。用户原话：「**这些不会落库的行，要在行上直接标**，比如给一个浅色底，或者其他明确提示，
这才叫好的前端设计，而不是还要**抬头去看文字说明**」。

⚠️ 为什么单独一件而不是在 3 个域测试里各写 4 行：那是**同一件事三个主人** ⇒ 口径一改必然漂
（总有一份忘了改，而"某个域悄悄不自报"在界面上**看不出来**：只是那一页**不再标行**而已）。
⇒ 契约只此一份；**"本域该有几行不落库"由各域自己的测试给**（那是域知识，不属于契约）。
"""

from __future__ import annotations


def assert_skipped_contract(pre: dict, *, expect_bad: int, expect_skip: int = 0) -> None:
    """**③ 预览回执必须自报"哪几行不会落库"**（四条，缺一条通用面就标不出行 / 标错类）。

    ① `skipped` 是 `list`（⛔ **不是** `total - writable` 那种差值 —— 差值标不出"哪几行"）；
    ② 每项 = `{"row": Excel 行号(>0), "why": 人话原因}` —— 通用面**按行号**标行、`why` 挂悬停；
    ③ `kind` ∈ `{"bad", "skip"}`（**缺省 = `"bad"`**）：`bad` = **要你处理**（文件不合规）；
       `skip` = **本来就跳过**（合计/小计 · 说明 · 空行 ⇒ 不是数据行，用户不用改）；
       ⇒ 壳据此给**两种标记**（守则 §2.8：两类混成一种颜色/一个词，用户会以为"合计行也要我改"）；
    ④ 两类**条数分别**对得上（`expect_bad` / `expect_skip`，由调用方按**本域自己的** `kpis` 给）。

    ⚠️ 通用面**不猜**：域不给 `skipped` 就只是一行都不标（⛔ 绝不拿差值反推"大概是最后几行"，
       那是"看起来对"的猜法，守则 §4.2 状态必须真实）。
    """
    sk = pre.get("skipped")
    assert isinstance(sk, list), (
        f"③ 预览没自报**逐行**名单（`skipped`）—— 通用面手里只有一个总数，标不到行上：{sk!r}")
    kinds = [str(x.get("kind") or "bad") for x in sk]
    assert set(kinds) <= {"bad", "skip"}, (
        f"`skipped` 的 `kind` 只许 `bad`（要你处理）/ `skip`（本来就跳过）：{sk!r}")
    assert kinds.count("bad") == expect_bad, (
        f"「要你处理」的条数（{kinds.count('bad')}）与**本域口径**（{expect_bad}）对不上 —— "
        f"两处对不上就是「两个主人」：{sk!r}")
    assert kinds.count("skip") == expect_skip, (
        f"「本来就跳过」的条数（{kinds.count('skip')}）与**本域口径**（{expect_skip}）对不上：{sk!r}")
    for x in sk:
        assert isinstance(x.get("row"), int) and x["row"] > 0, (
            f"`skipped` 的每一项都要带 **Excel 行号**（通用面按它对行作标记）：{x!r}")
        assert str(x.get("why") or "").strip(), (
            f"`skipped` 的每一项都要带**人话原因**（它会被挂成那一行的悬停说明）：{x!r}")
