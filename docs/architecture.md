# 当前架构与工程不变量

FastAPI 承载业务，PostgreSQL 保存事实，NSSM 托管现行单 worker 服务。正式前端源码归`apps/frontend`，`FRONTEND_APP_DIR`将同源`/app`指向完整React发布目录；空值仅保API及可选隔离预览，`/app`返回404。`FRONTEND_PREVIEW_DIR`只启用隔离`/preview`。旧壳及其静态入口源码已按用户2026-10-28决定退出，界面回退使用上一套完整React资源并保当前数据库。构建与操作见[部署指南](guides/deployment.md)和[预览指南](guides/frontend-preview.md)，现场版本回[状态](status.md)。抓取走HTTP，PDF/打印渲染在服务身份下运行。

React 已获准采用构建步骤；原无构建/不另用 React 的旧阶段限制已被本次授权取代。业务判定、金额与写入仍归后端，正式切换和旧版退役分别守原授权。

## 分层与装配

工程分层、金额和模型约束见[编码规范](../CODING_STANDARDS.md)。

## 写入、幂等与恢复

改事务、并发、缓存失效、单格保存或恢复时，读[写入、幂等与恢复](architecture/writes-and-history.md)。其中同时包含与保存相关的 React 数据流和过程资料兼容路径。

## 安全操作历史

改撤销、重做、关联保护或历史记录时，读[安全操作历史](architecture/writes-and-history.md#安全操作历史)。

## 运行与资源

改配置、渲染、导入、导出资源或库存投影时，读[运行与资源](architecture/runtime-and-resources.md)。部署与运行操作继续按对应指南。

## React 表格与更新边界

改账号工作区、页面保活、表格布局、列宽或刷新时，读[React 工作区与表格架构](architecture/frontend.md)；界面设计和交互规则仍由[前端设计](guides/frontend-design.md)持有。
