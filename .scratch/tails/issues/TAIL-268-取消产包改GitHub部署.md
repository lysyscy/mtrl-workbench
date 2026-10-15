# TAIL-268: 取消产包：部署改走 GitHub 拉代码，另删 face/ 快照与 -Mode asis

**What to build:** 取消产包：部署改走 GitHub 拉代码，另删 face/ 快照与 -Mode asis

**Blocked by:** 无（TAIL-267 已销号；同日「够用即止」纪律已写进 ops/agents/issue-tracker.md §四）

**Status:** done

- [x] **产包脚本已删**，且活文档/脚本里对它的引用为 0（历史设计、旧操作脚本与票内过程引用保留，不作现行入口）
- [x] **部署入口改成 GitHub 三步**：`git clone` → 复制 `.env.example` 为 `.env` 并填 → 跑部署脚本；部署文档里**不再有任何"先改口令"的手工步骤**
- [x] **`-Mode asis`（从包内 dump 灌库）已移除**，部署脚本只支持空库路线；文档明说"**真实恢复仍未证明**"，不许读成"部署已验证"
- [x] **仓根 `face/` 已删**（同步 `.gitignore` 与 ROOT_ALLOW；README §三现无该目录行）；跑验收面仍能用 `.env` 指向的真实交付面出四态
- [x] 剩下的 PowerShell 件（部署 / 自检 / 服务控制）过语法与仓内路径存在性检查，且部署脚本 `-DryRun` 跑通
- [x] `tools/audit/doc_audit.py` **必须修 0**（含 `T6` 票面在位、`T10` 注入档预算、`T23` 活机器引用面）
- [x] ⚠️ **未证明项照实留**：每日备份 / 异盘校验 / 真实备份向隔离空库还原，仍挂 `TAIL-188`，本票**不**因删产包而宣称它们好了

---

## Comments

**2026-10-09 · 建票（agent）。** 来源：用户 2026-10-09 定「不再产包、以后上传 GitHub 做部署命令」＋ face/ 选①删干净｜不做会怎样：换机/重装仍要手工打一个包（含本机快照与 dump），目标机还得照文档先改口令｜落点：ops/pack.ps1（删）· ops/deploy_restore.ps1 · ops/deployment.md · ops/README.md · tools/oneoff/_ps_parse_check.ps1 · README.md §三/§四 · 仓根 face/ 与 .gitignore｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①产包唯一用途是换机，而落地脚本 ops/deploy_restore.ps1 已是完整流程，缺的只是代码来源 ⇒ GitHub clone 即可替代 ②asis 那条从包内 dump 灌库的分支随包一起消失，属死代码 ③face/ 零消费者（.env 的验收基线已指向真实交付面），留着等于拿过期快照当真源的风险 ④按同日「够用即止」：不为不存在的场景留机制

**2026-10-10 · 迁移复核轮补记（agent）。** 产品资料已迁入仓内 `delivery/` 后，本票第 4 条验收（删 `face/`）**多了一处机器耦合**，接手时按用户指示「先不动」如实留证：

- **`face/` 为什么"删不掉"**（不是文件锁）：`.gitignore` 里那行 `face/` 被 `audit_meta.py` 的 **`T25`** 核「写在 `.gitignore` 里的仓内路径必须真存在」⇒ **只删目录会立刻报红**。⇒ 删它必须**三处同批**：① 删目录 ② 删 `.gitignore` 那行（含注释）③ 删 `audit_common.ROOT_ALLOW` 里的 `"face/"`（`T24` 判根上落点取 `ROOT_ALLOW` ∪ `.gitignore`，两处都放过它）。
- **目录内容**（2026-10-10 实测）：`face/材料科业务全流程说明书.md`（243,575 B · 2026-10-01）· `face/PRD/验收/验收基线.json`（229,458 B · 2026-10-01）—— **两份都比 `delivery/` 里那份旧**（250,216 / 229,026 B 的口径以 `delivery/` 为准）⇒ 零消费者这一点已被本轮实测再次证实。
- **`ops/pack.ps1` 的 `$FaceRoot` 默认值已改**（2026-10-10 迁移轮）：原先指 `D:\dev\PRD编写夹 - Workbuddy专用`，该根现在只剩 `.workbuddy/` ⇒ 产包会报"缺件"；已改成随 `$RepoRoot` 取 `delivery`。**本票若仍要删整个脚本，这条改动随脚本一起消失**，不构成额外欠账。
- **未做**：目录未删、`.gitignore` 与 `ROOT_ALLOW` 未改（本轮明确不做）；跑四检不依赖 `face/`（`doc_audit --ui` 走 `.env` → `delivery/`，本轮实测 `_smoke 607/0` · `_doccheck 31/0` · `_links 489/0` · `_ids 121/0`）。


**2026-10-11 · 开工。** 用户授权执行交接书；HEAD=1437f141。保留既有286及主计划dirty；仅实施首次空库安装与旧快照清理，不执行真实建库/装服务，不提交。旧票两处更正：历史设计引用保留；README §三无face目录行，T25实际位于audit_drift。

**2026-10-11 · 实施与验收。** 取消产包，deploy_restore仅处理已clone仓：先核配置与SQL目标，实际安装先查同名角色/两库，再准备venv、依赖、一次性建库/迁移与原NSSM/selfcheck；Run统一非零即停并恢复工作目录/编码环境。DryRun不执行子进程或写入。旧Pack/Mode/WriteBaseline和恢复分支已撤；真实face两件确认是过期快照后已清理，delivery保留。SQL仅删除一行过时改口令注释，逐行比对执行语句与HEAD完全相同；口令实值未改。

核验（本轮独立输出均在 `.codebuddy/work/00-scratch/` 的 tmp-tail268-*，TTL 2026-10-25）：
- `powershell -NoProfile -ExecutionPolicy Bypass -File tools/oneoff/_ps_parse_check.ps1` rc=0，6份PS语法/固定路径通过；两段检查的正常/语法错/路径错隔离反例分别0/1/1。
- `powershell -NoProfile -ExecutionPolicy Bypass -File ops/deploy_restore.ps1 -DryRun` rc=0；前后.env/pip哈希、git含ignored状态、仓根条目不变；隔离无venv时不建目录。当前执行环境服务查询返回not-visible，两次相同，不能当服务健康证据。
- 隔离17项 rc=0：缺.env/模板占位、3个旧参数均拒绝；preflight/pip/init/alembic/service/selfcheck各失败时，只执行至该步、不报成功；mock成功顺序正确；真实子进程exit7时Run恢复环境/目录；PS尺子三反例。未连接生产PG；mock不是实际SQL/服务安装验收。
- `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_pipini_single_source.py -q` rc=0，2项通过、0 skip，四态输出隔离。ROOT_ALLOW隔离证伪通过：正常delivery放行、旧face拒绝、恢复旧白名单则反例被放过。
- `backend/.venv/Scripts/python.exe -X utf8 tools/audit/doc_audit.py --ui`：四检rc均0（607/31/472/121），links WARN13；首次主审计4红发生于同期其他工作文件暂时不在位，恢复后默认doc_audit rc=0，必须修0、疑似52。历史设计4黄保留，不为旧路径篡改历史。
- `backend/.venv/Scripts/python.exe -X utf8 tools/probe/_audit_face.py` rc=0，必须修0/疑似0；`tools/audit/acc_report.py` rc=0，644绿/0红/0待建/0未绑定，是既有账可读取，未刷新全套业务结果。
- 影响选择器只用于查看影响：首次凭据文件保护拒绝；确认SQL仅删注释后，按明确路径查询提示5项待调查。已逐一核清：部署与PS检查由上述隔离执行覆盖；pack现行调用随部署入口删除；gitignore/ROOT_ALLOW唯一行为消费者为T24/T25，由doc_audit和隔离证伪覆盖。未改审计算法或业务，不按共享模块名触发全套pytest/真机壳。

边界：没有真实新机/隔离PG首次部署、没有真实NSSM/selfcheck运行，故实际Skip未知；每日备份/异盘/真实恢复仍未证明。已公开SQL口令风险独立保留于ops/deployment.md §二，未旋转。未调用code-review（交接已有定点审查，局部核验足够），未提交/推送。HEAD从1437f141变为12648f1是同期TAIL-286会话提交，本轮未包含其改动；既有backend/.codebuddy/保留。最终销号后再核T6和本轮字节。

**最终收尾回执。** 销号后doc_audit rc=0（必须修0/疑似52），8件文本及SQL字节检查rc=0，git diff --check rc=0；字节工具不接受无后缀.gitignore，未将该次拒绝算通过，其改动仅删原有3行。最终HEAD=12648f1f064d90e61f81ddcaf9bb9fed0f264aec；共11个版本控制文件变更（含删除），无提交。相关检查单次均不足一分钟；未跑全套pytest/壳检查，未调用code-review。

**2026-10-11 · 用户授权提交推送。** 范围为本票11个版本控制文件；复用已完成的PS/隔离负例/交付面与局部pytest证据。提交运行现有pre-commit钩子；SQL只删过时注释，执行语句与口令实值保持，backend/.codebuddy/不入提交。真实部署和恢复仍未验。
