# runbook · 部署 / 运维 / 配置 / 换机

> **读者**：Agent（执行部署与运维）＋ 用户（换机/恢复时）｜**回答**：怎么装、怎么起停、配置在哪、备份怎么留
> **何时读**：部署、改后端、换机、备份/清理时｜**状态**：已定稿（2026-09-22 · 由 `MEMORY §十六/§十七` 与 `ops/README` 运维段收口而来）
> ⚠️ 业务口径不在这里（回交付面《说明书》/ `PRD/`）；实测结论不在这里（回 `ops/README.md` 索引）。

## 一、服务（NSSM）

- Windows 服务 **`mtrl-workbench-server`**（`0.0.0.0:8000` · **单 worker** · 开机自启 ＋ 崩溃自重启 ·
  日志分流 `logs\server.out.log` / `logs\server.err.log`，10 MB 轮转）。
- ⛔ **计划任务已停并删除**（D19 · 2026-09-21）—— 别再按计划任务写脚本。
- 起停/状态/日志/端口/PG 一律走 **`ops\server_ctl.ps1 -Action status|start|stop|restart|log|port|pg`**。
  ⚠️ **改完后端必须 `restart`**（无 `--reload` ⇒ 新端点一律 404，**而自检与 pytest 照绿**）。
- 安装/迁移：`ops\nssm_install.ps1`（幂等）；回滚：`ops\nssm_uninstall.ps1`（可 `-RestoreScheduledTask`）。
- ⚠️ NSSM = **LocalSystem** 会话：浏览器（Playwright）必须装在**服务找得到的位置**
  （实测踩坑：装在用户目录 ⇒「只导出 PDF」全失败而抓取正常 —— 详见 `ops/README.md` 的复做结论行）。

## 二、配置项

- 文件：`.env`（真值）/ `.env.example`（模板）；**取值唯一出口 = `app_settings.effective`**（⛔ 不直接读 os.environ）。
- 设置页（m14/`set`）：库值 → `.env` 兜底（`ACC-CFG-SETUP-001`）；改动留痕（改前/改后/操作人/时间）。
- 版式 ID 反直觉：**材料类 → 「其他支出」** / **外租机械类 → 「付款通知书」**（§4.3.3，设置页必须带提示）。

## 三、数据库

- PostgreSQL；测试库与开发库**物理隔离**（解析到开发库即熔断，工程纪律 1.4-14）。
- 建库脚本：`ops/init_db.sql`；schema 变更唯一入口 = **Alembic**（⛔ 禁"建表 API"改既有库）。

## 四、备份与保留期（⭐ 唯一手工备份点 = `.workbuddy/backups/`，留最近 **5** 份）

| 对象 | 怎么备 | 留多久 |
|---|---|---|
| 仓内文件 | **git**（⛔ 不手工备份；检查点提交由用户发令） | 永久 |
| 交付面（WPS 云树） | 云树自带版本历史；手工备份只进 `.workbuddy/backups/` | 留 5 份 |
| `artifacts/import_preview/` | 运行暂存（token 级） | **TTL 14 天**，月度清 |
| `artifacts/pdf/`、`exports/`、`shots/` | 运行产物 | 保留 **30 天**，月度清 |
| `artifacts/golden/` | **判据证据**（⛔ 不过期；删前必须改对应测试） | 永久 |
| `logs/` | 服务日志（10 MB 轮转 ＋ 按天 app 日志） | 保留 **30 天** |
| `i8_cookie/` | **凭证**（⛔ 不进 git） | 失效即清 |

## 五、换机 / 灾难恢复 checklist（按序）

1. 装 Python 3.13 ＋ `backend\.venv`（`pip install -r requirements.txt`，源 = 国内镜像 D10）；
2. 装 PostgreSQL ＋ `ops\init_db.sql` ＋ `alembic upgrade head`；
3. `.env`（含 `TEST_DATABASE_URL`）＋ i8 凭证（`i8_cookie/` 或重登）；
4. `ops\nssm_install.ps1` 注册服务 ＋ `ops\server_ctl.ps1 -Action start`；
5. 验证：`/healthz` · 登录 · `m03` 抓取 · **「只导出 PDF」真机一张**（LocalSystem 浏览器坑，见 §一）；
6. `git clone` 本仓 ＋ 交付面云树同步到位（⚠️ 盘符有变更前科 ⇒ 全仓 grep 旧盘符）；
7. `.workbuddy/backups/` 若迁移：只带最近 5 份。

### 五之补 · ⭐ 2026-09-24 实测补充（办公室 → 家里 · 放假 10 天那次）

**① 出发前先封存**（⛔ 否则家里拉不到这几天的工作）
```
git add -A   &&   git commit -F <msg文件>   &&   git push origin master
```
⚠️ 提交信息走**文件 ＋ `-F`**（⛔ 别内联多行 —— PowerShell 引号会打架）；
⚠️ `git add -A` 前**先审计**：`.env` / cookie / `nssm` / `.venv` / `scratch` **0 命中**才敢提交。

**② 四样必须手工带走**（⛔ 全在 `.gitignore` 里 ⇒ git 拉不到）

| # | 什么 | 在哪 | 不带会怎样 |
|---|---|---|---|
| 1 | **`.env`** ⭐ | 仓根（⛔ 不是 `backend/`） | 服务起不来 / 连不上库 |
| 2 | **库备份** ⭐ | 出发前：`"D:\pgsql\pgsql\bin\pg_dump.exe" -U <user> -d <db> --no-owner --no-privileges -f .workbuddy\backups\mtrl-db-<日期>.sql` | 家里没有真数据 ⇒ **现象复现不了** |
| 3 | `artifacts\i8_cookie\`（可选） | `artifacts\` | 要重新登录 i8 |
| 4 | Ollama 模型（可选） | `D:\dev\ollama\models` | 家里的 `ollama pull` 大概率**不通**（见 ⑤） |

> ⛔ **业务数据 / 凭据一律走 U 盘或私有渠道** —— `.workbuddy/backups/` 已被 gitignore（**不上 gitee**），
> 但别把它搬进公开网盘、更别提交进仓。

**③ 本机实况（下次换机直接抄）**
- PG = **自定义路径** `D:\pgsql\pgsql\bin`（数据目录 `D:\pgsql\data`）· 服务名 `postgresql-x64-16` · 端口 5432；
- `pg_dump` / `psql` 均为 16.4，都在那个 `bin`；建库照 `ops\init_db.sql`；
- 依赖与迁移文件都在 **`backend\`**（`requirements.txt` · `alembic.ini`）；
- ⚠️ **`venv` 不可移植** ⇒ 家里必须重建：`python -m venv .venv` ＋ `pip install -r requirements.txt`。

**④ 环境验收（四条全过 ⇒ 与办公室等价；缺一条都别急着开发）**
```
cd backend  &&  .\.venv\Scripts\python.exe -m pytest -q tests/            # 期望 rc=0
cd ..       &&  .\backend\.venv\Scripts\python.exe tools\audit\doc_audit.py        # 期望「必须修 0」
            &&  .\backend\.venv\Scripts\python.exe tools\audit\doc_audit.py --ui   # 四检全 0
            &&  .\backend\.venv\Scripts\python.exe tools\probe\_shell_smoke.py     # 真机 rc=0
            &&  .\backend\.venv\Scripts\python.exe tools\audit\acc_report.py       # 四态：绿 555 · 红 0
```
⚠️ 跑**非全套** pytest 时，`ACC_RESULTS_PATH` 要指到 `_mut_acc_results.json`（⛔ 否则冲掉权威四态）；
⚠️ 跑 `tools/mut/**`（靠 `finally` 复原的那类）⛔ **别接 `Select-Object -First N`**（掐断上游 ⇒ 靶件留坏态）。

**⑤ 换机那几条老坑（都是实测过的）**

| 坑 | 症状 | 解法 |
|---|---|---|
| 服务账户看不到用户目录 | PDF / 批量打印**全失败**，而抓取正常 | 浏览器放机器级 `C:\ProgramData\ms-playwright` ＋ 机器级环境变量 ＋ 服务上再设一份（见 §一） |
| GitHub 直连不通 | clone / 下二进制超时 | 走 `gh-proxy.com`（实测 7.8 MB/s） |
| `ollama pull` 不通 | 跑 10 分钟、模型目录 0 字节 | 魔搭 `modelscope.cn` 下 GGUF ＋ `ollama create`；或直接拷模型目录 |
| PowerShell 量行数不可信 | 同一文件数出 69 行 vs 真值 198 行 | 用 Python `len(text.splitlines())`；PS 要加 `-Encoding UTF8` |
| 改完 Python 没生效 | 看到的还是旧行为 | ⛔ 服务**无 `--reload`** ⇒ 必须 `ops\server_ctl.ps1 -Action restart` |

## 六、保留期与清理的责任

- **月度**（或换机前）：按 §四清过期件；`work/00-scratch/` 超 14 天的升档或删（`TAIL-74` 立尺子前人工自查）。
- ⛔ `artifacts/golden/` 与 `artifacts/acc_results.json` 不在清理范围（判据证据 / 权威四态）。
