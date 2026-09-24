# `ops/` 索引 —— 实测结论与工程底账

> ⭐ **部署/起停/配置/备份** ⇒ 本件 ＋ `ops/*.ps1`（`server_ctl.ps1` / `nssm_install.ps1` / `nssm_uninstall.ps1` / `init_db.sql`）。
> ⚠️ **2026-09-25 用户裁定**：「runbook **整份删除** —— 它纯粹是换机的时候搞出来的，换完机就无用了、反而会过期」
> ⇒ **那件已整份删除**（原在 `docs/` 下）。⛔ 别再引它；要**换机 / 灾难恢复**时**重新问用户**，⛔ 别照旧文档抄。

> **为什么有这份文件**：`ops/` 里的每条结论都带**成立前提**（哪台机 / 哪个环境 / 谁在跑），
> 而**前提是会变的** —— 没有索引，就没人知道「**哪条还有效、什么时候必须复做**」，
> 结论就会以"看起来还很新"的样子被一直引用下去。
>
> **读法**：引用任何一条结论前，先看它的**成立前提**与**何时必复做**；
> 两栏对不上（换机了 / 改了被实测的那段代码）⇒ **先复做，再引用**。
>
> ⚠️ 本目录**不属于交付面**（工程侧活账本，与 `.workbuddy/` 同类）· ⛔ **结论里不含业务取值**
> （业务取值一律回《材料科业务全流程说明书》）。
> **维护**：新增实测结论 ⇒ ① 文件自身写清「性质 / 方法 / 脚本 / 日期 / 本机」② **在本表加一行**。

---

## 一、实测结论

| 文件 | 性质（答什么问题） | 成立前提 | 复现命令 | 何时必复做 | 钉住它的测试 |
|---|---|---|---|---|---|
| `M0-0B-渲染实测结论.md` | 「**渲染 / 出纸能否在非交互会话（会话 0）内**跑」——决定切片 1 走 Plan A（进程内本地渲染）还是退路（WeasyPrint / 桌面代理） | 本机 `W11-20250421859` · Playwright headless chromium · 以**计划任务 `SYSTEM` 身份**运行（= 会话 0 的**近似**，不是真服务） | `backend/.venv/Scripts/python.exe tools/probe/render_smoke.py` | ① ✅ **已于 2026-09-21 用真实 NSSM 服务复做**（见下）② 换机 / 升 Playwright / 改打印链路 | `tests/test_acc_pay_pdf.py`（`ACC-PAY-PDF-001` 钉**产物形态**）· ⚠️ 「**会话 0 能跑**」这一条**断言测不了**，只能真机复做 |

> ⭐⭐ **2026-09-21 复做结论（`M7-A` 迁到 NSSM 之后 · 用户实测报障）**：
> 前一版结论只在"**计划任务**"这个**近似**下成立 → 换成**真正的 LocalSystem 服务**后 **当场露馅**：
> 「只导出 PDF」全失败（`BrowserType.launch: Executable doesn't exist …\systemprofile\…`），**而抓取照常可用**。
> 根因 = 浏览器装在**用户目录**、服务是 **LocalSystem** ⇒ 谁也找不到谁。
> 修法与验证见上面「Playwright 浏览器路径」表；修完用真服务的 `POST /api/m03/batch`（mode=pdf）实测：
> `total=1 · success=1 · failed=0`、产出 `FKTZS2026090456.pdf` ✔
> ⚠️ **教训（这条比结论本身值钱）**：`ops/README.md` 里那句"**M7 上线后必须用真实服务复做一次**"是**对的**，
> 而且**第一次复做就抓到一个真故障** ⇒ 「近似环境下的结论」**不能当"已验"用**。
| `M3-合计行置底实测结论.md` | 「合计行**视口吸附置底**」的**正确写法**：`position:sticky` 必须落在 **`<tr>`** 上；写在 `>td` 上**永不生效**（⚠️ 原型自己当时就是写错的 ⇒ **只抄原型必错、且静默**） | 本机 headless chromium · 表位于 `.tw` 滚动容器内 | `backend/.venv/Scripts/python.exe tools/audit/sticky_probe.py` | ① 改动合计行 / 滚动容器 CSS ② 换浏览器内核 ③ 新页要加"置底行" | **双保险**：`tests/test_page_shell.py`（第 94 行）＋ `tests/test_theme.py`（第 128 行）—— 断言 `tr.sumrow{position:sticky` **在**、`>td{position:sticky` **不在** |
| `i8-名单同步实测结论.md` | 真机 `API-06` 常用项目（含 `phid`）＋ `API-05` 仓库名单的**真实返回形态与条数** | 真机直连 i8（**一次登录**连抓两张表）。⚠️ **会强踢在线用户**（D9）；⚠️ 该账号**本来没有密码**，**空密码可登录**属正确配置 | 采集脚本**一次性、未入库**（跑完即弃）⇒ 要复现请照 `app/mod02_i8` 的 client 自写 | ① 名单抓不到 / 条数明显变 ② i8 改版 ③ 换机 | `tests/test_acc_prj_sync.py`（`ACC-PRJ-SYNC-001` 10 点：建档落库 / 去重 / 壳排除 / 尾码剥离） |
| `i8-接口契约-旁证摘要.md` | i8 接口**形态**（URL / 参数 / 字段名）的旁证摘录 —— ⭐ **并含 2026-09-17 真机实测纠正**（§真机实测纠正：收发结存**真实表头两行**·第 2 行才是列名；抓取**幂等范围 = 核算年月＋仓库**） | 来源 = `PRD素材包-20260911/` 里的**可读实现** ⇒ 它是**旁证、不是口径**；⚠️ 素材包含**已作废口径**；⭐ 其中「真机实测纠正」一节是**真机**结论（**冲突时以它为准**） | ——（阅读用；**不在其上写代码前先核验**） | ⭐ **改抓取 / 改导出解析前先看"真机实测纠正"一节**；技术栈 §9 更新时同步 | `tests/test_i8_contract.py`（接口形态）· `tests/test_acc_inv_fetch.py`（幂等范围 = 001-06）· `tests/test_acc_setl_fetch.py`（合并表头 = 001-05） |
| `原型断言-归属映射.md` | 把原型 `_smoke.js` 里那批**口径修正断言**逐条绑到**真用例号**或**明确的真缺口** | 对应**某一个版本**的 `_smoke.js`（文件内引用形如 `L1197` 的**行号** ⇒ 换版本即漂） | 抽取脚本**一次性、未入库** | ① ⭐ **原型 `_smoke.js` 一改就过期**（行号漂）② 新增 / 删除用例时 | 治理侧结论（无判据）；它核出的真缺口 ⇒ 台账 `TAIL-20` / `TAIL-21` |
| `原型断言-5k原始分组.txt` | `§5k` 的**机器抽取原始分组**（实测 **109 条 / 前缀 63 组**）—— 上一行那份映射的**底稿** | 同上（某个版本的 `_smoke.js`） | 抽取脚本**一次性、未入库** | 同上一行 | ——（底稿留痕，不单独承载判据） |
| `实测快照/i8-20260916-common_project.json`<br>`实测快照/i8-20260916-warehouse_list.json` | 真机 i8 的**原始响应**留痕（只读） | **2026-09-16 21:07** 那一次抓取 | ——（只读留痕） | 要复核名单结论时，**先看这两份快照**再决定是否复抓 | 间接：`ACC-PRJ-SYNC-001` |
| `模板法导出-实测结论.md` | **两个材料报表的成品文件怎么生成**（`demo/模板/模板清单.md` §一 **路径②**）—— "真·可操作透视表" = 以**用户手作成品 xlsx** 为基底做 **`zip` 字节替换**（sharedStrings / 数据 sheet / pivotCache 两件 / pivotTable ＋ `refreshOnLoad`），**外加缓存级对账** | 本机 `W11-20250421859` · venv Python 3.13.12 · openpyxl 3.1.5 / pandas 3.0.5 / xlsxwriter 3.2.9 · 输入 = **2026-09-17 真机抓取**的两份 i8 导出件（`artifacts/_diag/`）· 跑的是**交付面** `PRD素材包-20260911/input/` 里的现成管线 | `backend/.venv/Scripts/python.exe tools/probe/_probe_tpl.py` | ① **改这两份报表的模板**（用户手作件换代）② 改 `mod07_setl`/`mod08_inv` 的解析（列定义）③ i8 导出件表单结构变 ④ 换机 / 升 openpyxl / pandas / xlsxwriter | **本工程尚未接入**（现只出清单）⇒ 接 `TAIL-04` 时以本条为方法依据；成品对账口径见 `ACC-SETL-001/001-08` |
| `init_db.sql` | 一次性**建库**（开发库与测试库**物理隔离**，依据技术栈 §3.0 / §3.1） | 本机 PG 16 · 需 postgres 超级用户 | `"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -f "D:\dev\mtrl-workbench\ops\init_db.sql"` | 换机 / 重建库（**恢复演练**在 M8，见计划 §5.5） | 全套 `tests/test_acc_*`（库结构不对会直接红） |

## 一之二、运维脚本（**不是"实测结论"，但同样带前提** —— 2026-09-21 新增）

口径定案：**D19 服务形态 = NSSM**（用户 2026-09-21 拍板）⇒ 后端从**计划任务**迁到 **Windows 服务**
（`M7-A` 调试版；⏸️ `M7-B` 交付版的备份/演练**尚未开工**）。

| 脚本 | 干什么 | 前提 / 何时必复做 |
|---|---|---|
| `nssm_install.ps1` | **幂等**把后端注册成 NSSM 服务（服务名 `mtrl-workbench-server` · 单 worker · `0.0.0.0:8000` · 开机自启 · 崩溃自重启 · 日志分流 `../logs/server.out.log` / `server.err.log` 带 10 MB 轮转 · 依赖 `postgresql-x64-16`）。**先停并删除同名计划任务**（⛔ 不允许两个实例抢 8000） | ⚠️ **必须管理员** PowerShell；需要 `nssm.exe`（放 `ops/nssm/`，**已 gitignore**；获取渠道见脚本提示）。⭐ **换机 / 改启动参数（host、port、worker 数）/ 改 venv 路径 ⇒ 必复做** |
| `nssm_uninstall.ps1` | 撤销服务注册（⛔ 不动数据、不动 `backend/`、不动 `.env`）；`-RestoreScheduledTask` 可恢复迁移前的计划任务形态 | 同上 |
| `server_ctl.ps1` | 日常遥控：`status` / `start` / `stop` / `restart` / `log` / `port` / `pg`；⭐ `port` 那条会打印占用 8000 的**进程命令行与启动时间**（诊断"是不是旧进程"） | 普通窗口即可（`start`/`stop`/`restart` 需管理员）。⛔ **改完 Python 必须 `restart`**（无 `--reload`） |
| `_ps_bom.py`（在 `tools/`） | 给 `.ps1` 补 **UTF-8 BOM** | ⚠️ **PS 5.1 按 GBK 读无 BOM 的 .ps1** ⇒ 中文字节会**吞掉紧跟的 ASCII 引号** ⇒ 满屏 `ParserError`（文件本身没错）。**每次改完 ops 下的 .ps1 就跑一次** |

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

## 二、引用这些结论时的三条纪律

1. **先对前提**：文件头部写了「本机 / 方法 / 脚本 / 日期」。**换机后先把前提重核一遍**
   （本仓已有一次换机：2026-09-14 盘符变过 ⇒ 旧路径类结论一律作废）。
2. **能复现的必须能一键复现**：凡有 `tools/*.py` 的，**引用时顺手跑一遍**比读更省；
   没有脚本的（一次性采集），**要么补脚本、要么在结论里写明"不可复现"**。
3. **钉住它的测试 = 结论的保鲜剂**：本表最后一栏若写着「断言测不了」，那句话本身就是要害
   —— 说明**只有人能保证它**，别把它当"已自动化"。

---

> **本文件性质**：工程侧索引（`ops/`，**不进交付面**）· 不含业务取值 · 随新增结论滚动更新。
