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

## 六、保留期与清理的责任

- **月度**（或换机前）：按 §四清过期件；`work/00-scratch/` 超 14 天的升档或删（`TAIL-74` 立尺子前人工自查）。
- ⛔ `artifacts/golden/` 与 `artifacts/acc_results.json` 不在清理范围（判据证据 / 权威四态）。
