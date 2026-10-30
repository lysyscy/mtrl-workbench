# 编码规范

这些约束适用于本项目开发；当前结构与机制见[架构](docs/architecture.md)，业务金额定义见[需求](docs/requirements.md)，React 界面与交互约束见[前端设计](docs/guides/frontend-design.md)。

## 分层与装配

core 保存金额、时间、配置、身份和共用机制，不 import 业务包；需要业务数据时由 core_bindings 注入 loader，取数实现归数据主人。mod 包间调用 service，不跨包直查 repository/表；既有允许边界以 test_layering 与实现头说明为准。page 的按钮/表单 HTML 不进入 API 导出，PAGE_ONLY_KEYS 负责剔除。

操作人使用 core/identity.py 的 current_operator。金额规范回 [需求](docs/requirements.md)，唯一计算出口 core/money.py，数据库使用 numeric(18,2)，不引入整数分列或 float。月份展示可用 substr，月份过滤用日期闭区间以利用索引。新增 ORM 模型同步 models_registry；模型漏声明默认值/约束先修模型，不用迁移误删真实结构。

写入、幂等、恢复、操作历史和 React 数据流等专题机制由[架构](docs/architecture.md)持有；模板、i8 与其他动作入口见 [AGENTS](AGENTS.md)。
