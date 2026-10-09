# `.codebuddy/work/` —— Agent 开发工作记录分区（宪法）

> 读者：产生或查找工作资料的agent。回答：落点与用途。何时读：产生独立工作资料或整理结构时。
> 本区 **入 git**（除 `00-scratch/`）；⭐ 开工前先看下面的"产出物 → 落点"表，**对号入座，不许先建文件再问归属**。

## 一、产出物 → 唯一落点

| 你刚产出了什么 | 不要放哪 | 放这 |
|---|---|---|
| 脑子里的构思、几条 bullet、和用户讨论的备选 | 正式文档、根目录 | `.codebuddy/work/00-scratch/tmp-YYYYMMDD-主题.*`（**TTL 14 天**） |
| 成型方案、模块设计、A/B 对比、技术选型研讨 | artifacts、plans 活文档内 | `.codebuddy/work/10-designs/设计-主题-YYYYMMDD.md` |
| 一次探针/实测/对比试验（成功或失败） | journal 一句话、artifacts 裸 json | `.codebuddy/work/30-troubleshooting/实验-主题-YYYYMMDD.md`（⭐ 2026-10-01 起 —— 原 `20-experiments` **已撤区**，`实验-` 前缀归 30 区；脚本 → `tools/probe/`） |
| 稳定可复现的工程结论 | 长期留在 experiments | 升 `ops/<主题>-实测结论.md` ＋ ops/README 加索引行 |
| 报错排查、事故复盘、用户报障闭环 | artifacts、ops/README 备注 | `.codebuddy/work/30-troubleshooting/排查-现象-YYYYMMDD.md` |
| 用户拍板的决定（口径/技术/工作方式） | 只写进 MEMORY 或对话 | `.codebuddy/work/40-decisions/D<编号>-主题.md`（D21 起；MEMORY 留指针） |
| 待办、尾巴、"以后再说" | 自建 TODO.md、报告结尾 | ⭐ **票仓 = `.codebuddy/work/50-tickets/TAIL-<编号>-<短名>.md`**（2026-10-04 `TAIL-225` 起：**一张票一个文件**；用 `tools/oneoff/_tail_open.py` 建，⛔ 别手抄）＋ **索引 = 计划 §15 台账（一行一票 · 唯一）** —— 本区禁止第二份待办清单 |
| 需要保留的当天过程证据 | 活文档正文 | `.codebuddy/memory/journal/YYYY-MM-DD.md`（append-only）；何时记录回 ops/agents/issue-tracker.md §四 |
| 已完工单元的大段过程 | 继续占着计划正文 | 退出默认阅读；是否保留独立归档按用途判断，Git已有过程不复制全文。现有仓外归档经 `.codebuddy/plans/archive/归档-留痕索引-20261005.md` 追溯 |
| 实验证据数据（json/xlsx/截图） | work 区、docs | `artifacts/` 既定子目录（md 在 work、证据在 artifacts，互给路径） |
| 提交信息草稿 | artifacts/commit_msgN.txt | `.codebuddy/work/00-scratch/CB_MSG.txt`（`git commit -F` 后可删） |
| 交付面文件的手工备份 | artifacts 根、.codebuddy 根 | `.codebuddy/backups/`；类型、保留及清理唯一规则回 README.md §四 |
| 环境/部署/配置/架构知识 | MEMORY 注入档 | `ops/architecture.md` ＋ `ops/README.md`（随变更同批改） |
| 使用者可感知的变化 | 活文档正文 | `ops/changelog.md`（部署节点登记） |

## 二、升档 / 降档生命周期（防新区变新垃圾场）

```text
00-scratch ──14天内──► 10/30 升档，或删除（⛔ 不许长期停留）
10-designs ──定稿实施完──► 稳定结论回主人，退出默认阅读；是否另存归档按用途判断
30 区「实验-」那一类 ──结论稳定──► ops/<主题>-实测结论.md ＋ ops/README 索引行
30-troubleshooting ──沉淀出规则──► MEMORY / 阈值表 / 测试（档案本身保留，供复发检索）
40-decisions ──被推翻──► 只加 superseded 链接，⛔ 不改写原文
任何"留到以后" ──当场──► 计划 §15 台账（TAIL 编号）
```

独立设计仅在执行或验收对应任务时读，已实施后结论回主人，默认路径不再引用它。历史原文可经Git恢复；需要独立仓外恢复时才用 tools/oneoff/_doc_downgrade.py，并检查活引用。

## 三、红线（⛔ 全部有实证为据，见审计 P1–P6）

1. ⛔ 仓库根目录新建任何 md（**两个例外**：`README.md`（地图 ＋ §〇 给人看的一页）· `AGENTS.md`（**给 agent 的入口**，2026-10-04 起 —— ⚠️ 原口径只许 `README.md`，那条是 **AGENT 自定**的，用户 2026-10-04 已订正））；新增层级必须**先改根 README 四层表 ＋ `audit_meta.py` 白名单**，再建目录。
2. ⛔ 活文档/正式设计稿里写草稿与过程叙事（T13）。
3. ⛔ `artifacts/` 放过程类 md（设计/排查/审计/备份）—— 只许工具生成物白名单。
4. ⛔ 第二份待办/状态清单 —— 状态只信三处（`tools/audit/acc_report.py` 的输出 / 计划 §0 现状快照 / **根 `README.md` §〇**），尾巴只信 §15。
5. ⛔ 临时件放 tools 根、logs、artifacts 根 —— 一律 `00-scratch/`；一次性工具脚本 → `tools/oneoff/`。
6. ⛔ 手工备份散落 —— 仓内靠 git；交付面备份只进 `.codebuddy/backups/`。
7. ⛔ 引用已删除文件（CLAUDE.md 教训）；搬迁当批改完全部路径（T3）。
8. ⛔ scratch 超期不清（TTL 14 天，每轮收尾自查）。
9. 定稿实施后的资料退出默认阅读；稳定结论回主人。是否另存归档按用途判断，Git已有过程不再复制全文。

## 四、文头四行元信息（本区强制）

```
读者 / 回答什么问题 / 何时读 / 状态（草稿·在研·已定稿·已实施·已归档）＋ 创建/更新日期 ＋ 关联 ID（TAIL/D/MOD/ACC）
```
> ⚠️ **措辞不许自创**：`T15` 机核的是**这四个词**（`audit_work.WORK_HEADER_KEYS` = `读者 / 回答 / 何时读 / 状态`）。⭐ 2026-10-01（`TAIL-206`）**订正**：本模板原先写「**什么时候读**」而判据认「**何时读**」⇒ **按模板写反而判黄**（5 件文档因此白挂了一条既有欠账）⇒ 现统一成 `何时读`（判据与模板必须**同一个词**）。

⭐ **「已定稿 / 已实施」两档：结论落地了就加一行「落地位置」声明**（2026-10-05 `TAIL-236` 第 3 批立；
它是 `T26` 降档判据的输入 —— ⛔ **写法只此一处定义**，别处只指路）：

```text
**落地位置**：`<结论真正落到的文件>`、`<另一处>` · 同批改：`<它变了要一起改的文件>`
```

- **它给谁看**：① `T26` —— 有了它，机器才判得出「**结论已落地** ⇒ 该降档」
  （⛔ 没这一行 ⇒ 它**一声不响**，不会替你猜）；② **接手的人 / Agent** —— 这一行就是
  「**口径主人是哪个文件 · 它变了要同批改哪几处**」的答案（⛔ 别在这儿重述口径内容 —— 那是主人件的事）。
- ⚠️ 路径一律写**反引号里的仓库内相对路径** ⇒ 同时被 `T3` 核。⚠️ 档位看分区：**本区那两区是留痕档
  ⇒ `T3` 报黄**；同一行写在 `ops/` 这类**严判档**里才是红（⛔ 别把"黄"读成"没人管"）。
- ⛔ 它**不改状态词**：五档仍是 `草稿 · 在研 · 已定稿 · 已实施 · 已归档`（本档只给后两档**补判据**）；
  ⚠️ 也**不替它规定去向** —— 归仓外 / 沉进 `ops/` / 就地标收口，看本件 **§二** 里本区那一行。

结论性文字带 `[用户] / [交付面] / [助手自定]` 出处标记（T9 精神）；日期一律 `YYYY-MM-DD`；编号沿用 `TAIL-/D-/MOD-/ACC-`，⛔ 不另造前缀。

## 五、⭐ 各只有一个家（2026-10-01 `TAIL-204` 起收口 —— 原文这里是「两个 scratch 家 / 两个记忆家」）

| 家 | 是什么 | 保留期 / 机器眼 | ⛔ 别搞混 |
|---|---|---|---|
| `.codebuddy/work/00-scratch/` | **全仓唯一的临时区**（`tmp-YYYYMMDD-主题.*` / `CB_MSG.txt` / 各尺子输出 / 一次性脚本） | **TTL 14 天** · `T14` | ⭐ **2026-10-01 起**：原仓级活区 `.workbuddy/scratch/` **已取消**（它的尺子也撤了 —— 那是**僵尸判据**）；出区就按 §一 表升档 |

**记忆与状态**（只追加要求仅适用于日志；现行主人按变化更新）：

| 家 | 是什么 | 现状 |
|---|---|---|
| `.codebuddy/memory/journal/YYYY-MM-DD.md` | **唯一**的逐日日志（append-only） | ⭐ **要写日志就写这里**；⭐ 2026-10-01 起**随仓走（进 git）**；⛔ 别在别处再开一份 |
| `.codebuddy/memory/MEMORY.md` ＋ `细则.md` | 会话**注入档** ＋ 细则分册（同目录） | 每轮必要项与专题参考；执行流程回 ops/agents/issue-tracker.md §四，业务含义回交付面 |
| `.codebuddy/plans/开发计划-主文档.md` | **唯一**活文档（状态源 ＋ §15 台账） | ⭐「给用户看的那一页」= **根 `README.md` §〇**（原 `执行情况-主文档.md` 已取消） |

## 六、资料用途与默认读取边界（TAIL-247）

本页是工作记录落点与生命周期主人；目录地图回 README.md §三。以下逐件区分现行依据与被引用的历史证据，旧“在研/待拍板”标题不代表当前排期。

| 设计件（完整路径） | 用途与阅读入口 |
|---|---|
| .codebuddy/work/10-designs/设计-开发治理整改-20261007.md | TAIL-246～249的执行与验收依据；这些票已收口，追溯该整改时才读，当前流程回issue-tracker§四。 |
| .codebuddy/work/10-designs/设计-agent阅读与核验减负整改-20261008.md | TAIL-251～253已实施规格；追溯整改依据或核验对应票时读，日常流程回issue-tracker§四。 |
| .codebuddy/work/10-designs/设计-文件拆分必要性判据-20260924.md | 仍生效的拆分判断依据；遇T5黄或决定拆件时读，取值回阈值表。 |
| .codebuddy/work/10-designs/设计-识别样本-真实模板-20260922.md | 保留的真样表识别证据；改导入识别时按测试引用查。 |
| .codebuddy/work/10-designs/设计-统一导入模块-20260922.md | 已实施的导入设计依据；追查统一导入取舍时读，业务正文回交付面。 |
| .codebuddy/work/10-designs/设计-写动作标脏数据流图-20260924.md | 写动作与刷新依赖证据；改缓存刷新时按测试引用查。 |
| .codebuddy/work/10-designs/设计-表格筛选配置化-20260924.md | 表格重构历史与遗留依据；状态回§15，不按旧批次自行开工。 |
| .codebuddy/work/10-designs/设计-前端系统性重构审计-20260928.md | 已完工审计留痕；测试仍引用，查旧重构原因时读。 |
| .codebuddy/work/10-designs/设计-口径说明折叠块-20261001.md | 已撤折叠块的处置证据；追查文案删留原因时读。 |
| .codebuddy/work/10-designs/设计-交付包与迁移-20260929.md | 旧迁移取舍与脚本旁证；当前部署回ops/deployment.md，不重问旧六问。 |
| .codebuddy/work/10-designs/设计-分层门禁一般式-20261002.md | 已实施分层门禁的推导依据；当前模块规则回ops/architecture.md与测试。 |
| .codebuddy/work/10-designs/设计-架构候选3-异常原文-20261002.md | 已收口异常文案分类证据；当前上屏文字回D29与前端守则。 |

| 决定件（完整路径） | 一句话用途；需要核对或推翻该决定时才读 |
|---|---|
| .codebuddy/work/40-decisions/D21-文档架构整改三项拍板.md | 文档架构原始裁定。 |
| .codebuddy/work/40-decisions/D22-TAIL-71不建一致性清单卡片.md | 取消一致性卡片的理由。 |
| .codebuddy/work/40-decisions/D23-通用导入改映射式.md | 采用表头映射导入的决定。 |
| .codebuddy/work/40-decisions/D24-AI建议层用本地模型.md | AI建议层技术取舍，实际待办回§15。 |
| .codebuddy/work/40-decisions/D25-过程资料导入四条口径裁定.md | 过程资料导入原始裁定，现行业务回交付面。 |
| .codebuddy/work/40-decisions/D26-导入只留通用面.md | 统一导入入口的裁定。 |
| .codebuddy/work/40-decisions/D27-交接提醒维持每轮自检.md | 交接自检与宿主hooks的历史选择。 |
| .codebuddy/work/40-decisions/D28-普通用户可改自己密码.md | 用户密码修改的裁定。 |
| .codebuddy/work/40-decisions/D29-文案审计口径-以熟手为准.md | 现行上屏文案的读者与用词主人，写上屏文字前读。 |
| .codebuddy/work/40-decisions/D30-文档治理三条决定.md | 目录骨架、状态与归档人工决策的原始理由。 |
| .codebuddy/work/40-decisions/D31-规矩成色的裁决口径.md | 规则来源及撤项登记的裁决方法；取消旧扫描不推翻此决定。 |
| .codebuddy/work/40-decisions/D索引-D1-D20.md | 早期决定导航，正文回主计划§9。 |

**历史及临时类别**：30-troubleshooting中的收款账号印错、尺子过期清单是复发排查证据；10-designs中的import-wizard-mock.html及配套CSS是导入外观快照。已取消全仓扫描调查、已被选集代码取代的设计经归档索引追溯；它们不定义现行步骤。50-tickets一张票一个文件，现行目标/状态回主计划§15，关闭票只作证据。scratch、日志、备份与产物用途及生命周期回本页§一/§二/§五与根README，不逐件抄历史文件名。
