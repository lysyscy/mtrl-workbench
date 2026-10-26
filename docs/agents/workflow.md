# 项目执行绑定

本页只保存本项目的路径、授权、隔离与生命周期。个人方法来自 lysyscy/My-Skills，按宿主真实入口或 Skills Manager 登记定位实际安装资源；维护源发布不代表本机已经安装，读取不授权更新个人包。

## 按动作读取个人方法

普通实施与唯一收尾读 implement-solo-spec 的 `references/execution.md`；验证存在资金、权限、写入/恢复等风险时读其 `verification.md`。明确采用跨批统筹时读 `coordination.md`，确有独立收益并获准委派时先读 `delegation.md`。文档维护、选目录、专项迁移分别读 setup-solo-workflow 的 document-maintenance、document-layout、document-migration；写 Agent 消费资料时读实际安装的 writing-for-agents。在途任务按原规格固定业务、验收和授权基线；已批准治理切片的安装来源及采用点归原规格。

重要界面内容取舍、主预览与临时预览的协作方法，按实际安装的同源 implement-solo-spec / `references/human-collaboration.md` 读取。主预览在已有规划的验收点开放；当前入口、实际版本及需用户判断事项留在原任务记录，资源按本项目隔离、归属及生命周期退出。

## 输入与记录

现行业务回 [requirements](../requirements.md)，工程结构回 [architecture](../architecture.md)，命令与隔离回 [开发指南](../guides/development-and-verification.md)。普通明确改动用用户需求、实际验证及回执即可，不强制规格、票或每日记录。需要跨会话才复用一张票/必要任务说明；有真实依赖的 effort 保共同规格、必要票、累计基点和已确认授权。单票持有进度，status 仅导航活动 effort。

React 和 Mini App 的既有规格、身份、依赖、验收、Comments 与授权继续有效。开发、隔离验证、人工验收、正式切换和旧版退役分别判定；主线状态不能覆盖独立工作树进度。React 的文档吸收在安全批次边界由整合者安排，遇修改/删除冲突将新增知识迁到当前主人，保护双方有效内容。

## 提交与权限

用户2026-10-12明确授权 Agent 自主决定本仓提交与推送；任务的更窄限制优先。保存前核实际远端和范围，明确列举文件暂存，运行真实提交钩子；推送后核远端 SHA。保护已有无关修改，恢复只处理本任务拥有路径。源码提交、服务加载和现场验收分别报告。

仓根 `.env`、会话、Cookie、Token、真实 Excel、备份和业务原件不提交。`ops/init_db.sql` 按用户既有裁定保留，不能由它推导新增凭据公开授权。生产重启、迁移、真实库/外部写入按当次明确授权；开发测试使用已核专用目标。网页探查优先内置浏览器，接口复用 [i8 契约](../reference/i8-contract.md)。

## 目录与退出

本项目沿用 `backend/app`、`backend/tests`、`backend/alembic`、`backend/app/resources` 的 Python 组件契约，React 组件沿 `apps/frontend/{src,tests}` 及组件根依赖/锁/构建契约；第三方 `delivery`、字体及模板按运行消费者保留。`.scratch/<effort>` 只放活动 Markdown/票；工具输出按 `tools/audit/workspace_paths.py` 生成到 `.artifacts/active/<effort>/<run>/<kind>`，结束释放 work，必要证据有限保留到 `.artifacts/archive`。父运行负责自己创建的 run；手动指定 MTRL_EFFORT/MTRL_RUN_ID 后由操作者核实际消费者和退出去向。接入、专项迁移、复杂运行产物、共享资源退出或分类/保留有具体风险时，从实际 setup 安装运行 workspace_check 的相关范围；已触发检查非零须解决或保留阻塞。无相关产物/变化的简单任务不造 effort/run 或重复治理检查；仍供用户验收的主预览按原任务用途保留，不因回复结束停服。

历史正文沿同源 document-layout 的 Git-only 默认；本项目仍保活动依赖、验收和范围裁决所需最小集合，终态不推定缺票已完成。恢复用可达提交及原路径，核后续修改后只取所需内容。

`.env`、`var`、`.codex-attachments`、原始输入、成品、在用构建、非 Git/忽略资料及他人未提交内容由各自用途决定生命周期。本次处理直接相关且已无用途的产物，包含前序会话遗留；他人修改与在用原件保持受保护，专项清理逐文件核 Git 可恢复性。

## 够用即止

用户2026-10-22确认本项目为个人 Agent 开发、少量账号（大概率两个用户名），按实际发生可能性、业务后果与维护执行成本选保障。

- 默认复用已有验证；新增测试须能指出实际业务风险与现有覆盖缺口，无缺口就不加。
- 金额、正常保存/必要撤销、实际权限、归属、隔离、明显误操作与导出内容不丢不乱保留有效保障，选择最便宜的有效层；稳定后端覆盖的金额组合不在 UI 穷举，浏览器保必要连通与交互代表路径。
- 实现细节、源码形状、纯文案/布局及低概率理论边界不默认成为永久回归或交付阻塞；已修 bug 也按当前风险取舍，混合测试只裁多余断言并清无消费者专用夹具。
- 输入、环境、代码和预期仍覆盖且证据足够就复用；只验受影响范围。必要收尾完成即止，不以全仓复跑、重复计时、多轮审查、四态或全量变异作为默认加码。

未执行、失败、空选择、超时和未知都不报通过。JSON 用结构操作，改已有文件保留行尾，新文本 UTF-8 无 BOM（ps1 按既有契约）；共享文件重读后串行改。精确列举暂存文件，保持真实钩子，不用 add -A、--no-verify、reset/clean/stash 覆盖他人工作或改持久 Git 配置。Windows 复杂读取/脚本用 `python -X utf8`、显式编码与原始返回码。
