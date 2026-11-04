# 日常通道集成验证（真实 Edge 待验）

2026-11-05，集成工作树基于已推送 `90720465`，包含其后本任务候选改动。没有部署或修改正式配置。

## 主控验证

- 统一 `backend_verify` 运行 `test_frontend_preview_browser_check.py`、`test_acc_jc_fetch_orch.py`、`test_i8_browser_relay.py`、`test_i8_strict_propagation.py`，退出0。受管组 `023713-386228-17256` 的 `reports/backend-verify.json` 记录测试选择、目标和清理成功；包括先前DSH因无数据库配置未完成的合同编排。临时schema与pytest工作目录均已清理。
- 新验证模式只准指定月份的浏览器通知书抓取和必要连接控制；其它非GET/HEAD动作除登录/登出全部拒绝。默认预览仍允许原本地写入。边界测试包含同步业务处理线程的上下文传播、原body继续可读、错范围拒绝、普通HTTP/纯Cookie运输拒绝。定向独立审查原结果为none，之后主控仅进一步缩小非GET/HEAD范围，并在上述统一验证中通过。
- 统一入口 `final-closure-build` 的typecheck/build退出0。新建可丢弃真实副本 `frontend_rewrite_397_25564e3c1ac84469913f1ceea6459575`，真实i8外呼保持阻断。
- `apps/frontend/tests/test_i8_session.py` **5 passed in 52.82s**：通道停止压过服务端连接记录、同账号失效保留浏览器方式、未连接零请求、旧HTTP载荷保持、执行记录初读/错误/重试区域稳定。前四项以模拟通道状态/拦截请求核前端控制行为，不代表真实扩展或业务抓取成功；最后一项恢复真实本地记录读取。
- 启动尚未就绪时第一次页面命令得到5个fixture错误（无登记预览），未执行页面断言。待统一 `registered_preview()` 明确核到实例与产品后执行上述成功检查，没有绕过身份保护。
- 预览由统一stop正常退出0，确认自建schema已清理。加载UI原有24项和公共身份9项证据沿用，不因本轮扩大回归。

## 当前仍待完成

扩展执行前连接代号核对、必填绑定身份和发送页面归属已经第七轮修正；DSH协议31项、隔离Chromium38条判据通过。主控实际核对应源码后进一步拒绝代号的隐式类型转换，协议31项再次通过；合法数值输入行为不变。用户Edge安装/activeTab点击与从原抓取按钮完成真实业务链仍未执行，不能将单测、模拟页面或隔离Chromium的HttpOnly样例称为日常已可用。
