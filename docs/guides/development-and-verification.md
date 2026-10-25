# 开发与验证

先核当前任务范围与 [workflow](../agents/workflow.md)，业务预期回 [requirements](../requirements.md)。命令从仓根运行；依赖、Python 版本及 pytest 配置以 backend/pyproject.toml/uv.lock 为准，已有 backend/.venv 可用时不为文档改动重装。

## 按影响选检查

```text
backend/.venv/Scripts/python.exe -X utf8 -m pytest <明确文件或节点>
backend/.venv/Scripts/python.exe -X utf8 tools/audit/syntax_audit.py --staged
backend/.venv/Scripts/python.exe -X utf8 tools/audit/bytes_guard.py --staged
backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_list_tails.py
```

pytest 在 backend 组件运行；选文件/节点前先看 fixture。保留真实原始退出码、失败节点和未验边界，不从票终态推当前环境通过。普通局部改动复用现有定向检查，不自动全量回归/变异。文档验证看业务语义、当前引用、imports/动态读取/配置及接手路径，不再生成旧验收 JSON 或四态报告。`@acc` 在存量业务测试中仍可作历史标识，不是新开发前置。

## 隔离和写入

backend/tests/conftest.py 的守卫先保留原目标、验证专用 TEST_DATABASE_URL，再装配业务，核 Settings 与缓存 engine；缺失、同库别名或无法确认时拒绝。不能回退 SQLite 或借业务库。rollback_db 接管已核测试库的会话工厂，commit 仅释放 savepoint，结束回滚外层事务；自建 engine、原生连接和另一个进程不受它保护。真实写入必须另外核目标、身份、可废弃范围和清理所有权。

db_guard、test_guard_selftest、test_rollback_db 与有效付款/撤销/权限/模板回归保持。环境失败如实报告，不跳保护换绿灯。UI 模拟接口只证明交互；离线源码检查不能证明 DOM 已显示、真实数据库已写或文件实际可打开。先用可替代边界验证，再按现有授权判断是否需要现场。

## 界面和外部链路

网页探查优先内置浏览器，专用回归保留已有 Python Playwright 与原入口。需要 CLI 时读实际安装 playwright-cli；使用自己命名的会话，结束关闭。Python Playwright 浏览器路径只传子进程，服务身份与浏览器环境回 [部署](deployment.md)。i8 登录/抓取、真实打印、生产导入/付款均按当次明确授权，不能用浏览器或测试的存在推导权限。

界面改动与迁移按同来源 implement-solo-spec / `references/verification.md` 的界面分支核旧行为与实际结果，以“页面入口 + 用户动作 + 结果”复用当前规格或票。旧界面的操作、必要截图与源码/接口互补，无法运行时留具体未验项；本项目已有大型迁移验收保持。打印输出按已授权预览、PDF 或现场边界核对象集合和业务口径，不因规则验收操作真实打印机。

旧壳源码读取走 tools/audit/shell_source.py / shell_api.py 与 backend/tests/shell_src.py，前端机制见 [旧前端参考](../reference/legacy-frontend.md)，交互/文案归 [frontend-design](frontend-design.md)。壳快照只在对应现场调查需要时用，不强制差异清零。

## 工具与产物

工具用途及边界读 tools/README.md。syntax_audit、bytes_guard 和凭据文件名保护在真实 pre-commit 执行，不能跳钩子。票工具用临时 tracker/票目录验证高水位、依赖和失败回滚，干跑不得写入。audit_work 只提示运行产物生命周期；wiring_audit 的 W2 只是候选线索，不能当成业务缺陷或删除授权。

运行产物由 workspace_paths 分到本轮 .artifacts/active/<effort>/<run>/<kind>，父进程收尾；临时脚本放 work/系统临时目录，证据必要才有限保留。异常日志完整保留原始返回码后再读末尾。Windows 用 python -X utf8、显式文件编码与 subprocess encoding；PS1 保 UTF-8 BOM，其余保原行尾。禁止用跨壳字符串拼接处理删除/移动；按绝对路径、对象范围和原件恢复依据操作。
