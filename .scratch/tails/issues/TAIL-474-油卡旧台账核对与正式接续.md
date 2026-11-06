# TAIL-474: 油卡旧台账核对与首次正式接续

**What to build:** 油卡旧台账核对与首次正式接续

**Blocked by:** None

**Status:** needs-info

- [ ] 复核既有170项核对问题和309条待核来源及原件版本；明确接续期间、期初、账户/项目归属、旧费用身份与旧手填总额，逐项记录用户确认及依据，未确认项保持待核且不计账。
- [ ] 沿下述既有接续入口和稳定来源身份，先验证核对结果及拟写入清单；只取四张活动表，排除存档和临时区，已有PDF只补关联不重复记开票，保原件及人工更正。
- [ ] 获得本批次明确业务确认及正式接续写入授权后，使用已核来源与目标、恢复点执行确认范围；来源重跑幂等，未确认项目保持待核，保护现有正式记录与试用修改。
- [ ] 正式接续后读回核对账务、期初、发票及分配、特殊费用和会议大表及实际导出；记录来源与批次身份、金额一致性、剩余待核项及原件保全，分别报告准备、批准、写入和核验结果。

## Comments

2026-11-03 · Created.

2026-11-03 · 用户要求将已上线油卡的真实旧台账接续独立开票。本轮仅登记任务；needs-info表示等待接续期间、归属及旧金额等业务确认，尚未授权本票执行正式数据写入。油卡功能已上线，不因接续待办重新打开开发总票。

2026-11-06 · 已完成的油卡开发及上线不再作为本票的活动依赖，故Blocked by改为None；业务阻塞仍由needs-info及上列验收项持有。按用户要求，接续所需信息集中到本票，原开发effort和终态票退出，不据其存在维持整条历史依赖链。本次仅收敛文档，没有读取/导入业务原件、改试用数据或执行正式接续。

## 接手续用的最小信息

- 业务主人：[油卡需求](../../../docs/requirements/oil-cards.md#首次接续)。待确认的是接续期间及期初截至月、项目/账户和卡片归属、旧费用身份、旧手填总额及PDF对应关系；未确认项保持待核且不计账。
- 来源工作簿：`D:/工作/材料/台账/油卡/外租机械加油汇总清单（第四工程公司）.xlsx`，PDF在同级开票目录。仅四张活动表，保原始标记；不运行会重命名原件的旧脚本。
- 既有核对表：`D:/dev/mtrl-workbench/.artifacts/active/oilcard-implementation/20261031-463/outputs/01a19021-8c69-7053-a749-65fc1cb7b4bd/油卡接续核对.xlsx`。2026-10-31准备时为170项问题、309条全pending来源，数字仅是历史基线；接手先核实际版本及填写进度，不把旧空白状态当作重置依据。
- 私有来源依据：上述`20261031-463/reports/`下的`source-inventory.json`、`source-rows-private.json`、`pdf-facts-private.json`、`legacy-totals.json`、`project-candidates-private.json`；已编译清单在`20261031-463/work/continuation-manifest-private.json`。这些是接续依据，不能随开发文档退出删除或按普通临时文件重建覆盖。
- 稳定来源身份为`fourth-company-oilcard-ledger`配原表sheet/row，文件hash只核来源版本。现有[接续工具](../../../tools/oneoff/oilcard_continuation.py)仅提供只读manifest编译与登记可丢弃副本drill，没有正式写入模式。不能把隔离演练命令当正式接续入口；正式方案和目标须在得到业务确认及写入授权后核定。
- 已有PDF优先补关联，不重复记金额；同源重跑幂等，来源、决议或目标被人工更正时保现值。无日期/票号/归属的记录继续待核，不造日期、票号或主卡独立账务。旧完整用油金额先核自动部分和自定义差额，不能直接叠加。

## 保留的试用与恢复入口

这些是本机旧登记，2026-11-06仅核文件存在，不据旧PID或ready状态声称实例当前在线，未核数据库现值：

- 用户试用run：`.artifacts/active/oilcard-implementation/20261031-user-preview`；owner为`reports/real_owner.json`，登记schema为`frontend_writable_51fcec25f7044cea8202b5afcece03b7`、revision `oil464261031`、`preserve_schema_on_stop=true`。当前身份及操作沿[预览指南](../../../docs/guides/frontend-preview.md)核验。
- 同run恢复点：`recovery/before-oil464261031.dump`及`recovery/before-ui-redesign-20261031T082819053931Z/`；构建历史位置为`.artifacts/active/oilcard-implementation/20261031-ui-redesign/work/build-04`。用户试用记录、恢复点与原件保留，不重copy-source、seed或丢schema；升级仍走已登记existing流程。
- 更早原型owner：`.artifacts/active/oilcard-interaction/20261030-dsh/reports/owner.json`。是否仍有恢复用途须由实际消费者核定，本次未清理。

如需重读开发演练细节，使用[Git中的463记录](https://github.com/lysyscy/mtrl-workbench/blob/040bbdc2b9462a264490de2e9fd5add19ba96ffe/.scratch/oilcard-management/evidence/TAIL-463.md)。日常接续直接从本票及当前需求进入，不要求恢复整个旧effort。
