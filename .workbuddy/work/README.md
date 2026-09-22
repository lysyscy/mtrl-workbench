# `.workbuddy/work/` —— Agent 开发工作记录分区（宪法）

> 依据：`D:\mtrl-workbench-文档架构审计-20260922.md` §四/§六（P2 根因：记录五类缺三类 ⇒ 就近乱建文件）。
> 本区 **入 git**（除 `00-scratch/`）；⭐ 开工前先看下面的"产出物 → 落点"表，**对号入座，不许先建文件再问归属**。

## 一、产出物 → 唯一落点

| 你刚产出了什么 | 不要放哪 | 放这 |
|---|---|---|
| 脑子里的构思、几条 bullet、和用户讨论的备选 | 正式文档、根目录 | `work/00-scratch/tmp-YYYYMMDD-主题.*`（**TTL 14 天**） |
| 成型方案、模块设计、A/B 对比、技术选型研讨 | artifacts、plans 活文档内 | `work/10-designs/设计-主题-YYYYMMDD.md` |
| 一次探针/实测/对比试验（成功或失败） | journal 一句话、artifacts 裸 json | `work/20-experiments/实验-主题-YYYYMMDD.md`（脚本 → `tools/probe/`） |
| 稳定可复现的工程结论 | 长期留在 experiments | 升 `ops/<主题>-实测结论.md` ＋ ops/README 加索引行 |
| 报错排查、事故复盘、用户报障闭环 | artifacts、ops/README 备注 | `work/30-troubleshooting/排查-现象-YYYYMMDD.md` |
| 用户拍板的决定（口径/技术/工作方式） | 只写进 MEMORY 或对话 | `work/40-decisions/D<编号>-主题.md`（D21 起；MEMORY 留指针） |
| 待办、尾巴、"以后再说" | 自建 TODO.md、报告结尾 | **计划 §15 台账（唯一）** —— 本区禁止第二份待办清单 |
| 当天过程叙事 | 活文档正文 | `journal/当天.md`（append-only） |
| 已完工单元的大段过程 | 继续占着计划正文 | `plans/archive/归档-类型-主题-YYYYMMDD.md` ＋ 原处指针 |
| 实验证据数据（json/xlsx/截图） | work 区、docs | `artifacts/` 既定子目录（md 在 work、证据在 artifacts，互给路径） |
| 提交信息草稿 | artifacts/commit_msgN.txt | `work/00-scratch/CB_MSG.txt`（`git commit -F` 后可删） |
| 交付面文件的手工备份 | artifacts 根、.workbuddy 根 | `.workbuddy/backups/`（留最近 5 份） |
| 环境/部署/配置/架构知识 | MEMORY 注入档 | `docs/runbook.md` / `docs/architecture.md`（随变更同批改） |
| 使用者可感知的变化 | 活文档正文 | `docs/changelog.md`（部署节点登记） |

## 二、升档 / 降档生命周期（防新区变新垃圾场）

```text
00-scratch ──14天内──► 10/20/30 升档，或删除（⛔ 不许长期停留）
10-designs ──定稿实施完──► plans/archive/归档-设计-*.md；契约级变更 ► 交付面 PRD（走改契约流程）
20-experiments ──结论稳定──► ops/<主题>-实测结论.md ＋ ops/README 索引行
30-troubleshooting ──沉淀出规则──► MEMORY / 阈值表 / 测试（档案本身保留，供复发检索）
40-decisions ──被推翻──► 只加 superseded 链接，⛔ 不改写原文
任何"留到以后" ──当场──► 计划 §15 台账（TAIL 编号）
```

## 三、红线（⛔ 全部有实证为据，见审计 P1–P6）

1. ⛔ 仓库根目录新建任何 md（唯一例外 `README.md`）；新增层级必须**先改根 README 四层表 ＋ `audit_meta.py` 白名单**，再建目录。
2. ⛔ 活文档/正式设计稿里写草稿与过程叙事（T13）。
3. ⛔ `artifacts/` 放过程类 md（设计/排查/审计/备份）—— 只许工具生成物白名单。
4. ⛔ 第二份待办/状态清单 —— 状态只信三处（acc_report / 计划 §0 / 执行情况），尾巴只信 §15。
5. ⛔ 临时件放 tools 根、logs、artifacts 根 —— 一律 `00-scratch/`；一次性工具脚本 → `tools/oneoff/`。
6. ⛔ 手工备份散落 —— 仓内靠 git；交付面备份只进 `.workbuddy/backups/`。
7. ⛔ 引用已删除文件（CLAUDE.md 教训）；搬迁当批改完全部路径（T3）。
8. ⛔ scratch 超期不清（TTL 14 天，每轮收尾自查）。
9. ⛔ work 区文档"定稿"后不升档 —— 关联 TAIL 销号当轮必须随收尾归档。

## 四、文头四行元信息（本区强制）

```
读者是谁 / 回答什么问题 / 什么时候读 / 状态（草稿·在研·已定稿·已实施·已归档）＋ 创建/更新日期 ＋ 关联 ID（TAIL/D/MOD/ACC）
```

结论性文字带 `[用户] / [交付面] / [助手自定]` 出处标记（T9 精神）；日期一律 `YYYY-MM-DD`；编号沿用 `TAIL-/D-/MOD-/ACC-`，⛔ 不另造前缀。
