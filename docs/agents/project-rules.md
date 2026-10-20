# 项目约束与条件入口

> 读者：处理文件、保存、环境或真实写入的Agent。回答：项目约束与已确认边界。何时读：对应操作前按章节读取；本件不声明宿主自动注入。

## 〇、入口与核验

- `[用户·2026-10-08]` 本仓执行与核验绑定 = docs/agents/workflow.md；个人方法条件入口 = AGENTS.md；命令 = docs/guides/development-and-verification.md §十一。新删件、提交和旧dirty不自动全验；基点不是通过证明。相关失败不能报通过，自证用隔离输入。review按当前用户授权和实际需要使用。
- 当前状态回主计划§0和§15，测试证据以实际选集、原始退出码和未验边界为准；历史判据视图不证明当前完整通过。阅读分派只回 AGENTS.md。

## 一、用户偏好

- `[用户·2026-09-24]` 拍板给事实/证据、可选方案、明确推荐、理由与代价，用大白话。
- `[用户·2026-09-30]` 开工用一句人话说明看得见的目标；汇报先说做什么、还差什么，再讲机制。
- `[用户·2026-10-02]` 敢于质疑旧口径，以最终效果为目标；拷问也用大白话。
- `[用户·2026-10-07]` 提示词只在回复给可复制块，不落盘；票留完成判据。
- `[用户·2026-10-08]` 小改保留够验收和接续的记录，不写长日报或复制Git已有过程。

## 二、真源指针

AGENTS.md为会话入口；项目开发正文在docs/guides/，实现约束和核验方法分别回docs/guides/implementation-constraints.md与development-and-verification.md。业务取值回docs/requirements.md及其分册，术语及界面文字按AGENTS触发读取D29；目录职责回README.md §三。

## 三、环境操作入口

碰环境、服务身份或运行资源时，先读docs/guides/operations.md的“本机环境记录”，再核实际配置与当前授权；常载入口不保存动态版本和机器路径。

## 四、文件与工具

- `[助手自定]` JSON用结构操作；改已有文件保留其行尾，新文本UTF-8无BOM，ps1例外带BOM。字节保护由 tools/audit/bytes_guard.py 执行。
- `[助手自定]` 长脚本进本轮.artifacts/active/<effort>/<run>/work，运行证据进对应kind，.scratch仅放任务Markdown；输出完整落盘或取末尾，不能掐断正在写靶的进程。相关配方按需读docs/guides/development-and-verification.md §十七。
- `[助手自定]` 修改共享文件前重新读取；同一文件写入串行；变异用隔离夹具，不临时改正式工作文件。

## 五、协作边界

- `[用户·2026-09-24]` 业务选择未定不改行为，用户最新需求优先；已确认规格不重新访谈。
- `[用户·2026-10-05]` 独立交付按票制度；同批发现的问题在当前票修，不反复开票。开销票使用 _tail_open.py / _tail_close.py。
- `[用户·2026-10-08]` 本轮保留全部已有修改，只计新增影响；不修改/提交凭据。
- `[用户·2026-10-12]` 提交与推送的自主决策口径 = docs/agents/workflow.md「提交与推送」。
- `[助手自定]` 提交列举git add，禁止add -A、--no-verify和改git config；仓根`.env`实值不提交（i8账号），`ops/init_db.sql`已随库提交（2026-10-09用户裁定，理由见该文件与pre-commit注释）。
- `[助手自定]` 删除涉及手工数据先查牵连和备份；文档结构与归档按 docs/guides/document-governance.md 的主人指针办理。

## 六、坐标与禁区

仓：D:/dev/mtrl-workbench；现行产品资料：仓内`docs/requirements/`；旧交付面根仅余未交付的本机`.workbuddy/`。仓外历史经归档索引定位。现行产品资料随仓库版本管理；迁移过程按需查 Git 历史。
新任务证据只在 .scratch/<effort>/evidence.md 或原票Comments保存；旧日志按docs/archive/journal/明确追溯。现行要求回主人，不把过程作为默认必读。

## 八、工程纪律

- `[用户·2026-10-05]` 本机自用不设冻结前置；迁移升级两库、业务取舍和前端规则仍按对应主人。
- `[助手自定]` 架构约束回 docs/architecture.md、模块约束回 docs/architecture/modules.md；界面工程机制按任务读docs/guides/development-and-verification.md §十。
- `[用户·2026-10-12]` 一人开发练手，优先速度和token；不为假设情况扩测试，不强制每条新增测试配独立变异。选集/入口改动做定向自检；金额、权限、写入、回滚与已修复bug覆盖和隔离保护保留。流程回docs/agents/workflow.md。
- `[用户·2026-10-01]` 上屏文字以熟手为读者，具体规则回D29，按需读取本页不复述。
- `[用户·2026-10-09]` **够用即止**：一人开发·局域网2人；建任何检查前先过两问（在本项目会不会真发生？真发生是否真难受？）⇒ 取舍细则与手法回 docs/agents/workflow.md「取舍」。

## 附录 · 方法触发

只有改检查选择或排查假绿时读docs/guides/development-and-verification.md §十八/十九；只有追溯决定或复发事故时读指定历史。硬数字只回docs/reference/thresholds.md，不抄副本。
