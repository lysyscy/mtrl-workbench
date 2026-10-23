# 集采付款约定接口

供旧台账与新前端接入使用；业务规则主人为《材料科业务全流程说明书》§6.4.1，实施票TAIL-432—434。源码接口和正式部署状态分别核对原票。

## 合同字段

迁移 `c432261023`（前置 `c391261021`）只新增 `jc_contract.payment_term`（varchar(32)）和 `payment_method`（varchar(16)），NOT NULL、默认空串。不转换历史 `method`，不改备注、金额、发票和付款。

- `GET /api/m11/list` 的每行、`GET /api/m11/detail?id=` 的data包含这两个同名字符串。
- `POST /api/m11/add` 接受这两个字段；`POST /api/m11/fields` 通过fields只更新传入字段，空串清空。
- 账期接受非负整数 `90±10天`、`90±10`、`60天`，返回规范形式 `x±y天`；格式错误整次不写入。最大天数为x+y自然日。
- `GET /api/m11/list` 的 `payment_methods` 复用实际付款四种候选；合同字段空串表示未约定。旧 `method` 写入保持拒绝。
- 台账columns在备注前增加账期与合同付款方式，普通Excel导出跟随columns；打印模板维持既有列。重抓只刷新原有i8事实白名单。

## 备注迁移

`tools/oneoff/_jc_payment_terms.py <本机预览JSON>` 默认只读，生成JSON及同名Markdown逐条对照。只迁出独立明确片段，冲突、阶段、月份及质保条款留在备注；已填字段不覆盖。

正式字段迁移与真实备注回写分别需要用户明确授权。获准后才对已确认JSON使用 `--apply --confirmed-sha256 <摘要>`；同事务锁定并核对合同身份、原字段与重算建议，任一变化整批拒绝。JSON及真实合同对照保存在本机exports，不入Git。

## 付款窗口上下文

`POST /api/m03/payment-context`，请求`{"ids":[通知书id],"pay_date":"YYYY-MM-DD"}`；只读事实，返回`ok/pay_date/rows`，rows按去重后的请求顺序，未知ID省略。每行有`notice_id/default_pay_method/default_pay_method_source/term_warning`；来源为`plan`、`contract`或`fallback`。无关联合同时不带合同字段，默认仍按计划／现汇。

有关联合同时带`contract_id/contract_no/payment_term/contract_payment_method`。`term_warning`为空表示本次无需提醒；非空包含`message/payment_term/max_days/pay_date/invoice_side/invoices`，invoices逐条包含`invoice_id/invoice_date/remind_through`。`invoice_side`为supplier或trade；异常大账期超出可表达日期范围时remind_through为空，max_days仍保留完整依据。仅返回未满账期的相关日期，不推断付款分摊或到期可付额。

旧付款窗口打开时读取默认；日期变化只刷新提醒，保留手改。最终按当前日期重读并可继续确认提醒，所有实际付款仍走原batch-pay端点；该端点缺省方式也按同一后端优先级取值。未增加数据库迁移或实际流水字段。
