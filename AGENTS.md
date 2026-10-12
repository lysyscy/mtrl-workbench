# 材料报表自动化工作台 · 给 agent 的入口（**只放指针，不放内容**）

> ⛔ **本文件是唯一入口**：一张「**你要断定的事 → 权威文件**」表 ＋ 每个指针一句话说明**什么时候去读它**。
> ⛔ **它不复述任何口径** —— 复述 = 第二套口径 = 必漂。**地图**与**给人看的现状页**仍在根 `README.md`（§〇 / §二 / §三）。
> ⛔ **它不新增分层规则**：分层 / 命名 / 落点的主人 = 根 `README.md`。本件只回答「**现在该读哪一份**」。
> ⭐ 仓库与现行交付资料一并放在 GitHub；票仍走**本地 markdown**，见下面「Agent skills」。

## 口径在哪（先查这张表，⛔ 别满仓搜）

| 你要断定的事 | 权威文件 · 什么时候去读 |
|---|---|
| **目录职责 / 现行文档用途 / 历史资料在哪** | 根 `README.md` **§三** → `ops/README.md` 与 `.codebuddy/work/README.md` **§六** —— **找资料或检查读取范围时** |
| **现在到哪了 / 待办 / 要我验什么** | 根 `README.md` **§〇** —— ⭐ **每次接手第一份读它** |
| **上一轮干到哪、怎么接** | `.codebuddy/plans/开发计划-主文档.md` **§13.6** 表里**最新那一行** —— **接手时** |
| **还欠什么（尾巴 / 票）** | 同份 **§15** 索引 ＋ `.codebuddy/work/50-tickets/` 的票文件 —— **想开工前** |
| 业务规则 / 字段含义 / 界面措辞 | `delivery/材料科业务全流程说明书.md` / `delivery/PRD/` / `MOD-*` —— **动业务行为前**（⛔ 别从记忆复述） |
| 前端目标、布局、交互与视觉验收 | `ops/前端设计守则-以使用用户为中心.md` **§0 → §9** —— **改界面或处理显示／交互报障之前** |
| 任何"上屏文字"该怎么写 | `.codebuddy/work/40-decisions/D29-文案审计口径-以熟手为准.md` —— **写字之前** |
| 某个硬数字为什么是这个值 | `ops/阈值表.md` —— **怀疑数字错时** |
| **日常改动怎么做 / 何时用 skills / 核验范围 / 票怎么开收 · 提交前跑什么** | `ops/agents/issue-tracker.md` **§四**（流程）＋其余节（票协议）；运行命令见 `.codebuddy/memory/IDE-细节.md` **§十一** —— **开始改动 / 提交之前** |
| 某个决定**当初为什么这么定** | `.codebuddy/work/40-decisions/D*.md` —— **想推翻它之前** |
| 每轮都要守的纪律 ＋ 用户偏好 | `.codebuddy/memory/MEMORY.md`（**每会话自动注入**）—— **动手前** |
| 专题实现约束 | `.codebuddy/memory/细则.md` 的对应标题 —— **涉及打印、主题、历史数据、配置出口、模块搬运或判据时**先取标题，再读命中小节；业务含义仍回 `delivery/` 主人 |
| 壳工程机制与共享调用 | `.codebuddy/memory/IDE-细节.md` **§十 / §十五 / §十六** —— **改适配、监听、重画或共享调用时**；交互与视觉验收仍回前端守则 |
| 工具或脚本编辑 | `.codebuddy/memory/细则.md` **§廿三** ＋ `tools/README.md` —— **改Python/PowerShell、处理编码或文件操作时**取对应项；大件结构可用 `tools/oneoff/_skeleton.py` |
| 工程侧底账（实测结论 / 起停 / 部署 / 架构） | `ops/README.md`（索引）—— **碰环境 / 部署 / 模块分工时** |
| **文档体系本身怎么组织 / 某条口径住在哪 / 一件东西能不能删** | `ops/docs-governance.md`（⭐ **总图** · 只放总图与指针，⛔ 不重述条文）—— **建新文档 / 归档 / 动结构之前** |
| "文档又多又乱 / 该并该删" | `.codebuddy/skills/docs-audit/SKILL.md` —— **这个疑问出现时** |
| 改判据 / 尺子 | `tools/README.md` ＋ `ops/agents/issue-tracker.md` §四 —— **改检查入口时定向自检，反例按实际风险选，不强制每条新增测试另配脚本** |

## Agent skills

### Issue tracker

票（＝本仓说的"**尾巴**"）是**本地 markdown**：**一张票一个文件**，住在 `.codebuddy/work/50-tickets/`；**索引 = 主计划 §15**（一行一票）。
开票 / 收尾 / 阻塞边的写法见 `ops/agents/issue-tracker.md`。

### Triage labels

五个角色的字符串**沿用默认**（`needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`）。
见 `ops/agents/triage-labels.md`。

### Domain docs

**单上下文**（single-context）：术语主人 = `delivery/材料科业务全流程说明书.md` / `delivery/PRD/`（＋ `D29` 用词统一表）；决定 = `.codebuddy/work/40-decisions/`。
⛔ **不单建 `GLOSSARY.md`**（那会长出第二套口径；真要建由 `/domain-modeling` 按需懒建）。见 `ops/agents/domain.md`。

**提交与推送**：执行口径见 `ops/agents/issue-tracker.md` **§四「提交与推送」**；凭据（`.env`）不提交 —— `ops/hooks/pre-commit` 会拦。
