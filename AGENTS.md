# 材料报表自动化工作台 · 给 agent 的入口（**只放指针，不放内容**）

> ⛔ **本文件是唯一入口**：一张「**你要断定的事 → 权威文件**」表 ＋ 每个指针一句话说明**什么时候去读它**。
> ⛔ **它不复述任何口径** —— 复述 = 第二套口径 = 必漂。**地图**与**给人看的现状页**仍在根 `README.md`（§〇 / §二 / §三）。
> ⛔ **它不新增分层规则**：分层 / 命名 / 落点的主人 = 根 `README.md`。本件只回答「**现在该读哪一份**」。
> ⚠️ **本仓不是 GitHub 站**（远端是 Gitee）⇒ 票走**本地 markdown**，见下面「Agent skills」。

## 口径在哪（先查这张表，⛔ 别满仓搜）

| 你要断定的事 | 权威文件 · 什么时候去读 |
|---|---|
| **现在到哪了 / 待办 / 要我验什么** | 根 `README.md` **§〇** —— ⭐ **每次接手第一份读它** |
| **上一轮干到哪、怎么接** | `.codebuddy/plans/开发计划-主文档.md` **§13.6** 表里**最新那一行** —— **接手时** |
| **还欠什么（尾巴 / 票）** | 同份 **§15** 索引 ＋ `.codebuddy/work/50-tickets/` 的票文件 —— **想开工前** |
| 业务规则 / 字段含义 / 界面措辞 | 交付面《说明书》/ `PRD/` / `MOD-*` —— **动业务行为前**（⛔ 别从记忆复述） |
| 前端界面口径（能点的怎么长 / 颜色语义） | `ops/前端设计守则-以使用用户为中心.md` —— **改前端之前** |
| 任何"上屏文字"该怎么写 | `.codebuddy/work/40-decisions/D29-文案审计口径-以熟手为准.md` —— **写字之前** |
| 某个硬数字为什么是这个值 | `ops/阈值表.md` —— **怀疑数字错时** |
| **票怎么开 / 怎么收尾** | `ops/agents/issue-tracker.md` —— **开工一张票之前** |
| 某个决定**当初为什么这么定** | `.codebuddy/work/40-decisions/D*.md` —— **想推翻它之前** |
| 每轮都要守的纪律 ＋ 用户偏好 | `.codebuddy/memory/MEMORY.md`（**每会话自动注入**）—— **动手前** |
| 工程侧底账（实测结论 / 起停 / 部署 / 架构） | `ops/README.md`（索引）—— **碰环境 / 部署 / 模块分工时** |
| "文档又多又乱 / 该并该删" | `.codebuddy/skills/docs-audit/SKILL.md` —— **这个疑问出现时** |
| 改判据 / 尺子 | `tools/README.md` ＋ 同批给**反向灵敏度** `tools/mut/_mut_*.py` —— **动判据时（⛔ 判据与靶是一对）** |

## Agent skills

### Issue tracker

票（＝本仓说的"**尾巴**"）是**本地 markdown**：**一张票一个文件**，住在 `.codebuddy/work/50-tickets/`；**索引 = 主计划 §15**（一行一票）。
开票 / 收尾 / 阻塞边的写法见 `ops/agents/issue-tracker.md`。

### Triage labels

五个角色的字符串**沿用默认**（`needs-triage` / `needs-info` / `ready-for-agent` / `ready-for-human` / `wontfix`）。
见 `ops/agents/triage-labels.md`。

### Domain docs

**单上下文**（single-context）：术语主人 = 交付面《说明书》/ `PRD/`（＋ `D29` 用词统一表）；决定 = `.codebuddy/work/40-decisions/`。
⛔ **不单建 `GLOSSARY.md`**（那会长出第二套口径；真要建由 `/domain-modeling` 按需懒建）。见 `ops/agents/domain.md`。

## 提交前（唯一入口）

```
backend\.venv\Scripts\python.exe -X utf8 tools\oneoff\_run_rulers.py --all
```

尺子**全套**（⭐ 条数以脚本输出为准，⛔ 别抄）＋ 守尺子的**变异自证** ＋ **全套 pytest**；**改过壳**再加真机 `tools/probe/_shell_smoke.py` ＋ 壳基线盖章。
⛔ **提交要用户点头** · ⛔ **交付面在仓外、只读**（`D:\工作\AI\PRD编写夹 - Workbuddy专用`，WPS 云同步会回退）。
