# 当前架构与工程不变量

FastAPI 承载业务，PostgreSQL 保存事实，NSSM 托管现行单 worker 服务。旧前端在 backend/app/web；React 在独立工作树开发，不把主线源码当作已切换。抓取走 HTTP，PDF/打印渲染在服务身份下运行。

## 分层与装配

core 保存金额、时间、配置、身份和共用机制，不 import 业务包；需要业务数据时由 core_bindings 注入 loader，取数实现归数据主人。mod 包间调用 service，不跨包直查 repository/表；既有允许边界以 test_layering 与实现头说明为准。page 的按钮/表单 HTML 不进入 API 导出，PAGE_ONLY_KEYS 负责剔除。

操作人使用 core/identity.py 的 current_operator。金额规范回 [需求](requirements.md)，唯一计算出口 core/money.py，数据库使用 numeric(18,2)，不引入整数分列或 float。月份展示可用 substr，月份过滤用日期闭区间以利用索引。新增 ORM 模型同步 models_registry；模型漏声明默认值/约束先修模型，不用迁移误删真实结构。

## 写入、幂等与恢复

付款的读余额、防超付、写流水及重算在同一事务以 SELECT FOR UPDATE 串行化；低频编辑按版本拒绝冲突。重复 request_id 不重复付款。占位档案取号在事务内，唯一约束与受控重试兜底。导入替换限同源自动行，保手动行及人工覆盖；业务批次/撤销模型与数据保留，即使旧导入入口退出。

长任务先取得必要数据、释放写事务，再渲染/投递；外部请求不持有长写事务。同表抓取串行，人工触发留执行记录。i8 登录可能强踢其他会话，触发前告知并确认，失败不自动再次登录；内部必要空响应复核按 [i8 契约](reference/i8-contract.md)，不能扩大成外部动作重试器。

跨页写入后统一失效并重新读真实数据，不维护一张人工“写→读页”依赖副本；本项目读取量允许全标脏，避免读侧变化漏同步。保存成功而读回失败须区别于写入失败，保护后续草稿和编辑焦点。账号、项目、月份和记录身份进入读取/草稿范围，迟到响应不能覆盖新上下文。

## 安全操作历史

core/history 在业务 session_scope 内观察变更，history_bindings 装配允许模型/字段，与业务同事务保存 operation_history。历史值留服务端；按在用账号事务锁串行写/撤销，核预期历史头、锁定目标/关联、完整值及 PostgreSQL xmin，整批通过才改。可信恢复凭原事务版本和完整值续接，遇实际行修改/版本断点停止；只在同账号、同方向、最近 barrier 后作用。旧条目缺凭据仍可安全单步，不推断跨动作续接、不批改生产历史。

拟付款方式的账号锁、更新、barrier 和旧 redo 失效同事务；结构/规则变更不能猜测重放。deleted 与业务 voided 含义不同。现有 history_api、测试隔离和 rollback_db 继续保护真实撤销。

## 运行与资源

配置有效值沿 core/app_settings.py 的 effective 链，页面库值与 .env 职责见 [部署](guides/deployment.md)。PDF 使用 headless Chromium，服务账户必须能访问浏览器及字体；render.py 为避挂死保留的回收方式在改变生命周期前要核实际服务环境。打印版式来自 i8，IPP 接收不等于纸面完成。

Excel 机械读取复用 import_kit/workbook/readers，选表/映射/业务归域；模板生成及透视缓存回 [模板](reference/template-export.md)。真实资产由 report_export/resources.py 和文件字节定义，delivery 只作第三方来源，不能反推业务。有效分层、隔离、金额、撤销及模板测试保留；已退出文档机器链不再影响运行配置。
