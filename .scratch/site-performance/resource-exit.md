# 资源收尾（最终修复 d5a97eaf 之后）

只做证据保全、组结项登记与书面交接。未改产品、未启动 preview/DB、未操作 Git、未删除任何工作树或组内容。

## 1. 必要保全（在 `site-performance-readiness-20261103` 组内 lease 读写）

新增目录 `files/reports/resource-exit/`（9 个文件，62 KB）：

| 路径 | 内容 |
|---|---|
| `base-run/version.public.json` | build 身份：`index_sha256 b161ce3e…f1e4`、`source_commit 3c5712ed…`、`prepared_at`、`diagnostic_instrumentation false`、`package_manager pnpm@12.15.0`、39 个资产 sha256、`frontend_sources` 计数 115 + 整体 digest `f745e7b4…9d0d` |
| `base-run/real_owner.public.json` | `status stopped-disposable`、`disposable true`、`preserve_schema_on_stop false`、`synthetic false`、`database mtrl_workbench_test`、`host 127.0.0.1`、`port 8065`、两侧 commit、`revision mechauto261028`、`started_at`/`stopped_at`、schema 前缀校验 |
| `base-run/typecheck.log` + `build.log` | 427 B / 6894 B |
| `check-run/version.public.json` | `index_sha256 93bca6e8…4df99`（build-08）、`source_commit 78c79c8a…`、其余同上 |
| `check-run/real_owner.public.json` | 同字段，`started_at 2026-11-03T02:57:56Z`、`stopped_at 2026-11-03T02:58:58Z` |
| `check-run/typecheck.log` + `build.log` | 15 B / 6937 B |
| `receipt.json` | 两 run 的上述摘要 + 源文件 hash 回执 + 三棵树的 HEAD + candidate `git status` |

**刻意未复制**（私有/无关）：`cookie_name`、任何 Cookie/Token 值、`process`（命令行）、`schema` 全名之外的连接信息、`product_sources`/`product_digest`（仅在 `receipt.json` 里留 digest）、`preview-copy-verification.json`、`package-manager.log`、`logs/frontend_rewrite_397_*` 各 schema 日志目录，以及整套 build 产物与业务原件。生成脚本 `files/readiness-resource-exit.py`；两处 JSON 已 grep 确认不含 `cookie_name`/`process`/`product_sources`/`product_digest`，两份日志对 `password|token|cookie|dsn|postgresql://|secret` 命中 0。

## 2. 三文件 hash 回执（主根 = candidate = 提交 d5a97eaf）

| 文件 | 工作树 sha256 | 换行 | 提交 blob sha256 |
|---|---|---|---|
| `apps/frontend/src/page-surface.tsx` | `ef86ad2f885975e3a2e54cc99e5bff8f11a661c04040ed666f81247c3d3d68fe` | CRLF | `ca190a0d…68fe`(LF 归一后) |
| `apps/frontend/src/style.css` | `e6628b2afe90394891c0cefc4217976101b823a4c661ef9a82b286e285889e01` | CRLF | `1e6d362f…2b03`(LF 归一后) |
| `apps/frontend/tests/test_first_display_retained.py` | `a6ca49e2baf0e87a15d2d80c727070806229ae3baf1ffbc2ed6d75cdc12f204b` | LF | `a6ca49e2…204b`(逐字节相同) |

- 主根与 candidate **逐字节相同**（三项均 `main_equals_candidate_bytewise=true`）。
- 两处 `.tsx`/`.css` 的 blob sha 与工作树 sha 不同，仅因 `core.autocrlf=true`（工作树 CRLF、仓库 LF）；LF 归一后完全一致，非内容差异。
- 三文件均已包含在 `d5a97eafad676f45f346a1df75e4c35bab917cdd`（`in_commit=true`）；主根 `git status` 对这三项为空。
- **候选 WIP 只有这三个路径**：`M apps/frontend/src/page-surface.tsx`、`M apps/frontend/src/style.css`、`?? apps/frontend/tests/test_first_display_retained.py`，无第四个未知唯一文件。

## 3. 两物理根的本轮 group 枚举（只读，未改父组 owner）

**regular** `C:\Users\Administrator\AppData\Local\AgentArtifacts\projects\mtrl-workbench`（`.lifecycle.json` 自指，已登记）

| group | 记录 owner | 结项前 state | 结项后 | 文件/inventory | expires_at |
|---|---|---|---|---|---|
| site-performance-first-wave-20261102 | dsh-tail464 | active | **closed** | 64 / 64 | 2026-12-03T03:09:21Z |
| site-performance-tail465-20261103 | dsh-tail465 | active | **closed** | 180 / 180 | 2026-12-03T03:09:21Z |
| site-performance-tail468-20261103 | dsh-tail468 | active | **closed** | 8 / 8 | 2026-12-03T03:09:22Z |
| site-performance-tail469-20261103 | dsh-tail469 | active | **closed** | 14 / 14 | 2026-12-03T03:09:22Z |
| site-performance-tail470-20261103 | dsh-tail470 | active | **closed** | 31 / 31 | 2026-12-03T03:09:23Z |
| site-performance-tail471-20261103 | dsh-tail471 | active | **closed** | 12 / 12 | 2026-12-03T03:09:23Z |
| site-performance-readiness-20261103 | dsh-readiness | active | **closed** | 312 / 312 | 2026-12-03T03:09:23Z |

按工具 `close --group <id> --days 30` 逐组执行，均 EXIT=0；只设到期时间，**不删除任何内容**。7 组 `hold` 均为 null、无活跃租约（我已先退出那份 lease）；结项后逐组重算磁盘散列与 inventory 完全一致（missing/extra/diff 全 0）。`000435-920925-39732`、`042326-438996-30748`、`045821-303250-24944` 在此根**不存在**。

**AppX LocalCache** `C:\Users\Administrator\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\AgentArtifacts\projects\mtrl-workbench`（`.lifecycle.json` 声明的 root 是上面那条 regular 路径，故该物理根**不是**已登记 root，工具 `check --root` 返回 `invalid enrollment`）

| group | 记录 owner | state（未改） | 文件 | expires_at |
|---|---|---|---|---|
| site-performance-first-wave-20261102 | site-performance-controller | active | 7（`files/controller/*`） | 无 |
| 000435-920925-39732 | backend-verify | closed | 2 | 2026-12-02T16:04:50Z |
| 042326-438996-30748 | backend-verify | closed | 2 | 2026-12-02T20:23:43Z |
| 045821-303250-24944 | backend-verify | closed | 2 | 2026-12-02T20:58:33Z |

此根的 tail465/468/469/470/471/readiness **均不存在**；三个 `backend_verify` 组已是 closed（他人/主控 owner），我只记状态未动。AppX 的 first-wave 记录 owner 为 `site-performance-controller`、`state=active`：它属于主控首轮，**不在我可结项范围**（该根未登记且 owner 非我），保留待主控处理。

## 4. 遗留与交接

- **未删遗留**：上述两棵物理根的所有组内容完整保留；AppX first-wave（controller，active）与三个 backend-verify closed 组原样。两个更早的 disposable schema `frontend_rewrite_397_48c7dd99…`、`frontend_rewrite_397_68b8838c…` 按上一轮结论保留未动（无法证明本会话创建）。
- **两冻结树仍由主控移除**：`var/worktrees/site-performance-base-20261103`（HEAD `3c5712ed…`，干净）与 `var/worktrees/site-performance-check-20261103`（HEAD `78c79c8a…`，保留上述三文件 WIP 差异）我**都未删除、未改 Git**。
- 运行时现场：8065 无监听、`/visual-version` 无服务、`var/state/react-writable-preview/current.json` 不存在。
- 未触碰：未登记事故散件、凭据原始日志、油卡相关组（`oilcard-*`）、生产/public/8000、i8 与任何外部或业务写入。

## 5. 主控最终退出（11:13–11:14）

上述第3–4节是DSH交接时状态。主控通过Codex自身路径映射，在同一标准项目入口以canonical root访问并先核`owner=site-performance-controller/state=active`，随后成功close首轮7文件组，回读`state=closed`，到期`2026-12-03T03:13:16.949968+00:00`。未修改登记根或owner，也未删组内容；DSH从AppX物理路径直接调用得到invalid enrollment的结果仍属实，不能由此推导Codex原入口不可结项。

主控逐棵核绝对目标在`D:/dev/mtrl-workbench/var/worktrees`、HEAD及实际差异；candidate仅3个定稿文件，均与已保存`d5a97eaf`在LF归一后相同。递归检查仅有各自`apps/frontend/node_modules`一条Junction，目标为主根依赖；先以`os.rmdir`只移除链接，再用`git worktree remove --force <exact-path>`退出两棵本轮临时树（含已结束构建），均退出0且目录不存在。主根依赖仍存在；油卡树未操作。必要证据已在前述受管组和Git保全。

产品提交`d5a97eafad676f45f346a1df75e4c35bab917cdd`正常推送后远端相等，[Frontend checks](https://github.com/lysyscy/mtrl-workbench/actions/runs/41570045739)成功。最终结项文档另行保存并核远端，不重跑产品测试。
