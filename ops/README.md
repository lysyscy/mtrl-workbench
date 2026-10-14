# ops/ · 工程资料与脚本索引

> 读者：查工程依据的人与agent。回答：哪份资料负责什么、何时读取。现行用途在§〇；部署正文回ops/deployment.md。

## 〇、现行文档用途

现行Agent协议和执行绑定已实际迁入docs/agents，旧agents只为历史引用保留过渡入口。ops根目录仍持有未迁的工程主文档、运行脚本与实测结论；development为项目实现和开发核验；hooks为提交保护源。个人通用方法由My-Skills持有，下表按当前实际位置定位资料。

| 现行文档 | 用途与何时读 |
|---|---|
| ops/README.md | 工程资料与脚本索引；找工程依据时先读本页。 |
| ops/architecture.md | 运行结构、分层边界、共用工程约束（含查询文本与Excel机械读取）与删改保护；改模块边界或共用内核时读。 |
| ops/modules.md | 模块映射及剔除规则/人工指认/模板填充的实现约束；定位模块或改这些能力时读。 |
| ops/deployment.md | 本机部署与初始化入口；查部署步骤或恢复边界时读。 |
| ops/changelog.md | 部署节点的版本变化；核对版本行为时读。 |
| ops/delivery-surface.md | 仓内 `delivery/` 产品资料清单；找业务规则时先定位这里。 |
| ops/docs-governance.md | 治理口径主人、引用与归档衔接；动文档结构时读。 |
| ops/阈值表.md | 硬数字、预算及来源；疑问或修改数字时读。 |
| ops/前端设计守则-以使用用户为中心.md | 交互与颜色规则；改前端前读。 |
| ops/素材包-索引.md | 历史素材可复用实现及作废提醒；借用素材前读。 |
| ops/i8-接口契约-旁证摘要.md | i8接口旁证与实测纠正；改抓取解析前核对。 |
| ops/M3-合计行置底实测结论.md | 合计行置底的实测方法与成立前提；改滚动容器时复核。 |
| ops/模板法导出-实测结论.md | 透视表模板生成方法与前提；改模板导出时核对。 |
| docs/agents/workflow.md | 个人方法来源、本仓输入、验证、隔离和保存授权；实施与收尾时读。 |
| docs/agents/issue-tracker.md | 票协议与§四领取销号操作；开票、领票、写状态和销号时读。 |
| docs/agents/triage-labels.md | 票分诊用词；设置票状态时读。 |
| docs/agents/domain.md | 业务术语及决定的消费方式；记录领域决定时读。 |
| ops/development/实现约束.md | 打印、配置、页面/API分界与本仓技术案例；按AGENTS命中的章节读取。 |
| ops/development/开发与核验.md | 本机运行命令、壳适配、共享监听和工具反馈；日常开发或排障按需读取。 |

历史实测与原始分组只作旁证，引用前核对成立前提；已经归档的正文经 .codebuddy/plans/archive/归档-留痕索引-20261005.md 读取。脚本用途见本页§一之二及 ops/deployment.md，不逐个解释历史脚本。

## 一、实测结论

| 文件 | 性质（答什么问题） | 成立前提 | 复现命令 | 何时必复做 | 钉住它的测试 |
|---|---|---|---|---|---|

> ⭐⭐ **2026-09-21 复做结论（`M7-A` 迁到 NSSM 之后 · 用户实测报障）**：
> 前一版结论只在"**计划任务**"这个**近似**下成立 → 换成**真正的 LocalSystem 服务**后 **当场露馅**：
> 「只导出 PDF」全失败（`BrowserType.launch: Executable doesn't exist …\systemprofile\…`），**而抓取照常可用**。
> 根因 = 浏览器装在**用户目录**、服务是 **LocalSystem** ⇒ 谁也找不到谁。
> 修法与验证见本页§一之二「Playwright 浏览器路径」表；修完用真服务的 `POST /api/m03/batch`（mode=pdf）实测：
> `total=1 · success=1 · failed=0`、产出 `FKTZS2026090456.pdf` ✔
> ⚠️ **教训（这条比结论本身值钱）**：`ops/README.md` 里那句"**M7 上线后必须用真实服务复做一次**"是**对的**，
> 而且**第一次复做就抓到一个真故障** ⇒ 「近似环境下的结论」**不能当"已验"用**。
| `M3-合计行置底实测结论.md` | 「合计行**视口吸附置底**」的**正确写法**：`position:sticky` 必须落在 **`<tr>`** 上；写在 `>td` 上**永不生效**（⚠️ 原型自己当时就是写错的 ⇒ **只抄原型必错、且静默**） | 本机 headless chromium · 表位于 `.tw` 滚动容器内 | `backend/.venv/Scripts/python.exe tools/audit/sticky_probe.py` | ① 改动合计行 / 滚动容器 CSS ② 换浏览器内核 ③ 新页要加"置底行" | **双保险**：`backend/tests/test_page_shell.py`＋`backend/tests/test_theme.py`—— 断言 `tr.sumrow{position:sticky` **在**、`>td{position:sticky` **不在** |
| `i8-接口契约-旁证摘要.md` | i8 接口**形态**（URL / 参数 / 字段名）的旁证摘录 —— ⭐ **并含 2026-09-17 真机实测纠正**（§真机实测纠正：收发结存**真实表头两行**·第 2 行才是列名；抓取**幂等范围 = 核算年月＋仓库**） | 来源 = `delivery/PRD素材包-20260911/` 里的**可读实现** ⇒ 它是**旁证、不是口径**；⚠️ 素材包含**已作废口径**；⭐ 其中「真机实测纠正」一节是**真机**结论（**冲突时以它为准**） | ——（阅读用；**不在其上写代码前先核验**） | ⭐ **改抓取 / 改导出解析前先看"真机实测纠正"一节**；技术栈 §9 更新时同步 | `backend/tests/test_i8_contract.py`（接口形态）· `backend/tests/test_acc_inv_fetch.py`（幂等范围 = 001-06）· `backend/tests/test_acc_setl_fetch.py`（合并表头 = 001-05） |
| `模板法导出-实测结论.md` | **两个材料报表的成品文件怎么生成**（`delivery/demo/模板/模板清单.md` §一 **路径②**）—— "真·可操作透视表" = 以**用户手作成品 xlsx** 为基底做 **`zip` 字节替换**（sharedStrings / 数据 sheet / pivotCache 两件 / pivotTable ＋ `refreshOnLoad`），**外加缓存级对账** | 本机 `W11-20250421859` · venv Python 3.13.12 · openpyxl 3.1.5 / pandas 3.0.5 / xlsxwriter 3.2.9 · 输入 = **2026-09-17 真机抓取**的两份 i8 导出件（`artifacts/_diag/`）· 跑的是**交付面** `delivery/PRD素材包-20260911/input/` 里的现成管线 | 历史命令见正文；脚本仍含旧根，先核输入与路径，不直接当当前已验 | ① **改这两份报表的模板**（用户手作件换代）② 改 `mod07_setl`/`mod08_inv` 的解析（列定义）③ i8 导出件表单结构变 ④ 换机 / 升 openpyxl / pandas / xlsxwriter | **已接入** backend/app/report_export/（TAIL-04已完成）；改模板生成逻辑时以本条为方法旁证；成品对账口径见 `ACC-SETL-001/001-08` |
| **—（已归档 · 2026-10-05 `TAIL-235`）** | 原型断言归属映射（治理侧 · 无判据）· i8 名单同步原始返回（`实测快照/` 两份 json）· 渲染能否在会话 0 内跑 · 宿主 hooks 能力（含**负结果**：本 IDE 不跑 hooks） —— **正文已移出仓外** `D:\dev\.归档-mtrl\ops\`（原文可 `git show` 取回）| ⛔ **别再新增实测结论到这个落点** | 同左（脚本已随件归档）| ① 换机 / 升 Playwright / 改打印链路 ② 名单抓不到或条数明显变 ③ **原型 `_smoke.js` 一改就过期** ④ 换 IDE / 升宿主 | ⛔ 无判据（随件归档）|
| `init_db.sql` | 一次性**建库**（开发库与测试库**物理隔离**，依据技术栈 §3.0 / §3.1） | 本机 PG 16 · 需 postgres 超级用户 | 本机路径见 .codebuddy/memory/MEMORY.md §三；脚本见 ops/deployment.md（本轮不执行建库） | 换机 / 重建库（**恢复演练**在 M8，见计划 §5.5） | 全套 `tests/test_acc_*`（库结构不对会直接红） |

## 一之二、运维脚本（**不是"实测结论"，但同样带前提** —— 2026-09-21 新增）

口径定案：**D19 服务形态 = NSSM**（用户 2026-09-21 拍板）⇒ 后端从**计划任务**迁到 **Windows 服务**
（`M7-A` 调试版；⏸️ 备份、恢复演练及实际配置仍未证明；状态回TAIL-188与TAIL-223，不据旧排期推断未实现）。

| 脚本 | 干什么 | 前提 / 何时必复做 |
|---|---|---|
| `nssm_install.ps1` | **幂等**把后端注册成 NSSM 服务（服务名 `mtrl-workbench-server` · 单 worker · `0.0.0.0:8000` · 开机自启 · 崩溃自重启 · 日志分流 `../logs/server.out.log` / `server.err.log` 带 10 MB 轮转 · 依赖 `postgresql-x64-16`）。**先停并删除同名计划任务**（⛔ 不允许两个实例抢 8000） | ⚠️ **必须管理员** PowerShell；需要 `nssm.exe`（放 `ops/nssm/`，**已 gitignore**；获取渠道见脚本提示）。⭐ **换机 / 改启动参数（host、port、worker 数）/ 改 venv 路径 ⇒ 必复做** |
| `nssm_uninstall.ps1` | 撤销服务注册（⛔ 不动数据、不动 `backend/`、不动 `.env`）；`-RestoreScheduledTask` 可恢复迁移前的计划任务形态 | 同上 |
| `server_ctl.ps1` | 日常遥控：`status` / `start` / `stop` / `restart` / `log` / `port` / `pg`；⭐ `port` 那条会打印占用 8000 的**进程命令行与启动时间**（诊断"是不是旧进程"） | 只读查询普通窗口即可；启停/重启须当前明确授权及管理员权限。服务无 `--reload`，后端Python变化的加载要求不构成重启授权；操作边界见 ops/deployment.md §〇 |
| `install_hooks.ps1` ＋ `hooks/pre-commit` | 安装仓内提交钩子；当前仅核暂存语法、字节和凭据文件名，实际清单读 `ops/hooks/pre-commit`。业务与文档核验按 `docs/agents/workflow.md`执行 | 新环境/克隆后安装；保留真实钩子输出。安装脚本幂等，不改git config；钩子不依赖tail/sed等外部工具 |
| `_ps_bom.py`（⚠️ 在 **`tools/oneoff/`** —— 2026-09-29 订正：原写"在 `tools/`"**已过期**，照它找会**找不到文件** ✗） | 给 `.ps1` 补 **UTF-8 BOM** | ⚠️ **PS 5.1 按 GBK 读无 BOM 的 .ps1** ⇒ 中文字节会**吞掉紧跟的 ASCII 引号** ⇒ 满屏 `ParserError`（文件本身没错）。**每次改完 ops 下的 .ps1 就跑一次** |
| `_ps_parse_check.ps1`（在 **`tools/oneoff/`** · ⭐ 2026-09-29 立） | ⭐ **`ops/*.ps1` 的闸（两段）**：① **语法**（PS parser 逐份解析）② ⭐ **仓内路径字面量必须真的存在**（`Join-Path $RepoRoot '…'` 形态；⚠️ **先剥注释再扫** —— 不剥会把"解释缺陷的注释"当成缺陷）⇒ 任一段不过就 `rc=1` | ⚠️ 仓里**此前没有任何 PS 尺子**（Python 有 `syntax_audit.py`、前端有 `node --check` 那一路，PowerShell 没有）⇒ 改完只能等**真跑那一刻**才炸 —— 而那通常正是"要在目标机安装"的时候 ✗。⚠️ 它**不管语义/参数**，那半靠 `-DryRun` 真跑（两者互补：它查"写死的路径在不在"，`-DryRun` 查"流程对不对"） |

⭐ **Playwright 浏览器路径（`C:\ProgramData\ms-playwright`）—— 2026-09-21 实测补的，⛔ 别删**：

| 事项 | 说明 |
|---|---|
| 为什么机器级 | 服务以 **LocalSystem** 跑 ⇒ 它看不到任何**用户**目录下的东西；而 Playwright 默认把浏览器装在 `C:\Users\<人>\AppData\Local\ms-playwright` ⇒ 服务**一定找不到** |
| 症状 | 「只导出 PDF / 批量打印」全失败：`BrowserType.launch: Executable doesn't exist at C:\WINDOWS\system32\config\systemprofile\AppData\Local\ms-playwright\…`；⚠️ **抓取照常可用**（纯 HTTP、不用浏览器）⇒ **只打打印/导出那一路** |
| 怎么配 | ① 浏览器放 `C:\ProgramData\ms-playwright`（本机已把原用户目录那份**移动**过去，不重复占 300MB）② 机器级环境变量 `PLAYWRIGHT_BROWSERS_PATH` ③ ⭐ 服务上也显式设一份（`nssm set <服务> AppEnvironmentExtra`，见 `nssm_install.ps1`） |
| 重装浏览器 | `$env:PLAYWRIGHT_BROWSERS_PATH='C:\ProgramData\ms-playwright'; backend\.venv\Scripts\python.exe -m playwright install chromium` |
| ⚠️ 旧 shell | 环境变量**只对新进程生效** ⇒ 改完要**重启服务**、并**重开**自己的终端（旧窗口里跑 `_mut_*` / 探针会报同一个错） |

⚠️ **本机另两条硬约束**：`sc.exe` / `cmd.exe` 在**安全策略黑名单**（服务操作一律走 nssm 或 PowerShell cmdlet）；
`schtasks.exe` 同理 —— 计划任务一律用 `*-ScheduledTask` cmdlet。

⚠️ **`ops/nssm/nssm.exe` 不提交**（二进制 · 见 `.gitignore`）；新机重建照上表第一条重新下载一次即可。

## 一之三、本宿主的 **hooks 能力**（⭐ **已独立成件** · 2026-09-28）

旧宿主hooks调查仅在明确复核宿主时经归档索引追溯；日常读取与记录不由它决定，回 docs/agents/workflow.md。


## 一之四、GitHub 克隆与首次空库部署

换机或首次空库安装读取 ops/deployment.md；代码取得、目标依赖、执行步骤与未核实风险均由该页承载。

## 一之五、**配置主人表**（改了哪一项 ⇒ 在哪生效 ⇒ 要不要重启 · ⭐ 2026-09-29 立 · `TAIL-192`-②）

> **为什么有这一段**：同一个配置项**两处存** —— 页面「设置」写**库**、文件里是 `.env` ⇒ 最常见的误解是
> 「我改了 `.env` 怎么不生效」。⚠️ **取值链 = 库（页面所设）→ `.env`**，唯一出口 = `app_settings.effective()`
> （定义见 `backend/app/core/app_settings.py` 文件头）⇒ ⛔ 别在别处另定一套"谁是主人"，本表只**指路**。

| 想改什么 | 从哪儿改（推荐） | 存到哪 | 要重启后端吗 |
|---|---|---|---|
| **i8 服务地址** ＋ **两个打印版式 ID** | **页面**：`i8 接入层`（i8 地址）· 付款通知书页「打印机设置」弹窗（两个版式 ID） | 写**库** | ⛔ **不用**（保存即清缓存） |
| **打印机三项** `PRINTER_IPP_URL` / `PRINT_MODE` / `PRINTER_NAME` | **页面**：付款通知书页「打印机设置」弹窗 | 写**仓根 `.env`**（⚠️ 页面有入口，但**不存库**） | ⛔ **不用**（写完 `cache_clear()`） |
| **其余全部**（库口令 `DATABASE_URL` / `TEST_DATABASE_URL` · `ALLOWED_IP_CIDRS` · i8 账号 `I8_USER`/`I8_PASSWORD` · `SESSION_SECRET` · `ARTIFACTS_DIR`/`LOGS_DIR` …） | **仓根 `.env`**（键名见 **仓根 `.env.example`**） | 只在启动时读一次 | ✅ **要**：`ops\server_ctl.ps1 -Action restart` |

⭐ **一句话记法**：**有页面入口的那几项 ⇒ 改完不用重启；只在 `.env` 里手改的 ⇒ 必须重启**（后端**没有** `--reload`）。

⚠️ **第二句更要紧**：i8 地址与两个版式 ID 是「**库优先、`.env` 兜底**」⇒ **页面上设过之后，再改 `.env` 那几行就不生效了**
（页面显示的是**生效值** —— 要核对就看页面那一格，⛔ 别去看 `.env` 原文）。
⚠️ 两个打印版式 ID **与直觉相反**（材料类走「其他支出」版式）—— 以 `backend/app/core/app_settings.py` 的 `SPECS` 提示语为准。

## 二、引用这些结论时的三条纪律

1. **先对前提**：文件头部写了「本机 / 方法 / 脚本 / 日期」。**换机后先把前提重核一遍**
   （本仓已有一次换机：2026-09-14 盘符变过 ⇒ 旧路径类结论一律作废）。
2. **按变化补验**：日期、输入、代码与环境未变且已有有效结果时复用；变化或无证的相关输入才重验，范围回 docs/agents/workflow.md。先读脚本的读写与登录边界，实测引用不构成部署、登录或业务写入授权；历史脚本依赖缺失时明确记为未复现。
3. **钉住它的测试 = 结论的保鲜剂**：本表最后一栏若写着「断言测不了」，那句话本身就是要害
   —— 说明**只有人能保证它**，别把它当"已自动化"。

---

> **本文件性质**：工程侧索引（`ops/`，**不进交付面**）· 不含业务取值 · 随新增结论滚动更新。
