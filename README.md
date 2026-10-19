# 材料报表自动化工作台

科室内部局域网工具：从i8取得材料与付款数据，处理付款台账、欠款、报表和集采台账。业务定义从需求入口读取，运行方法从部署指南读取。

## 当前状态与任务

当前部署、待验边界、交接、排期和活动票索引见 `docs/status.md`；原票仍持有任务状态与验收。执行与保存授权从 `AGENTS.md` 按动作定位。

## 一、上手与使用

首次安装、启动和恢复读 `docs/guides/deployment.md`；运行配置、服务账号和实际资源前提读 `docs/guides/operations.md`。本机凭据不入Git；服务重启、数据库写入和外部登录按当前明确授权执行。

## 二、资料分层

现行规则按职责保存在docs；活动任务与直接依赖按需读取；历史退出默认接手和普通搜索，仅在追溯时读取。材料在场或目录名为scratch均不证明可以删除。

## 三、目录地图与资料入口

| 位置 | 内容与读取时机 |
|---|---|
| AGENTS.md | Agent的操作边界与条件指针；接手时读 |
| docs/agents/ | 项目方法绑定、票协议和领域消费配置；按动作读 |
| docs/requirements.md及同名目录 | 现行业务、能力、验收与产品资料入口；改行为或验收时读 |
| docs/status.md | 当前部署、未验边界、交接与§15活动票索引 |
| docs/architecture.md及同名目录 | 当前结构、模块与刷新关系；改结构时读 |
| docs/guides/、docs/reference/ | 长期指南和按需工程参考；按主题读，逐件工程索引见docs/guides/operations.md |
| docs/adr/ | 新重要决定；旧D件在docs/adr保留来源和编号 |
| docs/archive/index.md | 历史原文、旧路径及固定SHA；只在明确追溯时读 |
| .scratch/<effort>/ | 新活动任务的必要规格、调查与证据；有实质内容时创建 |
| .scratch/tails/issues/ | 已采用的真实TAIL票仓；开销票使用既有工具 |
| .scratch/legacy-active/ | 界面整改旧件仅余原型退出清单挂起；已完主线及保留理由见本目录README.md |
| docs/agents/project-rules.md | 文件、保存、环境与真实写入的条件约束；由AGENTS按操作触发 |
| .scratch/local/、.artifacts/recovery/backups/ | 既有临时证据、恢复现场及快照；已整体迁入新位置，原文字节与恢复用途保留 |
| backend/app/、backend/tests/、backend/alembic/ | 运行代码、测试与数据库迁移 |
| skills/ | 本项目业务技能源；付款原表核对入口见 skills/payment-plan-audit/SKILL.md |
| backend/app/resources/ | 程序实际消费的模板；由资源模块定义位置 |
| delivery/ | 原型HTML、检查JS、模板及第三方原件；现行产品Markdown已迁入docs |
| tools/、ops/ | 实际工具与运维脚本；说明分别从tools/README.md与ops/README.md读取 |
| artifacts/、logs/ | 按项目真实配置保存的输出；不作为另一份规则正文 |

资料创建、活动保护、归档和恢复方式见 `docs/guides/work-records.md`；目录迁移与例外见 `docs/adr/0033-document-layout.md`和workflow §六。

## 四、命名与格式规范（⛔ 别自创；`T12` 机器守）

| 类型 | 命名 | 放哪 |
|---|---|---|
| 当前状态 / 排期 | 固定入口 | `docs/status.md`；活动票仍以原票为准 |
| 已销号索引 | 既有短索引追加 | `docs/archive/tickets/index.md`；不保存另一份当前状态 |
| 历史来源 | 按主题保留原名与来源 | `docs/archive/`；既有仓外原文从来源索引追溯 |
| 任务证据 | 按实际需要 | `.scratch/<effort>/evidence.md`或原票Comments；旧逐日日志在docs/archive/journal |
| 实测结论与工程参考 | 按主题命名，如sticky-total-row、template-export、thresholds | `docs/reference/`；成立前提与来源随正文保留 |
| 索引 / 地图 | `README.md` | 该层根的目录 |
| **agent 入口 / 制度页** | 入口 = 固定名 `AGENTS.md` · 制度页 = 固定小写英文名 | 仓根 · `docs/agents/`（2026-10-15专项迁移首批；workflow为执行绑定，issue-tracker为票协议） |
| 新任务规格与调查 | spec.md或必要主题件 | `.scratch/<effort>/`；旧设计的真实余项从.scratch/legacy-active/README.md定位 |
| 实验记录 | 必要持久证据 | 所属任务evidence.md；运行产物仍按实际配置 |
| 问题排查 | 依用途保存 | 活动任务中保存；结束且有独有价值再归档 |
| 决策记录 | 已有 `D<编号>-<主题>.md` 保持原名；新ADR按编号与主题命名 | 已有件保留 `docs/adr/`；新目录决定为 `docs/adr/0033-document-layout.md` |
| **尾巴票** | `TAIL-<编号>-<短名>.md` | `.scratch/tails/issues/`（⭐ 2026-10-04 `TAIL-225` 起 —— 一张票一个文件；**索引 = 计划 §15 一行一票**；⭐ 用 `tools/oneoff/_tail_open.py` 建，⛔ 别手抄） |
| 临时件 | 任务内必要临时文件 | 新任务.scratch/<effort>；旧00-scratch的恢复和活动材料继续保留，日期只产生复核候选 |
| 现行权威 | 固定职责及主题名 | 需求docs/requirements.md及分册；状态docs/status.md；架构docs/architecture.md；指南、参考、协议各在docs对应目录 |
| 手工备份 | `YYYYMMDD-HHMM_<对象名>/` | `.artifacts/recovery/backups/`（**备份唯一落点**，留 5 份；超出的 ⇒ 移进 `_旧快照归档-YYYYMMDD/`，`T20` 守上限并照实报归档件数）。⚠️ **一天做多批时**（如逐页推进 11 批）：**同一轮工作只保留当日末个快照** —— 中间批次⛔ **不再各建目录**，改在当批设计件里写**「改前差异说明」**（2026-09-29 实测：一天造了 **16 个**目录 ⇒ `T20` 只能**事后报警**、管不了「每批都建」这个**动作**）⭐ **何时清** = **备份数量超线时**复核一次（超线就移/清；上限数字见 `docs/reference/thresholds.md`，⛔ 不在此处抄） |
| **产品资料改前备份** | `docs/requirements/` 正文及delivery原型与说明书的改前快照 | `.artifacts/recovery/backups/`；文件本身由 Git 版本管理，手工快照只用于需要快速恢复的批量编辑 |
| 产物 md | 仅工具生成物白名单（当前：`变异覆盖台账.md`） | `artifacts/` |

**格式三条**：① 每份文档**开头必须写**"读者是谁 / 回答什么问题 / 什么时候读"（work 区另加"状态 ＋ 关联 ID"）；② **跨文档引用写全路径**
（⚠️ 反引号里的仓库内路径会被 `T3` 校验，写错就红 —— 但**交付面文档不得出现 `.codebuddy/…` 路径**）；
③ **同一件事只在一处写**（真源唯一，其余给指针）。


## 五、唯一事实来源

业务含义回docs/requirements.md；当前状态回docs/status.md；任务范围、状态与验收回原票；实现结构回docs/architecture.md；重要取舍回ADR或旧D件；历史过程回来源索引。引用主人，避免复制第二份规则或手抄机器数。

## 六、核验入口

实际命令、隔离与结果保存见 `docs/guides/development-and-verification.md` §十一及 `docs/agents/workflow.md` §四；检查注册以tools为准。局部通过、人工验收、生产加载和归档分别记载。

## 七、新建与维护资料

先找现行主人；有实质新内容时按固定职责创建。新任务用.scratch/effort，重要决定用docs/adr，历史用docs/archive。现有tracker、旧D件和恢复材料遵守项目真实契约；日常维护方法按AGENTS指向个人来源。

## 八、常见定位问题

路径与字节以实际文件及检查输出为准；历史记录按其SHA和原位置解释。没有引用是调查信号，独有信息、活动用途和恢复依据核实后才能删除。
