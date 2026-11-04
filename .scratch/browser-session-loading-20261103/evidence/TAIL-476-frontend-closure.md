# TAIL-476 前端关闭清单（浏览器会话）

2026-11-05。工作树 `D:/dev/mtrl-workbench/var/worktrees/browser-session-loading-20261104`，基线 HEAD `9efebc87`。
本文件只覆盖**前端**这一个写域（`apps/frontend/src` 的会话层、七个抓取控件、`i8` 页、`main.tsx` 装配，以及 `apps/frontend/tests`）。后台与扩展归并行 476 会话，本轮未改。

本文件区分三种证据等级：
- **实际通过**：本会话真实执行并看到退出码/断言结果。
- **推断**：由源码与既有断言推出的行为，未在浏览器或真实环境观察。
- **未验**：需要主控在现场、真实 Edge 或生产 i8 才能确认。

本会话按任务要求**没有**启动 HTTP 服务、浏览器、前端预览、数据库或 `.env`，没有安装依赖，没有 Git 写入（只读了 `git status`），没有改 `backend/`、`apps/browser-extension/`、`src/read-region.*`、票与总规格。第四节第 2、3 条读到的后端/扩展状态属于**只读观察**，不计为本会话的验证证据。

---

## 一、已在源码里关闭的项

### 1. 通道停止后不再假连（closure 主控项一）

- `apps/frontend/src/i8-session.tsx:209` `const connected = state?.connected === true && !halted;`
  本地停止态 `halted` 压过服务端 `connected=true`。服务端还留着连接记录、但本页的 relay 循环已经结束时，UI 显示「未连接」。
- `apps/frontend/src/i8-session.tsx:115-118` `markHalted`；:220 通道 `stop()` 内 `markHalted(true)`；:178 `connect()` 的 catch 里 `markHalted(true)`；:165 `connect()` 开头、:194 `disconnect()` 成功后 `markHalted(false)`。
- `refresh()`（`apps/frontend/src/i8-session.tsx:125-138`）只把服务端状态记进 `state`，**不再能把 `connected` 拉回 true**——是否已连接由 `halted` 共同决定，而 `halted` 只有用户点连接/断开才改变。
- `apps/frontend/src/i8-session.tsx:246-251`：`blocked` 解除时只 `void refresh()`，**不清停止态**，恢复必须用户显式连接。
- `apps/frontend/src/i8.tsx:99` 新增诚实提示：服务端 `state?.connected` 仍在、本页已停时，说明「工作台那边还留着这条连接记录，但本页已经不再接收取数请求了……不会自动恢复，也不会改用登录方式。」
- 抓取控件的禁用条件经 `session.connected` 生效，因此停止后 browser 方式的按钮/提交当场不可用：`apps/frontend/src/notice-fetch.tsx:28`、`apps/frontend/src/inventory-fetch.tsx:18`、`apps/frontend/src/contract-tools.tsx:35`、`apps/frontend/src/mechanical-work.tsx:70`、`apps/frontend/src/notice-auto-link.tsx:19`、`apps/frontend/src/projects.tsx:243`，以及本轮新增的 `apps/frontend/src/notice-maintenance.tsx:69`。

### 2. 取数方式按账号隔离，登出不再默默回 HTTP（closure 主控项二前半）

- `apps/frontend/src/i8-browser-relay.ts:133-135` `modeStorageKey(owner)` → `mtrl.i8.relay.mode.<owner>`（无 owner 时退回旧键）；:143-145 `relayMode(owner?)`；:148-152 `setRelayMode(mode, owner?)`。
- `apps/frontend/src/i8-browser-relay.ts:164-166` `resetBrowserRelay()` **只** 清模块内存里的 `documentDeviceId`，不再删 `MODE_KEY`。同账号登录失效后，模式仍是 `browser`；换账号读的是另一个键，不串用。
- `apps/frontend/src/main.tsx:97` `<I8SessionProvider blocked={blocked} owner={...}>`（`owner = me ? me.id + ':' + me.account : 'anonymous'`），把真实账号身份交给 provider；`main.tsx:162` 的 `lost()` 与 `:171` 的 `onLogout` 仍调用 `resetBrowserRelay()`，但已不再影响模式。
- 身份预检没有绕开：`main.tsx` 原有 401 / 未知身份的暂停逻辑保持不变，本轮未改 `apps/frontend/src/api.ts`。

### 3. 连接标识每文档一份（closure 主控项二后半）

- `apps/frontend/src/i8-browser-relay.ts:114-119` `let documentDeviceId = ''` + `deviceId()` 首次生成 `dev-${crypto.randomUUID()}`，**不再写 sessionStorage**。复制标签页各自生成自己的 device，不继承 nonce。
- `apps/frontend/src/i8-browser-relay.ts:121-131` 扩展 ID 覆盖仍走 sessionStorage（那是配置而非连接身份，按页保留是原设计）。

### 4. 通道回帖不再滥用 599，协议畸形不再当空队列（closure 主控项四）

- `apps/frontend/src/i8-browser-relay.ts:241-255` `readRelayRequest` 现要求 `timeout_ms` 为正整数；缺字段即判无效。
- `apps/frontend/src/i8-browser-relay.ts:393-482` `runBrowserRelay`：
  - 只有 `payload.request === undefined || null` 才睡 `EMPTY_ROUND_MS` 继续（真正的空队列）。
  - `readRelayRequest` 失败 → `stopped('malformed')` 并返回，不再把它当空队列继续轮询。
  - `execute` 的 catch 里**先核 `aborted()`**：本页已停则 `stopped('idle')` 直接返回，**不回 599**。
  - 回帖 599 自身失败 → `stopped('failed')` 并抛 `ApiError('浏览器回帖失败：和工作台的连接断了，本次已停止，请重新连接。')`。
  - 每个 `await` 之后都再核一次 `aborted()`，`execute`/`postReply` 受同一 `alive/abort` 保护。
- `apps/frontend/src/i8-session.tsx:35-40` 新增 `malformed` 文案；`connected` 也随之置停。

### 5. wire 协议按 closure 对齐（身份 / 代号 / 设备 / 超时）

- `apps/frontend/src/i8-browser-relay.ts:323-335` `i8-relay:identity` 附 `device_id`。
- `apps/frontend/src/i8-browser-relay.ts:344-358` `bindBrowserIdentity(identity, generation, send)` 附 `device_id` + 服务端返回的 `generation` + `identity{origin,account,orgCode,orgName}`；`generation` 非正整数当场 `ApiError('这次连接没有拿到有效代号，请重新连接。')`。`apps/frontend/src/i8-session.tsx:171` 传的是 `connectBrowser` 刚被服务端校验过的身份与代号，不自行猜账号/组织。
- `apps/frontend/src/i8-browser-relay.ts:361-367` `i8-relay:unbind` 附 `device_id`，只撤本连接。
- `apps/frontend/src/i8-browser-relay.ts:393-482` `i8-relay:execute` 附 `device_id`，`request` 保留 `ticket/generation/method/url/headers/body_b64` 并携带后端给的 `timeout_ms`。
- 前端按新协议发送，拒绝不满足口径的回执：`bind` 只有在 `ok===true` 才算成功（`apps/frontend/src/i8-browser-relay.ts:350-357`），`execute` 的回执走 `readRelayReply` 严格校验；形状不符按失败处理，**不会当成功**。

### 6. 重复载荷收成一个窄助手，HTTP 原授权参数不变

- `apps/frontend/src/i8-browser-relay.ts:271` `BROWSER_MISSING`；:279-285 `sessionPayload(choice, http, base)`：`browser` 分支缺连当场抛 `ApiError`（本次零请求、不退回登录），有连时 `{...base, session_mode:'browser', device_id}`；`http` 分支 `{...base, ...http, session_mode:'http'}`，原 `allow_kick` 等授权参数照旧由调用方传入。
- `apps/frontend/src/i8-browser-relay.ts:288-294` `sessionParams(...)` 给查询串用。
- 七个调用点：`apps/frontend/src/notice-fetch.tsx:40`、`apps/frontend/src/contract-tools.tsx:42`、`apps/frontend/src/inventory-fetch.tsx:36`、`apps/frontend/src/notice-auto-link.tsx:30`、`apps/frontend/src/mechanical-work.tsx:116`、`apps/frontend/src/projects.tsx:270`、`apps/frontend/src/notice-maintenance.tsx:89`。browser 分支均无 `allow_kick`。

### 7. 仓库名单查询缺的 mode 字段（closure S1a）

- `apps/frontend/src/notice-maintenance.tsx:14-15` 新增 import；:68-72 `const session=useI8Session(); const browserBlocked = session.mode===SESSION_MODE_BROWSER && !session.connected;` 与按模式的 `warehouseQueryTitle`；:83-95 `checkWarehouse()` 前置 `browserBlocked` 直接返回，载荷改由 `sessionPayload(session,{allow_kick:true},{warehouse_name})` 生成；:106 按钮 `disabled={busy||done||browserBlocked||!newName.trim()}`，并补 `browserBlocked` 告警。
- browser 模式等待的是 `session.connected`（即第 1 项之后真实的连接态），不是服务端记录。

### 8. i8 页承诺收窄 + 记录区占位（closure Spec(a)）

- `apps/frontend/src/i8.tsx:76-79` 文案收窄为「本页的抓取与同步」，并明说「打印与导出 PDF 不受这条通道影响，仍按原来的方式走」。
- `apps/frontend/src/i8.css:22-24` 补上原先无定义的 `.i8-read-status` 与 `.i8-read-reserve`（`border:1px solid var(--bd)` / `var(--radius-input)` / `background:var(--sf)` / `min-height:calc(96px*var(--fscale))` / 内边距，与 `.i8-latest`/`.i8-records` 的几何对齐；`.i8-read-status:empty{display:none}`）。`apps/frontend/src/read-region.*` **未改**。
- 未读不报零：`apps/frontend/src/i8.tsx:110-120` 在 `idle|reading|error` 期间只渲染占位/固定错误槽，不出现「还没有执行记录。」（该文案只在就绪且真为空时才在 `:132` 出现）；同条件保留旧结果由 `readPhase` 的 `stale` 分支维持。

### 9. 剩余 i8 取数入口清点（口径：哪些入口受「取数方式」影响）

- 本次实际改到、且会发 i8 取数请求的前端入口共 7 个，都已改走窄助手（行号见第 6 项）：`apps/frontend/src/notice-fetch.tsx`、`apps/frontend/src/notice-auto-link.tsx`、`apps/frontend/src/inventory-fetch.tsx`、`apps/frontend/src/contract-tools.tsx`、`apps/frontend/src/mechanical-work.tsx`、`apps/frontend/src/projects.tsx`（同步）、`apps/frontend/src/notice-maintenance.tsx`（仓库名单）。
- 其余 i8 相关端点在前端没有第二处调用点：`grep -rn "api/m07" apps/frontend/src` 只命中 `apps/frontend/src/big-api.ts`、`apps/frontend/src/big.tsx`、`apps/frontend/src/settlement-api.ts`、`apps/frontend/src/settlement.tsx`，而 `/api/m07/fetch` 在 `apps/frontend/src` 内**没有任何调用点**（只在 `tools/dev/frontend_preview_copy.py:166` 与 `apps/frontend/tests/test_preview_copy.py:96` 的端点白名单里出现）。因此这次没有给 `m07` 加新入口，也没有把旧入口的授权参数改掉。
- 打印与导出 PDF（`/api/m11/print-export`、`/api/m07/settlement/export`、`/api/m07/extract/export`、`/api/m11/export` 等）**未改**，仍走 `SettlementExport` / `ContractExports` 原有路径；`apps/frontend/src/i8.tsx:77-78` 的文案也明确说明这条通道不影响它们。
- 结论：`i8` 页原先「本工作台里所有取数都可以改由…」的承诺已收窄为「本页的抓取与同步」；实际受影响的入口就是上面这 7 个，范围没有扩大。

---

## 二、检查结果（本会话实际执行）

| 检查 | 命令 | 结果 |
| --- | --- | --- |
| 类型检查 | `cd apps/frontend && npx tsc --noEmit` | **exit 0**，无错误输出（仅 npm notice） |
| 前端单测全量 | `cd apps/frontend && npm run test:unit` | **tests 121 / pass 121 / fail 0**，duration 4115ms，**exit 0** |
| GUI 用例语法 | `cd apps/frontend && python -m py_compile tests/test_i8_session.py` | **COMPILE_OK**，exit 0 |

单测改动明细（均为实际执行通过）：
- `apps/frontend/tests/unit/i8-browser-relay.test.mjs`（422 行，重写）：连接标识每文档一份且不落 storage；模式按账号（`alice`/`bob`）记住，`resetBrowserRelay()` 后同账号仍是 browser；`sessionPayload` 缺连当场失败、HTTP 保留 `allow_kick`；`bind` 带 `device_id/generation/3/identity`，`generation` 为 `0`/`1.5` 抛「这次连接没有拿到有效代号」；`readRelayRequest` 缺 `timeout_ms` 判无效；协议畸形 → `stops===['malformed']` 且只轮询 1 次、执行 0 次；中止期间的扩展失败 → 回帖 0 次、`stops===['idle']`；401 只轮询一次且模式仍是 browser；409 不执行；网络退避 2–4 次；回帖失败如实抛出。共 20 项。
- `apps/frontend/tests/unit/notice-maintenance-mode.test.mjs`（205 行，新建，已登记进 `apps/frontend/package.json` 的 `test:unit`）：仓库名单查询 browser 已连 → `session_mode==='browser'` + `device_id` + 无 `allow_kick`；HTTP → `session_mode:'http'` + `allow_kick:true` + 无 `device_id`；browser 未连 → 按钮 disabled 且零请求。共 3 项。

---

## 三、已写但**本会话未执行**的现场用例（交主控）

`apps/frontend/tests/test_i8_session.py`（229 行，pytest + playwright，按目录自动发现，无需登记）。**本会话没有启动预览，因此 5 个用例全部未运行**，只做了语法编译。它们分别对应任务要求的现场验证点：

1. `test_relay_stop_wins_over_server_side_connected` —— 服务端仍回 `connected=true`、`pending` 给的活缺 `timeout_ms`：UI 必须显示「未连接」、出现「协议对不上」与「工作台那边还留着这条连接记录」、`complete` 零回帖；刷新页面后仍「未连接」（证明不是内存假象）。
2. `test_browser_mode_survives_session_loss_for_the_same_account` —— 选 browser 后触发 `session-lost`：出现「登录已失效，当前只读」，同一账号的 `mtrl.i8.relay.mode.<owner>` 仍是 browser；刷新后 Segmented 仍选中「浏览器已有会话」（同账号不默默回 HTTP）。
3. `test_browser_mode_without_connection_sends_nothing` —— browser 未连时打开「按月抓取 i8」：「确认抓取」disabled，强行点击后 `/api/m03/notices/fetch` 零请求，提示含「本次不会改用登录方式」。
4. `test_http_mode_submit_keeps_the_original_payload` —— HTTP 方式提交：`session_mode==='http'`、`allow_kick===true`、`expected_account` 为本人、**无 `device_id`**（原授权载荷未被改动）。
5. `test_i8_records_first_read_failure_and_retry` —— i8 记录区：首次读取中只有占位、无「还没有执行记录。」；503 后就地报错并保留占位几何（bbox y/height 差 <1）、有用「重试读取」；重试成功后占位消失。

---

## 四、未验 / 需要主控现场确认

1. **上述 5 个 GUI 用例未执行**（未验）。它们在真实预览进程上能否通过，取决于预览端口、账号、以及 `page.route` 与既有 `conftest.py` 夹具的兼容性；本会话只做了语法编译。
2. **扩展与后台的新协议在写本轮证据时已由并行 476 落地（只读观察，未由本会话验证）**。收尾复核时读到：`apps/browser-extension/service_worker.js:84-99` 的绑定基准改为按连接分键 `i8RelayBound:<device_id>`，`:88` 的待核身份改为 `pendingIdentities` Map（按 `device_id` 隔离），`:494-541` 的 bind 要求 `device_id` + 正整数 `generation` + 与服务端核对值及扩展自己刚读到的值逐字段一致才写入，`:419-467` 的 execute 按 `device_id` 核绑定并把 `request.timeout_ms` 透传给注入脚本，`:307-345` 在页面侧按该预算中止；`backend/app/mod02_i8/browser_broker.py:143` 的 `outbound_payload()` 已含 `timeout_ms`；`backend/app/mod03_notice/schemas.py:126-140` 的 `WarehouseCheckRequest` 已加 `session_mode`/`device_id`，`backend/app/mod03_notice/router.py:242` 用 `scope_of(req)` 进入取数作用域。字段口径与本前端一致（identity/bind/unbind/execute 都带 `device_id`，bind 另带 `generation`+`identity`，execute 的 `request` 带 `timeout_ms`）。**但真实 Edge 上的绑定/执行/解绑没有验证过**，也不代表生产 i8 可用。
3. **`warehouse-check` 的 browser 分支实际行为未验**。后端已按 `scope_of(req)` 进入作用域并改走工厂（`backend/app/mod02_i8/router.py:64-72` 的 `_own_client` → `open_i8_client`），browser 模式下 `allow_kick` 结构上无效；前端 browser 分支确实不送 `allow_kick`。两者一致，但**没有在真实现场上跑过**。
4. **真实 Edge / 真实日常取数未验**。本会话没有启动浏览器，没有碰真实 i8，没有验证 `activeTab`、真实会话保持、真实业务回包。任务也明确未授权这部分。
5. **生产部署未做**。源码改动全部在工作树，未部署、未构建。
6. **未做全量 UI 回归**。已有的 478–481 的 24 项 UI 验收与窄窗结论未重跑，也未据此改写；本会话只动了 i8 页与会话层，`read-region.*` 与其他页面呈现未改，`apps/frontend/src/i8.css` 只新增两条此前无定义的类。

---

## 五、剩余最小主控现场步骤

1. 起预览（现有约定端口/schema），用一个预览账号登录。
2. `cd apps/frontend && python -m pytest tests/test_i8_session.py -q` —— 跑第三节 5 例，记录退出码与逐例结果。
3. 若第 1 例或第 3 例失败，先看是不是 `page.route` 抢在 `/api/m02/browser/state` 之前（用例里 state 是 `page.route` 伪造的），再判断是不是实现问题；断言文案以 `apps/frontend/src/i8-session.tsx:35-40` 与 `apps/frontend/src/i8.tsx:99` 为准。
4. 扩展与后台的 wire 协议（`device_id` / `generation` / `identity` / `timeout_ms`）在写本轮证据时已落地，但**还没有被任何人用真实标签验证过**。待主控用真实 Edge 做一次「选中标签 → 连接 → 一条只读取数 → 断开」的连通检查；本文件不对该环节作任何「已验」声明。

---

## 六、改动文件清单（本会话写域内）

源码：
`apps/frontend/src/i8-browser-relay.ts`（503 行，重写）、`apps/frontend/src/i8-session.tsx`（272 行，重写）、`apps/frontend/src/i8.tsx`（145 行）、`apps/frontend/src/i8.css`（35 行）、`apps/frontend/src/main.tsx`（175 行，仅 97 行传 owner）、`apps/frontend/src/notice-fetch.tsx`（68 行）、`apps/frontend/src/contract-tools.tsx`（131 行）、`apps/frontend/src/inventory-fetch.tsx`（61 行）、`apps/frontend/src/notice-auto-link.tsx`（43 行）、`apps/frontend/src/mechanical-work.tsx`（189 行）、`apps/frontend/src/projects.tsx`（291 行）、`apps/frontend/src/notice-maintenance.tsx`（118 行）。

测试与登记：
`apps/frontend/tests/unit/i8-browser-relay.test.mjs`（422 行，重写）、`apps/frontend/tests/unit/notice-maintenance-mode.test.mjs`（205 行，新建）、`apps/frontend/tests/test_i8_session.py`（229 行，新建，未执行）、`apps/frontend/package.json`（test:unit 追加一项）。

未改（按要求保持只读）：`backend/**`、`apps/browser-extension/**`、`apps/frontend/src/read-region.tsx`、`apps/frontend/src/read-region.css`、`review-standards-final.md`、`review-spec-final.md`、票与 Git。
