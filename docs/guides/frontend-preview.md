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

测试创建独占 schema、运行现有 Alembic 迁移，以真实后端验证 Cookie/身份/读取、历史编辑与撤销、拒绝和导出；只有加载/403/500 与迟到错误的浏览器分支使用定向替身。截图和服务日志由现有 workspace_paths 归档到本机 `.artifacts/archive/`，最长保留30天。模拟回包不能证明真实权限，另有普通用户真实管理动作被拒且账号数不变的检查。

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
- 请求出口为 `apps/frontend/src/api.ts`：同源 Cookie、AbortSignal、运行时响应校验、401/403与业务失败；查询不自动重试。数据与页面状态位于账号 key 对应的组件树和独立 QueryClient 中。初次身份读取失败只提供重试；已知身份的暂时核验失败保留该组件树和筛选，隐藏数据并用inert暂停操作，取消/暂停查询；重试确认同账号后恢复原上下文并重新读取。只有确认换号或会话失效才清缓存并重建账号树，不能把网络失败当退出。历史台账的草稿、保存队列及操作历史查询沿用该账号子树；草稿身份含账号、项目、截止月份、行记录和原所属月份，换号或失效时一并退出。
- 主题继续从 `/static/theme.css` 和官方本地 MiSans 获取，界面倍率取身份响应 `ui_scale_css`；不要复制主题色值或改 Excel/打印样式。
- 历史台账入口为 `/preview/ledger`，源码 `apps/frontend/src/ledger.tsx`、严格响应边界 `apps/frontend/src/ledger-api.ts`。AG Grid Community 36.2.0 只使用基础能力；直接输入、冻结月份、合计与虚拟窗口由单一网格承载，不引入企业版。pnpm受管补丁仅修正该版两处声明的undefined兼容，保留TS7全部严格选项；升级包时应先验证补丁是否可移除。复杂报表布局与适配结论仍待399，不由首个编辑表格推定。
- 保存离格立即发起，同记录后续修改等待新凭据，其他格的草稿继续保留；正常读回不替换活动输入，结束连续编辑后更新表格/合计。只推进自己已确认成功版本的基线，外部变更仍拒绝覆盖。账号核验暂停期间不发新写入，恢复同账号保留草稿；换号/失效重建树，取消旧请求的迟到401不清新账号。中断HTTP并不证明服务端没有完成原保存，重新进入后须读回核对。
- 旧版并行变更由父任务对共同调查点及每批交付 SHA 的后续差异按迁移面核对；不能把一次基线 clean 或某批通过当作未来无差异证明。


## 398人工试用（父任务安排开启，未试不计通过）

沿上面的隔离启动命令启动，进入 `/preview/ledger`；结束用Ctrl+C并核`ISOLATION cleaned`。没有为了等人工而保留无主服务。每次随机schema都会重置以下合成样例，全部与真实项目/历史数据无关。

登录 `preview-admin`（空密码），点“选择项目”选“隔离项目”，截止月份设为2025-11。辅材有“合成历史行甲/乙”，机械有“合成机械付款”；“长项目名验收”含另一项目行，可用来检查切换。`preview-user`（空密码）用于深色、大字号和账号隔离。页面的“打开旧版预览”指向同一隔离实例的旧前端，供对照该路径；不要改用正式端口。

1. 查询项目后，在辅材历史行连续改结算、Tab到付款继续输入，再用鼠标改备注；用真实中文输入法合成一段备注，观察前一格保存回执是否打断焦点/草稿。
2. 改历史行月份使其前后重排，再继续填下一格，离格保存；刷新确认改的是原记录。切截止月份、切另一项目再返回，核对范围及保留输入。
3. 先填非法金额、再清空，核对均被拒且原值未写；显式填0保存。看到冲突时先刷新核对，可复制保留输入，再放弃草稿重新填写；不要靠重复提交覆盖。
4. 结束编辑后点撤销、重做；删除一条新增辅材行后撤销。输入框内Ctrl+Z仍为文字撤销，框外Ctrl+Z/Ctrl+Y为业务撤销/重做。
5. 点导出台账，打开实际xlsx核对当前项目、截止月份、辅材/机械和特殊费用三表。保存后若读取失败，回执应明确已保存，刷新核对即可，避免重复新增。

保留的操作是直接填格、离格保存、同项目两侧台账和后端金额/撤销规则。可见变化为AG Grid的冻结列与内部滚动、项目搜索展开区、独立保存回执及截止月份输入；导出当前项目一本三表，旧版多项目zip选择界面未在本票接入。自动化合成事件不能代替真实输入法、鼠标手感和日常使用的人工验收；这些留待本次中途试用确认。399及后续票须等父任务确认。

预览导出由启动器限定到本轮 `.artifacts` 的exports目录，生命周期沿既有workspace_paths归档，避免落到用户正式exports；不可绕过启动器单独起预览工厂。pnpm声明与锁同行，复现安装必须使用frozen-lockfile，不手工修改node_modules。
