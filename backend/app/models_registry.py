"""模型注册表 —— 让 Alembic 的 `autogenerate` 能看到**全部**模型。

⚠️ 依据 工程坑 1.2-5：schema 变更的**唯一入口 = 迁移**。
⚠️ **新增模型后必须在此登记** —— 否则 autogenerate 看不到它，会把"库里有、元数据里没有"
   的表判成需要删除，生成破坏性迁移。

本文件随阶段推进逐行增长（M2 起）。
"""

# --- 随阶段登记（未启用时保持注释）---
from app.mod01_projects import models as _m01  # noqa: F401  ← M2 切片 2 启用
from app.mod02_i8 import models as _m02  # noqa: F401  ← 运行记录 RunRecord 2026-09-15 移入
from app.mod03_notice import models as _m03  # noqa: F401  ← M1 切片 1 启用
from app.mod04_plan import models as _m04  # noqa: F401  ← M3 切片 3 启用
from app.mod05_flow import models as _m05  # noqa: F401  ← M3 切片 3 启用
from app.mod06_proc import models as _m06  # noqa: F401  ← M4 报表域 2026-09-16 启用
from app.mod06_proc import workbench_models as _mechanical_workbench  # noqa: F401
from app.mod07_setl import models as _m07  # noqa: F401  ← M4 报表域 2026-09-16 启用
from app.mod08_inv import models as _m08  # noqa: F401  ← M4 报表域 2026-09-16 启用
from app.mod09_fee import models as _m09  # noqa: F401  ← M4 报表域 2026-09-17 启用
from app.mod11_jc import models as _m11  # noqa: F401  ← M5 切片 5 启用（2026-09-19：集采台账三张表）
# ⛔ `MOD-12` 差异登**已取消**（2026-09-20 用户裁定）⇒ 此处原有一行 `mod12_diff` 导入**已删除**。
#    依据：《说明书》§5.8.3「差异归属恒为「**库存单据**」（**不独立成模块**）」
#    ⇒ 差异的**载体 = 调整单**（`m08`）、**产出 = 差异表**（`m06` 按调整单算）⇒ ⛔ 无独立模块。
#    ⭐ 本行是**撤项记录**（由 `doc_audit` 的 `T8` 守卫兜着 —— 见 `audit_common.CANCELLED`）。
from app.mod14_config import models as _m14  # noqa: F401  ← M6 系统设置 2026-09-16 启用
from app.mod15_user import models as _m15  # noqa: F401  ← 2026-09-26 启用（`TAIL-102` 修复：原先这行是注释 ⇒
#   `user_account` 在元数据里根本不存在 ⇒ `alembic check` 判成「**要删掉这张表**」（⛔ 谁跑一次 autogenerate
#   就会生成一条删表的迁移 —— 那正是本条尾巴警告的雷）。⚠️ 登录/账号体系**早就在跑**（`main.py` 挂了
#   `mod15_api_router`、`core/identity.py` 靠它取「当前登录用户」）⇒ 这行只是**漏登记**，不是"未启用"。

__all__: list[str] = []
