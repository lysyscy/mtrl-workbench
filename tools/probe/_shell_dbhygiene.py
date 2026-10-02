"""㉒ · 开发库卫生：自检 / 调试脚本的残留不许留

**为什么单独立一件**（`TAIL-215` 批 2）：主自检件 `_shell_smoke.py` 只留**引导 ＋ 遍历注册表 ＋ 汇总**；
本段的**位置与理由**唯一出处 = `tools/probe/_shell_segments.py`（⛔ 别在本件讨论顺序）。

⚠️ 由 `tools/oneoff/_tail215_split.py` 从 `_shell_smoke.main()` **机械搬迁**而来 —— ⛔ **代码一字未改**。
"""

from __future__ import annotations


def _db_hygiene() -> list[str]:
    """⭐ **开发库的卫生检查**（2026-09-26 用户报障后立）：**自检 / 调试脚本不许留残留**。

    ⚠️ 病根：临时脚本按约定造 `__自检仓_<标记>_<随机>__` 项目跑真机验证（**跑完应自清**），
       实测留下两条（`__自检仓_DBG_…` / `__自检仓_BRANCH_…`）⇒ 它们**混进了
       「这批数据进哪个项目」的候选列表**（用户 2026-09-26 报障原话：「底下有两个自检仓」）。
       ⇒ 根子不是"列表该滤掉它们"（那会把脏数据藏到更多屏幕背后），而是**它们本就不该留在库里**；
       本检查每次自检**扫一遍**：有残留 ⇒ 报红（谁留的谁清，⛔ 别靠下次记得）。
    ⚠️ 只扫**开发库**（测试库归 pytest 自己管；本自检跑在开发库上）。
    """
    from sqlalchemy import text as _T

    from app.core.db import session_scope as _ss

    with _ss() as s:
        rows = s.execute(_T("select id, warehouse_name, disp, created_at from project "
                            "where warehouse_name like :p order by id"), {"p": "__自检仓%"}).all()
    return [f"㉒ 开发库里留着**自检残留**：id={r[0]} 仓库名={r[1]!r}（展示名 {r[2]!r} · 建于 {r[3]}）"
            " —— 自检/调试脚本跑完**必须自清**（它会混进「这批数据进哪个项目」的候选里，"
            "用户 2026-09-26 报过这个障）" for r in rows]


def check(page, errors) -> None:
    """㉒ —— ⚠️ **位置由 `_shell_segments.py` 定**（⛔ 别在这里讨论顺序）。"""
    # ---- ㉒ **开发库卫生**（2026-09-26 立）：自检/调试脚本的临时数据**不许留残留**
    #      （残留会混进项目候选列表 —— 用户报障原话「底下有两个自检仓」）。
    leftover = _db_hygiene()
    errors.extend(leftover)
    print(f"㉒ 开发库自检残留：{len(leftover)} 条{'（✅ 干净）' if not leftover else ''}")
    for line in leftover:
        print(f"   ❌ {line}")


