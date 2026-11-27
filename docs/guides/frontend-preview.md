# React 真实副本预览

用于构建、启动、更新、核验和退出预览。业务定义回需求分册，界面约束回[前端设计](frontend-design.md)，自动验证回[开发与验证](development-and-verification.md)。正式 `/app` 的切换另按[部署](deployment.md)授权；开放 `/preview` 不表示上线。

主预览供既定人工验收，临时预览供局部调查或验证；构建成功不自动增加审批点，局部样例也不代表整体完成。用户仍需查看时保留预览，回复结束不等于用途结束；停止服务与删除源码、数据库或工作树分别按用途和授权判断。

## 界面改版何时需要评审

- **需要评审**：用户明确要求点验，或仍需用户决定主要入口、操作步骤、关键信息的组织、关键状态或异常的处理方式。指出具体待决事项，围绕受影响路径安排评审。
- **小改直接做**：文案勘误、按现有规范调整间距或尺寸、恢复已确认的行为，按影响验证。已有明确方案的改动按方案实施和验收，人工评审沿约定的节点执行。业务规则与验收仍按对应需求和[隔离验证](development-and-verification.md)执行。
- **评审怎么做**：既有页面从登记的 `/preview` 进入，复用现有 React 路由和组件，按下节选代表性真实数据副本。需要模拟时，把本次新增或变更的后端行为限定在评审入口，使用模拟回执走完操作，并标明模拟范围。交互确认后接真实接口，在登记副本上验证实际写入、读回和业务结果。

## 先确定当前实例和数据用途

每个 Git 工作树同一时间可运行一个真实副本预览。同仓各工作树合计最多 3 个，使用回环地址的 `8065`、`8066`、`8067`，启动未指定端口时使用 `8065`。先用 `--list` 找可用端口。预览没有空闲超时，会一直运行到显式停止，或同工作树的正式发布核验成功后清理符合条件的可丢弃副本。自动 HTTP 测试默认连接当前工作树登记的实例。

统一入口为 `tools/dev/frontend_preview.py`。同仓共享 `var/state/react-writable-preview`，每个工作树使用 `slots/<slot>.lock` 和 `instances/<slot>.json`，登记指向 run 的 `reports/real_owner.json`。共享 `registry.lock` 短时串行更新登记。启动在创建或升级副本前占用工作树和端口，服务进程持有工作树锁直至退出。旧 `current.json` 中仍存活的实例也占一个名额和端口。异常退出由系统释放工作树锁，下次启动按实际 PID、创建时间和命令核实并移除已死的新式登记，保留原 owner 回执。

| 用途 | 操作边界 |
|---|---|
| 新建验证副本 | 显式 `--copy-source --disposable`；来源只读一致快照，目标先匹配来源版本，核复制计数/内容/序列，再只升级目标。退出只清其自建schema。 |
| 现有用户试用副本 | `--existing`只接受已登记可写副本；需要时显式目标升级，先保恢复点并核已有表数据不丢。停止保留schema、私有状态和用户修改，禁止重拷正式库覆盖。 |
| 冻结历史性能样本 | 保既定版本、数据指纹和离线原件；无额外常驻服务，不为最新产品迁移原样本。获准测量时再安排符合条件的只读副本。 |

新副本账号经去凭据/停用投影，再建专用本地验看账号，配置、操作历史与运行记录按复制工具的明确边界处理；不打印或复制来源凭据到工作树.env。验证副本保持所有既有i8/物理打印外呼入口阻断，本地读写和Excel导出完整开放。已有业务试用实例保其明确授权的绑定及私有会话，读取配置不代表认证成功或新外部动作授权。

### 单独获批的浏览器通知书验证

浏览器通道的真实日常入口验收须另行取得用户对安装/权限与真实读取范围的确认，普通预览不因此放开外部动作。需要时，先把具体月份、站点原点和已核i8账号写到本登记run的`work`内JSON文件；字段仅为`year_month`、`origin`、`i8_user`，不放密码、Cookie或Token。范围文件只是输入，不是授权依据，不提交真实范围文件。

在原统一构建、登记和租约流程中增加`--browser-notice-check <run>/work/<scope.json>`，仅允许`--copy-source --disposable`新副本，拒绝已有/保留用途副本。它仅在本进程使用批准站点，并给生成的preview账号绑定指定i8用户名和空密码，不改来源配置或来源账号。原有认证/账号预期校验、严格站点/组织核对和连接票据校验继续执行。

该模式只开放相应浏览器连接控制路由及指定月份的`POST /api/m03/notices/fetch`；必须为browser方式、生成的preview账号、非空device_id且不允许强踢。除登录/登出及上述明确入口，其它非GET/HEAD动作均拒绝，包括无关本地写入、抓取、同步、批量打印/PDF；普通预览的本地写入策略不变。HTTP方式继续拒绝；进程内另禁止普通I8Client开启会话，严格客户端也只准BrowserRelayTransport。业务落库沿原通知书流程，目标仍是登记的可丢弃schema。退出清理其自建schema；owner只记范围及i8账号散列。默认预览的`GET /api/m02/browser/state`只读本地连接状态，不发i8请求。

范围边界通过`backend/tests/test_frontend_preview_browser_check.py`核默认阻断、错月份/账号/方式拒绝、原请求体继续交业务路由及直连运输阻断；这不代表真实Edge或i8业务验收通过。实际启用前仍须有当次明确批准，不得通过修改owner的`i8_enabled`绕过本范围。

## 离线构建

依赖及最低版本读 `apps/frontend/package.json`（Node范围）与锁文件（pnpm精确版本）；复用已准备环境。仓根运行，`<run>`默认取已登记的`.artifacts/runs/<run-id>`，旧全局登记的files目录和`.artifacts/active/<effort>/<run>`沿原配置兼容。构建目录须为run/work下不存在的新目录；构建、提权交接和在用预览分别登记消费者，不能随构建命令结束就删除待用资源。发布、构建和资源核验共用归属检查，拒绝未登记目录、链接及已关闭或保护中的写入：

```text
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --run <run> --prepare-build <run>/work/<new-build>
```

入口依次执行现有typecheck/build，保存日志与version清单，核HTML入口、src/public、依赖/构建配置输入及完整资源散列。可在旧实例运行时离线构建；待用清单不会改变旧owner的实际身份。最新产品还核后端/迁移与预览工具输入，纯文档提交不触发重建。运行时theme链接保留，不能把index中的运行期链接改成相对构建资源。

输入声明包含组件`pnpm-workspace.yaml`与`patches`；完整预览身份另包含浏览器验证门。新增这些输入前生成的旧清单不再满足最新输入校验，应沿统一入口重建；不手工补写旧清单。已加载正式包可继续运行、保留原回退用途，后续标准restart可能要求publish重建完整清单，仍按独立部署授权执行。

## 启动、更新与切换

先离线准备。构建统一经Corepack调用package.json声明的pnpm，先核实际版本，再typecheck/build，版本身份随version.json记录；缺Corepack或版本不符即停止，不回落PATH中的其他pnpm。核旧owner后正常退出，再开放新实例；统一入口在任何副本持久写入前取得排他锁及目标端口。未知来源修订、迁移分叉、数据库身份或search_path不符均拒绝，不stamp、不回退public、不改来源结构。参数中的配置只用于明确来源和专用测试目标。

共享检出上开始累计回归或加载前，先与相关输入主人核目标修订和产品指纹，约定需要稳定的源码及窗口；实施期间可并行，验证窗口内保持这些输入稳定。无法冻结时使用隔离检出，为该工作树登记真实副本和空闲端口。沿现有任务/owner沟通，不增加登记表；独立清理与归档不占共享索引窗口。

来源和目标沿[父入口身份核验](development-and-verification.md#后端隔离验证参数)在连接前校验。新副本与existing均拒绝明确文件和有效环境的身份冲突；普通应用Settings的环境优先规则不变。

```text
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --stop
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --source-env <正式检出的.env> --run <run> --copy-source --disposable --port 8065
```

已有用户试用副本使用原run和owner，不经过自建schema的finally清理：

```text
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --source-env <正式检出的.env> --run <原试用run> --existing --port 8065
```

确需升级该副本时增加 `--upgrade-existing --pg-bin <现场匹配PG/bin>`。升级只作用登记目标，schema恢复点使用现有pg_dump/pg_restore目录校验；原表数据摘要前后核对。恢复点留在原run/recovery，风险窗口关闭后按既有生命周期处置。正式服务不在预览停止/升级范围。

## 实际核验与退出

Agent 自动核验可在本次运行内启动可丢弃预览，检查结束后正常停止。交给用户长时间验看时，若当前宿主会在会话空闲后回收后台进程，交接时提供下列单行启动命令，填入已登记的 run、来源文件与空闲端口，由用户在自己的终端或项目脚本中运行。预览随该终端或脚本运行，独立于聊天会话。

```text
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --source-env <正式检出的.env> --run <run> --copy-source --disposable --port <空闲端口>
```

从当前工作树现有解释器调用 `tools.dev.frontend_preview_runtime.registered_preview()`，核固定进程身份、HTTP `/visual-version`的实际schema/revision、产品输入、完整构建及实际HTML。再由入口导航检查登录、权限、受影响读取/正常保存读回或实际下载；不从健康200推完整业务正确。独立Cookie、精确search_path、导出目录及配置/i8缓存/导入状态都由原run隔离。

```text
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --list
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --stop
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --stop --port 8066
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --stop --all
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --prune --files-only
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --prune --source-env <正式检出的.env>
```

`--list` 列出所有登记中的活动预览和已退出的残留登记，包括旧实例。`--stop` 默认只作用当前工作树，可显式按端口或全仓停止。已就绪实例按登记进程和实际 HTTP 身份请求正常退出，待用构建清单不影响停止。用户试用 schema 和私有状态保留，可丢弃验证 schema 由创建者清理。需要在同一工作树临时做写入验证时，先停止并保留试用副本，验证后恢复原试用入口。

`--prune` 清除已确认进程退出的登记，包括旧 `current.json`。预览运行目录只剩 0 字节 `runtime.env` 且无活动登记引用时一并清理。`--files-only` 只执行本地文件清理。默认 `.env` 缺失时也只清理本地文件。

数据库清理使用指定 `--source-env`，默认使用当前工作树的 `.env`，仅作用于 `mtrl_workbench_test` 中由测试库账号拥有且无活动预览引用的 `frontend_rewrite_397_*` schema。命令列出移除的登记、运行目录和 schema。

正式 `publish` 在核实 `/app` 已加载目标版本后，请求同工作树的可丢弃预览正常退出。其他工作树与用户试用实例记录在发布回执的 `other_active_previews`。`preview_cleanup` 记录停止结果、清理警告及已经释放的 `work/build-*` 目录，目录清理限于同工作树内已登记、无活动消费者且未受保护的预览 run。清理警告不影响已核验的发布结果。

## 布局采集

`tools/dev/frontend_layout.py`只附着指定run且与当前登记一致的最新可丢弃真实副本，使用其本地验看账号和新浏览器context。先按本任务授权把临时账号设为目标字号；采集器核实际字号，保留账号设置。

```text
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_layout.py --preview-run <本任务run> --width 1920 --height 1080 --scale 1.12
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_layout.py --preview-run <本任务run> --route /contracts --route /inventory
```

页面从实际侧栏导航枚举，`--route`只选择其中的入口。采集等待页面、数据与当前展开网格就绪，记录视口、字号、列、行数、页面横向溢出、单元格及其内容容器的横竖溢出和实际可见横向条；关闭的details不参与。无可验网格、零可见数据行或明确空结果、页面错误或超时分别记录且返回非零，不能当作布局通过；整数测量1px取整差与0高隐藏横向条区分。失败截图沿frontend_capture带预览身份；JSON绑定采集器散列和实际预览身份，运行前后核相同实例/产品输入。产物按workspace_paths退出，结束给出实际证据路径；明确失败的现场暂缓删除。此检查覆盖所选主视图，额外明细、弹窗和交互按本次变化选测。

布局采集器的无溢出判据用于本任务明确要求无溢出的自动布局样本。窄窗允许横滚、批准的长文本省略或用户主动手调裁剪，按[前端设计](frontend-design.md)的对应规则用定向操作核内容与动作可达，不能仅凭采集器的 overflow 判为产品违约。保留原始结果及原因，说明该判据是否适用；不得伪报工具通过，也不得用“不适用”跳过本任务明确的无溢出验收。

## 性能测量

`tools/dev/frontend_measure.py`只消费已存在的只读真实副本，保留owner、读写身份、schema、版本与构建保护。当前可写业务预览不能冒充冻结性能条件；采集器集成检查也不等于重跑性能基线。

```text
backend/.venv/Scripts/python.exe -X utf8 tools/dev/frontend_measure.py check --samples <samples.jsonl> --interactions <interactions.json>
backend/.venv/Scripts/python.exe -X utf8 tools/dev/frontend_measure.py run --preview-run <只读run> --baseline-summary <summary.json> --label <新label> --stage screen
```

先小样筛查；有明确完整对照用途才用 `--stage all`。原始输入、版本、数据、浏览器/视口/字号及冷/热条件必须对应，较差样本和未验边界保留。ready为标题/networkidle/fonts/双rAF代理，不是现场INP、热SPA LCP或Lighthouse TBT；自动输入和导航传输开销分别解释，`fonts.ready`后新触发加载不伪称字体全稳定。现有纯计算、输出保护与真实页采集器检查入口见开发指南。
