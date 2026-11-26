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

工作台界面默认选择浏览器已有会话。所有访问 i8 的工作台业务接口都要求显式传 `session_mode`（`browser` 或 `http`），浏览器模式还需传当前页面的 `device_id`。缺失、空白或无效的模式会在连接 i8 前被拒绝。浏览器连接、站点或登录态异常时结束当前操作。工作台直连由用户主动选择，先复用本人账号隔离的 Cookie。i8 返回在线冲突时，工作台返回 `409 i8_online_conflict` 与一次性 `kick_token`。用户确认下线后用该令牌重发同一操作。令牌绑定工作台身份、i8 站点、账号、操作和范围，120 秒内只可消费一次。接口收到旧字段 `allow_kick` 时忽略该字段。

| 界面动作 | 工作台入口与业务条件 |
|---|---|
| 项目档案同步仓库及常用项目 | `POST /api/m02/sync/{warehouses,common-projects}`，会话字段可用 query 或 JSON body，保留 query 的 `expected_account` |
| 通知书按月取数及新小微仓库查询 | 通知书页用 `POST /api/m03/notices/fetch-jobs`，同步 `POST /api/m03/notices/fetch` 仍可用。仓库查询用 `POST /api/m03/notices/warehouse-check`，i8 接入层沿用 `POST /api/m02/fetch/{preview,run}` |
| 通知书批量打印及只导出 PDF | `POST /api/m03/print-batches/prepare`、`POST /api/m03/batch`，用同一会话读取版式、单头、明细、流程和签名图 |
| 批量关联集采合同 | `POST /api/m11/auto-link-preview` 仅在金额匹配需要时读取一次采购应付。`POST /api/m11/auto-link` 只复核并写入本地关联 |
| 机械费抓取及单项目更新 i8 | `POST /api/m06/workbench/i8-fetch`，取回预览后须选择采用 |
| 收发结存、库存及采购合同抓取 | `POST /api/m07/fetch`、`POST /api/m08/fetch`、`POST /api/m11/fetch`，保留业务范围确认 |

独立 EXE 和诊断脚本沿各自授权执行。i8 配置、执行记录、已准备批次的投递和状态读取、PDF 下载与本地 Excel 导出使用工作台本地结果。HTTP 登录失败后直接报错，会话失效时沿既有规则允许至多一次重新登录及重发当前 i8 请求。有效空响应的单次复核沿各接口既有契约。

直连 Cookie 按 i8 原点和 i8 账号复用。旧缓存须带匹配的原点才能使用。取消在线冲突确认时，页面立即作废本地确认，再提交当前令牌至 POST /api/m02/session/kick-cancel，由服务端按工作台账号撤销。撤回未确认时，页面提示短期令牌将自动失效。

## 设备台账与流动资产调拨（协同办公自定义表单）

2026-11-23 至 24 日在第四工程公司（组织主键 `3700000000000014`）核验了 `sbzx`（流动资产设备台账）和 `ldzcdb`（流动资产调拨）的列表、设备详情、一次设备改号与恢复、一次调拨保存。Edge 扩展新标签直接打开同源 `/ngweb/portal/index.html#/` 可沿用当前 Edge 会话，访问裸根路径 `/` 会跳到登录页。本次使用已有会话，未发起登录或下线操作。

| 方法及路径 | 请求与结果 | 验证范围 |
|---|---|---|
| `POST /sup/customServer/getList` | 表单字段为 `customBusCode`、`containerId=p_form_<业务码>_m_list`、从 0 起的 `page`、行偏移 `start`、页长 `limit`，以及该组织列表的 `clientfilter`、`queryfilter`。返回 `total` 与行数组 `data`。 | 两表在同一组织筛选下实测。设备每页 100 条，3 页共 285 个唯一 `phid`。调拨主表行包含 `phid`、`bill_no`、`bill_dt`、`phid_org`、`phid_pc`、`app_status` 和 `wf_flag`。 |
| `GET /sup/customServer/getInfo` | 查询参数为设备主键 `id`、`oType=edit`、`customBusCode=sbzx` 和页面由主键生成的 `encryptPrimaryKey`。详情主表在 `data.p_form_sbzx_m`。 | 设备详情及各次编辑前的 `ng_record_ver` 已实测。 |
| `POST /sup/customServer/save` | 使用表单编码的 `customBusCode`、JSON 字符串 `data`、`billNoStatus=1`、JSON 字符串 `isContinue`。其中 `warn`、`validateWarn`、`checkProjOrgWarn` 初始值均为字符串 `0`。实测保存字段中无 `encryptPrimaryKey`。 | 两种表单成功均返回 HTTP 200，JSON 中 `status="success"`、`data` 为所存记录的主键字符串、`msg` 和 `total` 为 `null`。`bill_no` 由列表按主键回读。 |

设备主表 `p_form_sbzx_m.form` 的 `key` 为 `phid`。修改提交整个 `modifiedRow` 对象，保留原 `phid` 和写前服务端的整数 `ng_record_ver`。`u_device_code` 为设备编码，最长 50 字符。`bill_name` 为设备名称，`phid_org` 为管理组织，`u_use_org` 为使用组织。编辑提交的 `u_indata` 和 `bill_dt` 为 `YYYY-MM-DD`，列表中 `u_indata` 带零点时间。实测改号后再用新版本改回，三个连续列表版本为 1、2、3，设备主键和项目一致。原为空的 `bill_no` 在首次保存时由 i8 生成，恢复设备编码后仍保留。新增形态沿用前端定义的 `newRow`，设备新增及历史调拨引用变化未实测。

调拨主表 `p_form_ldzcdb_m.form.newRow` 带当前录入人 `phid_fill_psn`、组织 `phid_org`、调出项目 `phid_pc`、方案 `phid_schemeid=3700000000000363` 和 `YYYY-MM-DD` 的 `bill_dt`。本次页面使用默认单据日期，`bill_no`、`bill_name`、`wf_flag`、`app_status` 在提交时为 `null`。明细写入 `p_form_ldzcdb_d`，其 `isChanged` 为 `true`，`table.key` 为 `phid`，`table.newRow` 形如 `[{"row":{...}}]`。首行 `detail_row_no=0`，`key` 和 `rel_key1` 为 `null`。单据引用选择器带出设备主键 `u_sbmc`、设备编码 `u_sbbm`、规格 `u_spe`、单位 `u_msuint` 和调出项目 `phid_pc`，再选择必填的调入项目 `u_inproj`。显示名称以各字段的 `_EXName` 传递。明细的 `imp_info` 为独立 JSON 字符串，包含 `SchemePhId`、`SSign=p_form_sbzx_m`、`TSign=p_form_ldzcdb_d`、`SOrgPhId=3700000000000869`、`STable=p_form_sbzx_m`、`SPk=phid`、`SPkValue`（设备主键）和 `SName=流动资产台账`。

调拨单 `20261124-0001` 保存后按回执主键回读到了单号，`app_status=0`、`wf_flag=0`。同期回读同一设备，`sbzx.phid_pc` 仍为调出项目。2026-11-24 用户在 i8 对该 `ldzcdb` 调拨单执行送审并确认，i8 自动将设备当前项目（`sbzx.phid_pc`）更新为调入项目。

设备新增和调拨先提交本地。启用 `M16_I8_SYNC_ENABLED` 后，前端提交成功才调用 `POST /api/m16/i8-sync/retry`，手动补同步也用同一入口。查询参数 `session_mode=browser&device_id=...` 复用当前浏览器 i8 会话。显式选择 `session_mode=http` 时使用本人账号与当前站点匹配的已缓存 Cookie。连接缺失或取消等待时，本地记录保留待同步。设备接口不会登录、下线或跟随重定向。

2026-11-26 实测 `ldzcdb` 送审使用如下顺序。工作流请求带 `env: java` 和 `gatewayauthparams: ldzcdb|<组织主键>|<当前录入人主键>|ldzcdb|`。会话身份由当前连接提供。

| 方法及路径 | 请求和核对 |
|---|---|
| `POST /sup/customServer/startFlow?customBusCode=ldzcdb` | 预检，JSON 数组含一项 `id=<调拨单 phid>`、`isContinue="0"`、`impSchemeId="3700000000000363"`。必须回同一单据和方案且 `passFlag="1"`。 |
| `GET /WorkFlow3/WorkFlow/GetStartFlowExecutionInfo` | `biztype=ldzcdb`、`bizphid=<调拨单 phid>`、`flowType=1`。核对无运行中的流程、定义 `xzd_102196:2:369735` 及签名和意见要求。已有流程时改为读回。 |
| `GET /WorkFlow3/WorkFlow/GetProcessDynamicInfo` | `procDefId=xzd_102196:2:369735`、`formMetadataId=ldzcdb`、`formPk=<调拨单 phid>`、空 `orgId`、`flowType=1`。核对项目设备员分支。 |
| `POST /WorkFlow3/WorkFlow/CreateProcInst` | 表单字段为 `flowType=1` 和 JSON 字符串 `data`。后者含上面的 `pdid`、`biztype`、`bizphid`，`dynamicNode=[{"sourceId":"ext-gen1795","transitionId":"ext-gen3164","destActId":"ext-gen2225"}]`，以及 `candidateUsersMap={"ext-gen2225":["3700000000000715"]}`（项目设备员史程远）。`minCommentLen=0`、`needsignature=false`、`hasDiagramPermission=true`，`flowdesc` 为空或 null，`remark`、`signature` 为空字符串，`orgId`、`formApproveUserId`、`assignedApproveUsers`、`formUrlParam` 为 null。 |

已关联项目使用项目档案的 `phid` 提交和核对。同一档案下的自定义位置变动只生成本地调拨。以下环境变量使用 JSON，默认为空对象。映射缺失的记录保留待同步。

| 环境变量 | 值 |
|---|---|
| `M16_I8_SYNC_PROJECT_IDS` | 未关联位置的本地名称到已核 i8 `phid_pc`，例如 `{"本地地点名":"项目主键"}` |
| `M16_I8_SYNC_UNIT_IDS` | 已核单位名称到单位主键，例如 `{"台":"单位主键"}` |
| `M16_I8_SYNC_OPERATORS` | 已核 i8 账号到录入人主键和姓名，例如 `{"i8账号":["人员主键","姓名"]}`。调拨建单使用当前会话 i8 账号的配置 |

适配器按完整组织列表精确匹配设备编码。调出项目已配置主键时，以设备当前 `phid_pc` 核对，调拨明细带入 i8 返回的项目名称。设备原值 `u_yz` 按两位小数提交和核对。调拨单保存后先持久化单据主键，再送审。回读 `ldzcdb` 的 `app_status=1`、`wf_flag=2`，并确认同一设备的 `sbzx.phid_pc` 已变为调入项目后才标记已同步。送审发出后回执未知或结果待生效时，重试只回读。送审预检失败且尚未发送时，重试先核对原单，再续办送审。升级前已有的待回读记录沿用原回查流程。

## 抓取回执

通知书后台任务在受理前验证选定的 i8 会话。直连用一条限量查询确认会话，在线冲突仍在受理前返回下线确认。任务复用已验证的客户端读取通知书和所需的采购应付，采购应付按整批读取一次。任务进度及关闭回执通过 `/api/m03/notices/fetch-jobs` 的本地接口读写。

集采、付款通知书、收发结存和库存共用回执摘要。摘要显示本批次的状态、范围、时间、分组统计及待处理提示。各业务按自身口径提供数字。结存和库存的「刷新已有」统计更新过的源行，包含数值相同的行。付款通知书的归属未定行本次不写入，规则剔除行仍按通知书原规则处理。

在「i8 接入层 → 执行记录」按批次查看当时的结果。通知书复用原执行记录明细，结存和库存从新批次开始将写入统计保存在同一条执行记录中。旧批次缺少的统计和明细保持未知。

收到可确认的抓取回执后，若台账重读失败，窗口保留回执并提供「重读台账」。重读仅刷新本地数据。原请求结果未知时沿执行记录核对流程处理。

## 浏览器已有会话通道（`TAIL-476`）

日常抓取及设备同步可复用用户在 Edge 中已登录的 i8 会话。浏览器管理会话材料。
2026-11-05已用真实Edge与原工作台月度抓取按钮完成通知书代表，验证范围见文末；其它端点不由这一代表自动升级为现场已验。

### 通路

`I8Client` → 后端进程内 broker 排队 → 已登录的工作台页面长轮询取走 → 专用 MV3 扩展在自动选中的可用 i8 标签里用 `fetch(credentials:'same-origin')` 发出后端构造的请求 → 回帖 → 各 source 解析。

- 会话留在浏览器里：扩展不读 Cookie、不用 `debugger`、不开远程调试端口；HttpOnly Cookie 由浏览器自动携带（已在隔离 Chromium 里固化为样机判据）。
- 扩展是**无状态搬运工**：不接受任意 URL / 方法 / 头，只执行 broker 分配的票。
- 前端默认选择「浏览器已有会话」，并把明确的选择随业务请求发给工作台。缺少或无效的选择会被拒绝。

### 与既有 HTTP 模式的关系

- **两套策略并存、互不回退**：HTTP 模式先复用本人账号的 Cookie，在线冲突遵循上面的单次确认流程；浏览器模式下站点不符或会话失效就停止。
- 浏览器模式下 `I8Client` 的重登与强踢路径**结构上不可达**：子类 `_login()` 直接抛 `StrictSessionEnded` 并计数，`_ensure_cookie()` 不碰产品会话缓存 ⇒ 不会登录、不会顶掉在线会话、不写 `cookie_store`。
- 浏览器模式连不上就失败（`i8_browser_relay_unavailable`），⛔ 绝不静默改走登录。

浏览器连接代号在操作确认后固定，每条取数均核对原代号。浏览器重连后请重新发起本次操作。

浏览器搬运失败通过回帖的可选`relay_failure`传递固定类别（timeout、redirect、target、network、unavailable、malformed、session-ended），不借HTTP 599推断会话状态。后端在解析HTTP响应前还原严格异常；所有严格停止共用`StrictSessionStopped`基类穿透业务降级。没有该标记的真实上游HTTP错误保持原有业务处理；前端和扩展都不重放失败的取数票。

### 只读端点范围（两侧必须逐条一致）

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/WorkFlow3/WorkFlowApi/getFlowHisForPrint` | 审批流程节点 |
| GET | `/SUP/RichHelp/GetCommonUseList` | 常用项目 |
| GET | `/reportcenter/printManage/getPrintDesign` | 取版式 |
| GET | 同源栅格签名图片路径，带单个非空 `s` 参数 | 读取流程返回的签名图 |
| POST | `/FC/FM/PaymentBill/getList` | 付款通知书列表（`API-01`） |
| POST | `/FC/FM/PaymentBill/getInfo` | 通知单单头 |
| POST | `/FC/FM/PaymentBill/getDetInfo` | 通知单明细 |
| POST | `/PMS/PMM/KcBaseSetting/GetWareHouseList` | 仓库列表（`API-05`） |
| POST | `/reportcenter/reportExport/export` | 库存/结存**二进制报表读取**（xlsx 字节；**不是**实际打印动作） |
| POST | `/PMS/PCM/Contract/ProjBal/GetCntProjBalList` | 采购合同应付 |
| POST | `/PMS/PCM/Contract/GetCntMInfoFirst` | 合同详情（补材料名） |
| POST | `/PMS/PCM/Contract/GetCntMList` | 采购合同列表 |
| POST | `/sup/customServer/getList` | 机械费工作台小列表、设备台账及调拨单回读 |

- 后端及扩展均逐条校验方法和路径。扩展在 service worker 与 i8 标签内各校验一次。
- 拒绝：非以上路径、方法不匹配、`..`、`//`、结尾斜杠、带 userinfo 的地址、非 http(s)。
- 签名图片由两侧校验来源、路径、响应类型及栅格图片文件头。签名图须为 2xx 且具有支持的栅格文件头；接受 `image/*`、`application/octet-stream`、`binary/octet-stream` 或缺失的媒体类型，嵌入时按文件头确定图片格式。将会话失效内容标为图片的响应仍按会话失效停止本批。库存和结存的 `reportExport/export` 返回 xlsx 字节，后端校验长度与文件头。IPP 作业由工作台直接投给设备。

### 设备同步端点范围

设备补同步入口创建的客户端可排队发送两类写入。`POST /sup/customServer/save` 仅接受 `sbzx` 主表及 `ldzcdb` 新单主从表的约定字段。 `POST /WorkFlow3/WorkFlow/CreateProcInst` 仅接受上节定义的 `ldzcdb` 送审载荷。三个预检接口只接受该流程的查询及单据参数。后端入队、扩展 service worker、i8 标签页执行前均核对请求。 `env` 和 `gatewayauthparams` 只随设备流程请求转发。设备同步需要扩展 0.1.7。

### 身份与目标约束

- 用户 2026-11-05 裁定：取消依赖悬浮菜单的账号、组织核验。连接及取数都无需展开账号菜单，扩展不另读隐藏值或凭据替代。
- 工作台保留当前登录身份、本人 i8 绑定和配置站点检查。实际账号和组织由浏览器当前 i8 登录态决定。取数沿现有配置的内部组织范围。
- 扩展连接时读取实际站点，发请求时再次核同源；绑定按 `device_id` 分连接存，保留发送页面/文档归属和正整数代号。
- 请求代号（`generation`）由 broker 进程内发号器给，**每次连接都新建**（断开重连也不复用）；回帖必须带这张票自己的正整数代号，缺省/0/不匹配一律丢弃。

### 超时与停止语义

- 每条请求用它**自己的** read 预算（`httpx.Request.extensions['timeout']['read']`：合同列表 200s、详情 60s、其余默认 30s），broker 不用统一常量截断；扩展按 `timeout_ms` 用 `AbortController` 落实预算。
- 空闲连接清理（120s）只清真正失联的连接：有效轮询及有效回帖更新活动时间，状态查询不续期；排队和在途请求保留原预算。超时票从排队/在途集合移除，恢复后不会迟到执行。
- 用户确认操作后，扩展在已获授权的配置站点自动查找可用标签。没有匹配标签时在后台打开该站点，焦点留在工作台。缺少注入授权或登录态时，窗口提示授权、完成登录，或按浏览器提示临时点击扩展。连接就绪后，只提交一次仍有效的确认。取消、关闭窗口或修改会话模式、身份及业务范围会使等待失效。
- 刷新使用新的文档和连接标识，按账号记住的连接意图恢复通道。标签休眠、临时断线或扩展暂时失联时自动重试。主动断开或切换直连后停止恢复。已提交的业务操作通过原执行记录或批次核对，恢复流程只重建连接。
- 停止都有固定中文文案，超时归超时（`i8_strict_session_ended` 的"没回音"分支），⛔ 不谎称"会话失效"（那会把用户推向重登、反而顶号）。
- 严格停止**穿透业务容错**：补档案、补材料名、抓取降级这些 `except Exception` 落点都先抬出 `Strict*`，不让"身份/目标已失效"被吞成"本条留空""降级为手动 Excel"继续跑。

### 验证状态

- **隔离验收入口**：`apps/browser-extension/tests/browser_smoke.py` 使用交付扩展、隔离工作台、模拟 i8 和 IPP，从通知书抓取、批量打印、只导出 PDF 验证自动续接、签名图和投递回执。
- **真实代表已验**：用户安装固定包并选中i8标签后，工作台原按钮抓取2026-11通知书17条、写入测试副本17条，逐条读回单号/日期/名称/项目/审批金额相等；无模型中转，观察区间无登录、强踢或重定向，副本已清理。见[Git中的验收回执](https://github.com/lysyscy/mtrl-workbench/blob/e79b50fe9bd049ede5fbabdd1152fbddecfed9bb/.scratch/browser-session-loading-20261103/evidence/TAIL-476-daily-live.md)。
- **本轮现场待验**：当前交付扩展在日常 Edge 中加载、真实 i8 登录和业务取数、打印机实际出纸。

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
| `ipp` | 配置的 IPP URI，例如 `ipp://<ip>:631/ipp/print` | IPP 状态及设备返回的作业号、作业状态 | 批量打印先用 Validate-Job 核对显式 A4 |
| `driver` / `raw` | Windows 文件关联打印 / `<ip>:9100` | 无设备作业回执 | 当前实现无法指定作业纸型，批量打印会拦截 |

- **默认 IP** = `192.168.5.248`（**用户已确认无误**，工具与原型一致）
- **实测机型** = **RICOH IM 3000 PS3**（`printer-info` 自报；`printer-state = Idle`）
  设备信息来自历史实测，不能代替本轮设备状态或出纸验证。
- **IPP 状态码**：`0` 成功 · `1` 部分成功 · `1028` **文档格式不支持** · `1280` 服务端错误 …
- **作业状态**：`3` 排队中 · `4` 待处理 · `5` 打印中 · `6` 中断 · `7` 已取消
- ⇒ 工程侧 `.env` 的 `PRINTER_IPP_URL` = **`ipp://192.168.5.248:631/ipp/print`**（**2026-09-16 已真机出纸验证通过**，一次连投 4 张）

### IPP报文与排障边界

整批 PDF 就绪后，先用 Validate-Job 验证显式 A4。Validate-Job 和每个 Print-Job 均在操作属性组 `0x01` 发送 `document-format=application/pdf`（`mimeMediaType`，`0x49`）及 `ipp-attribute-fidelity=true`，在作业属性组 `0x02` 发送 `media=iso_a4_210x297mm`（`keyword`，`0x44`）。自动选择通道也受 A4 校验约束。校验未通过时，可切换通道或导出同一批已生成的 PDF。

IPP 成功表示打印机已接收。回执保留设备返回的作业号、作业状态、`status-message` 及各通道尝试的原因。设备拒绝或发送前连接失败记为明确失败。请求可能已送达但回执中断时记为结果待核实，当前批次禁止自动换通道重投。刷新后读取原批进度和回执。排障优先使用不出纸的属性读取或 Validate-Job。

打印批次及逐张回执保存在工作台运行目录，保留 15 分钟。准备好的 PDF 在内存中暂存，服务重启后可查看原批范围并重新确认准备。投递前先记录正在投递，取得回执后即时保存。服务重启后，已中断的投递批次结束，正在投递的单据显示结果待核实，其余未开始的单据显示待投递。原批按批次编号和工作台账号恢复。

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

## 采购合同列表与详情

列表 `POST /PMS/PCM/Contract/GetCntMList`，query 带 `model=7`、`floatmenuCondition` 和防缓存时间戳，表单包含组织范围、日期和分页条件。详情 `POST /PMS/PCM/Contract/GetCntMInfoFirst`，query 带 `id` 和 `type=cnt`，用于补取材料名。两条路径均从当前生效的 i8 服务地址派生，设置页优先于 `I8_BASE_URL`。已有 `I8_CONTRACT_LIST_URL` 配置会被忽略。取数实现位于 `mod02_i8/contract_source.py`。

## 采购合同应付与附件（2026-10-20 Edge CDP只读核实）

列表POST `/PMS/PCM/Contract/ProjBal/GetCntProjBalList?model=7&floatmenuCondition=`；form带page/start/limit、queryfilter及公司OrgQuery上下文，与采购合同同组织。返回Success/Record/totalRows；PhId为应付键，PhidCnt/PhidCnt_EXName为合同主键/编号，PhidPc_EXName、PhidBalComp_EXName为项目/收款单位，AppAmtVatFc为审批本币额。批量关联取 WfFlag=2、币种为人民币且汇率为 1 的应付，包含 AsrFlag=0 的已完成流程。分页不完整或重复键应拒绝继续关联；取数实现 `mod02_i8/payable_source.py`。

详情POST `/PMS/PCM/Contract/ProjBal/GetCntProjBalInfoFirst`，form `id`。抽查8条invoiceGrid均空，不能据此判定无发票；附件目录使用 **GET** `/JFileSrv/reactAttach/tableAttachInit`，query带asrTable=pcm3_cnt_projbal、asrCode=应付PhId、busTypeCode=PCM_BAL7；返回code/data/message，code=200时从data.attachmentRecordList取文件列表，asrFid是文件键，asrName是文件名（2026-10-23浏览器会话只读核实，POST不受支持）。PDF预览可取得文字层；不在正文存签名文件URL、Token或Cookie。已核样本不代表全历史覆盖。

### 附件预览文件读取（2026-10-23 已验证）

POST `/JFileSrv/api/getPreviewUrl`，JSON带`asrFids`文件键数组、当前会话的`loginId`/`orgId`、`busTypeCode=PCM_BAL7`，本次`wmDisabled="1"`、`billWM=""`沿页面实际参数。响应`code=200`、`data`为文件键到相对预览文件路径的映射；随后GET返回的`/JFileSrv/previewFiles/...`地址，保留服务生成的签名参数，不自行拼接、修改或长期保存。实际验证单键及最多20键一批、99个PDF/图片读取成功；检验Word不作为发票来源，未验证其预览转换。

调用复用I8Client及当前浏览器恢复的会话，未重新登录或踢人；目录与文件读取不修改业务单据，页面原生PDF预览空白不等于文件无法下载。预览转换可能产生服务端缓存；未验证永久缓存期限或原件下载接口，不登记为通用原件下载能力。未新增常驻封装；Cookie/签名URL不入Git。
