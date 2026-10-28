# i8 接口契约

本文件统一收录本项目已探测接口。业务意义见 [需求](../requirements.md)，封装复用 backend/app/mod02_i8/client.py 与对应 source。下列既有请求形态在2026-09-15/17样本核过；后续采购应付/附件以各节日期和范围为准。旧素材仅作旁证，不覆盖实测纠正。接口变化/新输入按实际影响复验；历史成功不证明当前会话、权限或分页完整。

纯 HTTP 登录使用 SM2/Cookie；Cookie状态由本机受保护位置保存，登录策略见下节。通知书数据来自审批金额而非i8付款事实。

## 〇、统一收录与调用

[用户·2026-10-23] 本文件是本项目 i8 已探测接口的统一收录入口。调用或继续探测前先查本文件与现有接入封装；确认缺口后再探测。

- 接口完成与用途相应的验证后，在本文件按业务归类收录：用途、HTTP 方法与路径、必要参数及组织范围、关键响应字段、会话与读写副作用、验证日期和适用边界、已有调用封装位置。分页、附件或业务写入按实际涉及的行为验证，不统一扩展测试矩阵。
- 尚未完成验证的接口标为“待验证”，注明已知部分和缺口；仅探测成功不能登记为可稳定调用，文档收录也不代表已接入产品。
- 可复用调用沿用 `backend/app/mod02_i8/client.py` 及对应数据源；其他位置已有实现时记录其指针，避免重复封装。一次性取数不因此自动变成长驻功能。
- 收录参数结构与去敏后的响应形态；Cookie、Token、签名下载地址及业务原件保留在各自受保护位置，不进入接口文档或 Git。

### 配置就绪与实际认证

`GET /api/m02/config`只核有效地址、当前身份与本人绑定，不登录i8；`ready`不是认证成功。用户明确使用空密码时，沿既有HTTP登录封装原样提交空串，配置接口不得仅因密码为空禁用操作。未登录、账号未绑定或地址无效仍拒绝，凭据不混搭、不回落到别人账号；真实认证与在线冲突沿登录封装判定。

### 界面主动操作与登录策略

用户2026-10-28决定：本系统界面内由用户主动发起的 i8 操作默认允许强踢已有在线会话，不能仅因该账号已登录就禁止抓取。本决定替代此前界面内强踢另行确认的要求；保留操作处的会话下线提示及业务操作自身的范围确认、预览、选择采用、金额减少确认和权限保护。

有 `allow_kick` 的通用接口由界面显式传 `true`，省略仍为 `false`；`I8Client`、HTTP登录与通用取数函数的默认值保持关闭，脚本调用按自身授权选择。当前界面调用包括：

| 界面动作 | 调用与策略 |
|---|---|
| 项目档案同步仓库/常用项目 | `POST /api/m02/sync/{warehouses,common-projects}`，query传 `allow_kick=true` |
| 通知书按月抓取/新小微仓库查询 | `POST /api/m03/notices/{fetch,warehouse-check}`，body传 `allow_kick=true` |
| 一键关联集采合同的预览/确认 | `POST /api/m11/{auto-link-preview,auto-link}`，body传 `allow_kick=true`；只预览不写关联，确认时重新核来源 |
| 机械费抓取/单项目更新 i8 | 共用 `POST /api/m06/workbench/i8-fetch`，body传布尔 `allow_kick=true`；省略关闭，读取后仍须选择采用 |
| 库存、收发结存、采购合同抓取 | `POST /api/m08/fetch`、`/api/m07/fetch`、`/api/m11/fetch`，既有抓取服务显式允许强踢，保留抓取范围确认 |
| 通知书打印/导出 PDF | `POST /api/m03/batch` 的既有执行器显式允许强踢 |

上述策略也适用于保留作回退的旧壳入口；i8接入层的配置/执行记录和本地Excel导出只读本地结果，不因此登录i8。先复用本人账号隔离的Cookie缓存；真正需要登录时才可能强踢。登录失败直接报错，不循环登录或自动重跑抓取；已建立会话失效时仍保留既有至多一次重新登录并重发该请求的恢复。有效空响应的单次复核沿各接口已有契约，不扩为登录失败重试。

## 一、`API-01` 付款通知书列表

**URL**：`{I8_BASE_URL}/FC/FM/PaymentBill/getList`（**POST**，`application/x-www-form-urlencoded`）

**固定表单**（`_LIST_FORM`）：

| 键 | 值 |
|---|---|
| `busType` | `PaymentBill` |
| `pageId` | `Web:PaymentBill` |
| `isLoadHistory` | `1` |
| `relateId` | `14` |
| `inputSource` | `2` |
| `phidOrgList` | `3700000000000014` |
| `phidProjList` / `dataKey` | `""`（⚠️ **`dataKey` 必须传空串**） |
| `saveTableName` | `fc3_code_table` |
| `payStatus` | `0` |
| `summaryCols` | `ApplyAmtFc,ApplyAmt,ApproveAmtFc,ApproveAmt` |
| `limit` / `page` / `start` | `5000` / `0` / `0`（单张精确查用 `limit=5`） |
| `queryfilter` | `{"queryFilter":"{\"BillDt*date*ge*1\":\"YYYY-MM-DD\",\"BillDt*date*le*1\":\"YYYY-MM-DD\"}"}` |

**单张精确查**（性能硬规则）：`queryfilter` 用 `PhId*guid*eq*1`（15 位以上纯数字）或 `BillNo*string*eq*1`；
**不得用全量列表代替单张精确查询**；历史耗时样本只说明当时选择，不作为当前延迟承诺。
⚠️ **空结果要重试确认一次**：i8 会**偶发返回有效但空的响应**（并发时更明显）—— 空 = "单据不存在"，
不确认就会**少出一张单**。同理 **`getFlowHisForPrint` 回空 ⇒ 所有签名静默漏印**，也必须确认一次。

**响应**：`{"Record": [ ... ]}`（`PageTotal` 等分页字段同在顶层）

**字段映射**（12 字段定稿，2026-09-08 用户拍板）：

| 输出列 | i8 字段 |
|---|---|
| 单据编码 | `BillNo` |
| 单据名称 | `BillName` |
| 单据日期 | `BillDt` |
| 付款项目 | `PhidPc_EXName` |
| 付款类型（**分流依据**） | `PhidRecPayType_EXName` |
| 业务类型 | `PhidBusType_EXName` |
| 付款组织 | `PhidPayOrg_EXName` |
| 收款单位 | `user_skdw_EXName` |
| **审批金额** | `ApproveAmt` |
| 录入人 | `PhidFillPsn_EXName` |
| **审批状态** | `AppStatus`（**原始值**；`0`/`""`/`None`/`"None"`/`"null"` ⇒ 未审批，否则已审批） |
| 备注 | `Remark` |
| 主键 | `PhId` |

> ℹ️ **2026-09-16**：**本工程不再取 `ApplyAmt`** —— 原「付款金额（源）」字段**已取消**（见付款需求）；
> 金额只取 **`ApproveAmt`（审批金额）**（实测 `ApplyAmt ≡ ApproveAmt`，且**付款动作不在 i8 发生**）。

### 详情与流程（同一单的另三个接口）

| 用途 | URL | 响应 | 关键字段 |
|---|---|---|---|
| 主表 | `{BASE}/FC/FM/PaymentBill/getInfo`（POST `{"id": PhId}`） | `{"Data": {...}}` | `PhidBusOrg_EXName` `PhidPayOrg_EXName` `BillNo` `BillName` `PhidPc_EXName` `user_skdw_EXName` `ApplyAmt`（本次支付总额）`ApproveAmt`（本次结算金额）`Remark` `PhidFillPsn_EXName` `PhidApp_EXName` `PrintCount` |
| 明细 | `{BASE}/FC/FM/PaymentBill/getDetInfo`（POST `{"id": PhId}`） | `{"Record": [...]}` | `ResourceType` `ResourceBillCode` `ApplyAmt` `ApplyAmtFc` `ConAmtFc` `RecName`/`RecAccName` `RecAccNo` `PhidBank_EXName` `Remark` |
| 审批流程（**签名来源**） | `{BASE}/api/WorkFlow3/WorkFlowApi/getFlowHisForPrint?bizId=paymentbill&bizPk=<PhId>`（GET） | `{"data": [...]}` | 节点名 + 签名图相对路径（URL 上 `?s=<token>` 每次变 ⇒ **缓存键用去 query 的 path**；TTL 15 天） |

---

## 二、`API-05` 仓库列表 / `API-06` 常用项目

### `API-05` GetWareHouseList（**已实测可用**）

- **URL**：`{BASE}/PMS/PMM/KcBaseSetting/GetWareHouseList`（**POST** urlencoded）
- **固定参数**：`orgQuery=#type:ORG#curOrg:3700000000000014#subOrg:#curProj:#cubProj:#parentNode:` ·
  `pcid=0` · `page=0` · `start=0` · `limit=100` ·
  `sort=[{"property":"PhidPc_EXName","direction":"ASC"}]` · `ng3_logid=`（空）
- **响应**：`{"Record": [...]}` · **字段**：`PhId` · `Whname`（仓库名）· `PhidPc_EXName`（全名）· `Nullify`（`"1"` = 作废，跳过）
- **全名尾部编号**：`新疆慧能横窑安装项目(XMCB2025080001)` ⇒ 需剥离（正则 `\s*[（(][A-Za-z]{2,}[0-9]+[)）]$`）

本地 `POST /api/m02/sync/warehouses` 取数后调用项目域的占位档案扶正，规则回[项目需求](../requirements/projects.md#名称与归属)。`count`仍为取回名单条数，`counts.promote/unresolved`为扶正/待人工数；`message`与`sample`列实际处理结果，执行记录`detail.warehouse_promotion`保同一明细。`degraded`表示取数或事务失败；已取回但需人工的情况正常返回并记partial，不报成已扶正。查询 `/api/m03/notices/warehouse-check` 仍只查名单，不触发该写入。

### `API-06` GetCommonUseList（**`phid` 的权威来源**）

- **URL**：`{BASE}/SUP/RichHelp/GetCommonUseList?helpid=project_table_pchelp&ORMMode=true&skipInfoAuth=1`（**GET**）
- **响应**：`{"Record": [...]}`（兼容小写 `record`）
- **字段**：`PhId`（→ `phid`）· `BillNo`（→ `code`）· `BillName`（→ `name`，**同样要剥尾部编号**）· `Ab`

---

## 三、`API-07` 取版式 `getPrintDesign`（**即 `.env` 的 `I8_PRINT_DESIGN_URL` 所指**）

**URL**：`{BASE}/reportcenter/printManage/getPrintDesign?printId=<printId>`
（另有一个 `RW/Print/GetPrintTemplate`，同族备用）

**printId（按「付款类型」分流）** —— `TYPE_TO_PRINTID`：

| 付款类型（`PhidRecPayType_EXName`） | printId |
|---|---|
| 付款通知书 | `3700000000000203` |
| 其他支出 | `3700000000000215` |

**响应形态**（**关键**）：

| 键 | 形态 | 用途 |
|---|---|---|
| `printSchema` | **JSON 字符串** → `[0]` | `[0].cells`（单元格：`cellType` / `cellData` / `className` / `cellBorders` / `dataFilter`）＋ `[0].globalSettings{cols, rows, widths[{col,width}], heights[{row,height}]}` |
| `printSetting` | **JSON 字符串** → `[0].printConfig` | `margin{top,left,right,down}` 等版面设置 |
| `printName` | 字符串 | 日志展示 |

**模板 dataset id**（`DS_HEADER` / `DS_DETAIL`）：
`DS_HEADER = "3700000000000010"` · `DS_DETAIL = {"3700000000000212", "3700000000000019"}`

**几何参数**（`GEO`）：`scale 0.684` · `col_w 110` · `row_h 30` · `font_px 14` · `line_height 1.5` · `border_px 1.0` · `sig_h 36`

**渲染与签名解析的现行要求**：

1. 框线使用完整CSS border；当前几何参数保持，未采用局部坐标系缩放方案。
2. 节点过滤同时识别 `fieldId="办理节点"` 和 `fieldId="task_des"`，均从 `value` 取节点名。无筛选条件可按版式合法留白；有筛选却无法识别时必须报错停单，不能归成合法留白。实现出口为 `template.node_of()` 与 `signatures.unresolved_image_slots()`。
3. 取人按图片格的 `dataFilter`，不按邻近标签文字。同一节点可占多个物理图片格，按版式渲染，不按去重节点数推图片数或自行删重复格。历史错配与样本数量属于排障经验，不是未来模板常量。

---

## 四、打印机（IPP 直投）

| 通路 | 地址 | 应答 | 说明 |
|---|---|---|---|
| **`ipp`（默认）** | **`ipp://<ip>:631/ipp/print`**（`IPP_PATHS = ["/ipp/print", "/ipp"]`，先试前者） | ✅ status + job-id + job-state | 可确认投递接收；纸面完成须另有证据 |
| `raw`（兜底） | `<ip>:9100`（JetDirect） | ❌ 无应答 | 实测 Ricoh PDF 直打有效 |

- **默认 IP** = `192.168.5.248`（**用户已确认无误**，工具与原型一致）
- **实测机型** = **RICOH IM 3000 PS3**（`printer-info` 自报；`printer-state = Idle`）
  设备信息来自历史实测，不能代替本轮设备状态或出纸验证。
- **IPP 状态码**：`0` 成功 · `1` 部分成功 · `1028` **文档格式不支持** · `1280` 服务端错误 …
- **作业状态**：`3` 排队中 · `4` 待处理 · `5` 打印中 · `6` 中断 · `7` 已取消
- ⇒ 工程侧 `.env` 的 `PRINTER_IPP_URL` = **`ipp://192.168.5.248:631/ipp/print`**（**2026-09-16 已真机出纸验证通过**，一次连投 4 张）

### IPP报文与排障边界

`document-format` 为 `mimeMediaType`，值标签使用 `0x49`，不能误用 `keyword` 的 `0x44` 或以删除该属性作正式修法。错误文本保留服务器 `status-message`。排障优先使用不出纸的属性读取/Validate-Job，一次隔离一个变量；真实投递仍需本次相应授权。历史首次出纸及已作废试法进入项目经验，不证明当前端点、设备或会话可用。`raw` 9100只证明字节发送，不提供纸面完成回执。

---


## 打印解析边界

模板签名过滤同时识别“办理节点”和 task_des/workflow_history；有筛选但无法识别节点名应停止该单，不能误作合法留白。无筛选的槽位可按版式留白。模板驱动映射与实际槽位数量沿 mod03_notice/print 的 template/signatures/render；节点名未归一化和版式无槽位是已接受边界，不能据其他签名命中推全签名齐全。IPP成功类别只证明接收，不能称纸面完成。

## §真机实测纠正（2026-09-17 · `API-03` 库存单据明细 ＋ `API-02` 收发结存）

> 2026-09-17样本实测纠正；与旧素材冲突时以本节为准。
> ⚠️ 本次是**一次登录**（`KillOnlineUser` 强踢过一次），导出件留证在 `data/source/i8-diagnostics/`
> （`artifacts/`不进库；先核本机现存样本与离线fixture。样本缺失时记录未复现；重新登录或抓取须按本节既有授权边界处理）。

### 一、收发结存（`API-02`）的**真实表头是两行**，第 2 行才是列名

| 行 | 内容（前 17 列原文） |
|---|---|
| 第 1 行 | `仓库 资源分类 资源编码 资源名称 规格型号 计量单位 物料性质` ／ `期初统计`(跨 2 列) `收统计`(跨 3) `发统计`(跨 3) `结存统计`(跨 2) |
| 第 2 行 | `期初数量 期初金额 收数量 收单价 收金额 发数量 发单价 发金额 结存数量 结存金额` |

- ⛔ **不是**「组名 ＋ 后缀」拼接；组名与叶子列名不能拼成新的业务字段。
- ✅ **正确取法 = 每列取表头块里最下面一个有文字的行**（叶子行胜出）。
- 数据从**第 3 行**开始；「合计」行按 `TOTAL_WAREHOUSE` 剔除。

### 二、抓取落库的**幂等范围 = 「核算年月 ＋ 仓库」**（不是只按月份）

库存刷新读取既有行时按核算年月与仓库限定；现有 `mod08_inv/repository.py` 还在Python侧核仓库范围，不能在同月跨仓库删除。历史模拟Session未执行SQL过滤的局限及当次行数已迁入项目经验；业务隔离要求、既有实现与测试保护继续保留。陌生仓库尚无档案时，沿项目同步/人工确认入口处理，不自动猜配。

## 采购合同应付与附件（2026-10-20 Edge CDP只读核实）

列表POST `/PMS/PCM/Contract/ProjBal/GetCntProjBalList?model=7&floatmenuCondition=`；form带page/start/limit、queryfilter及公司OrgQuery上下文，与采购合同同组织。返回Success/Record/totalRows；PhId为应付键，PhidCnt/PhidCnt_EXName为合同主键/编号，PhidPc_EXName、PhidBalComp_EXName为项目/收款单位，AppAmtVatFc为审批本币额，AsrFlag=1、WfFlag=2为已批结束。分页不完整或重复键应拒绝继续关联；取数实现 `mod02_i8/payable_source.py`。

详情POST `/PMS/PCM/Contract/ProjBal/GetCntProjBalInfoFirst`，form `id`。抽查8条invoiceGrid均空，不能据此判定无发票；附件目录使用 **GET** `/JFileSrv/reactAttach/tableAttachInit`，query带asrTable=pcm3_cnt_projbal、asrCode=应付PhId、busTypeCode=PCM_BAL7；返回code/data/message，code=200时从data.attachmentRecordList取文件列表，asrFid是文件键，asrName是文件名（2026-10-23浏览器会话只读核实，POST不受支持）。PDF预览可取得文字层；不在正文存签名文件URL、Token或Cookie。已核样本不代表全历史覆盖。

### 附件预览文件读取（2026-10-23 已验证）

POST `/JFileSrv/api/getPreviewUrl`，JSON带`asrFids`文件键数组、当前会话的`loginId`/`orgId`、`busTypeCode=PCM_BAL7`，本次`wmDisabled="1"`、`billWM=""`沿页面实际参数。响应`code=200`、`data`为文件键到相对预览文件路径的映射；随后GET返回的`/JFileSrv/previewFiles/...`地址，保留服务生成的签名参数，不自行拼接、修改或长期保存。实际验证单键及最多20键一批、99个PDF/图片读取成功；检验Word不作为发票来源，未验证其预览转换。

调用复用I8Client及当前浏览器恢复的会话，未重新登录或踢人；目录与文件读取不修改业务单据，页面原生PDF预览空白不等于文件无法下载。预览转换可能产生服务端缓存；未验证永久缓存期限或原件下载接口，不登记为通用原件下载能力。未新增常驻封装；Cookie/签名URL不入Git。
