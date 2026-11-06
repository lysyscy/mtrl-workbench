# 质量路线候选验证

2026-11-06。此记录按实际候选阶段追加；基线及旧证据见 [frontend-evidence](frontend-evidence.md)，整改范围和停止条件见 [decisions](decisions.md)。

## 第一候选：恢复回归通过，显示验收暂停

运行前后 `registered_preview()` 核相同进程、HTTP 身份、产品输入、完整构建及 HTML，并核 `disposable`。候选 `127.0.0.1:8065` 使用 `mtrl_workbench_test` 的 `frontend_rewrite_397_81e54d4e5dbe4334ad475bf6295ddc91`，revision `oilmerge261103`，`synthetic=false`、`read_only=false`；后端与构建清单的 `source_commit` 均为 `1ae1543c526e8fd24c974341b0873e13d966bfff`，构建包含本批未提交产品输入，实际产品指纹 `c1204478e55062b5d4afa0d4092b2ae8f31836e3c8edbcf4247f94895c8f2214`，index SHA256 `8981848355cbb693ca82b1d2a1010da34a600ec842d96d89f3fe259427925538`。主控另持 160 项 unit、typecheck 与生产构建回执。仅在可丢弃副本写测试规则及临时账号偏好；未调用真实 i8、打印或操作正式数据。

现有项目 Python Playwright 回归在初始字号 1、1920×1080 下运行，退出 0，`3 passed in 34.72s`：

1. `test_rules.py::test_actual_rule_add_lost_response_never_resubmits`：同步双点只发一笔真实写入；成功丢回执后不能再次提交，分别核无匹配、读取失败、切页保留、实际重读及人工结束；原通知书剔除标记不变。
2. `test_rules.py::test_rejected_rule_stays_editable_and_confirmed_rule_retries_only_the_read`：真实拒绝保留可编辑输入；真实成功但列表读取失败只重读，不重投。
3. `test_report_maintenance_read_lanes.py::test_bad_project_pending_row_only_fails_its_read_lane`：注入坏 200 的 `items:[null]`，待办局部报错，项目列表仍在；解除注入后局部重试，列表节点保持。

测试依原 `registered_preview`/`disposable` 夹具。临时 pytest 插件仅为失败截图标签加 `candidate-` 前缀，不修改产品、夹具逻辑或断言。另对一笔真实成功的规则新增只在浏览器将回执替换为 HTTP 200 `{}`：真实新增 1 条、请求 1 次，界面保留只读草稿和“提交结果待核对”，无新增按钮或假成功；这只证明指定故障条件。截图 `candidate-rule-incomplete-receipt-072033-103524.png` 已实看。

随后仅在本副本账号将字号从 1 设为 1.12 并读回；下列桌面为 headless Chromium `156.0.8078.4`、1920×1080 CSS 像素、DPR 1，窄窗为 390×844。截图含真实副本画面，只留本机受管组。

### 发票子表

- 同基线选样路径：274 条合同中检查 7 个非空候选，取真实 3 行供应商发票。三条金额、合计与 API 一致，摘要与新增按钮可见；等待动画结束后，明细框宽 638.64px，日期/金额/操作列约 `189/268.80/179.19px`，合计 636.98px，空白约 0.3%。基线分别为 1,153.84px 框、311px 列和约 73% 空白。截图 `candidate-invoice-default-072221-763052.png` 已由主控实看。
- 金额列自动 268.80px，实际拖至 50px、关闭重开稳定 50px，恢复自动后回 268.80px 且该偏好移除。用户主动缩窄导致的裁剪符合现行手调规则。首次重开立即读取 `bounding_box` 的断言失败：弹窗入场缩放尚未结束；等待动画后同操作通过，原失败截图/报告保留。
- 当前可得唯一标签合同中最长供应商 17 字，在摘要中完整换行；付款子表仍约 1,209.59px，显示结算摘要、引用及新增动作；展开贸易公司列后，真实贸易发票 2 行、摘要、超额警示和新增入口可见，合计与 API 一致。更长来源名称未以造数冒充真实样本。
- **窄窗反例**：390×844 下弹窗宽 342px，正文可纵向滚动，表格有 16px 横向滚动条；初始“全部按钮完整”的判断撤回。正文滚到底时纵向偏移最多 1px，第三行删除按钮约 y=544.22–575.58，其底部 y=573.58 实际命中 `ag-body-horizontal-scroll-container` 而非按钮。合计仍可见，横条覆盖按钮下沿；这不能签为完整可达。

### 月度会大表

2026-10 真实 9 行的工程用油均为待接续且金额为 null：9 个状态文字容器均为 `clientWidth=82`、`scrollWidth=82`，完整显示；用油合计及另一列代表值与 API 一致。油列自动约 92.95px，手调至 152.95px、刷新保持，再恢复自动回 92.95px 且偏好移除。当前副本 2025-12 至 2026-11 每月 9 个待接续行均无非空金额；“非空金额加待核文字”真实 GUI 组合仍缺，不能用零或模拟冒充通过。

**末行反例**：在 2026-10 桌面页滚到底后，末行开工时间的带入标签约 y=968.38–1010.69，横条约 y=999.67–1015.67；标签底部 y=1008.69 实际命中横条而非标签。末行几何框与合计相邻不足以证明内容未遮挡。候选界面 `candidate-big-last-row-visibility-073120-184230.png` 已实看。

### 临时样式诊断：仅定位，不算候选通过

浏览器内分别对发票网格和大表网格临时注入已有费用页同款 `.ag-body-horizontal-scroll.ag-scrollbar-invisible{position:static}`，未改产品源码或 owner。两个受影响横条原 class 均包含 `ag-scrollbar-invisible`、computed `position:absolute`，注入后均为 `static`。

- 发票 390×844：表框高度不变，正文最大滚动从约 1px 增到 17px，横条移到合计之后；滚到底并横到右侧后，末行删除按钮上/中/下三点均命中按钮。合计与 API 一致；新增按钮滚入可视区后启用且三点可命中。诊断截图 `candidate-invoice-injection-after-073252-124872.png`、`candidate-invoice-injection-action-073449-142110.png`。
- 大表：自然高度由 906.39px 增到 922.39px，增加 16px 横条自身空间，页面可多滚 16px；末行与合计仍相隔 1px，带入标签上/中/下三点均命中标签。诊断截图 `candidate-big-injection-after-073346-895252.png` 已实看。

两个诊断只说明当前浏览器注入下的因果关系。主控选择正式改动时把发票规则进一步限定到独立发票弹窗，避免影响嵌入式合同编辑器；待停止此副本、修改源码及重新构建后，须在新候选复验两处实际滚动条、末行命中、合计和动作。恢复回归及 unit 可按实际未变输入复用，不因本诊断重复全部矩阵。

### 失败与材料

第一次贸易子表脚本未先展开默认隐藏的贸易列而超时；按实际入口展开后取得上述真实结果。窄窗初始几何脚本假定了当前 AG 不存在的 viewport 类，导致 null 异常；后续按真实网格及 `elementFromPoint` 核出遮挡。两者属于脚本前提错误，原报告和失败截图保留。

本轮受管组 `C:/Users/Administrator/AppData/Local/AgentArtifacts/projects/mtrl-workbench/groups/quality-candidate-20261106/files` 中，`reports/candidate-recovery-tests.log`、`candidate-rule-incomplete-receipt.json`、`candidate-invoice-display.json`、`candidate-invoice-followup.json`、`candidate-trade-narrow.json`、`candidate-invoice-narrow-body.json`、`candidate-big-display.json`、`candidate-big-last-row-visibility.json`、`candidate-big-oil-coverage.json`、`candidate-invoice-overlay-injection.json`、`candidate-invoice-injection-actions.json`、`candidate-big-overlay-injection.json` 分别保存原始结果；对应截图和身份元数据在 `screenshots/`。本代理所有浏览器 context 已关闭，结束身份已复核并通知主控可退出；服务、可丢弃 schema 与组租约由主控持有。未在此阶段自行更改产品或永久测试。

## 最终候选：两处真实构建复验通过

2026-11-06，未注入样式。`registered_preview()` 核实可丢弃副本 `127.0.0.1:8065`：数据库 `mtrl_workbench_test`，schema `frontend_rewrite_397_3025608c198d435da18b82c6e67e5ab4`，revision `oilmerge261103`，`synthetic=false`、`read_only=false`、`disposable=true`；后端 commit `1ae1543c526e8fd24c974341b0873e13d966bfff` 加本批未提交产品输入，产品指纹 `a0e2d668fb6cd6db634e70fe5a727ca809aaf382eeae29667434058f951ec6cb`，index SHA256 `94d16c3cd988812dde34b3fd81f4d93d7cd86cd0c1eb5c8907024576ccb8b9f4`。账号字号由 1 设为 1.12 后读回；桌面 headless Chromium、1920×1080、DPR 1，窄窗 390×844。最终源码中的两条局部 `position:static` 已包含在该生产构建，不是上一节的浏览器注入。

- 发票：274 条合同中按同一选样路径检查 7 个明细，使用真实供应商发票 3 行。桌面框宽 638.64px，日期/金额/操作列约 `189/268.80/179.19px`；三行金额、合计与 API 一致，摘要及新增入口可见。窄窗表格内部宽 311px、视口 284px，可横滚；正文滚动范围 17px，滚到底并横向至右端后，末行删除按钮上、中、下三点均命中按钮。横条 computed `static`，位于合计之后；合计与 API 一致。新增按钮滚入视口后启用且三点命中，未实际新增。正文及文档的滚动宽分别等于各自可视宽，未见全页横向溢出。截图已实看：`final-invoice-desktop-074106-850180.png`、`final-invoice-narrow-last-074108-244890.png`、`final-invoice-narrow-add-074109-109111.png`。
- 大表：2026-10 真实 9 行均为待接续，9 个状态容器均 `clientWidth=82`、`scrollWidth=82`，文字完整；工程用油合计、焊材累计首行及其合计与 API 一致。页滚到底时末行底缘 y=998.67、合计顶缘 y=999.67；带入标签 y=952.38–994.69，上、中、下三点均命中标签；横条 computed `static`，在合计之后 y=1039.98–1055.98。截图 `final-big-oil-074416-313142.png`、`final-big-last-074517-422149.png` 已实看。真实待接续行仍均无非空用油金额，因此金额加待核文字的组合仍未覆盖。

大表第一次末行脚本所限定的容器选择器没有匹配，金额和文字检查已完成；按 API 末行标识重新定位后，上述命中与几何检查通过。原失败和后续报告均保留，不能把定位失败误作产品失败。`reports/final-invoice.json`、`reports/final-big.json`、`reports/final-big-last-retry.json` 及截图位于 `C:/Users/Administrator/AppData/Local/AgentArtifacts/projects/mtrl-workbench/groups/quality-final-20261106/files`。手调、长名、贸易及付款子表与恢复回归沿用第一候选的有效证据；未重跑性能或整个页面矩阵。此次不代表部署或正式数据变更。

两个复验浏览器 context 均已关闭。结束时重新核对当前登记预览与桌面发票、大表末行截图元数据，进程、schema、版本、产品指纹和 HTML 构建指纹均一致，副本仍为 disposable；服务退出、schema 清理由主控负责。
