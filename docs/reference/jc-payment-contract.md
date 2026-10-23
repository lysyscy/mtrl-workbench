# 集采付款约定接口

供旧台账与新前端接入使用；业务规则主人为《材料科业务全流程说明书》§6.4.1，来源 main/master 固定提交 `a8004d605b409d70ba5e255e2218d7d2c530368d` 的 TAIL-432/433；本次只接后端契约，React UI 消费进度回[规格](../../.scratch/frontend-vue-rewrite/spec.md#阶段2a后端付款契约)。

## 合同字段

迁移 `c432261023`（前置 `c391261021`，与main原件一致）只新增 `jc_contract.payment_term`（varchar(32)）和 `payment_method`（varchar(16)），NOT NULL、默认空串。空合并节点 `c2a261023` 汇合本分支 `c419261022` 与main的 `c432261023`，保持两条已发布父链身份；从任一前置升级都保留另一侧必要迁移。不转换历史 `method`，不改备注、金额、发票和付款。

- `GET /api/m11/list` 的每行、`GET /api/m11/detail?id=` 的data包含这两个同名字符串。
- `POST /api/m11/add` 接受这两个字段；`POST /api/m11/fields` 通过fields只更新传入字段，空串清空。
- 账期接受非负整数 `90±10天`、`90±10`、`60天`，返回规范形式 `x±y天`；格式错误整次不写入。最大天数为x+y自然日。
- `GET /api/m11/list` 的 `payment_methods` 复用实际付款四种候选；合同字段空串表示未约定。旧 `method` 写入保持拒绝。
- 台账columns在备注前增加账期与合同付款方式，普通Excel导出跟随columns；打印模板维持既有列。重抓只刷新原有i8事实白名单。

## 付款窗口上下文

`POST /api/m03/payment-context`，请求`{"ids":[通知书id],"pay_date":"YYYY-MM-DD"}`；只读事实，返回`ok/pay_date/rows`，rows按去重后的请求顺序，未知ID省略。每行有`notice_id/default_pay_method/default_pay_method_source/term_warning`；来源为`plan`、`contract`或`fallback`。无关联合同时不带合同字段，默认仍按计划／现汇。

有关联合同时带`contract_id/contract_no/payment_term/contract_payment_method`。`term_warning`为空表示本次无需提醒；非空包含`message/payment_term/max_days/pay_date/invoice_side/invoices`，invoices逐条包含`invoice_id/invoice_date/remind_through`。`invoice_side`为supplier或trade；异常大账期超出可表达日期范围时remind_through为空，max_days仍保留完整依据。仅返回未满账期的相关日期，不推断付款分摊或到期可付额。

main 的旧付款窗口打开时读取默认；未满账期的通知书整行黄底，下方按通知书逐条展示付款项目、合同材料名、本条付款金额、发票日期、账期、提醒截止，并标明可继续付款。同合同多张通知书分别展示；材料名按合同id取已加载的集采台账，金额及窗口合计随当前付款草稿即时更新，多张相关发票逐行保留日期。日期变化按notice_id同步更新行标记与日期依据，排序或刷新提醒不覆盖手改方式和金额。最终按当前日期重读并可继续确认提醒，所有实际付款仍走原batch-pay端点；该端点缺省方式也按同一后端优先级取值。未增加数据库迁移或实际流水字段。

兼容现行旧后端：仅当payment-context端点返回404时，窗口保留既有计划／现汇默认和原付款流程，并明确显示账期提醒未启用、需人工核对；不声称已完成账期判断。认证、网络或服务器错误不走此兼容分支。新后端可用时继续统一读取合同默认和日期依据。静态资源由当前工作区直接提供，分支隔离不等于浏览器发布隔离；新增接口调用必须保留未加载后端的兼容路径。

## 日期依据的边界与接入依赖

`remind_through` 是录入发票日期加最大账期的提醒截止，不能标为准确应付款日。来源接口没有可信度等级、开票来源核验或到期可付额；不解析备注来猜账期。无法解析的发票日期跳过；空提醒只说明本次规则没有返回提醒，不证明日期真实或合同可付。金额、准入、幂等和事务仍由原 batch-pay 校验。

迁移只允许在明确的专用测试 schema 验证；原8037预览仍使用旧模型/旧schema，未加载本契约。后续2D验证需新建自有schema并升级到c2a261023，不能直接给8037旧schema升级。通知书列表、payment-preview及batch-pay的既有React响应字段保留；本端点不写草稿、关联或流水。
