# i8 接口契约

本文件统一收录本项目已探测接口。业务意义见 [需求](../requirements.md)，封装复用 backend/app/mod02_i8/client.py 与对应 source。下列既有请求形态在2026-09-15/17样本核过；后续采购应付/附件以各节日期和范围为准。旧素材仅作旁证，不覆盖实测纠正。接口变化/新输入按实际影响复验；历史成功不证明当前会话、权限或分页完整。

纯 HTTP 登录使用 SM2/Cookie；Cookie状态由本机受保护位置保存，登录可能强踢，人工链路授权与失败不重登边界见 [架构](../architecture.md)。通知书数据来自审批金额而非i8付款事实。

## 〇、统一收录与调用

[用户·2026-10-23] 本文件是本项目 i8 已探测接口的统一收录入口。调用或继续探测前先查本文件与现有接入封装；确认缺口后再探测。

- 接口完成与用途相应的验证后，在本文件按业务归类收录：用途、HTTP 方法与路径、必要参数及组织范围、关键响应字段、会话与读写副作用、验证日期和适用边界、已有调用封装位置。分页、附件或业务写入按实际涉及的行为验证，不统一扩展测试矩阵。
- 尚未完成验证的接口标为“待验证”，注明已知部分和缺口；仅探测成功不能登记为可稳定调用，文档收录也不代表已接入产品。
- 可复用调用沿用 `backend/app/mod02_i8/client.py` 及对应数据源；其他位置已有实现时记录其指针，避免重复封装。一次性取数不因此自动变成长驻功能。
- 收录参数结构与去敏后的响应形态；Cookie、Token、签名下载地址及业务原件保留在各自受保护位置，不进入接口文档或 Git。

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
**绝不走全量列表**（实测 全量 1064 条 = **44.9s** vs 精确 1 条 = **0.16–0.33s**，快 138 倍）。
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

**两条渲染实现要点**：
1. **框线用 CSS border**（四边完整、粗细一致）；⚠️ Chrome 会把 border 宽度**取整**（实测 0.68/0.5/0.35 都 = 1px）⇒ 要真变细只能**整体缩放局部坐标系**（外层 `transform:scale(0.68)` + 几何 ×1.4706）。**用户判定外观无所谓，未启用**。
2. **签名图格**取节点名有**两种 `dataFilter` 写法**（**都要认**）：
   ① `fieldId="办理节点"`（付款通知书那批 —— 自定义字段写法）⇒ 节点名在 `value`；
   ② `fieldId="task_des"`（其他支出模板 `row=15 col=3` 那格 —— 直接筛流程字段）⇒ 节点名同样在 `value`。
   ⚠️ **漏认第 ② 种 ⇒ 那格连"签名槽位"都不算** ⇒ 既不进 `missing` 也不进 `blank_by_design` ⇒
   **静默印出缺签名的件**（2026-09-16 实测：其他支出的「核算部部长」），且 `001-04/05/06` 三条判据一条都不触发。
   **没有筛选条件就不渲染**（真实件验证：无筛选的格 i8 本身也印空）—— 这是**合法留白**，与"写法不认识"**不是一回事**。
   ⇒ 实现出口 = `template.node_of()`（认两种）＋ `signatures.unresolved_image_slots()`（认不出就报警停单）。
3. ⚠️ **签名格旁边的「标签文字」不可信 —— 取人一律按 `dataFilter`，千万别按标签匹配**（2026-09-16 实测）：
   付款通知书模板（`printId=3700000000000203`）里**标签与取人条件对不上**的格，至少 3 处 ——
   · 标签「**分公司财务科长**」（`row=13 col=6`）的图片格（`col=7`）取人条件 = **核算部部长**；
   · 标签「**分公司主管经理**」（`row=12 col=4`）的图片格（`col=5`）= **分公司常务副经理/事业部分部经理**；
   · 标签「**公司主管领导**」（`row=13 col=4`）的图片格（`col=5`）= **主管领导**（字面不同）。
   ⇒ 同一节点**可以占多格**（`核算部部长` 在 `row13` 出现 **2 格**：`col=3` 与 `col=7`）⇒
   **`signature_slots()` 去重后 7 个槽位、渲染却出 3 张图**（`分公司经理` ×1 ＋ `核算部部长` ×2）是**正常**的，
   别把它误当"重复插图"bug。ℹ️ 这是 i8 模板自身的设计，**我们照抄**（契约：不得自行设计版式）⇒
   原生件在这些格上应当**同样**如此。

---

## 四、打印机（IPP 直投）

| 通路 | 地址 | 应答 | 说明 |
|---|---|---|---|
| **`ipp`（默认）** | **`ipp://<ip>:631/ipp/print`**（`IPP_PATHS = ["/ipp/print", "/ipp"]`，先试前者） | ✅ status + job-id + job-state | 可确认"打印机真的收件/打完" |
| `raw`（兜底） | `<ip>:9100`（JetDirect） | ❌ 无应答 | 实测 Ricoh PDF 直打有效 |

- **默认 IP** = `192.168.5.248`（**用户已确认无误**，工具与原型一致）
- **实测机型** = **RICOH IM 3000 PS3**（`printer-info` 自报；`printer-state = Idle`）
  ⚠️ **2026-09-14 那次只验了「TCP 连通 ＋ URI 转换」，没真投过作业**；**首次真出纸 = 2026-09-16**（见下方补记）
- **IPP 状态码**：`0` 成功 · `1` 部分成功 · `1028` **文档格式不支持** · `1280` 服务端错误 …
- **作业状态**：`3` 排队中 · `4` 待处理 · `5` 打印中 · `6` 中断 · `7` 已取消
- ⇒ 工程侧 `.env` 的 `PRINTER_IPP_URL` = **`ipp://192.168.5.248:631/ipp/print`**（**2026-09-16 已真机出纸验证通过**，一次连投 4 张）

### 补记：2026-09-16 首次真出纸 ＋ 唯一那个坑（⭐ 踩坑实录）

首次以 `print/ipp.py` 投递，**4 张全部回 `0x0400 client-error-bad-request`**（HTTP 200）。只读诊断（`Get-Printer-Attributes`，**不出纸**）显示：
机器 = `RICOH IM 3000 PS3`、`Idle`、`document-format-supported` **含 `application/pdf`** ⇒ 端点与格式都正常，**是报文被拒**。

**逐变量二分 → 真因 ＝ 值标签（value tag）用错**（⚠️ 不是「打印机不支持某属性」）：

| # | 试法 | 结果 |
|---|---|---|
| ① | 报文里**整个删掉** `document-format` | `0x0000` ✅（说明**问题就在这一个属性上**） |
| ② | 保留属性，**把标签从 `0x44` 改成 `0x49`** | `0x0000` ✅ ⇒ **这才是正解**（`0x44` = `keyword`；`document-format` 的类型是 `mimeMediaType` ⇒ 必须 `0x49`） |
| ③ | `printer-uri` 带不带 `:631`（只读隔离，用 `0x000B`） | 两者**同为** `0x0000` ⇒ **端口无关**（机器自报的形式就是不带端口的） |
| ④ | `Validate-Job`（0x0004，**不打印**）用对标签 | `0x0000` ✅ ⇒ **本机可用**，是排障最好用的非出纸探测 |

⚠️ **两个中途的错误结论（已作废，记下来免得再犯）**：① 「报文里不得带 `document-format`」（那只是绕过，把报文改成非标准形态）② 「`printer-uri` 必须带 `:631`」与「`Validate-Job` 在本机一律回 0x0400」——**这两条当时都是带着错标签测的**，属**同一变量的污染**。
- 失败响应仅 **115 字节**，唯一线索 ＝ `status-message = client-error-bad-request`（**不指出是哪个属性**）⇒ ⚠️ **实现必须把 `status-message` 带进错误文本**（原 `ipp.py` 算出来了却**扔掉没用**，已修）。
- ⚠️ **排障纪律**：一次只改**一个**变量，并用**不出纸**的操作（`0x000B` / `0x0004`）验证 —— 否则像「「带端口」」这种**无关变量会被误判成原因**。
- `raw` 9100 通路：**能把字节发出去、机器无任何应答**（是否出纸不可知）⇒ 保留兜底、不作主力。

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

- ⛔ **不是**「组名 ＋ 后缀」拼接（我原先按素材包那样实现 ⇒ 得到 `期初统计期初数量` ⇒ **关键列一个都认不出**）。
- ✅ **正确取法 = 每列取表头块里最下面一个有文字的行**（叶子行胜出）。
- 数据从**第 3 行**开始；「合计」行按 `TOTAL_WAREHOUSE` 剔除。
- 真机实测：**480 行 / 8 个仓库 / 收金额合计 1,218,821.92**（2026-09）。

### 二、抓取落库的**幂等范围 = 「核算年月 ＋ 仓库」**（不是只按月份）

- 真机实测：库存单据明细解析 **559 行 / 8 个组**，修复前**只落库 18 行** —— 根因 = 幂等刷新取
  `existing` 时只按 `ym` 过滤 ⇒ **同月多仓库时，后一个仓库的刷新把前一个仓库的行删掉**。
- ⚠️ **离线断言看不见**：`FakeSession` 忽略 SQL 的 `where` ⇒ 修法必须在 **Python 侧**按仓库过滤。

### 三、其它实测数字（2026-09）

| 项 | 实测 |
|---|---|
| 库存单据明细 | 解析 559 行 · 分组 8 个（12 个 phid 里当月有单据的 8 个仓库）· 落库 559 行 |
| 收发结存 | 解析 480 行 · 8 个仓库 · 落库 480 行（`inserted 480`） |
| 陌生仓库 | `兰考金不换前置车间项目` —— **项目档案里没有**（抓取给了提示、未自动建档）⇒ 需在「项目档案」页点一次「同步常用项目列表」 |

## 采购合同应付与附件（2026-10-20 Edge CDP只读核实）

列表POST `/PMS/PCM/Contract/ProjBal/GetCntProjBalList?model=7&floatmenuCondition=`；form带page/start/limit、queryfilter及公司OrgQuery上下文，与采购合同同组织。返回Success/Record/totalRows；PhId为应付键，PhidCnt/PhidCnt_EXName为合同主键/编号，PhidPc_EXName、PhidBalComp_EXName为项目/收款单位，AppAmtVatFc为审批本币额，AsrFlag=1、WfFlag=2为已批结束。分页不完整或重复键应拒绝继续关联；取数实现 `mod02_i8/payable_source.py`。

详情POST `/PMS/PCM/Contract/ProjBal/GetCntProjBalInfoFirst`，form `id`。抽查8条invoiceGrid均空，不能据此判定无发票；附件目录使用 **GET** `/JFileSrv/reactAttach/tableAttachInit`，query带asrTable=pcm3_cnt_projbal、asrCode=应付PhId、busTypeCode=PCM_BAL7；返回code/data/message，code=200时从data.attachmentRecordList取文件列表，asrFid是文件键，asrName是文件名（2026-10-23浏览器会话只读核实，POST不受支持）。PDF预览可取得文字层；不在正文存签名文件URL、Token或Cookie。已核样本不代表全历史覆盖。

### 附件预览文件读取（2026-10-23 已验证）

POST `/JFileSrv/api/getPreviewUrl`，JSON带`asrFids`文件键数组、当前会话的`loginId`/`orgId`、`busTypeCode=PCM_BAL7`，本次`wmDisabled="1"`、`billWM=""`沿页面实际参数。响应`code=200`、`data`为文件键到相对预览文件路径的映射；随后GET返回的`/JFileSrv/previewFiles/...`地址，保留服务生成的签名参数，不自行拼接、修改或长期保存。实际验证单键及最多20键一批、99个PDF/图片读取成功；检验Word不作为发票来源，未验证其预览转换。

调用复用I8Client及当前浏览器恢复的会话，未重新登录或踢人；目录与文件读取不修改业务单据，页面原生PDF预览空白不等于文件无法下载。预览转换可能产生服务端缓存；未验证永久缓存期限或原件下载接口，不登记为通用原件下载能力。未新增常驻封装；Cookie/签名URL不入Git。
