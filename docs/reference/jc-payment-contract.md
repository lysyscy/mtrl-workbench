# 集采付款约定接口

供旧前端与 React 接入；业务含义见[集采](../requirements/central-procurement.md)。后端来源固定 `a8004d605b409d70ba5e255e2218d7d2c530368d`；本分支当前 UI、验证与加载状态回[阶段2D](../../.scratch/frontend-vue-rewrite/spec.md#阶段2d付款预检接线与阶段2验收范围)。

## 合同字段

迁移 `c432261023`（前置 `c391261021`，与main原件一致）只新增 `jc_contract.payment_term`（varchar(32)）和 `payment_method`（varchar(16)），NOT NULL、默认空串。空合并节点 `c2a261023` 汇合本分支 `c419261022` 与main的 `c432261023`，保持两条已发布父链身份；从任一前置升级都保留另一侧必要迁移。不转换历史 `method`，不改备注、金额、发票和付款。

- `GET /api/m11/list` 的每行、`GET /api/m11/detail?id=` 的data包含这两个同名字符串。
- `POST /api/m11/add` 接受这两个字段；`POST /api/m11/fields` 通过fields只更新传入字段，空串清空。
- 账期接受非负整数 `90±10天`、`90±10`、`60天`，返回规范形式 `x±y天`；格式错误整次不写入。最大天数为x+y自然日。
- `GET /api/m11/list` 的 `payment_methods` 复用实际付款四种候选；合同字段空串表示未约定。旧 `method` 写入保持拒绝。
- 台账columns在备注前增加账期与合同付款方式，普通Excel导出跟随columns；打印模板维持既有列。重抓只刷新原有i8事实白名单。

## 付款窗口上下文

`POST /api/m03/payment-context`，请求`{"ids":[通知书id],"pay_date":"YYYY-MM-DD"}`；只读事实，返回`ok/pay_date/rows`，rows按去重后的请求顺序，未知ID省略。每行有`notice_id/default_pay_method/default_pay_method_source/term_warning`；来源为`plan`、`contract`或`fallback`。无关联合同时不带合同字段，默认仍按计划／现汇。

有关联合同时带`contract_id/contract_no/payment_term/contract_payment_method`。`term_warning`为空表示本次无需提醒；非空包含`message/payment_term/max_days/pay_date/invoice_side/invoices`，invoices逐条包含`invoice_id/invoice_date/remind_through`。`invoice_side`为supplier或trade；异常大账期超出可表达日期范围时remind_through为JSON null，max_days仍保留完整依据。仅返回未满账期的相关日期，不推断付款分摊或到期可付额。

main 的旧付款窗口打开时读取默认；未满账期的通知书整行黄底，下方按通知书逐条展示付款项目、合同材料名、本条付款金额、发票日期、账期、提醒截止，并标明可继续付款。同合同多张通知书分别展示；材料名按合同id取已加载的集采台账，金额及窗口合计随当前付款草稿即时更新，多张相关发票逐行保留日期。日期变化按notice_id同步更新行标记与日期依据，排序或刷新提醒不覆盖手改方式和金额。最终按当前日期重读并可继续确认提醒，所有实际付款仍走原batch-pay端点；该端点缺省方式也按同一后端优先级取值。未增加数据库迁移或实际流水字段。

兼容现行旧后端：仅当payment-context端点返回404时，窗口保留既有计划／现汇默认和原付款流程，并明确显示账期提醒未启用、需人工核对；不声称已完成账期判断。认证、网络或服务器错误不走此兼容分支。新后端可用时继续统一读取合同默认和日期依据。静态资源由当前工作区直接提供，分支隔离不等于浏览器发布隔离；新增接口调用必须保留未加载后端的兼容路径。

## 日期依据的边界与接入依赖

`remind_through` 是录入发票日期加最大账期的提醒截止，不能标为准确应付款日。来源接口没有可信度等级、开票来源核验或到期可付额；不解析备注来猜账期。无法解析的发票日期跳过；空提醒只说明本次规则没有返回提醒，不证明日期真实或合同可付。金额、准入、幂等和事务仍由原 batch-pay 校验。

迁移/模型验证先核明确的专用测试 schema 及当前版本；本分支目标为合并节点 `c2a261023`。在用预览的模型、schema、前端和回退依据分别核实，不能仅换前端而沿旧 schema 使用新模型；本次文档吸收不操作任何预览。notice-list、payment-preview 及 batch-pay 的 React 既有字段继续保留；payment-context 不写草稿、关联或流水。

React阶段2D已按上述契约接入付款窗口，状态与证据回[阶段2D](../../.scratch/frontend-vue-rewrite/spec.md#阶段2d付款预检接线与阶段2验收范围)。默认只初始化未手改方式，改期不重置金额/备注/方式，最终确认先重读；404明确人工核对，其他错误阻止继续并可重试。材料名读取失败单独提供重读，不冒充已获取材料或完整合同页；付款成功后列表重读失败与未知提交结果分别表述。

## 主线原表核对与备注迁移

主线已有合同方式快照/核对例外及逐条备注迁移的共享接口扩展，其有效契约和真实写入确认边界见[主线固定接口正文](https://github.com/lysyscy/mtrl-workbench/blob/e55ff04822c78338d130e0fd914835ce60deaa2b/docs/reference/jc-payment-contract.md#excel核对与计划回写)及同件“备注迁移”。本分支尚未吸收对应 snapshot/method-preview/methods 与 `_jc_payment_terms.py` 实现；文档吸收不等于这些能力或个人技能已发布到 React，后续范围回共同规格。
