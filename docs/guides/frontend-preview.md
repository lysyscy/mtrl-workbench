# React 隔离前端预览

> 读者：开发和验收前端的人。回答：如何构建、验证、启动和停止隔离预览。操作 TAIL-397 及后续前端票时读取；业务范围回共同规格与原票。

现用系统仍由 `backend/app/web/` 提供。React 组件位于 `apps/frontend/`，源码和测试分别在其 `src/`、`tests/`；单包声明、pnpm 锁和包管理策略同放组件根，产物只写其 `dist/`。构建时不复制现用资源，不要求生产常驻 Node。

## 构建与定向验证

使用组件声明固定的 Node/pnpm 版本。若 corepack 缓存已经准备，复用现有 `COREPACK_HOME`；不重新全局安装。

```powershell
Set-Location apps/frontend
corepack pnpm@12.14.0 install --frozen-lockfile
corepack pnpm@12.14.0 typecheck
corepack pnpm@12.14.0 build
```

每条分别核原始退出码；构建不代替类型检查。`/static/theme.css` 由同源 FastAPI 按账号返回，Vite 的构建期资源提示是保留运行时 URL。Vite 开发代理仅指向回环 8037；生产形态验收使用下面的 FastAPI 入口。

在仓根运行隔离回归。`MTRL_PREVIEW_SOURCE_ENV` 必须指向当次获准读取的配置；只消费其原库/测试库目标，禁止输出配置内容。无配置直接失败，不回退真实库。

```powershell
$env:MTRL_PREVIEW_SOURCE_ENV='<已授权配置文件绝对路径>'
$env:PLAYWRIGHT_BROWSERS_PATH='C:/ProgramData/ms-playwright'
$env:MTRL_EFFORT='frontend-vue-rewrite'
backend/.venv/Scripts/python.exe -X utf8 -m pytest apps/frontend/tests/test_preview.py -q --tb=short
```

测试创建独占 schema、运行现有 Alembic 迁移，以真实后端验证 Cookie/身份/读取及拒绝；只有加载/403/500 与迟到错误的浏览器分支使用定向替身。截图和服务日志由现有 workspace_paths 归档到本机 `.artifacts/archive/`，最长保留30天。模拟回包不能证明真实权限，另有普通用户真实管理动作被拒且账号数不变的检查。

## 启动与退出

构建完成后从仓根启动；端口先绑定，冲突会在任何数据库写入之前失败。

```powershell
backend/.venv/Scripts/python.exe -X utf8 tools/dev/frontend_preview.py --source-env '<已授权配置文件绝对路径>' --port 8037
```

实际入口：`http://127.0.0.1:8037/preview/projects`。测试账号 `preview-admin`、`preview-user` 均为空密码，仅存在本次构造数据中；后者预设深色与“大一点”。未登录沿现行语义只读，登录表单、身份和项目均复用现行后端实现。预览 Cookie 名为 `mw_preview_397`，签名密钥每次运行生成，不覆盖现用 Cookie 或写回 `.env`。

启动器先用 TestDatabaseGuard 核对专用测试库与原库不同，再创建随机 `frontend_rewrite_397_` schema。所有子进程连接限定其 search_path，禁止 public 回退；不存在的表会报错。迁移和测试数据仅落该 schema，不使用建表 API 修改共享表；不携带 i8、打印等现场凭据。

正常退出用当前终端 Ctrl+C。停止服务后启动器检查自有 schema 所有者并删除该 schema，打印 `ISOLATION cleaned`；测试夹具在服务子进程退出后同样清理。硬杀进程/机器掉电不会保证 finally 执行；如未见清理回执，保留准确 schema 名并核归属，禁止按前缀批量删除。不要把会话隔离或 pytest 保存点当成另一后端进程的写入保护。

## 公共接合与接续

- 后端仅新增可选配置 `FRONTEND_PREVIEW_DIR`：未配置时无 `/preview` 入口；配置完整 dist 后由 FastAPI 提供索引与版本化 assets。索引每次重验证，缺失 asset 返回404。`/app` 和现行 JSON/表单接口保持原主人。
- 请求出口为 `apps/frontend/src/api.ts`：同源 Cookie、AbortSignal、运行时响应校验、401/403与业务失败；查询不自动重试。数据与页面状态位于账号 key 对应的组件树和独立 QueryClient 中。初次身份读取失败只提供重试；已知身份的暂时核验失败保留该组件树和筛选，隐藏数据并用inert暂停操作，取消/暂停查询；重试确认同账号后恢复原上下文并重新读取。只有确认换号或会话失效才清缓存并重建账号树，不能把网络失败当退出。当前未建设草稿编辑与历史摘要功能。
- 主题继续从 `/static/theme.css` 和官方本地 MiSans 获取，界面倍率取身份响应 `ui_scale_css`；不要复制主题色值或改 Excel/打印样式。
- 本票只读项目列表。398 在该账号边界内接历史台账，不复建请求或身份存储；新增草稿/操作历史状态必须留在账号子树，不放模块全局或未区分账号的持久缓存；沿用blocked暂停边界，身份不确定期间不能发起保存，确认同账号后保留草稿，确认换号/失效再清旧状态。398必须将“编辑中焦点核验网络失败/500，恢复同账号不丢草稿”加入异常验收；本票只验证筛选上下文，没有提前实现草稿功能。网格适配留398/399。
- 旧版并行变更由父任务对共同调查点及每批交付 SHA 的后续差异按迁移面核对；不能把一次基线 clean 或某批通过当作未来无差异证明。
