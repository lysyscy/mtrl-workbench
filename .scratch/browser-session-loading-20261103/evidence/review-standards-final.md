# 累计独立审查 · Standards 轴

范围 `22cc48f8..工作树`（含未提交/新增）。规则源：AGENTS.md、CONTRIBUTING.md、CODING_STANDARDS.md、前端/写入架构、i8 契约、规格。只读，未跑服务/真实 i8。

## 硬问题

**S1 P1 两个入口仍会登录/强踢，与页面承诺相反**
`apps/frontend/src/i8.tsx:77` 承诺"所有取数都可改由浏览器发出：不登录、不顶号"。
① 仓库名单：`apps/frontend/src/notice-maintenance.tsx:78` 只发 `{warehouse_name,allow_kick:true}`，无 `session_mode`；`backend/app/mod03_notice/router.py:209` 未包 `relay_scope`；`backend/app/mod02_i8/router.py:60-69` 作用域默认 `http` ⇒ 仍走 `I8Client(allow_kick=True)`，真登录、真顶号（触发：指定项目归属→新建小微→查名单）。同处 `:94` 提示"可能重新登录"，自相矛盾。
② 打印/PDF：`apps/frontend/src/notice-print.tsx:38` 无 `session_mode`，`backend/app/mod03_notice/notice_executors.py:80` 固定 `I8Client(allow_kick=True)`，且无提示。
违 `frontend-design.md:109`"提前禁用并说明原因与可解决路径"、规格:19、`i8-contract.md:35`。

**S2 P1 采购合同在浏览器模式是死路，归因错**
`backend/app/mod02_i8/browser_relay.py:99-101` 并入 `i8_contract_list_url`，扩展 `apps/browser-extension/service_worker.js:49-65` 无此项（`:45-47` 自认）⇒ 点击后只得到"不在只读取数白名单里"（`:124`）。`apps/frontend/src/contract-tools.tsx:35` 仅门控未连接，`:49` 仍承诺经浏览器发出。违规格:88、`frontend-design.md:109`；`README.md:73` 已记该限制，UI 未同步。

**S3 P2 新通道未进 i8 契约**
`docs/reference/i8-contract.md` 本任务零改动，而它自述"统一收录入口"（:3、:9），`AGENTS.md:9` 亦指向它；11 条只读端点与禁登录/强踢边界只存在新源码。违 `CONTRIBUTING.md:9`；S2 即其后果。

## 判断（possible）
- P2 浏览器模式载荷 `session.mode===SESSION_MODE_BROWSER?{session_mode,device_id}:{…}` 在 contract-tools:40、inventory-fetch:35、mechanical-work:114、notice-auto-link:28、notice-fetch:39-40、projects:270-271 六处同形：Duplicated Code，正是 S1 被漏的原因，宜抽 helper。
- P3 `browser_broker.py:11` 自称"条件变量"，`:303` 实为轮询；死字段 `created_at:111`、`redirect_to:123`、`_waiting:157` 无读写。
- P3 `ticket`（`:266`）含 `id(body)&0xFFFF` 用途不明；丢队标 `timeout`（`:275-278`）与"没有回音"文案不符。
- P3 `i8_identity.py:43-45` 组织映射硬编码 mod02，`CODING_STANDARDS.md:7` 谓配置/身份归 core。

## 未验
Edge 安装/权限与日常按钮验收待审批，属外部条件，不计硬违规；S1/S2 与其无关，是源码内可判缺口。
