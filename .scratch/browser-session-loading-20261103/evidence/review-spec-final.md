# Spec 轴独立审查（终稿）

范围：`22cc48f8..9efebc87` 全量 tracked diff（排除继承的 CONTRIBUTING.md / frontend-design.md）+ 本任务 untracked 源码/测试/文档。只读，未启停服务、未用浏览器/真实 i8/数据库。

## (a) 规格缺失／部分完成

**P1｜浏览器模式下「采购合同抓取」必停，UI 仍可选并承诺可用。**
`apps/frontend/src/contract-tools.tsx:40` 在 browser 模式确实发送 `session_mode`；后端白名单靠 `_CONFIGURED_ENDPOINTS` 放行（`backend/app/mod02_i8/browser_relay.py:100`），但扩展侧白名单少这一项，并在注释里写明会拒绝（`apps/browser-extension/service_worker.js:41-65`，L45-47）。触发：用户按日常流程切「浏览器已有会话」→ 点「确认抓取」→ 必得"不在只读取数白名单"。影响：spec L88"还须核工作台日常入口→浏览器连接→既有取数/解析及原流程的实际接线"对该入口不成立；`apps/frontend/src/i8.tsx` 无采购合同相关提示，用户无从预知。属硬问题（"日常抓取能用才算能用"，L7）。

**P1｜通知书维护「查询 i8 仓库名单」在浏览器模式下仍会登录／强踢。**
`apps/frontend/src/notice-maintenance.tsx:78` 只发 `{warehouse_name, allow_kick:true}`，无 `session_mode`；`backend/app/mod03_notice/schemas.py:127-134` 无该字段；`backend/app/mod03_notice/router.py:203-231` 不设 relay_scope ⇒ `open_i8_client(allow_kick=True)` 落回 ContextVar 默认 http，返回原 `I8Client`。触发：已选浏览器方式的同一账号，在编辑通知书、新建小微时点该按钮。影响：违 spec L19"浏览器模式不自动回退登录或强踢"、L54"无会话…时停止，禁止调用登录／强踢"。UI L94 已声明会顶号（诚实告知），但不改变行为违规。属硬问题。

**P2｜i8 页占位不占真实内容区。**
`apps/frontend/src/i8.tsx:119` 的 `i8-read-reserve` 在 `apps/frontend/src/i8.css`（29 行，无 read 规则）及全库 CSS 中无任何规则（grep 只命中 i8.tsx:119）；对照 `apps/frontend/src/notices.css:76`、`apps/frontend/src/projects.css:54` 均有 padding/min-height。违 spec L64"占位消费真实内容区/字体/已知结构"。该页首屏与错误态不回填真实表格高度；且 478–481 验收明言 i8 页未纳入。

## (b) 未要求的扩张

**P2｜只读通道纳入导出／打印读取端点。**
`backend/app/mod02_i8/browser_relay.py:82-95` 含 `reportcenter/reportExport/export`、`printManage/getPrintDesign`。spec L109-117 把"实际打印"与"导出…重写"列为范围外；虽未改写业务，但浏览器通道新增了导出/打印读取面，且与下述 30s 上限结构性冲突。判断项（低危）。

## (c) 看似实现实则错误

**P2｜浏览器模式下长请求必被 30s 截断。**
`backend/app/mod02_i8/contract_source.py:131-136` 显式 `timeout=LIST_TIMEOUT`（200.0，见 `:94`），而 `backend/app/mod02_i8/browser_broker.py:58` `RELAY_WAIT_SECONDS=30.0`，`wait()`（`:350-359`）超时即 `StrictSessionEnded`。即使合同列表进了扩展白名单，也必在 30s 停；`report_export.export`（无显式 timeout）同风险。方向正确（严格停），但把该入口可用性堵死，且用户看到的是"会话失效"话术而非超时。判断偏硬。

## 反例核对：以下维度未发现问题（none）

- **严格失败 vs 旧 HTTP 保持**：`backend/app/mod02_i8/browser_relay.py:317-353` http 分支仍返回 `I8Client(allow_kick=allow_kick)`；`apps/frontend/src/notice-fetch.tsx:40` 等 http 分支保留 `allow_kick:true`；browser 缺连接当场 `BrowserRelayUnavailable`（不退回登录）；`backend/app/mod02_i8/browser_session.py:100-160` `_login()` 只计数并抛 `StrictSessionEnded`，`_ensure_cookie()` 不读 cookie_store。符合 L19/L54/L57。
- **页面必要数据门控与保草稿**：`apps/frontend/src/notices.tsx:96,244`、`apps/frontend/src/fees.tsx:67,111` 读取中禁用动作、占位不含金额/行数（`apps/frontend/src/read-region.tsx` 只渲染空 span），`stale` 保上次结果并显示"更新未成功"。符合 L63/L64/L66/L69。
- **无新增轮询／通用缓存期限**：全库 `staleTime:0`，唯一长轮询即 relay 通道（L70 允许）。
- **会话材料不外泄**：`facts()` 去敏、扩展不申请 `cookies`（`apps/browser-extension/manifest.json`、`README.md:17`）。符合 L57。

## 外部条件（不计为已验／也不计为代码缺陷）

Edge 安装与权限、当前目标上的日常真实按钮验收仍待具体包审批；476、478–481 票未勾。477 已验但缺真实空汇总样本。
