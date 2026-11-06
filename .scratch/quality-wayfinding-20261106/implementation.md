# 质量路线实施与验证

总范围、授权及调度归[路线地图](../tails/issues/TAIL-483-工程质量达标路线.md)，覆盖事实归[基线](baseline.md)，判据归[acceptance](acceptance.md)。本记录按实际批次追加，未完成子票不随一个批次通过而关闭。

## 第一批：可靠的隔离取证与产品身份

主人[隔离取证保护](../tails/issues/TAIL-491-隔离取证保护.md)，起点`6d01f996`。全库具名盘点后发现并实际证明父进程可选继承的错误测试目标，且输入指纹漏了实际workspace/patch/browser_check。此批是后续运行取证的必要前置，不预定任何业务模块重构。

变更：三个入口复用`verified_database_source`，文件与有效Settings的源/测试身份及默认原库同库检查在任何连接/复制/DDL之前完成；同身份凭据环境优先规则保留，正式Settings不变。后端runner在准备schema前拒绝非空PYTEST_ADDOPTS/PYTEST_PLUGINS，给出键名与明确选项入口。预览后续引擎/应用使用已建立隔离环境的实际目标。前端指纹加入workspace/patches，完整预览加入browser_check。

保留：正常专用测试目标、随机schema、返回码、清理、外呼阻断、existing用户副本及六个补丁；没有升级依赖、迁移正式库或改业务。新增两类反例在既有纯工具层，未引入配置框架。旧已安装依赖与锁一致性仍沿既有流程，未声称本批提供全供应链证明。

### 验证

- 修改前主控用系统临时合成env、在create_engine处抛标记异常，证明选中`target_b_test`而非明确`target_a_test`；完全未连接DB。
- 实现代理定向纯工具：`test_backend_verify.py`与新`test_frontend_product_inputs.py`共29项通过。虚构配置、临时Git及资源替身，含首连接前拒绝、pytest继承拒绝、指纹增改删、发布拒dirty；系统临时目录随父脚本退出。没有业务conftest或DB连接。
- 主控实际新runner：明确`--source-env D:/dev/mtrl-workbench/.env`，选择`tests/test_guard_selftest.py`、`test_rollback_db.py`、`test_frontend_preview_runtime.py`、`test_frontend_preview_browser_check.py`，退出0。实际目标`mtrl_workbench_test`、独占schema `backend_verify_60f88e8e4400461fa7a0fb5a6f5d5890`，schema和pytest临时目录清理均true。原报告：`C:/Users/Administrator/AppData/Local/AgentArtifacts/projects/mtrl-workbench/groups/143107-095272-17200/files/reports/backend-verify.json`；源码身份为起点+本批dirty，未把它记成已提交版本。
- 本轮证据组`quality-baseline-20261106`经lease离线prepare-build完成（退出0）；类型检查/生产构建日志及version归该组，尚未启动副本。构建不等于GUI或正式服务验证。

### 独立审查

固定基点`6d01f996`、本任务累计工作区差异+新增材料；原无关dirty不在范围。两个全新上下文分别请求`gpt-6-astra/xhigh`，返回只给任务身份，没有运行模型元数据。

- Standards：0项实质发现，无阻断。核父子目标、默认源同库、脱敏、输入分层及当前规则，旧清单兼容影响明示。
- Spec：0项需修复发现。对照原请求/最新授权与491，未发现遗漏或扩围；盘点与运行通过保持分开，487/492继续前置未完成。

审查未重跑有效检查，未要求无关重构。后续源码若改变，只补受影响检查/发现。

### 兼容、回退及资源

新增输入后，旧manifest不能当作最新输入清单；已运行正式`7156a5aef8d4`继续在用、原回退保留。后续标准restart可能提示先publish重建，不能手工补hash冒充旧构建包含新输入；发布仍需独立授权。本批代码可整体回退，无数据迁移。

未创建附加工作树、未启停正式服务、未写正式业务/调用真实i8/打印。backend验证组已按工具正常结项；质量基线组保留给后续运行取证，当前用途未结束。原主检出无关dirty保留。提交/推送身份见下方追加回执。
