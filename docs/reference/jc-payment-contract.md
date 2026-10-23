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

旧付款窗口打开时读取默认；未满账期的通知书整行黄底，下方按通知书逐条展示付款项目、合同材料名、本条付款金额、发票日期、账期、提醒截止，并标明可继续付款。同合同多张通知书分别展示；材料名按合同id取已加载的集采台账，金额及窗口合计随当前付款草稿即时更新，多张相关发票逐行保留日期。日期变化按notice_id同步更新行标记与日期依据，排序或刷新提醒不覆盖手改方式和金额。最终按当前日期重读并可继续确认提醒，所有实际付款仍走原batch-pay端点；该端点缺省方式也按同一后端优先级取值。未增加数据库迁移或实际流水字段。

兼容现行旧后端：仅当payment-context端点返回404时，窗口保留既有计划／现汇默认和原付款流程，并明确显示账期提醒未启用、需人工核对；不声称已完成账期判断。认证、网络或服务器错误不走此兼容分支。新后端可用时继续统一读取合同默认和日期依据。静态资源由当前工作区直接提供，分支隔离不等于浏览器发布隔离；新增接口调用必须保留未加载后端的兼容路径。

## Excel核对与计划回写

现有`GET /api/m03/plan-audit/snapshot`的每条notice增加`jc_contract`，未关联为null；已关联为`{id,contract_no,payment_method}`。payment_method为空表示合同未约定，包括正式字段尚未迁移的兼容读取；不冒充i8原值或已确认计划。

技能compare比较原Excel方式与此约定，冲突或未填时标原方式格及M列，并跳过本行候选，普通未关联合同行保持原行为。明确确认例外用核对命令`--confirm-method-row`原Excel行号重建预览；金额、归属及既有预览确认仍有效。

现有method-preview每条change附带`jc_contract`及布尔`method_exception_confirmed`。原methods端点在同一事务锁定现有通知书/流水及合同/关联表，再核当前关联、合同方式、原拟方式、金额和状态；合同上下文变更整批拒绝。方式不一致或未约定须有明确例外确认，否则拒绝。旧预览未带上下文时，仅未关联合同的行可按原规则处理；当前有关联的须重新核对。客户端原文件SHA、预览SHA、备份和回执机制保持。

新快照字段依赖后端加载；技能发布/实际安装与工作台后端部署分别核实。已有Mini App继续复用这些端点与skill脚本，不另造核对网页。
