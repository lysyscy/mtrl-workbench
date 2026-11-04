# TAIL-476 当次真实会话验证

2026-11-04。结论：**在本次已核Edge会话、用户确认站点和一个精确单据代表条件下可复用**。这不是对全部浏览器、站点、账号或日常产品入口的推广承诺。

## 事实与过程

1. 原先Edge处于登录表单，之后用户自行提供已登录业务页。Agent未执行登录、退出或强踢。通过可见账号面板核账号、组织及账套；以页面真实对象的单号、项目、日期、审批金额和状态作为独立核对依据。原始名称/金额不进入本Git说明。
2. 浏览器站点与工作台配置不同，严格客户端先返回`StrictTargetMismatch`，尚未生成浏览器请求。用户明确裁定“以当前Edge为准，仅测试，不改工作台配置”后，仅在独立临时进程用现有配置注入口装配该次目标；工作台持久配置未改。
3. 宿主中转transport把既有`strict_payment_notice_by_bill_no`生成的POST、路径、form逐项转交给当前标签支持的CDP调用。浏览器原生fetch限定同origin、`credentials: same-origin`、`redirect: manual`，只访问已收录`/FC/FM/PaymentBill/getList`，按单号精确查、limit=5；不导出或注入Cookie、不新增服务、不复制浏览器配置。
4. 真实HTTP 200返回1条。只将既有解析所需字段原值投影经stdin交回等待中的同一严格客户端，仍走既有响应校验、`_extract_records`和`_map_record`。解析出的单号、项目、日期、审批金额和状态与已见页面一致，主键非空。没有伪造业务回包，未以空列表或200本身判成功。
5. 该次有界网络记录未截断；仅观察到目标POST及页面自身`UserOnline/refresh`，无登录/强踢/重定向。客户端facts：`cookie_present=false`、`transport_injected=true`、`product_session_cache_used=false`、`requests_attempted=1`、`login_blocked=0`、`redirect_blocked=0`。身份交叉核对由宿主人工完成，不能将客户端恒false字段改写成机器核验成功。

## 不能省略的边界

定位代表对象时曾通过i8原生页面查询限定5条；观察发现该按钮还调用查询面板及组织树选择相关保存接口。未核这些辅助偏好的实际持久化结果，不能将这段UI准备称为纯只读；没有使用业务保存/审批/付款/打印动作。此后停止用UI查询按钮进行验证，上述严格transport的单次请求单独计证，不包含这些辅助调用。

原始响应、账号、Cookie与签名信息未保存到Git。去敏细节在受管组`i8-browser-reuse-live-20261104/files/reports/live-reuse.json`；临时宿主适配在同组`work/browser_relay.py`，进程已正常结束。后续需将这个有界协议整理成可复现维护入口后再关闭本票，不能把目前仍需宿主桥接的CLI写成无人值守生产能力。
