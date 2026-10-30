# 项目执行绑定

本页只保存个人方法绑定、项目目录与运行例外、共享记忆身份。个人方法来自lysyscy/My-Skills，按宿主真实入口或Skills Manager登记定位实际安装资源；维护源发布不代表本机已经安装，读取不授权更新个人包。

## 按动作读取个人方法

普通实施与唯一收尾读 implement-solo-spec 的 `references/execution.md`；验证存在资金、权限、写入/恢复等风险时读其 `verification.md`。明确采用跨批统筹时读 `coordination.md`，确有独立收益并获准委派时先读 `delegation.md`。文档维护、选目录、专项迁移分别读 setup-solo-workflow 的 document-maintenance、document-layout、document-migration；写 Agent 消费资料时读实际安装的 writing-for-agents。在途任务按原规格固定业务、验收和授权基线；已批准治理切片的安装来源及采用点归原规格。

重要界面内容取舍、主预览与临时预览的协作方法，按实际安装的同源 implement-solo-spec / `references/human-collaboration.md` 读取。主预览在已有规划的验收点开放；当前入口、实际版本及需用户判断事项留在原任务记录，资源按本项目隔离、归属及生命周期退出。

React 重写已签收，现行业务和界面约束归 requirements 与 frontend-design，原任务材料按 Git 追溯。开发、隔离验证、人工验收、正式切换和旧版退役分别判定；主线状态不能覆盖独立工作树进度。跨任务文档在安全批次边界整合，遇修改/删除冲突先将独有有效知识迁到现行主人，保护双方内容。

## 目录与退出

本项目沿用 `backend/app`、`backend/tests`、`backend/alembic`、`backend/app/resources` 的 Python 组件契约，React 组件沿 `apps/frontend/{src,tests}` 及组件根依赖/锁/构建契约；第三方 `delivery`、字体及模板按运行消费者保留。`.scratch/<effort>` 只放活动 Markdown/票；工具输出按 `tools/audit/workspace_paths.py` 生成到 `.artifacts/active/<effort>/<run>/<kind>`，结束释放 work，必要证据有限保留到 `.artifacts/archive`。父运行负责自己创建的 run；手动指定 MTRL_EFFORT/MTRL_RUN_ID 后由操作者核实际消费者和退出去向。接入、专项迁移、复杂运行产物、共享资源退出或分类/保留有具体风险时，从实际 setup 安装运行 workspace_check 的相关范围；已触发检查非零须解决或保留阻塞。无相关产物/变化的简单任务不造 effort/run 或重复治理检查；仍供用户验收的主预览按原任务用途保留，不因回复结束停服。

历史正文沿同源 document-layout 的 Git-only 默认；本项目仍保活动依赖、验收和范围裁决所需最小集合，终态不推定缺票已完成。恢复用可达提交及原路径，核后续修改后只取所需内容。

`.env`、`var`、`.codex-attachments`、原始输入、成品、在用构建、非 Git/忽略资料及他人未提交内容由各自用途决定生命周期。本次处理直接相关且已无用途的产物，包含前序会话遗留；他人修改与在用原件保持受保护，专项清理逐文件核 Git 可恢复性。

## 共享记忆

共同政策来自 lysyscy/My-Skills → setup-solo-workflow → `references/agent-instructions.md`，由宿主自定义指令消费。本项目固定 bank ID 为 `project-3379fef93fbada35`；子目录和同项目其他工作树沿用此身份，分支相关记录保留来源分支、必要版本及合并/部署状态。无有效内容不建空库。

普通业务按已有业务入口和显式技能执行，记忆使用不触发工程实施、票务或额外收尾；开发代码、辅助工具或技能才读取本页实施方法。现行规则、关键理由与活动状态仍由项目文件持有，偏好、决定背景及验证经验按共同政策留存。首次完整接入和专项内容迁移才读取同源 `references/memory-adoption.md`，平常任务不重跑筛选。

本仓历史React重写分支沿用同一记忆库。2026-10-28用户已签收正式React入口并批准旧版退役，原React与切换候选两棵冻结工作树在必要本机资料保全后均已退出；分支提交仍可达。源码退役、现场加载和资源退出分别记录，当前状态回status及TAIL-424；后续任务的预览按实际登记由对应owner持有。
