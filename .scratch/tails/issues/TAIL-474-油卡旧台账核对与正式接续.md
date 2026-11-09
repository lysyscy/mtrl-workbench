# TAIL-474: 油卡旧台账核对与首次正式接续

**What to build:** 油卡旧台账核对与首次正式接续

**Blocked by:** None

**Status:** done

- [x] 复核旧核对清单和来源版本，按用户确认冻结首批账户、项目归属、日期及期初截至月。
- [x] 从四张活动表验证拟写入清单，保留稳定来源行身份。旧 PDF 留原目录，已核票面信息用于确认旧开票。
- [x] 按单独授权在正式库执行首批接续。入账前恢复点已校验并在隔离库恢复演练，同源重跑零增量。
- [x] 提交后读回账户、卡片、充值、转账、期初、发票及分配，并核总台账导出。用油联动、自定义费用和会议大表由用户另行处理。

## Comments

2026-11-03 · Created.

2026-11-03 · 用户要求将已上线油卡的真实旧台账接续独立开票。本轮仅登记任务；needs-info表示等待接续期间、归属及旧金额等业务确认，尚未授权本票执行正式数据写入。油卡功能已上线，不因接续待办重新打开开发总票。

2026-11-06 · 已完成的油卡开发及上线不再作为本票的活动依赖，故Blocked by改为None；业务阻塞仍由needs-info及上列验收项持有。按用户要求，接续所需信息集中到本票，原开发effort和终态票退出，不据其存在维持整条历史依赖链。本次仅收敛文档，没有读取/导入业务原件、改试用数据或执行正式接续。

## 正式入账与核对结果

2026-11-09 14:15 · 用户授权后将 17 个账户、134 条来源一次提交到正式库，使用稳定来源 `fourth-company-oilcard-ledger`。五个账户按旧表状态归档，89 条开票含 26 条手工登记。旧 PDF 入库为零。提交前核同源重跑，提交后以独立只读事务核验。17 个账户的累计充值及转账净额、已开和未开金额逐一与保留范围的旧表一致，总台账导出一致。

正式版本 `bd2939c0`，数据库修订 `oil474261109`。入账前恢复点 `20261109-141122-59bb1310`。本机正式回执 `.artifacts/runs/141500-493530-29116/reports/tail474-formal-receipt.json` 持有批次指纹、目标与金额明细，恢复演练回执为 `.artifacts/runs/141356-752781-36192/reports/tail474-restore-validation.json`。用户确认本票结项，后续前端打磨另行设计。

## 历史接续依据

- 业务主人：[油卡需求](../../../docs/requirements/oil-cards.md#首次接续)。本机拟接续清单保留业务裁定、原值和恢复边界。
- 来源工作簿：`D:/工作/材料/台账/油卡/外租机械加油汇总清单（第四工程公司）.xlsx`，PDF在同级开票目录。仅四张活动表，保原始标记；不运行会重命名原件的旧脚本。
- 既有核对表：`D:/dev/mtrl-workbench/.artifacts/active/oilcard-implementation/20261031-463/outputs/01a19021-8c69-7053-a749-65fc1cb7b4bd/油卡接续核对.xlsx`。2026-10-31准备时为170项问题、309条全pending来源，数字仅是历史基线；接手先核实际版本及填写进度，不把旧空白状态当作重置依据。
- 私有来源依据：上述`20261031-463/reports/`下的`source-inventory.json`、`source-rows-private.json`、`pdf-facts-private.json`、`legacy-totals.json`、`project-candidates-private.json`；已编译清单在`20261031-463/work/continuation-manifest-private.json`。这些是接续依据，不能随开发文档退出删除或按普通临时文件重建覆盖。
- 稳定来源身份为`fourth-company-oilcard-ledger`配原表sheet/row，文件hash只核来源版本。现有[接续工具](../../../tools/oneoff/oilcard_continuation.py)仅提供只读manifest编译与登记可丢弃副本drill，没有正式写入模式。不能把隔离演练命令当正式接续入口；正式方案和目标须在得到业务确认及写入授权后核定。
- 同源重跑核已入账目标，人工更正继续保留。无票号但已明确账户和金额的开票按手工登记接续，无日期的历史原样保留原标记及核定截至月。

## 保留的试用与恢复入口

这些是本机旧登记，2026-11-06仅核文件存在，不据旧PID或ready状态声称实例当前在线，未核数据库现值：

- 用户试用run：`.artifacts/active/oilcard-implementation/20261031-user-preview`；owner为`reports/real_owner.json`，登记schema为`frontend_writable_51fcec25f7044cea8202b5afcece03b7`、revision `oil464261031`、`preserve_schema_on_stop=true`。当前身份及操作沿[预览指南](../../../docs/guides/frontend-preview.md)核验。
- 同run恢复点：`recovery/before-oil464261031.dump`及`recovery/before-ui-redesign-20261031T082819053931Z/`；构建历史位置为`.artifacts/active/oilcard-implementation/20261031-ui-redesign/work/build-04`。用户试用记录、恢复点与原件保留，不重copy-source、seed或丢schema；升级仍走已登记existing流程。
- 更早的合成交互原型及专属运行资料已于2026-11-09核对后退出；用户试用、正式接续依据和恢复资料仍按上文保留。

如需重读开发演练细节，使用[Git中的463记录](https://github.com/lysyscy/mtrl-workbench/blob/040bbdc2b9462a264490de2e9fd5add19ba96ffe/.scratch/oilcard-management/evidence/TAIL-463.md)。日常接续直接从本票及当前需求进入，不要求恢复整个旧effort。

2026-11-09 · done: 2026-11-09 用户确认结项。首批 17 个账户、134 条来源已正式提交并逐账户对平，期初、开票分配及总台账导出均已读回核验。入账前备份已完成隔离恢复演练，正式回执和恢复入口见上文。用油联动及会议大表由用户另行处理。
