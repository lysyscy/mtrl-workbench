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
from app.mod07_setl import models as _m07  # noqa: F401  ← M4 报表域 2026-09-16 启用
from app.mod08_inv import models as _m08  # noqa: F401  ← M4 报表域 2026-09-16 启用
from app.mod09_fee import models as _m09  # noqa: F401  ← M4 报表域 2026-09-17 启用
from app.mod11_jc import models as _m11  # noqa: F401  ← M5 切片 5 启用（2026-09-19：集采台账三张表）
# from app.mod12_diff import models as _m12  # noqa: F401
from app.mod14_config import models as _m14  # noqa: F401  ← M6 系统设置 2026-09-16 启用
# from app.mod15_user import models as _m15  # noqa: F401

__all__: list[str] = []
