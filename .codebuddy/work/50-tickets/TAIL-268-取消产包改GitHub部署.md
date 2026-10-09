# TAIL-268: 取消产包：部署改走 GitHub 拉代码，另删 face/ 快照与 -Mode asis

**What to build:** 取消产包：部署改走 GitHub 拉代码，另删 face/ 快照与 -Mode asis

**Blocked by:** 无（TAIL-267 已销号；同日「够用即止」纪律已写进 ops/agents/issue-tracker.md §四）

**Status:** ready-for-agent

- [ ] **产包脚本已删**，且活文档/脚本里对它的引用为 0（`git grep pack` 只允许命中 `journal/` 与仓外归档件 —— 那是历史原文，不改）
- [ ] **部署入口改成 GitHub 三步**：`git clone` → 复制 `.env.example` 为 `.env` 并填 → 跑部署脚本；部署文档里**不再有任何"先改口令"的手工步骤**
- [ ] **`-Mode asis`（从包内 dump 灌库）已移除**，部署脚本只支持空库路线；文档明说"**真实恢复仍未证明**"，不许读成"部署已验证"
- [ ] **仓根 `face/` 已删**（含 `.gitignore` 那段与 `README.md` 的目录行）；跑验收面仍能用 `.env` 指向的真实交付面出四态
- [ ] 剩下的 PowerShell 件（部署 / 自检 / 服务控制）过语法与仓内路径存在性检查，且部署脚本 `-DryRun` 跑通
- [ ] `tools/audit/doc_audit.py` **必须修 0**（含 `T6` 票面在位、`T10` 注入档预算、`T23` 活机器引用面）
- [ ] ⚠️ **未证明项照实留**：每日备份 / 异盘校验 / 真实备份向隔离空库还原，仍挂 `TAIL-188`，本票**不**因删产包而宣称它们好了

---

## Comments

**2026-10-09 · 建票（agent）。** 来源：用户 2026-10-09 定「不再产包、以后上传 GitHub 做部署命令」＋ face/ 选①删干净｜不做会怎样：换机/重装仍要手工打一个包（含本机快照与 dump），目标机还得照文档先改口令｜落点：ops/pack.ps1（删）· ops/deploy_restore.ps1 · ops/deployment.md · ops/README.md · tools/oneoff/_ps_parse_check.ps1 · README.md §三/§四 · 仓根 face/ 与 .gitignore｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①产包唯一用途是换机，而落地脚本 ops/deploy_restore.ps1 已是完整流程，缺的只是代码来源 ⇒ GitHub clone 即可替代 ②asis 那条从包内 dump 灌库的分支随包一起消失，属死代码 ③face/ 零消费者（.env 的验收基线已指向真实交付面），留着等于拿过期快照当真源的风险 ④按同日「够用即止」：不为不存在的场景留机制
