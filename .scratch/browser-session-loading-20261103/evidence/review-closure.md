# 累计审查处置

2026-11-05 · 原两轴报告独立保留：[Standards](review-standards-final.md)、[Spec](review-spec-final.md)。本表为主控处置，不合并或改写原轴内等级。真实Edge安装/日常入口验收仍未授权、未执行。

## 接受的实质项（代码已修，真实日常链待验）

- Standards S1a / Spec(a)仓库名单：维护入口必须携带已选模式并进入统一工厂，浏览器模式不能走HTTP登录/强踢。
- Standards S2 / Spec(a)采购合同：已只读核当前I8_CONTRACT_LIST_URL路径为`/PMS/PCM/Contract/GetCntMList`，无查询参数，既有ContractFetcher以POST读取；补这一已核只读端点，不能要求用户改回HTTP或把任意配置路径放行。
- Spec(c)超时：合同既有LIST_TIMEOUT=200、DETAIL_TIMEOUT=60，broker固定30不能满足。沿每条HTTP请求现有预算传递并执行，连接空闲清理不误杀合法在途请求；不能把超时误报成身份失效。
- Standards S3：把候选浏览器通道、既有身份/站点约束、只读端点/方法和适用范围登记到i8契约，真实验证与部署分别标明。
- Spec(a)i8记录占位：按实际最近结果/历史区边界提供局部读取空间，补该页具名验证。
- 主控：relay终止后provider仅refresh仍可能保持connected=true；必须停止动作并诚实回显，重连由用户发起。
- 主控：同账号登录失效不应清掉浏览器方式后默默恢复HTTP；模式按账号隔离并保留显式选择。
- 主控：全局pendingIdentity/BOUND_KEY需按连接隔离，不能被另一工作台页面预检/重连替换；每请求仍核实际可见身份。
- 主控：send失败catch在已abort时不得再postReply；未知协议形状不得当无任务继续轮询。
- 主控：不存在连接的disconnect已纯内存复现AttributeError（queue=None后clear），应幂等受控；连接代号在断开重连后亦不得复用。

## 范围与判断

- Standards S1b打印：打印/PDF的原策略是独立已确认业务契约，本轮不把它改成浏览器抓取。接受收窄i8页“所有取数”承诺并在正式契约说明范围，保留既有打印授权/提示，不执行打印。
- Spec(b)报表导出路径：部分reportExport端点本来就是库存/结存取数链的二进制响应，不是业务导出重写或实际打印，保留必要读取；只退役确无日常消费者的额外白名单项。
- Standards判断：重复载荷归一个窄助手以避免漏接；无消费者字段/不实注释清理；ticket用明确不透明唯一标识。外部i8组织映射归mod02适配契约，工作台身份仍归core，不为判断性smell把业务组织映射塞入通用身份层。

## 并行修复写域与协议

后台/扩展归原476会话：backend、apps/browser-extension、docs/reference/i8-contract.md及其证据。前端修复归新会话：i8-session/i8-browser-relay/i8/main及各现有抓取控件、前端测试和独占证据；不改共享read-region和已验加载页面呈现。源码稳定后由主控整合与定向验证，不重跑全部独立审查。

双方使用同一消息形状，避免各造接口：

- `i8-relay:identity`：附`device_id`；缓存待核身份按该连接/发送页面隔离。
- `i8-relay:bind`：附`device_id`、服务端返回的正整数`generation`、`identity`（刚被服务端核对的`{origin,account,orgCode,orgName}`）。扩展核其与该连接待核值及当前DOM一致才绑定，不能仅接受页面声明。
- `i8-relay:execute`：附`device_id`和`request`；request保留ticket/generation/method/url/headers/body_b64，新增正数`timeout_ms`，来自后端原HTTP read预算。扩展只接受相应绑定和代号并在发前重核真实身份。
- `i8-relay:unbind`：附`device_id`，只撤该连接。选中另一个i8标签仍使旧标签绑定失效。
- server pending/complete的既有device_id字段与归属校验保持；complete的generation必须有效且匹配。服务端代号在每次connect都新建，含断开之后的重连。
- 页面device标识可改为每文档内存唯一值，避免复制标签继承sessionStorage nonce；所选方式按账号保留。helper集中生成HTTP/browser载荷并对未连接browser当场失败，保原HTTP授权参数含义。

## 新证据

完整候选在主控统一backend_verify六文件退出0；公共身份/读取9项GUI通过；HttpOnly假会话自动携带、不可被页面读取且伪造Cookie头被拒的隔离Chromium检查通过。上述证据不证明真实Edge activeTab点击、生产i8或各日常业务结果已验。

2026-11-05最终定向处置：后端四文件统一隔离验证退出0；前端121单测、统一typecheck/build及5项新GUI通过，详情见[集成回执](TAIL-476-integration-final.md)。扩展第六轮曾漏代号与sender核验，主控核出后第七轮补齐，DSH实际31项协议测试和38条隔离Chromium判据通过（含HttpOnly自动携带、另一页面不能借连接）。主控另将代号输入限定为number正整数，拒绝Number隐式转换，协议31项再次通过；合法数值输入未变，复用已验Chromium证据。原两轴报告独立保留，没有重跑累计审查。真实安装、activeTab点击与通知书日常按钮验收仍待用户批准，不关闭476。
