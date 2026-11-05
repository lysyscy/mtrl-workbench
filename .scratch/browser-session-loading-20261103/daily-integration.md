# i8 日常抓取接入：工作台按钮直接用浏览器已有会话

2026-11-05最新结果：用户安装固定扩展后，原工作台日常按钮抓取2026-11通知书17条、写入17条并逐条读回一致；真实代表已通过，正式服务未部署。当前事实以[真实验收](evidence/TAIL-476-daily-live.md)为准。

以下为第六轮实施时的历史回执（按 `evidence/review-closure.md` 具名修复；当时尚未验收），其中“未授权/未执行/未验”只描述该轮时点。
读者：主控 / 审阅人。本文只回答一件事：用户点工作台现有日常抓取按钮时，如何复用本机浏览器里**已有**的 i8 登录态完成取数，**不需要 Codex/DSH 模型逐条中转**。

结论分三档：`[已证]` 已由源码 / 已跑命令 / 第一方文档核实；`[待样]` 必须样机验证；`[未验]` 未验证。
**本轮状态**：后端 + 扩展 + 契约文档已落地并有退出码（§9、§11）；本轮对 `apps/frontend/` 改动为 **0 行**
（前端按 closure §3 的消息形状由另一会话接线，字段未变）。真实 Edge 安装、真实业务取数**均未执行**，一切真实验收项未勾。

---

## 0. 本轮（第 6 轮）按 closure 具名修复的七处（先看这里）

本轮**不重跑全量审查**，只处置 `evidence/review-closure.md` 里主控接受的具名项。

| # | closure 指出的问题 | 本轮处理 | 位置 |
|---|---|---|---|
| 1 | 维护页查 i8 仓库名单没带取数方式，选了浏览器仍会去登录 | `WarehouseCheckRequest` 加 `session_mode`/`device_id`；`warehouse_check` 用 `scope_of(req)` 包住取数；严格停止**不被"回落上次缓存"吞掉** | `mod03_notice/{schemas,router}.py`；`test_i8_strict_propagation.py` 断言作用域真是 `(browser, device)`、缺省仍是 `(http, "")` |
| 2 | 采购合同列表被白名单挡住、被要求改回直连 | 后端与扩展**两侧**白名单补 `POST /PMS/PCM/Contract/GetCntMList`（正式 `I8_CONTRACT_LIST_URL` 实测值、无查询参数）；删掉"请改用直连"的说法 | `browser_relay.py`、`service_worker.js`、`i8-contract.md`；样机有一条真浏览器判据真发出去 |
| 3 | 合同列表 200s / 详情 60s 被 broker 30s 截断；空闲清理误杀在途；超时谎称会话失效 | 每条请求的 read 预算从 `httpx.Request.extensions["timeout"]["read"]` 取 → `PendingRequest.timeout_seconds` → `outbound_payload()["timeout_ms"]` → 扩展 `AbortController`；`wait()` 默认用该票预算；有在途请求时不算空闲；超时用超时语义 | `browser_relay._request_read_timeout`、`browser_broker.{enqueue,wait,connection_of}`、`service_worker.executeInPage` |
| 4 | 全局 `pendingIdentity`/`BOUND_KEY` 会让另一个页面把连接顶掉 | 待核身份改 `Map<device_id>`；绑定基准改 `i8RelayBound:<device_id>`；`bind` 校验 `device_id` + 正整数 `generation` + 服务端核对过的身份 + **当前 DOM 再核一次**；`execute` 按请求的 `device_id` 核该连接；`unbind` 只撤本连接 | `service_worker.js`；扩展新增 8 例 |
| 5 | `disconnect` 打不存在的连接会崩；断开重连 `generation` 回 1；`complete` 传 0 能绕过代号 | `disconnect()` 幂等；发号器改进程内单调（含断开后重连）；`complete()` 要求正整数且相等；`ticket` 改不透明唯一 ID；删无消费者字段与不实注释 | `browser_broker.py` |
| 6 | 候选通道协议/只读范围/适用范围没登记进契约 | `docs/reference/i8-contract.md` 新增一节（59 行）：用途、与 HTTP 模式的关系、12 条只读端点、身份与目标约束、超时与停止语义、验证状态（候选 · 真实未验） | `i8-contract.md` |
| 7 | 业务容错可能吞掉严格停止后继续取数/部分采用 | `Strict*`（含子类 `BrowserRelayUnavailable`）在 5 处业务容错前**先抬出去**；普通单条业务失败容错保持原样 | `sources.py`、`contract_source.py`、mod02 router、mod07/mod08/mod11；新增 32 例 + 变异验证 |

范围判断（主控已定）：打印原策略**不在**本通道内、本轮 0 改动；`reportExport` 是库存/结存二进制读取、
**不等于**实际打印，保留；组织映射留 `mod02_i8/i8_identity.py`，不下沉 `core`。

---

## 1. 推荐方案（一句话）

**后端进程内 broker 保存"这一条待发请求"，工作台页面长轮询取走并交给 Edge 伴随扩展，扩展在用户选中的已登录 i8 标签里以同源 `fetch` 执行，把状态/头/字节原样交回后端；后端仍用既有 `I8Client` 解析链完成校验与解析，抓取后的业务链一行不改。**

- 请求由**后端**构造（既有 `LIST_FORM`、`queryfilter`、分页、`limit` 全部不变）。
- 响应由**后端**解析（既有 `_is_session_invalid`、`get_json/post_json`、`_extract_records`、`_map_record` 全部不变）。
- 浏览器只做一件事：在**当前已登录的 i8 页面**里，用该页面自己的 Cookie 发一条同源请求，把原始响应交回。
- 不导出/不解密/不导入 Cookie；不复制浏览器配置；不依赖模型在线；不新增常驻服务。

被否掉的替代路线（并附本轮再次确认的理由）：

| 替代 | 否决理由 |
|---|---|
| Agent/CLI 逐请求转接（`tools/dev/i8_browser_session_reuse.py` + 临时 transport） | 要模型在场；用户已明确"日常抓取能用才算能用"。保留为离线/现场取证工具，**不是**日常通道 |
| 后端直连浏览器远程调试端口 | 需要开远程调试端口或改安全设置，硬约束禁止（§14 说明这与"CDP 曾能用"不冲突） |
| 后端读浏览器 Cookie 库（DPAPI / ABE） | 等于导出解密浏览器 Cookie，禁止；Edge 127+ 的 App-Bound Encryption 本就阻断 |
| 手工粘贴 Cookie | 持久导入会话 + 凭据进后端，禁止 |
| 前端直连 i8 取数 | 造平行取数系统，绕过既有校验/解析/落库链，禁止 |
| 新增常驻本地服务 | 禁止；且要另开端口、另做鉴权与生命周期 |
| 复用 Codex/DSH 私有桥（ego 扩展通道、内部 CDP 管道、配对令牌） | 私有管道不是可发布 API，且把日常运行绑回模型宿主 |

---

## 2. 日常操作步骤（用户视角）

1. **一次性**：Edge 里装上本项目发布的伴随扩展（`apps/browser-extension/`），按 §12 授予最小权限。
   **不需要填任何扩展 ID、也不需要改 manifest**（固定 `key` ⇒ ID 恒定；`externally_connectable` 已含生产与预览端口）。
2. **每天**：正常在 Edge 登录 i8，停在业务页（保留原有标签与未保存状态，**不要求退出、不要求关页**）。
   - 扩展按**已现场核对过的窄 DOM** 读账号/组织，不再有"填 CSS 选择器"的选项页（该流程已退役）。
3. 打开工作台 → 「i8 接入」页 → 点扩展图标选中那个 i8 标签 → 回工作台点「连接浏览器会话」。
   - i8 页面的账号/组织通常只在**展开的账号面板**里可见；若工作台提示读不到，请先展开面板再点连接。
   - 连接时会核站点、账号（与本人绑定的 i8 账号比对）、组织（名称 + 短码），三项任一不符/读不到即明确失败。
4. 到抓取弹窗确认「会话来源：浏览器已有会话」→ 点原有抓取按钮 → 取数完成，结果与执行记录照旧。
5. 若中途提示"会话已失效"或"超时"：前者自己回 Edge 重新登录 i8 再试，后者稍后重试；
   **不自动重登、不自动重试、不强踢**；**不会**自动切回直连。

模型、CLI、DSH 会话在第 4–6 步全程不参与。

---

## 3. 责任边界

| 角色 | 只做 | 绝不做 |
|---|---|---|
| **后端** | 校验连接（身份/组织/站点）、构造请求、持有严格客户端、校验响应、解析、落库/执行记录、broker 排队 | 不碰浏览器文件、浏览器模式下不调 `http_login`/强踢/`cookie_store` |
| **工作台页面** | 长轮询取待办、交给扩展、回帖、展示状态 | 不构造 i8 请求、不解析业务字段、不留存响应正文 |
| **伴随扩展** | 找用户选中的已登录 i8 标签、在其中执行**后端给的那一条** fetch、把 status/头/字节原样回传 | 不拼 URL、不猜端点、不跟随重定向、不读 Cookie、不存会话、不做第二跳 |
| **i8 标签** | 提供同源 Cookie 上下文 | 不改 DOM、不点按钮、不触发业务动作、不刷新 |

扩展是**无状态搬运工**：不接受任意 URL，只执行 broker 分配的那一张票；离开这次抓取没有入口。

---

## 4. 传输与控制流（实际实现）

```
后端 I8Client.request() → BrowserRelayTransport.handle_request()
   ①核目标 origin（逐请求，不是只核 base）→ ②脱敏请求头 → ③enqueue 并挂起
        ↓
页面 GET /api/m02/browser/pending?device_id=…（长轮询，上限短于后端等待）
        ↓
页面 chrome.runtime.sendMessage(extensionId, {type:'i8-relay:execute', device_id, request})
        ↓
扩展 scripting.executeScript({world:'ISOLATED', func, args:[payload, 白名单, 方法, 端点, timeout_ms]})
   → i8 标签 fetch(credentials:'same-origin', redirect:'manual', signal=AbortController(timeout_ms))
        ↓
页面 POST /api/m02/browser/complete {ticket, generation, status, headers, body_b64, declared_length}
        ↓
broker 唤醒 → 既有解析链（_is_session_invalid / get_json / NoticeFetcher / _extract_records / _map_record）
```

- `request` 形状（双方共用，字段不可改）：`{ticket, generation, method, url, headers, body_b64, timeout_ms}`；
  `timeout_ms` 由后端按这条请求自己的 read 预算给出（§8）。
- `identity` / `bind` / `unbind` 消息都带 `device_id`；`bind` 另带服务端给的正整数 `generation`
  与刚被服务端核对的 `identity`，扩展核"与该连接待核值 + 当前 DOM 一致"才绑定。

复用点**一行不改**：`I8Client.request()` → `_is_session_invalid()` → `get_json/post_json` → `notice_source.NoticeFetcher` → `_extract_records` → `_map_record`。
新增的只有：一个 `httpx.BaseTransport` 实现 + 一个进程内 broker + 页面/扩展两端的搬运代码。

**业务流程照旧**：`mod03_notice/notice_executors.py` 的 `_exec()` 只把会话来源从 `I8Client(...)` 换成 `open_i8_client(...)`，其余**不动**——`effective_rules` → `rows_needing_ownership` → `resolve_ownership` → `sync_and_archive`（缺档时复用同一个 client 拉常用项目/仓库）→ `apply_fetched_row` 落库 → `finish_run_record` 执行记录。浏览器模式失败时同样落一条 failed 执行记录，而不是悄悄降级。

`[已证]` 后端单进程单 worker（`ops/nssm_install.ps1:59,136`；`ops/frontend_release.py:230` 校验同一命令）⇒ 进程内 broker 可行。
`[已证]` `mod02_i8` 路由全是同步 `def` ⇒ FastAPI 线程池执行，阻塞式 transport 天然合适。
`[已证]` 全仓无 SSE/`StreamingResponse`/`EventSource` ⇒ 长轮询是新机制，超时与中断必须自己写。

---

## 5. 什么时候必须停（实现里落成的停止点）

| 条件 | 停止点 | 用户看到（受控文案，不拼异常原文） |
|---|---|---|
| 没装扩展 | 页面侧，未进后端 | "没有检测到浏览器扩展，请按安装说明装好后再连接" |
| 没选中 i8 标签 | 扩展侧，未发任何请求 | "还没有选中 i8 标签…" |
| 没带 `device_id` | 扩展侧（identity/bind/unbind/execute 全拒，不发请求） | "缺少连接标识…请回「i8 接入」页重新连接" |
| `bind` 缺/非法 `generation`（`0`/负数/小数/非数） | 扩展侧 | "绑定时缺少有效的连接代号…" |
| 站点与工作台配置不一致 | 后端连接时 + transport 逐请求 | "浏览器里的 i8 站点与工作台当前配置不一致，本次已停止" |
| 读不到 i8 页面账号 / 组织 | 后端连接时 | "没读到 i8 页面上的登录账号（组织），无法确认这个会话是本人的…本次未建立连接" |
| 账号 ≠ 本人绑定 i8 账号 | 后端连接时 | "i8 页面当前登录的账号与工作台本人绑定的 i8 账号不一致…" |
| 组织 ≠ 取数组织 | 后端连接时 | "浏览器里 i8 当前组织与工作台取数使用的组织不一致…" |
| 会话失效 | 既有 `_is_session_invalid` → 严格客户端 `_login()` 抛 `StrictSessionEnded` | "浏览器里的 i8 会话已经不认了，本次已停止（没有重新登录、也没有顶掉任何在线会话）" |
| 被重定向 | **真机是不透明响应**（`opaqueredirect`、status 0、读不到 Location）⇒ 扩展侧直接停；后端 `StrictRedirectStopped` 只是兜底 | "浏览器返回了不透明响应（无法核对结果）" |
| 页面关闭 / 等不到回帖 | broker 按**该票预算**等待 | "浏览器那边一直没有回音，本次已停止（没有重新登录，也没有重试）" |
| **请求超时** | 扩展 `AbortController`（按 `timeout_ms`） | "这条请求超过它自己的时间预算还没回来，本次已停止（超时）。没有重试，也没有当成登录状态问题。" |
| 回帖代号缺失/为 0/与票不符 | broker `complete()` | 丢弃回帖，等待方按"连接被替换"停 |
| 响应体长度对不上（截断） | transport 长度核对 | "浏览器回的响应体长度对不上（传输可能被截断），本次已停止" |
| 响应不是 JSON / 解码失败 | 严格客户端 `_json_or_stop` | "i8 那边的这次取数没成功"（固定文案） |

全部停止路径**不触发**：登录、强踢、`cookie_store.save`、自动重试、降级到 HTTP。

---

## 6. 身份核对

- **比对对象是 i8 账号，不是工作台账号**：后端取 `current_i8_credentials()[0]`（工作台本人绑定的 i8 账号；"有身份但没绑 i8"照既有规则抛 `MustReportError`，不回落 `.env`）与扩展从 i8 页面读到的可见账号**逐字比对**。
- **两种组织标识不混算**：`expected_org_id()` 从既有 `sources.WH_PARAMS["orgQuery"]` 解析出**内部号** `3700000000000014`；i8 页面可见的是"第四工程公司 | **109**"。换算集中在 `i8_identity.ORG_MAP`（只登记已核的这一对本部署映射），**未知映射直接失败**——不把内部号与可见短码直接相等比较。
- **身份在每一条请求前重核**（不只是连接时一次）：`identityStillBound()` 每次重读页面账号/组织并比对绑定基准，同源换号或换组织立即停。
- **读不到就停**：账号或组织任一为空 ⇒ 拒绝连接并提示"请在 i8 页面展开账号面板后再点连接"。**不使用 `declared_target` 之类用户声明充当机器核验**；`facts()` 里 `declared_target_machine_checked` 恒为 `false`、`identity_cross_checked` 恒为 `false`。
- **不猜接口、不读 Cookie/令牌**：身份只来自 i8 页面**可见文本**，由扩展按**已现场核对过的窄 DOM 结构**读取（不是让用户填选择器；选项页与选择器流程已退役）。原始账号/姓名**不进 Git、不进日志**。
- 固定 `LIST_FORM["phidOrgList"]` 的组织过滤**不等于**证明会话身份：它只说明"本入口没有改写组织参数"，不证明服务端按该组织裁剪，也不说明这个会话是谁的。

---

## 7. 身份门、并发与设备隔离

- **不绕过任何既有门**：`/api/m02/browser/*` 与其它接口走同一套中间件（会话加载、未登录写动作 401、IP 白名单、request_id）。前端所有调用都走 `requestJson()`，因此 `401` 仍按既有语义 `dispatchEvent('session-lost')` 并抛错，本地身份未核时照旧等待（`api.ts` 的 `identityCheck`）。
- **两类失败分开**：`ApiError.status > 0`（400/409/502/401/403）⇒ **立刻停**，不重试；网络类异常 ⇒ 有限退避（≤3 次）后停。绝不把网络抖动当"身份失效"，也绝不把身份失效当"重试一下"。
- **owner 只认服务端身份**：broker 的键是 `(current_name(), device_id)`；`owner` 一律由后端从会话 cookie 取，**客户端声明的 owner 一概不信**（回帖只按"服务端身份 + 本页 device"找票，别人的票回不进来）。
- **设备/连接隔离**：`device_id` 每页一份、只放 `sessionStorage`（`crypto.randomUUID()` 前缀 `dev-`，不落盘、不入库、不是凭据）；登出/换号时页面清掉它（`resetBrowserRelay()` 只清本地、**不发请求**，避免此刻 401 自激）。
- **扩展侧也按连接隔离**（本轮修正）：待核身份是 `Map<device_id, identity>`、绑定基准是 `i8RelayBound:<device_id>` ——
  不再是全局单值。所以**另一个页面/另一条连接**的 identity 或 bind **不会覆盖**这一条的基准；
  `unbind` 只撤自己那条；用户换选 i8 标签时才 `clearAllBindings()`（旧标签的绑定全部失效）。
  `execute` 每一条都按该请求的 `device_id` 核绑定，并再比一次当前 DOM。
- **换号/断连/过期清队列**：`clear_owner(owner)` 把该账号的连接与在途请求判 `switched`；`disconnect` 判 `disconnected`（**幂等**，不存在的连接不会抛）；按该票预算等不到回帖判 `timeout`；同键重连把旧队列判 `replaced`——四条都让等待方拿到**受控停止**，不是静默挂死。
- **不自动回退 HTTP**：浏览器模式下若连接不在，`open_i8_client` 当场抛 `BrowserRelayUnavailable`；不会"顺手用账号密码登录一次"。
- **同表串行照旧**：既有 `serialize_fetch`（同表锁）仍然生效，浏览器模式不另开一条并发路径。

---

## 8. 只读白名单、超时预算与二进制完整性

- **只读接口逐项允许，不接受任意 URL/方法/头**：
  - **12 条只读端点**（与 `docs/reference/i8-contract.md` 新增的"浏览器已有会话通道"一节、后端
    `browser_relay._READONLY_ENDPOINTS`、扩展 `READONLY_ENDPOINTS` 三处**逐条一致**）：
    GET 3 条（流程历史、常用项列表、取版式 `getPrintDesign`）；POST 9 条（付款通知书
    `getList|getInfo|getDetInfo`、仓库名单、报表导出、合同应付、合同详情、
    **合同列表 `GetCntMList`**、`/sup/customServer/getList`）。改一处就必须同步改另外两处。
  - 方法白名单：`GET` / `POST`（i8 取数实际只用这两种）；后端注入脚本前先拒，扩展这侧再拒一次。
  - 请求头白名单：`accept`、`content-type`、`x-requested-with`、`accept-language`；**`cookie`/`authorization`/`proxy-authorization`/`host`/`content-length`/`set-cookie`/`referer`/`origin` 显式拒绝**（黑名单 + 白名单双保险）。**不向扩展提供任何秘密**——扩展根本拿不到 Cookie，它靠"在页面里发请求"自然带上同源 Cookie。
  - 响应头只回传 `content-type`/`content-length`/`location`。
  - 目标：transport 对**每一条**请求核对 origin，扩展再核一次"必须与选中标签同源"；`//evil.test/x` 这类协议相对地址在 join 后会被识别并拦下（有离线用例）。
  - 重定向：`redirect:'manual'`。⚠️ 真机实测跳转返回的是**不透明响应**（`opaqueredirect`、status 0、读不到 Location），所以扩展见不透明响应即停，**读不出"跳到哪了"**；后端 `_decode_reply` 里的 3xx 分支只是兜底。**非 JSON 也停**。
- **时长预算跟着每条请求自己的 read 超时走，不另设业务预算**：`httpx` 把 `Timeout.as_dict()` 写进 `Request.extensions["timeout"]`（`BaseClient._build_request` / `_set_timeout`），所以 `post_json(..., timeout=LIST_TIMEOUT)` 的**合同列表 200s**、`DETAIL_TIMEOUT` 的**详情 60s**、其余默认 **30s** 会原样传到 broker：`_request_read_timeout()` → `PendingRequest.timeout_seconds` → `outbound_payload()["timeout_ms"]` → 扩展 `AbortController`；`wait()` 也按**这张票自己的**预算等。`RELAY_WAIT_SECONDS = 30.0` 只是取不到预算时的兜底。⛔ 别在这里统一成 30s（那会把 200s 的正常请求凭空判死）。长轮询上限取更短值（`PENDING_WAIT_SECONDS = 10.0`）。
- **空闲清理不误杀在途**：连接空闲 120s 才清，且 `connection_of()` 先看该连接**有没有挂起/在途请求** —— 一个慢慢跑的 200s 合同列表不会在第 121 秒被判成"页面关了 / 连接已断开"。
- **超时就说超时**：扩展 `AbortError` ⇒ "这条请求超过它自己的时间预算还没回来，本次已停止（超时）。没有重试，也没有当成登录状态问题。" **不**谎称会话失效（那会把用户推向重登、反而顶号）。
- **二进制靠完整性而非阈值**：扩展自己数 `declared_length`，后端拿它与实际解码长度比对，**对不上即判截断并停止**（不说"8MB 上限"）；base64 解码失败也停。这条做过离线与真浏览器验证：300+ 字节二进制（含 `PK\x03\x04` 头）无损往返。
- `[待样]` 真实 xlsx 导出的实际大小、是否需要分块 —— 不先设阈值，等样机量到再讨论。

---

## 9. 实际改动文件（全部在本票写域内）

> 本轮（第 6 轮）只动**后台 + 扩展 + 契约文档**：`apps/frontend/` 改动 **0 行**（前端按 closure §3 的消息形状由另一会话接线）。

| 文件 | 状态 | 作用 |
|---|---|---|
| `backend/app/mod02_i8/browser_broker.py` | 新增 425 行 | 进程内 broker：连接登记、进程内代号发号器、排队、长轮询取活、`_inflight` 一次性回帖、按请求预算等待、四类受控停止 |
| `backend/app/mod02_i8/browser_relay.py` | 新增 399 行 | `BrowserRelayTransport`（httpx transport，逐请求核 origin + 只读白名单 + read 预算透传）+ `relay_scope`/`scope_of`/`resolve_mode` + **可复用工厂 `open_i8_client`** |
| `backend/app/mod02_i8/browser_session.py` | 274 行（第 2 轮） | 严格客户端：结构上不能登录/强踢/写缓存 |
| `backend/app/mod02_i8/i8_identity.py` | 118 行 | 可见身份、内部组织号 ↔ 可见短码/名称的**显式映射**、身份比对 |
| `backend/app/mod02_i8/sources.py` | 改 | `load_warehouse_rows` **放行** `Strict*`（不再当"补档案失败"） |
| `backend/app/mod02_i8/contract_source.py` | 改 | `fetch_item_name` **放行** `Strict*`；单条业务失败仍返回空串 |
| `backend/app/mod02_i8/router.py` | 改 | 5 个 Browser* 路由；`/config` 扩键；三个自建客户端走工厂；`fetch_preview`/`fetch_run` 不把严格停止说成"降级为手动 Excel"（`fetch_run` 先落失败执行记录再抛） |
| `backend/app/mod02_i8/schemas.py` | 改 | 5 个 Browser* 模型 + `session_mode`/`device_id` 入参 |
| `backend/app/mod03_notice/schemas.py` | 改 | `FetchRequest` / `WarehouseCheckRequest` 均带 `session_mode`（默认 `http`）/`device_id` |
| `backend/app/mod03_notice/router.py` | 改 | 抓取与仓库名单查询都用 `scope_of(...)` 包住；严格停止不被缓存兜底吞掉 |
| `backend/app/mod03_notice/notice_executors.py` | 改 | 抓取主链路**唯一**构造点走 `open_i8_client`（业务链其余不动；打印链路 `get_batch_executor` **未动**） |
| `backend/app/mod06_proc/{workbench_i8,workbench_api}.py` | 改 | 机械工作台读取走工厂 + 作用域 |
| `backend/app/mod07_setl/{fetch_service,api}.py` | 改 | 结算抓取工厂 + `scope_of` + 严格穿透 |
| `backend/app/mod08_inv/{fetch_service,router}.py` | 改 | 库存抓取工厂 + `scope_of` + 严格穿透 |
| `backend/app/mod11_jc/{fetch_service,api}.py` | 改 | 集采抓取/应付读取工厂 + `scope_of` + 两处严格穿透 |
| `apps/browser-extension/service_worker.js` | 新增 564 行 | 已核 DOM 窄适配器 + 双侧一致的白名单 + 按 `device_id` 隔离绑定 + `timeout_ms` → `AbortController` |
| `apps/browser-extension/manifest.json` | 新增 19 行 | MV3；`activeTab`+`scripting`+`storage`；固定 `key` ⇒ 稳定 ID `jfkgliolimmpceandogfimjkadplidem`；`externally_connectable` 四条 |
| `apps/browser-extension/README.md` | 78 行 | 安装/卸载、最小权限、账号面板需展开、限制（真实未验） |
| `docs/reference/i8-contract.md` | +59 行 | 登记候选浏览器通道协议、12 条只读端点、身份与目标约束、超时与停止语义、验证状态 |
| `backend/tests/test_i8_browser_relay.py` | 784 行 / **66 例** | 后端协议测试（白名单 10 组伪装、generation 4 例、身份映射、工厂反向验证）+ 幂等/断连重连不回 1/回帖代号缺省非正数拒/票不透明/每请求读超时预算/空闲清理不误杀在途 |
| `backend/tests/test_i8_strict_propagation.py` | 325 行 / **32 例（本轮新增）** | 严格停止穿透 5 处 + 普通失败仍降级的对照 |
| `apps/browser-extension/tests/protocol.test.mjs` | 686 行 / **26 例** | 扩展协议测试（vm 替身，按真实 API 签名收紧） |
| `apps/browser-extension/tests/browser_smoke.py` | 628 行 / **25 判据** | **真浏览器样机**（独立临时 profile、假站点、不碰用户 profile） |

**范围外（已确认不动）**：`shared read-region`/grid、其它业务前端、票与共享索引、`docs/`、`core/*`、部署脚本、`CONTRIBUTING.md` 等他人改动。

**可复用工厂**：`open_i8_client(allow_kick=…, owner=…)` 是给其它日常读取口（仓库、常用项目、合同、应付……）复用同一条浏览器通道的**唯一入口**；其它模块要接，只改各自的构造点，解析与数据源一律不动。

---

## 10. 模式从哪一层选

- **连接与模式都在「i8 接入」页**（`apps/frontend/src/i8.tsx` 的 `I8BrowserRelay`）：连接 / 断开 / 显示站点·账号·组织 / 「取数方式」`Segmented` 两档（工作台直连 / 浏览器已有会话）。一个账号 + 一个浏览器工作区 = 一条连接 + 一个模式。
- **模式提升到账号工作区级 provider**（`apps/frontend/src/i8-session.tsx`，挂在 `main.tsx` 的 `AccountWorkspace` 里）：**不是每个抓取弹窗各选一套**，也不是全局开关。通知抓取、项目同步、库存抓取、自动关联、合同抓取、机械台账六个日常入口都消费同一个 `useI8Session()`。
- **抓取弹窗只回显不选择**（`notice-fetch.tsx`）：显示"会话来源：浏览器已有会话（在「i8 接入」页切换）"；选了浏览器但连接不在 ⇒ 按钮禁用并提示去连接，**本次不会改用登录方式**。
- **模式只有用户能改**：断开、刷新、抓取失败、服务端说"没连了"，都**不会**自动切回直连（否则下一次抓取就会去登录、可能顶号）；要改回直连得用户自己在「取数方式」里切。
- **默认 `http` 与改动前逐字节一致**：`session_mode` 缺省 `http` ⇒ 旧调用行为不变，仍带 `allow_kick: true`；`browser` 分支**不带** `allow_kick`。
- **选了 browser 但没连接 ⇒ 明确失败**，提示去「i8 接入」页连接；`resolve_mode()` 对认不出来的值也是直接拒。

---

## 11. 已验证的命令与结果（第 6 轮实跑）

| 命令 | 退出码 | 结果 |
|---|---|---|
| `backend/.venv/Scripts/python.exe -B -X utf8 -m pytest tests/test_i8_browser_relay.py tests/test_i8_strict_propagation.py tests/test_i8_browser_session_reuse.py tests/test_i8_cookie_cache.py tests/test_i8_ui_policy.py tests/test_layering.py tests/test_i8_contract.py -o addopts= -q` | **0** | **164 passed in 8.43s** |
| 同上，仅 `tests/test_i8_strict_propagation.py` | **0** | 32 passed |
| 同上，仅 `tests/test_i8_browser_relay.py` | **0** | 66 passed |
| `pytest tests/test_acc_prj_wh_check.py -o addopts= -q`（仓库名单入口既有验收） | **0** | 8 passed |
| `pytest tests/test_acc_jc_fetch_orch.py -o addopts= -q` | 非 0 | 3 failed / 8 passed，原因 `RuntimeError: DATABASE_URL 未配置`（`app/core/db.py:40`）⇒ DB fixture 用例，**按指令只由主控经 `backend_verify.py --source-env` 跑 ⇒ 本轮未验，不是失败** |
| `node --test apps/browser-extension/tests/protocol.test.mjs` | **0** | tests 26 / pass 26 / fail 0 |
| `backend/.venv/Scripts/python.exe -B -X utf8 apps/browser-extension/tests/browser_smoke.py` | **0** | **25 条判据全部通过**（真浏览器、独立临时 profile、端口 8071） |
| `%TEMP%\i8-smoke-profile-*` 残留检查 | **0** | 无残留 |

**本轮复核指出、已修掉的真缺陷（第 6 轮）**：

1. **`disconnect` 打不存在的连接会崩**：`AttributeError: 'NoneType' object has no attribute 'clear'`（已复现）。原因是先 `self._queues.pop(key)` 再让 `_fail_queue` 对 `None` 调 `clear()`。修法：`disconnect()` 幂等，只 `pop` 连接 + `_fail_queue`（后者自己容忍空队列）。
2. **断开重连后 `generation` 回到 1**：旧实现 `当前连接代号 + 1`，而断开时连接已被摘掉 ⇒ 重连又发 1，上一代的迟到回帖会撞上新代。修法：broker 进程内单调发号器 `_generation_seq`，每次 `connect()` 都 `+= 1`。
3. **`complete(..., generation=0)` 能绕过代号校验**：旧判据 `if generation and generation != item.generation` 对 0 短路。修法：要求正整数且等于该票代号，缺省/0/负数一律拒。
4. **严格停止被业务容错吞掉**：`load_warehouse_rows` / `fetch_item_name` 原本 `except Exception` 一律降级 ⇒ 浏览器方式下"会话没了"会被当成"补档案失败"继续往下跑（甚至部分采用）。修法：`Strict*` 先抬；**变异验证**删掉两处 `raise` 后 6 例立刻红。
5. **仓库名单查询入口根本没进作用域**：`WarehouseCheckRequest` 没有 `session_mode`/`device_id`，选了浏览器方式仍按直连登录。修法：加两字段 + `scope_of(req)` 包住取数（严格停止不被缓存兜底吞掉）。
6. **合同列表被白名单挡住**：正式 `I8_CONTRACT_LIST_URL` 就是 `POST /PMS/PCM/Contract/GetCntMList`，两侧白名单都补上。
7. **回帖代号对不上时谎称"连接被替换"**（补定向用例时暴露）：`complete()` 的代号不符分支复用了 `stopped="replaced"`，用户会看到"同一次连接被新的连接替换"——实际是页面回了一份对不上代号的票，与"谁顶了你的连接"完全无关。修法：单独的受控原因 `"rejected"`，并断言 `pending.status is None`。
8. **`browser_broker` 模块注释两处不实**（自查发现）：自称"内存表 + 条件变量"（实际只有 `dict`/`deque` + 每条请求自己的 `threading.Event`，没有任何 `threading.Condition`）、自称判停抛 `StrictSessionUnavailable`（实际 `wait()` 抛 `StrictSessionEnded`）。已按实际实现改正。

**第 5 轮记录的六个缺陷仍然有效**（都已修，见 `evidence/TAIL-476.md` §B）：
broker `_inflight`、注入函数模块作用域、页面忙等、仓库/常用项目绕回登录、`chrome.storage.session.set` 签名、`redirect:'manual'` 不透明响应。

**既有欠账（与本票无关，改动前即红）**：`backend/tests/test_ux_text.py::test_用户可见串里不许拼异常正文` 报 `backend/app/mod02_i8/router.py` 与 `backend/app/mod08_inv/adjustment_values.py` 拼接 `{exc}`（后者不在写域；前者虽在本票改动文件内，但该断言属他人负责的既有权衡，本轮未动）。`apps/frontend/src/big.tsx` 有多条 TS6133（他人并行改动）。`backend_verify.py --source-env` 未提供 ⇒ 依赖数据库 fixture 的用例本轮未运行（非通过非失败）。

---

## 12. 安装时必须由用户确认的动作（全部尚未授权）

1. **安装伴随扩展**（一次性）：`edge://extensions` → 开发者模式 → 加载解压缩的 `apps/browser-extension/`。商店发布需另立授权。
2. **权限最小集**（manifest 现状）：`activeTab`（用户**点扩展图标**才授予当前标签）、`scripting`（在标签里执行那一条 fetch）、`storage`（存选中的标签与**按连接分开**的身份基准）。
   - **不申请**：`cookies`、`debugger`、`webRequest`、`tabs`、`<all_urls>`、`host_permissions` 通配。
   - `[已证]` 不需要 `cookies` 权限也能复用会话：HttpOnly 会话 Cookie 由浏览器**自动携带**在同源 fetch 上
     （样机三条判据：自动带上、`document.cookie` 读不到、页面手塞的 `Cookie` 头被浏览器过滤）。
3. **`externally_connectable.matches`** 已固定含 `127.0.0.1`/`localhost` × 8000（生产，见 `ops/nssm_install.ps1`）与 8065（预览，见 `docs/guides/frontend-preview.md`）。**用户不需要编辑 manifest**；换内网域名或其它端口属权限变更，需改 manifest 并重新确认。
4. **不需要填扩展 ID**：manifest 带固定 `key` ⇒ 打包 ID 恒为 `jfkgliolimmpceandogfimjkadplidem`，前端默认值就是它；构建期可用 `VITE_I8_RELAY_EXTENSION_ID` 覆盖（仅调试用）。
5. 装后**手动刷新一次工作台页面**（页面加载时才检测扩展），并在 i8 页面**展开右上角账号面板**（否则读不到账号/组织，连接会明确失败）。
6. **权限扩张**（加地址、加权限）需单独确认，不继承本次批准。

---

## 13. 真实验收如何无需 Agent 转接

以下由用户在 Edge 里自己做，主控旁观结果；模型是否在场**不构成任何一条证据**：

1. 装扩展 → 刷新页面；i8 标签停在业务页并**展开右上角账号面板**。
2. 工作台「i8 接入」→ 点扩展图标选中 i8 标签 → 「连接浏览器会话」（显示站点/账号/组织）→ 把「取数方式」切到「浏览器已有会话」。
3. 去通知抓取弹窗直接点原按钮 → 页面状态：已连接 → 取数中 → 完成；执行记录照旧出现（**含原有业务校验/落库**，见 §4）。
4. 同时看 i8 标签：未被退出、未被顶下线、无登录页、无跳转。
5. 抽 1 条抓到的单据，与 i8 页面同一条的对象（单号、项目、日期、审批金额、状态）逐项对上；**空结果不算通过**。
6. 机械证据（`facts()`，不含正文）：`requests_attempted >= 1`、`login_blocked == 0`、`product_session_cache_used == false`、`session_origin` 与配置一致；连接侧 `generation` 与本次一致。跳转在真机上表现为不透明响应而停，**不再以 `redirect_blocked` 作为必查项**。
7. **反例必跑两次**：①在 i8 里主动退出登录后再抓 ⇒ 必须显示"会话已失效，本次已停止"，不出现登录表单、不出现顶号；②在 i8 里换成另一个账号后直接点抓取（不重连）⇒ 必须显示"登录账号或组织已经变了"而停（证明每请求重核，不是只在连接时核一次）。
8. **合同列表也要在浏览器方式下取一次**（本轮补了白名单），不需要切回直连；若某部署换了 `I8_CONTRACT_LIST_URL` 路径，会在扩展侧明确停（可诊断，不会静默登录）。
9. **业务写入仍只限已核可丢弃副本**；预览外部动作熔断不绕过，需要测试例外由主控先交可审阅边界。

`[待样]` `relay_source` 这类来源标记是否落进执行记录字段（需按现有 `RunRecord` 模型评估），本轮只保证 `facts()` 可读。

---

## 14. 已证实 vs 仍需样机验证

`[已证]`（含本轮真浏览器样机结论）：
- 后端单进程单 worker ⇒ 进程内 broker 可行（`ops/nssm_install.ps1:59,136`）。
- 既有链只需替换 transport：live 已用临时 transport 跑通 `strict_payment_notice_by_bill_no` → `_extract_records` → `_map_record`（`evidence/TAIL-476-live.md`）。
- 严格客户端**结构上**不能登录/强踢/写缓存（`browser_session.py` + 既有 16 例）。
- 报表导出返回二进制、需 bytes 通道（`report_export.py:119-143`）。
- **真实 Edge 已经通过宿主 CDP 通道跑通一次精确单据读取**（`evidence/TAIL-476-live.md`）。
- **真浏览器（Chromium 1248，独立临时 profile）里**：扩展能被未打包加载且 ID 与前端硬编码一致；`externally_connectable` 真的生效（未列的 origin 进不来）；没有 activeTab/host 授权时注入被浏览器拒（activeTab 无法程序化授予）；注入脚本能按已核 DOM 读到账号与组织；**HttpOnly 会话 Cookie 由浏览器自动携带、`document.cookie` 读不到、页面手塞的 `Cookie` 被过滤**；`fetch` 沿页面 origin、`credentials:'same-origin'`；只读白名单在真浏览器同样拦住登录/强踢/保存/伪装地址且服务器上一条记录都没有；**合同列表口能在浏览器方式下真发出去**；`bind` 缺正整数代号即拒；没有 `device_id` 时连读身份也拒（按连接隔离真的生效）；`unbind` 后旧身份不能再取数。
- `[已证]` 严格停止**穿透**业务容错：`test_i8_strict_propagation.py` 32 例；删掉两处 `except (Strict…): raise` 后 6 例立刻红（变异验证）。
- Edge 扩展支持 `runtime`/`scripting`/`storage` 等 API：<https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/api-support>
- `activeTab`：用户主动调用后临时授予当前标签权限，关闭/跨源导航撤销，可与 `scripting` 配合避免 `all_urls`：<https://developer.chrome.com/docs/extensions/develop/concepts/activeTab>
- content script 的请求沿页面 origin 发出，所以**不能**给它任意 URL 转发能力：<https://developer.chrome.com/docs/extensions/develop/concepts/network-requests>
- 外部网页与扩展通信须经 `externally_connectable` 匹配，且扩展端还应校验 sender：<https://developer.chrome.com/docs/extensions/develop/concepts/messaging>
- match pattern 对 `localhost`/`127.0.0.1` 有正式支持，端口/路径写法需实测：<https://developer.chrome.com/docs/extensions/develop/concepts/match-patterns>
- `scripting.executeScript` 需要 `scripting` 权限 + host 权限或 `activeTab`；结果须可 JSON 序列化；`world` 可选：<https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/scripting/executeScript>

**关于 CDP**：真实 Edge **已经**通过宿主 CDP 通道工作过，因此"CDP 在生产浏览器被禁用"是**无依据断言，已撤回**。真正的结论只有两条：①那条通道是 **Agent 宿主的工具能力，不是可发布、可长期运行的日常产品 API**；②不能因为"它当时能用"去开远程调试端口或解密 Cookie。日常接入走本方案的扩展通道。

`[待样]`（必须样机确认，不得先写成通过）：
1. **Edge 真机**安装与 activeTab 授权（本机只验证过 Chromium；`chrome.action.onClicked` 无法程序化触发，真实用户点图标的路径未走）。
2. 真实 i8 站点上 `externally_connectable` 匹配与 `executeScript` 行为（样机用假站点）。
3. 真实 i8 账号面板结构/可见性（样机按主控只读核过的结构复刻；i8 改版即失效）。
4. MV3 service worker 冷启动对一次取数等待的实际影响（等待预算已跟着每条请求自己的 read 超时走，量到再谈）。
5. 真实 xlsx 导出大小 / 是否需分块（不先设阈值，靠后端既有长度核对判截断）。
6. 长轮询与 `api.ts` 身份核验门在真实浏览器里的共存表现（离线用例覆盖了 401 直停）。
7. 组织映射在其它部署下是否成立（`ORG_MAP` 只登记已核的那一对）。
8. 各部署的 `I8_CONTRACT_LIST_URL` 若换路径，浏览器方式会在扩展侧当场停（可诊断，不会静默改走登录）。

`[未验]`：以上全部真实行为；本机是否真能装上并授予该扩展；真实业务取数结果。

---

## 15. 本轮（第 6 轮）**没有**做的事

- 未安装扩展到任何 **Edge**（只在本机 Chromium 的**独立临时 profile** 里加载过，未碰用户 Edge profile）、未改浏览器设置、未连真实 i8、未读 `.env`/令牌、未连库、未写业务数据。
- **未改 `apps/frontend/` 任何源码 / 测试 / `package.json`**（本轮 0 行；前端按 closure §3 的消息形状由另一会话接线，字段未变）。
- **未改打印原策略**（打印链路仍是 `I8Client(allow_kick=True)`，本通道不含打印）；只把"`reportExport` 是二进制报表读取、不是实际打印"这一句写清楚。
- 未跑全仓测试/audit，未跑依赖数据库 fixture 的用例（需主控经 `backend_verify.py --source-env`）。
- 未提交 Git、未推送、未部署。票状态与共享索引由主控维护。
- `review-standards-final.md` / `review-spec-final.md` 保持原样未改（本轮只按 `review-closure.md` 处置具名项）。
