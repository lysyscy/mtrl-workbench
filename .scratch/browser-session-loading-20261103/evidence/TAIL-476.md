# TAIL-476 · i8 已有浏览器会话复用 · 实现与证据

> 本文件只记**事实**：做了什么改动、依据是什么、跑了什么命令、哪些还没验。
> 结论分档见 §A.0 与 §A.9。**没有一条真实验收项被勾选**。

---

# 0 · 第 7 轮：主控复核指出的三处**真实**缺陷（已修）

主控 `m04041` 复核指出：上一轮回执写的"按连接隔离、按请求代号核绑定"与实际代码不符。**三处指控逐条核对代码后全部成立**，不是误报：

| # | 主控指出的问题 | 核对结果 |
| --- | --- | --- |
| 1 | `execute()` / `identityStillBound()` 从未比较 `request.generation` 与 `bound.generation` | 成立。`identityStillBound(deviceId)` 只核 `sameIdentity(now, bound)`；`execute` 里根本没有取 `request.generation` ⇒ **旧代号的请求照样执行** |
| 2 | `bind` 用 `if (message.identity && !sameIdentity(...))`，缺 `identity` 直接放行 | 成立。缺 `identity` 时整个条件短路为 false ⇒ **"没报"被当成"没意见"** |
| 3 | `pendingIdentities` 只按 `deviceId` 键，未确认 sender 页面归属 | 成立。`device_id` 是页面自己生成的串（`sessionStorage`），同一浏览器里另一个本地工作台页面拿到同一个串就能覆盖/借用 |

**上一轮回执的措辞错误已就地更正**：§A.1 里"按 device 隔离绑定"那一行、§A.5 里"按页面（连接）分开记"的说法，在第七轮之前**只做到按 `device_id` 隔离**，未核发送页面归属、未比较请求代号。第七轮才补齐。

## 0.1 修法（`apps/browser-extension/service_worker.js`，现 677 行）

新增四个窄助手（都在 `service_worker.js` 顶部常量区附近）：

- `senderKeyOf(sender)` → `` `${tabId === null ? '-' : tabId}#${documentId || '-'}` ``，两者都没有返回 `''`。
  注释写明**为什么不能只看 origin**：所有本地工作台页面同源（`http://127.0.0.1:8000` / `:8065`、`localhost` 同款），`origin` 分辨不出"另一个页面"。页面刷新会换 `documentId` ⇒ 旧连接自然失效、要求重连，这是**有意**的：认不出来的归属宁可让它重连。
- `nonEmptyString(value)` / `identityComplete(value)`：要求 `origin`、`account`、`orgCode`、`orgName` **全部**为非空字符串。
- `positiveGeneration(value)`：非正整数（`0`、负数、小数、字符串、`undefined`）一律返回 `0` 表示无效。
- `pendingKeyOf(deviceId, senderKey)` → `` `${deviceId}\u0000${senderKey}` ``：待核身份按 **(连接, 发送页面)** 两个维度存。

三处判据改动：

1. **`identityStillBound(deviceId, generation, senderKey)`**（顺序即实现，注释写明"先核代号（本地读，不碰标签），再读 DOM"）：空 `deviceId` → 空 `senderKey` → 代号缺失/非法 → 读 `boundKeyOf(deviceId)` 无基准 → `bound.sender !== senderKey`（`code:'sender-mismatch'`）→ `positiveGeneration(bound.generation) !== generation`（`code:'stale-generation'`）→ 最后才 `readIdentity()` 核 DOM。
2. **`execute(message, senderKey)`**：代号闸**提到最前**，`!deviceId` / `!generation` 都在 `selectedTab()` 之前返回 ⇒ 缺/0/旧/不成形代号 **零 DOM 读取、零注入、零请求**。`identityStillBound` 失败时把 `code` 一并带回给调用方（此前吞掉 `code`，页面只能看到一句笼统的话）。
3. **`bind`**：`!identityComplete(message.identity)` 先拒（文案"绑定时没有带上完整的身份（站点/账号/组织名称/短码）…"），再比 `sameIdentity`，再核当前 DOM；通过后**先读已有基准**，若已被**另一个发送页面**占用（`existing.sender !== senderKey`）则 `code:'sender-mismatch'`，**不允许顶掉**；存基准时把 `sender: senderKey` 一起写进去。
4. **`unbind`**：缺 `senderKey` 拒；先读基准，`bound.sender !== senderKey` ⇒ "这条连接是另一个工作台页面建立的，本页面不能撤绑。"；只撤自己那格的待核身份。

`chrome.runtime.onMessageExternal` 顶层统一算 `senderKey = senderKeyOf(sender)`，`identity`/`bind`/`unbind` 三种消息缺 `senderKey` 一律拒（"认不出这个工作台页面，本次已停止。请刷新页面后重新连接。"）。

## 0.2 验证（**真实通过**的部分）

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 扩展协议单测 | `cd apps/browser-extension && node --test tests/protocol.test.mjs` | **31 passed / 0 failed，EXIT=0**（新增 5 例：代号 7 种非法全部零注入；断线重连后的旧代号 `stale-generation`；`bind` 缺/残身份 5 种全拒；另一页面借同 `device_id` 不能执行/不能顶绑/不能撤绑；认不出来源则不建立待核身份） |
| 真浏览器样机 | `./backend/.venv/Scripts/python.exe -B -X utf8 apps/browser-extension/tests/browser_smoke.py` | **38 条判据全 PASS，EXIT=0**（隔离 Chromium `chromium-1248` + 独立临时 profile + 假站点，端口 8071） |
| 变异验证（单测） | 同时打掉代号闸、代号比对、`identityComplete`、sender 检查 | **4 failed / 27 passed**，正好是新增的四条；恢复后 31 例全绿 |
| 变异验证（样机） | 打掉三处 sender 检查 | **4 条 FAIL**：另一页面能取数、能顶绑、能撤绑、原页面基准被动过；其中"能取数"那条的服务器记录里**真的出现了** `Cookie: MTRLSESSION=httponly-sentinel-9f3a` ⇒ 证明缺了归属校验就会碰到用户的标签；恢复后 38 条全 PASS |

样机新增判据分组：代号闸 4 条（缺/`0`/旧/不成形，每条都断言服务器 `RECEIVED == []`）、完整身份 4 条（完全没带/账号空/组织短码空/缺站点，且随后同 device 执行也被拒 ⇒ 没留下基准）、发送页面隔离 4 条（另一文档借同 `device_id` 取数被拒且 `RECEIVED == []`、顶绑 `sender-mismatch`、撤绑被拒、**原页面仍能正常取数**）。**HttpOnly 三条判据保持不变**（自动携带 / `document.cookie` 读不到 / 页面手塞头被过滤）。

## 0.3 仍未验（不得由上述通过关闭）

- **真实 Edge 安装**：本包没有装进任何真实 Edge。
- **真实 `activeTab` 用户点击授权**：样机用的是**临时副本 + `tabs` 权限**程序化选中标签，这**不能**算作 `activeTab` 已验。
- **真实 i8 站点与账号面板**：样机的 i8 页面是按现场核过的窄 DOM **复刻**的假页面，不含真实 i8 前端行为。
- **真实日常业务结果**：没有跑过一次真实取数、没有核对过一条真实业务数据。

# A · 第 6 轮：按 `review-closure.md` 逐项具名修复

本轮不重跑全量审查，只处置 `evidence/review-closure.md` 里主控接受的具名项；
`review-standards-final.md` / `review-spec-final.md` 保持原样未改。
写域收窄为**后台 + 扩展 + 契约文档 + 本票证据**：本轮对 `apps/frontend/` 的改动为 **0 行**（前端协议由另一会话按 closure §3 接线）。

## A.0 结论先行（范围务必看清）

- **本轮改动已编译、已跑定向检查**：后端 i8 七文件 **164 例通过**（含新增严格穿透 32 例、broker 幂等/代号/票/超时预算 9 例）；扩展协议 **26 例通过**；真浏览器样机 **25 条判据通过**；仓库名单入口既有验收 **8 例通过**。
  （⚠️ 这两个数字是第 6 轮当时的；第 7 轮已增至扩展 **31 例**、样机 **38 条**，见 §0.2）
- **真实复用与真实验收仍未完成**：没有装到任何 Edge、没有连过真实 i8、没跑过一次真实取数。
  ⇒ **所有真实验收项一个都没勾**；离线、样机、`backend_verify` 之外的通过**都不**关闭真实项。
- **证据等级**："真浏览器通路"级（独立临时 profile 的 Chromium），**不是**"Edge 真机"级、更不是"真实业务"级。
- 用户验收要求仍是"日常抓取能用才算能用"（spec 头部 2026-11-04 修订）。**该要求尚未兑现。**

## A.1 本轮按 closure 各项逐项关账

| closure 项 | 处理结果 | 落实位置 / 怎么验的 |
| --- | --- | --- |
| **S1a** 维护页查 i8 仓库名单没带取数方式，browser 下会走登录 | `WarehouseCheckRequest` 加 `session_mode`/`device_id`；`warehouse_check` 用 `scope_of(req)` 包住取数；严格停止**不被"回落上一次缓存"吞掉** | `mod03_notice/{schemas,router}.py`；`test_i8_strict_propagation.py` 断言 loader 里 `current_scope() == [(MODE_BROWSER, "dev-1")]`、缺省仍是 `[(MODE_HTTP, "")]` |
| **S2** 采购合同列表被白名单挡住、被要求改回直连 | 后端与扩展**两侧**白名单都补 `POST /PMS/PCM/Contract/GetCntMList`（正式 `I8_CONTRACT_LIST_URL` 实测值，无查询参数）；删掉"请改用直连"的说法 | `browser_relay._READONLY_ENDPOINTS`、`service_worker.READONLY_ENDPOINTS`、`docs/reference/i8-contract.md`；样机有一条真浏览器判据真的发出去了 |
| **Spec(c)** 超时被 broker 30s 截断、空闲清理误杀在途、超时谎称会话失效 | 每条请求的 read 预算从 `httpx.Request.extensions["timeout"]["read"]` 取 → `PendingRequest.timeout_seconds` → `outbound_payload()["timeout_ms"]` → 扩展 `AbortController`；`wait()` 默认用这张票自己的预算；`connection_of()` 有在途请求时**不算空闲**；超时用 `_REASONS["timeout"]` 文案 | `browser_relay._request_read_timeout`、`browser_broker.{enqueue,wait,connection_of}`、`service_worker.executeInPage`；扩展 2 例（有/无 `timeout_ms`）钉住，文案断言排除"会话/登录不/重新登录" |
| **主控**：`disconnect` 不存在连接时崩 | `disconnect()` 去掉先 `_queues.pop` 再 `_fail_queue` 的写法，改为幂等（返回 False 并清残留队列） | `browser_broker.disconnect`；`_fail_queue` 记下原崩溃 `AttributeError: 'NoneType' object has no attribute 'clear'` |
| **主控**：断开重连后 `generation` 又回 1 | 发号器改进程内单调 `_generation_seq`，`connect()` 一律 `+= 1` 取号 | `browser_broker.connect`；`ConnectionInfo.generation` 注释说明"断开之后再连也不回 1" |
| **主控**：`complete` 传 0 能绕过代号 | `complete()` 要求 `generation` 是正整数且等于这张票的代号，缺省/0/负数一律拒（`stopped="rejected"`，⛔ 不谎称"连接被替换"） | `browser_broker.complete`；后端 66 例里 9 处回帖全部改为显式带 `generation=pending.generation` |
| **主控**：`ticket` 含构造信息、有无消费者字段与不实条件变量注释 | `ticket` 改 `secrets.token_urlsafe(16)`（不透明一次性令牌，非授权凭据）；删无读写的 `_waiting` 与无消费者的 `redirect_to`；常量与条件变量注释按实际语义重写 | `browser_broker.py` |
| **主控**：全局 `pendingIdentity`/`BOUND_KEY` 会让另一个页面把连接顶掉 | 第 6 轮：待核身份改 `Map<device_id, identity>`；绑定基准改 `i8RelayBound:<device_id>`；`bind` 校验 `device_id` + 正整数 `generation` + 服务端核对过的身份 + **当前 DOM 再核一次**；`unbind` 只撤本连接；换标签 `clearAllBindings()`。**⚠️ 第 6 轮只做到按 `device_id` 分开**（`device_id` 是页面自生成串，另一本地页面可冒充），且 `execute` 未比对请求代号、`bind` 缺 `identity` 会放行 —— **这三处由第 7 轮补齐，见 §0** | `service_worker.js`；第 6 轮新增 8 例；第 7 轮再新增 5 例（代号 7 种非法零注入、旧代号 `stale-generation`、`bind` 缺/残身份 5 种全拒、另一页面不能执行/顶绑/撤绑、认不出来源不建待核身份） |
| **S3** 候选通道协议/只读范围/适用范围没登记进契约 | `docs/reference/i8-contract.md` 新增一节（59 行）：用途、与 HTTP 模式的关系、12 条只读端点表、身份与目标约束、超时与停止语义、验证状态（候选 · 真实未验） | `docs/reference/i8-contract.md` |
| **第⑦条** 业务容错吞掉严格停止后继续取数/部分采用 | `Strict*`（含其子类 `BrowserRelayUnavailable`）在 5 处业务容错前**先抬出去**：`sources.load_warehouse_rows`、`contract_source.fetch_item_name`、mod02 `fetch_preview`/`fetch_run`、mod07/mod08/mod11 抓取。普通单条业务失败容错**保持原样** | 5 个生产文件 + 新增 `test_i8_strict_propagation.py` 32 例；**变异验证**：删掉两处 `except (Strict…): raise` 后 6 例立刻红，恢复后核对 sha256 |
| **范围判断** 打印策略不动 | 打印链路 `notice_executors.get_batch_executor` 仍 `I8Client(allow_kick=True)`，本轮 0 改动；只在契约文档写明"打印不在本通道内" | `mod03_notice/notice_executors.py` |
| **范围判断** `reportExport` 是库存/结存取数，不等同打印 | 保留在只读白名单里，注释与契约文档都写明"二进制报表读取，**不是**实际打印动作" | `browser_relay.py`、`service_worker.js`、`i8-contract.md` |
| **范围判断** 组织映射归 mod02 适配、不搬进 core | `ORG_MAP` 仍在 `mod02_i8/i8_identity.py`，未下沉 `core` | `i8_identity.py` |
| **新证据** HttpOnly 会话 Cookie 真实行为 | 样机固化成 3 条判据：浏览器**自动携带** HttpOnly Cookie、`document.cookie` 读不到、页面手塞的 `Cookie` 头被浏览器过滤 | `browser_smoke.py`；同时把一条写错的旧判据（假设"请求不带 Cookie"）改成只断言页面塞的哨兵不出现 |
| **样机** 按新协议更新（先 identity 再 bind、带 `device_id`/`generation`/`timeout_ms`） | 已更新；另有一条"没有 device_id 时读身份也被拒" | `browser_smoke.py`；25 条判据 |

## A.2 改动清单（本轮，全部在本票写域内）

| 文件 | 现状 | 本轮作用 |
| --- | --- | --- |
| `backend/app/mod02_i8/browser_broker.py` | 425 行 | 幂等 disconnect、进程内发号器、不透明 ticket、按请求预算等待、在途不算空闲、清无消费者字段 |
| `backend/app/mod02_i8/browser_relay.py` | 399 行 | 白名单补 `GetCntMList`、`_request_read_timeout()` 取 httpx read 预算并传入 `enqueue` |
| `backend/app/mod02_i8/sources.py` | 144 行 | `load_warehouse_rows` 放行 `Strict*`（不再当成"补档案失败"） |
| `backend/app/mod02_i8/contract_source.py` | 344 行 | `fetch_item_name` 放行 `Strict*`，单条业务失败仍返回空串 |
| `backend/app/mod02_i8/router.py` | 593 行 | `fetch_preview`/`fetch_run` 不把严格停止说成"降级为手动 Excel"；`fetch_run` 严格分支先落失败执行记录再抛 |
| `backend/app/mod03_notice/schemas.py` | 173 行 | `WarehouseCheckRequest` 加 `session_mode`/`device_id` |
| `backend/app/mod03_notice/router.py` | 453 行 | `warehouse_check` 进作用域 + 严格停止不被缓存兜底吞掉 |
| `backend/app/mod07_setl/fetch_service.py` | 169 行 | 严格停止穿透（原降级分支不变） |
| `backend/app/mod08_inv/fetch_service.py` | 172 行 | 同上 |
| `backend/app/mod11_jc/fetch_service.py` | 362 行 | 两处穿透（内层同步降级 + 最外层抓取降级） |
| `backend/tests/test_i8_browser_relay.py` | 784 行 / **66 例** | 回帖全部显式带 `generation`（适配新的代号校验）；新增 broker 幂等/断连重连不回 1/回帖代号缺省非正数拒/票不透明/每请求读超时预算/空闲清理不误杀在途 共 9 例 |
| `backend/tests/test_i8_strict_propagation.py` | 325 行 / **32 例（新增）** | 严格停止穿透 5 处 + 普通失败仍降级的对照 |
| `apps/browser-extension/service_worker.js` | 564 行 | 白名单补合同列表、绑定按 `device_id` 隔离、`bind` 核代号/身份/DOM、`execute` 按请求核绑定、`timeout_ms` → `AbortController` |
| `apps/browser-extension/tests/protocol.test.mjs` | 686 行 / **26 例** | 新增 8 例（列表口、隔离、缺 device_id、代号、身份不符、DOM 变号、超时 2 例） |
| `apps/browser-extension/tests/browser_smoke.py` | 628 行 / **25 判据** | 补 HttpOnly 三项判据、新协议（先 identity 再 bind）、合同列表口可发 |
| `docs/reference/i8-contract.md` | 266 行（+59） | 登记候选浏览器通道协议与边界 |

**本轮 0 改动**：`apps/frontend/` 全部（源码/测试/`package.json`）、`browser_session.py`、`i8_identity.py`、
`client.py` 的产品缓存/重登策略、`login.py`、`cookie_store.py`、打印链路与打印策略、`core/*`、
共享 `read-region`/grid、其它业务前端、票状态与共享索引、部署脚本、`.env`。

## A.3 控制流（解析链仍一行未改）

```
I8Client.request() → BrowserRelayTransport.handle_request()
  ① 核 origin（逐请求）  ② 核只读白名单（逐请求）  ③ 头脱敏
  ④ 取这条请求自己的 read 预算 → 入队挂起
        ↓ 页面长轮询 GET /api/m02/browser/pending（同中间件、同身份门）
        ↓ 扩展在该 device_id 绑定的 i8 标签里 executeScript
           → fetch(credentials:'same-origin', redirect:'manual', signal=AbortController(timeout_ms))
        ↓ 页面 POST /api/m02/browser/complete（带 ticket + 正整数 generation）
  ⑤ 唤醒 → 长度核对 → 交回 I8Client 既有解析链（_extract_records / _map_record 等）
```

- `session_mode` 缺省 `http` ⇒ 旧调用行为逐字节不变；选了 browser 但连接不在 ⇒ **当场失败**，绝不回退登录。
- 严格停止**穿透**补档案 / 补材料名 / 各 mod 抓取降级：不再被改成"i8 抓不到数 ⇒ 可以手动导 Excel"。

## A.4 停止条件（实现里真正落成的）

| 条件 | 停止点 | 用户看到（受控文案） |
| --- | --- | --- |
| 没装扩展 | 页面侧，未进后端 | "没有检测到浏览器扩展…本次未发出任何 i8 请求" |
| 没选中 i8 标签 | 扩展侧 | "还没有选中 i8 标签…" |
| 没带 `device_id` | 扩展侧（identity/bind/unbind/execute 全拒） | "缺少连接标识…请回「i8 接入」页重新连接" |
| `bind` 缺/非法 `generation` | 扩展侧 | "绑定时缺少有效的连接代号…" |
| **`bind` 缺/残身份**（第 7 轮） | 扩展侧 | "绑定时没有带上完整的身份（站点/账号/组织名称/短码）…" |
| **请求代号缺失/为 0/不成形**（第 7 轮） | 扩展侧，**在任何 DOM 读取与注入之前** | "这条请求没有带连接代号，已忽略…"（零注入、零请求） |
| **请求代号属于上一次连接**（第 7 轮） | 扩展侧，同上 | "这条请求属于上一次连接（代号已过期），本次已停止，没有发出任何请求…" |
| **另一工作台页面借同一 `device_id`**（第 7 轮） | 扩展侧（执行/顶绑/撤绑三处） | "这条连接是另一个工作台页面建立的，本页面不能借用它取数…" / "…不能顶掉它…" / "…不能撤绑。" |
| **认不出来自哪个工作台页面**（第 7 轮） | 扩展侧 | "认不出这个工作台页面，本次已停止。请刷新页面后重新连接。" |
| 站点与工作台配置不一致 | 连接时 + transport 逐请求 | "浏览器里的 i8 站点与工作台当前配置不一致，本次已停止" |
| 账号面板未展开 / 多个面板 / 结构变了 | 扩展侧 | 分别给"请先展开账号面板"/"面板不唯一"/"结构读不出来" |
| 账号 ≠ 本人绑定 i8 账号 | 连接时 + **每请求** | "…与工作台本人绑定的 i8 账号不一致…" |
| 组织 ≠ 取数组织（按短码/名称） | 连接时 + **每请求** | "…组织与工作台取数使用的组织不一致…" |
| 组织不在已登记映射内 | 连接时 | 明确拒绝，**不猜**内部号与短码的对应 |
| 同源换号 / 换组织 | **每请求**重核 | "登录账号或组织已经变了" |
| 会话失效 | 既有判据 → `_login()` 抛 `StrictSessionEnded` | "…本次已停止（没有重新登录、也没有顶掉任何在线会话）" |
| 跳转 | 扩展见不透明响应即停 | "浏览器返回了不透明响应（无法核对结果）" |
| 非白名单端点 / 伪装路径 / 方法错配 | 后端 + 扩展各拦一次 | "这次请求不在只读取数白名单里…（未发出去、未登录、未改任何数据）" |
| **请求超时** | 扩展 `AbortController`（按 `timeout_ms`） | "这条请求超过它自己的时间预算还没回来，本次已停止（超时）。没有重试，也没有当成登录状态问题。" |
| 页面关闭 / 等不到回帖 | broker 按该票预算等待 | "浏览器那边一直没有回音，本次已停止（没有重新登录，也没有重试）" |
| 回帖长度对不上 | transport 长度核对 | "…长度对不上（传输可能被截断），本次已停止" |
| 连接被替换 / 账号切换 | broker | "同一次连接被新的连接替换"/"当前登录账号已变化" |

全部停止路径**不触发**：登录、强踢、`cookie_store.save`、自动重试、降级到 HTTP。

## A.5 身份与隔离

- 比对**工作台本人绑定的 i8 账号**（`current_i8_credentials()[0]`），不是工作台 `account`。
- **两种组织标识不混算**：`expected_org_id()` 给内部号 `3700000000000014`；i8 页面可见的是
  "第四工程公司 | 109"。换算集中在 `i8_identity.ORG_MAP`（已核本部署），未知映射**直接失败**。
- 原始个人账号/姓名**不进 Git、不进日志**；`facts()` 只给站点原点与布尔。
- broker 键 `(服务端 current_name(), device_id)`；扩展侧待核身份按 **(device_id, 发送页面)**、
  绑定基准 `i8RelayBound:<device_id>`（内含 `sender` 与 `generation`）
  ⇒ **一个页面换连接不会顶掉另一个页面**；`device_id` 每页一份放 `sessionStorage`。
  ⚠️ 第 6 轮时这两处**只按 `device_id` 分开**、未核发送页面归属，第七轮才补齐（见 §0）。
- `generation` 由 broker 进程内发号器给，**每次 connect 都新建**（含断开后重连）；回帖必须带正整数代号，
  过代/缺失回帖一律丢弃并判停。

## A.6 本轮实跑的命令与退出码（全部离线 / 本地）

```
cd backend
.venv/Scripts/python.exe -B -X utf8 -m pytest \
  tests/test_i8_browser_relay.py tests/test_i8_strict_propagation.py \
  tests/test_i8_browser_session_reuse.py tests/test_i8_cookie_cache.py \
  tests/test_i8_ui_policy.py tests/test_layering.py tests/test_i8_contract.py \
  -o addopts= -q
→ 164 passed in 8.43s                                            EXIT=0

（仅 tests/test_i8_strict_propagation.py）                       → 32 passed  EXIT=0
（仅 tests/test_i8_browser_relay.py）                            → 66 passed  EXIT=0
（tests/test_acc_prj_wh_check.py，仓库名单入口既有验收）          → 8 passed   EXIT=0
（tests/test_acc_jc_fetch_orch.py）                              → 3 failed / 8 passed
   失败原因 RuntimeError: DATABASE_URL 未配置（app/core/db.py:40）
   ⇒ DB fixture 用例，按指令只由主控经 backend_verify --source-env 跑 ⇒ 本轮【未验】，不是"失败"

cd apps/browser-extension
node --test tests/protocol.test.mjs     → tests 26 / pass 26 / fail 0          EXIT=0

（仓库根）
backend/.venv/Scripts/python.exe -B -X utf8 apps/browser-extension/tests/browser_smoke.py
→ 25 条判据全部通过（端口 8071，不使用 8000/8065）                              EXIT=0
（以上为第 6 轮数字；第 7 轮重跑：protocol 31 例 / 样机 38 条，见 §0.2）
→ %TEMP%\i8-smoke-profile-* 残留检查：无残留
```

行尾审计：本轮改动都是小块（`git diff --numstat` 最大为 `mod02_i8/router.py 259/22`、
`i8-contract.md 59/0`、`mod02_i8/schemas.py 65/0`），**没有整文件翻红**；
`sources.py`/`contract_source.py`/`browser_smoke.py` 磁盘为 CRLF 但 diff 仍只有几行，属 `core.autocrlf` 归一化。

### 本轮复核指出、已修掉的真缺陷

1. **`disconnect` 打不存在的连接会崩**：`AttributeError: 'NoneType' object has no attribute 'clear'`（已复现）。
   修：`disconnect()` 幂等，不再先 `pop` 再让 `_fail_queue` 拿到 `None`。
2. **断开重连后 `generation` 回到 1**：旧实现"当前连接代号 + 1"，断开时连接已被摘掉 ⇒ 重连又发 1，
   上一代的迟到回帖会撞上新代。修：进程内单调发号器。
3. **`complete(..., generation=0)` 能绕过代号校验**：`if generation and …` 对 0 短路。修：要求正整数且相等。
4. **严格停止被业务容错吞掉**：`load_warehouse_rows` / `fetch_item_name` 原本 `except Exception` 一律降级，
   浏览器方式下"会话没了"会被当成"补档案失败"继续往下跑（甚至部分采用）。修：先抬 `Strict*`；
   变异验证删掉这两处 `raise` 后 6 例立刻红。
5. **回帖代号对不上时谎称"连接被替换"**（补定向用例时暴露）：`complete()` 里代号不符的分支复用了
   `stopped="replaced"`，用户看到的是"同一次连接被新的连接替换" —— 实际是页面回了一份对不上代号的票，
   与"谁顶了你的连接"完全是两件事。修：单独的受控原因 `"rejected"`
   （"浏览器回的那份结果对不上这次连接…"），并加断言钉住 `pending.status is None`。
6. **`browser_broker` 模块注释两处不实**（自查发现）：①自称"内存表 + **条件变量**"，
   实际只有 `dict`/`deque` + 每条请求自己的 `threading.Event`，没有任何 `threading.Condition`；
   ②自称判停抛 `StrictSessionUnavailable`，实际 `wait()` 抛的是 `StrictSessionEnded`。
   两处注释已按实际实现改正 —— 注释写错会直接误导后来的人去"修"不存在的东西。

（第 5 轮记录的六个缺陷仍然有效：broker `_inflight`、注入函数模块作用域、页面忙等、仓库口绕回登录、
`chrome.storage.session.set` 签名、`redirect:'manual'` 不透明响应。）

**既有欠账（与本票无关，改动前即红）**

- `test_ux_text.py` 报 `backend/app/mod02_i8/router.py` 与 `backend/app/mod08_inv/adjustment_values.py`
  在 except 里拼 `{exc}`（后者不在写域；前者是本票在改的文件，但该断言属他人负责的既有权衡，本轮未动）。
- `apps/frontend/src/big.tsx` 多条 TS6133（他人并行改动）。
- `backend_verify.py --source-env` 未提供 ⇒ 依赖 DB fixture 的用例本轮**未运行**（非通过非失败）。

## A.7 真实验收怎么跑（无需任何 Agent 转接）

用户在 Edge 里自己完成；模型是否在场不构成任何一条证据。

1. 装扩展（§A.8）→ 刷新工作台页面（**不需要填扩展 ID，也不需要改 manifest**）。
2. i8 标签停在业务页，**展开右上角账号面板**（让账号与组织显示出来）。
3. 工作台「i8 接入」→ 点扩展图标选中那个 i8 标签 → 点「连接浏览器会话」→ 显示站点/账号/组织。
4. 在「i8 接入」把取数方式切到「浏览器已有会话」→ 去通知抓取弹窗直接点原按钮
   → 取数完成，执行记录照旧出现（**含原有业务校验/落库**）。
5. 同时看 i8 标签：未被退出、未被顶下线、无登录页。
6. 抽 1 条抓到的单据与 i8 页面同一条逐项对上；**空结果不算通过**。
7. 机械证据：`requests_attempted >= 1`、`login_blocked == 0`、`product_session_cache_used == false`、
   `session_origin` 与配置一致；连接侧 `generation` 与本次一致。
   （**不要**再要求 `redirect_blocked >= 1`：真机上跳转表现为不透明响应，扩展那步就停了。）
8. **反例必跑**：i8 里主动退出登录后再抓 ⇒ 必须显示会话已失效并停止，不出现登录表单、不顶号。
9. 采购合同列表也应在浏览器方式下取到（本轮已补白名单），不需要切回直连。
10. 真实业务写入仍只限已核可丢弃副本；预览外部动作熔断不绕过，需测试例外由主控先给边界。

**不算成功**：HTTP 200、拿到 Cookie、空结果、重登后的成功、离线/样机通过、后端缓存命中、
`requests_attempted == 0`、只看到"已连接"没跑过取数。

## A.8 安装确认项（全部尚未授权）

1. 装扩展：`edge://extensions` → 开发者模式 → 加载解压缩的 `apps/browser-extension/`。
2. 权限最小集（manifest 现状）：`activeTab`（**用户点图标**才授予当前标签）、`scripting`、`storage`。
   **不申请**：`cookies`、`debugger`、`webRequest`、`tabs`、`<all_urls>`、`host_permissions` 通配。
3. `externally_connectable.matches` 已固定含 `127.0.0.1`/`localhost` × 8000/8065；换内网域名或端口
   属权限变更，需改 manifest 并重新确认。
4. 装后手动刷新一次工作台页面（页面加载时才检测扩展）。
5. 权限扩张需单独确认，不继承本次批准。

## A.9 已证实 vs 仍需验证

`[已证实（本地/离线/真浏览器通路）]`

- 后端单进程单 worker ⇒ 进程内 broker 可行（`ops/nssm_install.ps1:59,136`）。
- 既有链只需替换 transport：live 已跑通 `strict_payment_notice_by_bill_no` 精查 → `_map_record`。
- 严格客户端**结构上**不能登录/强踢/写缓存。
- 报表导出是二进制，需 bytes 通道（`report_export.py:119-143`）。
- **真浏览器（Chromium 1248）里**：扩展能加载且 ID 与硬编码一致；`externally_connectable` 真的生效；
  没有 activeTab/host 授权时注入被浏览器拒；注入脚本能按已核 DOM 读到账号与组织；
  **HttpOnly 会话 Cookie 由浏览器自动携带、`document.cookie` 读不到、页面手塞的 `Cookie` 被过滤**；
  `fetch` 沿页面 origin；白名单在真浏览器同样拦住登录/强踢/保存/伪装地址，服务器上一条记录都没有；
  采购合同列表口能在浏览器方式下真发出去。
- **第 7 轮补齐的三条**（真浏览器样机 + 协议单测双向钉住，均已做变异验证）：请求代号缺失/为 0/旧代号的请求**零注入零请求**（服务器一条记录都没有）；`bind` 缺/残身份一律拒绝；**发送页面归属**参与隔离 —— 另一工作台文档借同一 `device_id` 不能取数、不能顶绑、不能撤绑，而建立连接的那个页面照常取数。
  ⚠️ 第 6 轮曾声称"按页面隔离"，当时只做到按 `device_id` 分开，**该措辞已更正**（见 §0）。
- 官方文档（第一方）：`activeTab` <https://developer.chrome.com/docs/extensions/develop/concepts/activeTab>；
  网络请求沿页面 origin <https://developer.chrome.com/docs/extensions/develop/concepts/network-requests>；
  消息与 `externally_connectable` <https://developer.chrome.com/docs/extensions/develop/concepts/messaging>；
  match pattern <https://developer.chrome.com/docs/extensions/develop/concepts/match-patterns>；
  `scripting.executeScript` <https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/scripting/executeScript>。

**关于 CDP**：真实 Edge **已经**通过宿主 CDP 工作过，故"CDP 在生产浏览器被禁用"是**无依据断言，已撤回**。
成立的是：①那条通道是 Agent 宿主工具能力，**不是可发布、可长期运行的日常产品 API**；②不能据此开
远程调试端口或解密 Cookie。

`[待验（未做，不得先写成通过）]`

1. Edge 真机安装与授权（本机只验证过 Chromium；`activeTab` 的真实授权路径无法程序化触发 ——
   样机是在**临时副本**里加 `tabs` 权限程序化选中标签才跑通的，**因此不能算 `activeTab` 已验**）。
2. 真实 i8 站点上 `externally_connectable` 匹配与 `executeScript` 行为。
3. 真实账号面板结构与可见性（样机按主控只读核过的结构复刻，i8 改版即失效）。
4. 真实 xlsx 导出大小与回帖耗时（本轮**没有**自设字节上限，用的是后端既有长度核对）。
5. 长轮询与 `api.ts` 身份门在真实浏览器里的共存表现。
6. 组织映射在其它部署下是否仍成立（`ORG_MAP` 只登记了已核的那一对）。
7. 各部署的 `I8_CONTRACT_LIST_URL` 若换成别的路径，浏览器方式会在扩展侧当场停（可诊断，不会静默登录）。

`[未验]`：以上全部真实行为；本机是否真能装上并授予该扩展；真实业务取数结果。

## A.10 风险

- **风险 1（最大）**：真实 Edge 上 `externally_connectable`/activeTab 授权/`executeScript` 的表现
  若与样机不同，通道要改设计；届时如实记"已验证不可用"或"仅在具名条件下可复用"。
- **风险 2**：站点比对只比规范化后的 `协议://主机[:端口]`，不做 DNS/证书校验；别名/反代会误停
  （保守方向，可接受，需现场知悉）。
- **风险 3**：浏览器模式与产品常态路径共用 `I8Client._lock` 与 `serialize_fetch` 同表锁；
  并发时最多等同表锁释放，不串数据但可能等待。
- **风险 4**：扩展依赖 i8 页面 DOM；改版后表现为"读不到账号/组织，拒绝连接"，不会静默放行。
- **风险 5**：`ORG_MAP` 是**部署相关**的显式映射；换部署未更新时会拒绝连接（不会误取）。

---

# B · 第 1–5 轮历史（仍有效）

- 第 1–2 轮：`browser_session.py`（严格客户端，结构上不能登录/强踢/写缓存）、
  `tests/test_i8_browser_session_reuse.py`、`tools/dev/i8_browser_session_reuse.py`（离线取证入口，**不是**日常通道）。
  仍然成立的修正：入口退出 `0` 只表示"响应解析完成"，紧跟"⚠️ 只证明解析链跑通…仍须人工交叉核对"；
  撤回"跨组织读取结构上不可达"的过度断言；`facts()` 只给站点原点。
- 第 3 轮：`daily-integration.md` 给出"后端 broker + 页面长轮询 + MV3 扩展"方案与否决表。
- 第 4 轮：broker/relay/工厂/路由/前端 provider/扩展全部落地，四个真实缺陷被测试抓出
  （broker `_inflight`、注入函数模块作用域、页面忙等、仓库口绕回登录）。
- 第 5 轮：端点白名单双向、已核 DOM 窄适配器 + 每请求重核、`generation`、固定扩展 ID、
  P0 行为检查（真的跑提交）、真浏览器样机；样机又抓出两个缺陷
  （`chrome.storage.session.set` 签名、`redirect:'manual'` 不透明响应）。
- ⚠️ "3xx ⇒ `StrictRedirectStopped`"在**真浏览器链路上不会因跳转而触发**：真机给的是不透明响应，
  扩展那边就停了。后端这条分支只是兜底。

---

# C · 环境与产物

- Python：`D:/dev/mtrl-workbench/backend/.venv/Scripts/python.exe -B -X utf8`（未安装、未改环境）。
- Node：系统已装 v24.22.1；扩展协议测试只用 `node --test` + `vm`；样机用仓库已有的
  playwright 1.64 + `ms-playwright/chromium-1248`，**未安装新依赖**。
- 样机用**独立临时 profile**，端口从 8071 起自动选空闲（不碰 8000/8065 的他人服务），
  退出后 profile 目录清理且核过无残留；**不碰用户 Edge profile、不连真实 i8、不改系统设置**。
- 未走 `tools/dev/backend_verify.py --source-env`：来源参数由主控提供，本轮未提供 ⇒ **未运行**（不算通过）。
  本轮用例不连库、不读 `.env`，未绕过也未改 DB 守卫。
- 未连接真实 i8、未读 `.env`（仓内只有 `.env.example`）、未读取浏览器会话、未连数据库、
  未安装扩展到任何真实浏览器、未改浏览器设置。
- 未提交 Git、未推送、未部署；票状态与共享索引由主控维护。
- 本轮未扩跑全仓 audit 与无关测试；证据即 §A.6 的命令与退出码。
