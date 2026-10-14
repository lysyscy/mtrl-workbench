# i8 接口契约 · 旁证摘要（**实现层参考**）

> **性质**：旁证摘录（来源 = `delivery/PRD素材包-20260911/` 的**可读实现**）。
> ⚠️ **红线**：素材包是**旁证**，**口径一律不得反推** —— 本文件只登记**接口形态**（URL / 参数 / 字段名），
> 业务取值一律回《材料科业务全流程说明书》。改接口与解析时先核§六/§真机实测纠正的日期、样本、账户与版式前提；已有未变有效结果可复用，变化输入按 docs/agents/workflow.md补验。
>
> **本文用途**：把原先登记为「待用户提供」的三项（取版式契约 · API-01 字段名 · 打印机 IPP 路径）
> 从素材包中**取齐并固化**，避免每次交接重复查找。
> ⭐ **2026-09-15 真机核验**：§一 / §二 / §三 / §四 **全部经真机复核**（探测脚本 = `tools/probe/i8_contract_probe.py`、
> 取数冒烟 = `tools/probe/i8_fetch_smoke.py`）—— 结论见 **§六 真机核验记录**；下文保留"旁证"原始记载以便对照。
>
> 摘录日期 2026-09-15。⚠️ 以下为**素材包（老工程）内路径，非本工程**，仅供溯源：
> 源文件：
> input/pay_notice_export_http.py · app/warehouse_sync.py · app/project_sync.py ·
> `i8一键打印/反解件/{profiles_payment_bill,print_paynotice,print_pdf}.py{,c}`

---

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

> ℹ️ **2026-09-16**：**本工程不再取 `ApplyAmt`** —— 原「付款金额（源）」字段**已取消**（§4.2.5）；
> 金额只取 **`ApproveAmt`（审批金额）**（实测 `ApplyAmt ≡ ApproveAmt`，且**付款动作不在 i8 发生**）。

### 详情与流程（同一单的另三个接口）

| 用途 | URL | 响应 | 关键字段 |
|---|---|---|---|
| 主表 | `{BASE}/FC/FM/PaymentBill/getInfo`（POST `{"id": PhId}`） | `{"Data": {...}}` | `PhidBusOrg_EXName` `PhidPayOrg_EXName` `BillNo` `BillName` `PhidPc_EXName` `user_skdw_EXName` `ApplyAmt`（本次支付总额）`ApproveAmt`（本次结算金额）`Remark` `PhidFillPsn_EXName` `PhidApp_EXName` `PrintCount` |
| 明细 | `{BASE}/FC/FM/PaymentBill/getDetInfo`（POST `{"id": PhId}`） | `{"Record": [...]}` | `ResourceType` `ResourceBillCode` `ApplyAmt` `ApplyAmtFc` `ConAmtFc` `RecName`/`RecAccName` `RecAccNo` `PhidBank_EXName` `Remark` |
| 审批流程（**签名来源**） | `{BASE}/api/WorkFlow3/WorkFlowApi/getFlowHisForPrint?bizId=paymentbill&bizPk=<PhId>`（GET） | `{"data": [...]}` | 节点名 + 签名图相对路径（URL 上 `?s=<token>` 每次变 ⇒ **缓存键用去 query 的 path**；TTL 15 天） |

---

## 二、`API-05` 仓库列表 / `API-06` 常用项目

### `API-05` GetWareHouseList（**已实测可用**，见 §⑥ M0-0C）

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

## 五、历史落地记录（2026-09-15；当前状态回主计划§0/§15）

| # | 待办 | 状态 |
|---|---|---|
| 1 | `.env` 填真值（`PRINTER_IPP_URL` · `I8_PRINT_DESIGN_URL` · `I8_PRINT_ID_*` · 三个取数 URL） | ✅ 已填（2026-09-15） |
| 2 | `_map_record` 按 12 字段真名对齐 | ✅ 已改 ＋ `tests/test_i8_contract.py`（10 项） |
| 3 | `API-05`/`API-06` 的 URL / 参数 / 字段对齐 | ✅ 已改（`API-05` 改 POST form） |
| 4 | IPP 路径真机核验 | ✅ 已核（`ipp://192.168.5.248:631/ipp/print`，转换与素材包一致） |
| 5 | **`API-01` 取数方式改为 POST form（＋空结果确认）** | ✅ 已改，**真机取到 124 条** |
| 6 | **版式渲染改为"模板驱动"** | ✅ **已接线（2026-09-15）** —— 见下 |

---

## 六、真机核验记录（**2026-09-15** · 探测脚本可复现）

> ⚠️ 下列探测均**登录 i8**（含 `KillOnlineUser` 强踢）—— 只在用户同意时运行。
> 复现：`backend/.venv/Scripts/python.exe tools/probe/i8_contract_probe.py [YYYY-MM]`（契约探测）
> 　　　`backend/.venv/Scripts/python.exe tools/probe/i8_fetch_smoke.py [YYYY-MM]`（取数冒烟 + 取样本）

### ① `API-01` 取数方式 —— ✅ **POST form 确认可用**

- `POST {BASE}/FC/FM/PaymentBill/getList`，`application/x-www-form-urlencoded`
- 用素材包的 11 项固定表单 ＋ `queryfilter`（**双层 JSON 串**）**实测取到 2026-08 月 124 条**；
  原实现的「GET + `yearMonth` 参数」**一条也取不到** ⇒ 已改为 POST（`notice_source.build_list_form`）。
- ⚠️ **`dataKey` 必须传空串**（素材包旁证一致）。
- ⚠️ **空结果必须再确认一次**：i8 偶发返回"有效但空"（`EMPTY_RETRY=1`，`notice_source.fetch_month` 已实现）。
- ⚠️ 响应里 `AppStatus` 是**原始值**（`1` = 已审批），需映射为本工程字面量「已批」（§4.4.1）。
- ⚠️ 响应字段包含**远超 12 个**（`PhidApp_EXName` / `ApplyAmt` / `PrintCount` / `NgRecordVer` …）——
  12 字段是**导出表**口径，取数时按需取。

### ② `API-05` / `API-06` —— ✅ 与旁证一致

- `API-05` = **POST form**（`WH_PARAMS`）· `API-06` = **GET**（URL 自带 query）⇒ 已分别实现。

### ③ `API-07` 取版式 —— ⭐ **真契约不是 HTML，是"版式模板 JSON"**

- `GET {BASE}/reportcenter/printManage/getPrintDesign?printId=<id>` ·
  **外层** = `{"Status","Code","Msg","Data"}` ⇒ **模板在 `Data` 里**（不是顶层）。
- `Data` 的键（**实测**）：
  | 键 | 形态 | 说明 |
  |---|---|---|
  | `printId` / `printName` | str | `3700000000000215` / `其他支出` |
  | **`printSchema`** | **JSON 串** → `[0]` | `cells[]` · `globalSettings{cols,rows,widths,heights,frozen}` · `sheetName` |
  | **`printSetting`** | **JSON 串** → `[0].printConfig` | `page{direction,scaleRatio,paperSize:"210,297",…}` · `margin{top,down,left,right,header,footer}` · `headerFooter`（**空壳**）· `paging`（**空壳**） |
  | `sheetProperty` / `globalProperty` / `dataSetInfos` / `workflowHistorySetting` | JSON 串 | `dataSetInfos` 含 `PaymentBill` / `PaymentBillD` / **`3700000000000010`（主表）** / **`3700000000000212` `3700000000000019`（明细）** |
- `cells[i]` = `{cellType, className, row, col, colspan, rowspan, cellData, cellBorders, cellName, extension, interaction}`；
  `cellType="text"` ⇒ `cellData.value`；`cellType="field"` ⇒ `cellData.{dataSetId,fieldId}`（图片格另有 `otherShowType:"image"` + `dataFilter`）。
- **真实样本已入库**：`backend/tests/fixtures/i8_print_design_sample.json`（65 701 字节，**不含业务数据**，只含模板与静态标题）。
- ⇒ **实锤结论**：原实现「取回 HTML 再注字段」**必然报"取不到版式"** ⇒ 必须**模板驱动渲染**；
  引擎已落地 = `backend/app/mod03_notice/print/template.py`（353 行，13 项自检）。

### ④ 打印机 IPP —— ✅ 与旁证一致

- `ipp://192.168.5.248:631/ipp/print`；工程侧 `print/ipp.py::_to_http_uri` 转换后 =
  `http://192.168.5.248:631/ipp/print` —— **与素材包 `print_pdf.py` 完全一致**（端口不能省）。

---

## 七、接线落地记录（**2026-09-15 · 打印链路已换到模板驱动**）

> 目的：把"预览看到的"与"实际印出来的"变成**同一条路径**，并删掉那条已被真机证伪的旧路。

### 收敛后的打印件（`backend/app/mod03_notice/print/`）

| 文件 | 行数 | 职责 |
|---|---|---|
| `design.py` | 70 | 按类型取版式 → **解析成模板**（`Data` → `extract_design_data` → `parse_design`）；取不到**显式报错** |
| `template.py` | 388 | 模板驱动渲染（几何/样式/明细行/签名格全部**现场取自模板**）＋ `node_of()` **认两种筛选写法** |
| `fields.py` | 174 | 字段值组装（千分位＋2 位小数 · 零值留空）＋ **覆盖度自检** `uncovered_field_ids()` |
| `signatures.py` | 279 | 签名图取值 + 缓存 ＋ **零命中报警**（`001-06`）＋ **认不出写法报警**（`unresolved_image_slots`） |
| `ipp.py` | 78 | IPP 直投 |
| `render.py` | 67 | **只剩** HTML→PDF（Playwright） |

**已删**（其核心假设被真机证伪）：
- `print/sign.py`（73 行）—— 依赖 `<span class="sign-slot" data-node="…">`，而真实版式里**没有这种东西**；
- `render.py::build_print_html`（＋`_fmt_scalar`/`_is_amount_key`）—— 依赖"响应是 HTML、做 `{{占位符}}` 替换"，而真实响应是**模板 JSON**。

**唯一渲染入口** = `service.render_notice_html(notice, tpl, detail_fetcher, signature_store)`
⇒ `run_batch`（生产）与 `tools/probe/render_preview.py`（预览工具）**都调它**；预览不再自己拼一份组装。

### 验收处置（**判据语义一字未改，仅迁断言载体**）

`ACC-PAY-PRINT-001` 的 `001-04/05/06/10` 原打在 `build_print_html` / `sign-slot` 上 ⇒ 迁到真实模板形态
（签名格 = `cellData.otherShowType=image` ＋ `dataFilter` 的「办理节点」）；`ACC-PAY-PDF-001` 全组补上新增依赖。
**M1 = 22/22 保持全绿**；全套 `pytest 216 passed`。

### 离线一致性核对（用真机快照跑新入口）

| 单据 | 类型 | td | 签名图 | 表格宽 |
|---|---|---|---|---|
| `FKTZS2026090065` | 材料 / 其他支出 | 79 | ~~3~~ → **4** | 575.23px |
| `FKTZS2026082350` | 机械 / 付款通知书 | 73 | 4 | 701.11px |

⚠️ **2026-09-16 更正**：上表「其他支出 · 签名图 3」是**当时的错误值**（不是"与真机一致"）——
真机件上那一格（`row=15 col=3` · 核算部部长）也是**有签名**的，只是我们**漏认了第 ② 种筛选写法**，
于是它被当成"无节点 ⇒ 留空"。**当时的"逐项一致"只证明了两条路径同样地漏**，不证明对 ——
⚠️ **教训：「两处产出相同」不等于「产出正确」**，同源一致性只能证明没有分叉，证明不了正确。
修法见 §三-2 与 §六-③ 的补记。

### 遗留

- ✅ **已清理（2026-09-15）**：`payment_notice.sign_nodes` / `signatures` 两列**已删**（迁移 `dca078236657`）——
  写入点 `notice_source._map_record` 同步删掉（⚠️ 它此前仍在写这两列，是本次核查才发现的）；
  `upgrade`/`downgrade` **往返实测可逆**；执行时表 0 行 ⇒ 无数据丢失。删后 `payment_notice` = 24 列。
- ⏳ **唯一未做项 = 真机打印件对照**（需登录 i8 ＋ 打印机在位）—— 已按用户指示登记为**待办**，见交接文件 §⑦「待办」。

---

## 八、真机打印件对照结论（**2026-09-16 · 用户实印**）

> **这一节补上了 §七 的"唯一未做项"。** 用户拿 `artifacts/` 里生成的打印件**实打了一次**。

| 项 | 结论 |
|---|---|
| **版式**（版心 / 行列 / 框线 / 字号） | ✅ **无问题** |
| **数据**（字段值 / 金额格式 / 零值留空） | ✅ 无问题 |
| **签名** | ❌ **「其他支出」的核算部部长是空的** —— 已定位并修复，见下 |

### 根因（**纯本地逻辑，不依赖 i8**）

`i8_print_design_sample.json`（其他支出 · `printId=3700000000000215`）的 `row=15 col=3` 签名格，
`dataFilter` 用的是**第 ② 种写法**：

```json
{"fieldId": "task_des", "dataSetId": "workflow_history", "operator": "eq", "value": "核算部部长"}
```

而旧 `node_of()` **只认** `fieldId == "办理节点"` ⇒ 该格返回空 ⇒ **它连签名槽位都算不上**：
`signature_slots()` 只返回 6 个（漏了核算部部长）⇒ 既不在 `missing`、也不在 `blank_by_design` ⇒
`001-04/05/06` **三条判据一条都不触发**（`001-06` 要求"一个签名都没命中"才报，而此处其余 4 个都命中了）。

> ⚠️ **这是"静默失效"的教科书形态**：不报错、不崩、日志干净、报表全绿，只是**印少了一个签名**。

### 修复（2026-09-16）

1. `template.node_of()` —— **两种写法都认**（`NODE_FILTER_FIELD` / `NODE_FIELD_ID`）；
2. `signatures.unresolved_image_slots()` —— **带了筛选却取不到节点名** ⇒ 不认识的写法 ⇒
   `check_signature_coverage()` **抛错停单**（⚠️ 与"无筛选 ⇒ 合法留白"严格区分，不许误报）；
3. 测试更新：`test_模板签名格节点名去重保序` 原先把漏认的输出（6 个）**写死成了契约** ⇒ 改为 7 个；
   新增 4 条自检（两种写法 / 真实模板无未决 / 认不出必报 / 无筛选不报）。

### 离线复算（真机快照 + 真机模板 → **生产同一渲染入口**）

| 单据 | 槽位 | 命中 | 留空（流程未走到） | 模板里的签名图 |
|---|---|---|---|---|
| `FKTZS2026090065` · 其他支出 | **7**（原 6） | **4**（含**核算部部长**） | 事业部分部经理 / 财务公司经理 / 总经理 | **4**（原 3） |
| `FKTZS2026082350` · 付款通知书 | 7 | 3 → **4 张图**（核算部部长占 2 格） | 事业部分部经理 / 分公司常务副经理…/ 资产管理部总经理 / 主管领导 | 4 |

> 复算脚本 = 本文件 §六 的一次性离线跑法（读 `artifacts/preview_data_*.json` 快照 + `tests/fixtures/` 模板，
> **不发任何 i8 请求、不登录、不强踢**）。⇒ 以后调渲染都可先离线复算，不必登录 i8。

### 遗留

- ⏳ **待用户复打一次「其他支出」**确认真机上核算部部长已有签名（本次只到"离线复算"为止）。

---

## §真机实测纠正（2026-09-17 · `API-03` 库存单据明细 ＋ `API-02` 收发结存）

> **性质**：本文件是**旁证**（来自素材包），而这一节是**真机实测**——按本文件索引行自己写的
> 「⭐ 真跑前需真机核验一次」，这就是那次核验的结论。**冲突时以本节为准**。
> ⚠️ 本次是**一次登录**（`KillOnlineUser` 强踢过一次），导出件留证在 `artifacts/_diag/`
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
