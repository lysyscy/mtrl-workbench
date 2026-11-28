"""模型注册表 —— 让 Alembic 的 `autogenerate` 能看到**全部**模型。

⚠️ 依据 工程坑 1.2-5：schema 变更的**唯一入口 = 迁移**。
⚠️ **新增模型后必须在此登记** —— 否则 autogenerate 看不到它，会把"库里有、元数据里没有"
   的表判成需要删除，生成破坏性迁移。

本文件随阶段推进逐行增长（M2 起）。
"""

# --- 随阶段登记（未启用时保持注释）---
from app.core.history import OperationHistory as _operation_history
from app.mod01_projects import models as _m01
from app.mod02_i8 import models as _m02
from app.mod03_notice import models as _m03
from app.mod04_plan import models as _m04
from app.mod05_flow import models as _m05
from app.mod06_proc import models as _m06
from app.mod06_proc import workbench_models as _mechanical_workbench
from app.mod07_setl import models as _m07
from app.mod08_inv import models as _m08
from app.mod09_fee import models as _m09
from app.mod11_jc import models as _m11
from app.mod13_oilcard import models as _oilcard
# ⛔ `MOD-12` 差异登**已取消**（2026-09-20 用户裁定）⇒ 此处原有一行 `mod12_diff` 导入**已删除**。
#    依据：《说明书》§5.8.3「差异归属恒为「**库存单据**」（**不独立成模块**）」
#    ⇒ 差异的**载体 = 调整单**（`m08`）、**产出 = 差异表**（`m06` 按调整单算）⇒ ⛔ 无独立模块。
#    ⭐ 本行是**撤项记录**（相关退役行为由现行业务测试保护）。
from app.mod14_config import models as _m14
from app.mod15_user import models as _m15
#   `user_account` 在元数据里根本不存在 ⇒ `alembic check` 判成「**要删掉这张表**」（⛔ 谁跑一次 autogenerate
#   就会生成一条删表的迁移 —— 那正是本条尾巴警告的雷）。⚠️ 登录/账号体系**早就在跑**（`main.py` 挂了
#   `mod15_api_router`、`core/identity.py` 靠它取「当前登录用户」）⇒ 这行只是**漏登记**，不是"未启用"。

from app.mod16_equipment import models as _equipment

del (_operation_history, _m01, _m02, _m03, _m04, _m05, _m06, _mechanical_workbench,
     _m07, _m08, _m09, _m11, _oilcard, _m14, _m15, _equipment)

__all__: list[str] = []
