"""一次性件（2026-09-25 · 用户裁定「B」）：为那 2 条「归属未走完」的合同，在壳下**新建具体小微**。

**依据（全部查实过的口径，⛔ 不是自创）**：
· 情形 = `resolve_ownership` 的 `needs_keyword`，其 reason 原文：「需用户指定（**选已有小微并补词 / 新建小微**）」
  —— 即**系统本来就规定**这种情况该"新建小微"，而**新建小微的唯一出口** = `mod01_projects.repository.create_project`
  （与付款侧 `ownership-assign` 弹窗「新建小微」走的是**同一个函数**，见 `mod03_notice/router.py:169-176`）。
· 「仓库名**不许人手打**」（§9.4）⇒ 用户裁定 **B = 不查 i8** ⇒ `warehouse_name` 只能留空
  ⇒ 由 `create_project` 自动取**占位名** `未建仓-N`（§2.3.1 允许：全名对应 0 个仓库时先建占位）。
· **关键词**只能从单据名里取（唯一可得信息），且必须真出现在单据名里（`domain.validate_keyword_in_doc` 同理）：
  `佰利` ← 「四分2024小微佰利/河南曼德西/铜母线（98196）」· `内蒙古储能` ← 「四分2024小微内蒙古储能（临建）项目/中德/水泥沙石（154730）」
· 幂等：同关键词的小微已存在 ⇒ 跳过（可反复跑）。

用法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\oneoff\\_tail93_create_two_smalls.py`
"""

from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import select                                        # noqa: E402

from app.core.db import session_scope                                # noqa: E402
from app.mod01_projects import repository as R                       # noqa: E402
from app.mod01_projects.domain import can_create_small               # noqa: E402
from app.mod01_projects.models import (                              # noqa: E402
    STATUS_ACTIVE,
    TYPE_SHELL,
    TYPE_SMALL,
    Project,
)

#: 壳的全名（那 2 条合同的项目名都指向它）
SHELL_FULL = "第四工程公司 2024小微项目(XMCB2024030001)"

#: (关键词, 展示名) —— 展示名只为界面上看得懂（`disp` 是"展示名"字段的正是用途，且可人工改）
WANTED = [
    ("佰利", "焦作百利项目"),
    ("内蒙古储能", "内蒙古储能（临建）项目"),
]


def main() -> int:
    with session_scope() as s:
        shells = list(s.execute(
            select(Project).where(Project.project_type == TYPE_SHELL,
                                  Project.name_full == SHELL_FULL)).scalars())
        assert len(shells) == 1, f"壳不唯一/找不到：命中 {len(shells)} 条"
        shell = shells[0]
        assert shell.status == STATUS_ACTIVE, f"壳不是在建（{shell.status}）⇒ 按 001-05 不能新建小微"
        can_create_small(shell)                                       # 正式校验（已归档壳会在这里报错）
        kids = list(s.execute(select(Project).where(Project.parent_shell_id == shell.id)).scalars())
        print(f"壳 id={shell.id}「{shell.name_full}」现状小微 {len(kids)} 个：")
        for k in kids:
            print(f"   id={k.id:<5} 仓库={k.warehouse_name} 关键词={k.match_keywords}")

        for keyword, disp in WANTED:
            hit = [k for k in kids if keyword in (k.match_keywords or [])]
            if hit:
                print(f"\n关键词「{keyword}」已存在（id={hit[0].id}）⇒ 幂等跳过")
                continue
            p = R.create_project(
                s, project_type=TYPE_SMALL, name_full=shell.name_full,
                parent_shell_id=shell.id, match_keywords=[keyword], disp=disp,
            )
            print(f"\n新建小微 ✓ id={p.id} · 仓库名={p.warehouse_name}（占位 · §9.4 不许人手打）"
                  f" · 关键词={p.match_keywords} · 展示名={p.disp}")

        s.flush()
        kids = list(s.execute(select(Project).where(Project.parent_shell_id == shell.id)).scalars())
        print(f"\n建后：壳下小微 {len(kids)} 个")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
