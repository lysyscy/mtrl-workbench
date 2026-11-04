# TAIL-476 · i8 已有浏览器会话严格复用 · 实现与离线证据

日期 2026-11-04 · 实施真源 `codex/browser-session-loading-20261104`（基点 `22cc48f8`）· 交接登记 `PH-20261104-loading-i8-01`
本轮 = 首轮复核清单（`review-round1.md`）TAIL-476 四条的修正轮。

## 结论先行（范围务必看清）

- **真实复用 = 未验证**。现场既有 i8 标签是登录表单，没有可核的已登录业务会话（`baseline-observation.md`），
  `--execute` 从未对着真实 i8 跑过 ⇒ 任何真实成功判据都没有被兑现。
- **浏览器通道 = 未接线**。本票只交付了"通道要满足什么"的最小契约（`_CHANNEL_CONTRACT`）与注入点，
  没有实现、也没有验证任何真实通道；**抽象 transport ≠ 已接线**。
- **离线 16 条用例通过只证明"严格模式的停止/脱敏/目标约束行为正确"**，
  不证明会话身份、组织、页面对象，也不关闭上面两项。
- 本轮修正的三处验收措辞问题见 §2。

## 1 · 改动清单（写域内，全部为新增文件；未改动任何既有产品文件）

| 文件 | 规模 | 作用 |
| --- | --- | --- |
| `backend/app/mod02_i8/browser_session.py` | 新增 273 行 | 严格「仅复用已有会话」客户端 `I8BrowserSessionClient`（继承 `I8Client`）+ 会话材料 `ReusedBrowserSession` + 单号精确查 `strict_payment_notice_by_bill_no` |
| `backend/tests/test_i8_browser_session_reuse.py` | 新增 392 行 / **16 个用例** | 离线行为覆盖（见 §4） |
| `tools/dev/i8_browser_session_reuse.py` | 新增 222 行 | 具名严格复用入口：`--plan` 只打印计划与通道契约、`--execute` 才真正复用 |
| `.scratch/browser-session-loading-20261103/evidence/TAIL-476.md` | 本件 | 去敏证据与未验边界 |

未改：`backend/app/mod02_i8/client.py`（产品缓存/重登策略**一字未动**）、`login.py`、`cookie_store.py`、
`notice_source.py`、`sources.py`、`router.py`、前端全部、`backend/tests/conftest.py`、DB 守卫、票状态/索引。

## 2 · 本轮按复核清单修正了什么

### 2.1 收紧结果措辞（复核第 2 条）

原先入口只核「四个字段非空 + 单号相等」就打印"核对通过"，容易被读成整体验收通过。现改为：

- 退出 `0` 的文案固定为「**响应解析完成**：单号一致、具名字段齐全；本次未登录、未强踢、未写产品会话缓存、未跟随跳转。」
- 紧随其后固定一行：**「⚠️ 以上**只**证明解析链跑通；账号 / 组织 / 页面对象是否与声明的目标一致，仍须人工交叉核对。」**
- 模块 docstring 与 `--plan` 都写明：退出 `0` **不等于**整体真实复用验收通过。
- `facts()` 增 `identity_cross_checked: false`（与既有 `declared_target_machine_checked: false` 并列），
  即"声明"永远不冒充"机器核对结果"。

### 2.2 修正证据里的过度断言（复核第 2 条后段）

首轮本件写过「组织范围不被改写 ⇒ 借别人组织的数据在结构上不可达」。**该断言过强，已撤回**：

- 请求表单确实仍用既有常量 `LIST_FORM["phidOrgList"]="3700000000000014"`（`backend/app/mod02_i8/notice_source.py:44`），
  严格模式不提供改组织/项目的参数；
- 但**固定组织过滤常量既不证明会话属于该组织，也不证明会话身份**——若浏览器里的会话属于他人或他组织，
  服务端按会话权限裁剪/回包，客户端无从分辨。故正确表述是：
  **"组织参数未被本入口改写" ✓ / "跨组织读取在结构上不可达" ✗**。
- 同理，`declared_target`（本人·组织·服务器）只是操作者的声明，`facts` 里只输出"有无声明"这一个布尔。

### 2.3 去敏（复核第 3 条前半）

| 位置 | 首轮问题 | 现状 |
| --- | --- | --- |
| 入口成功输出 | 打印整个 `row`（`_map_record` 的 `fields` 键存**整条原始记录**） | 只输出 `REPORT_FIELDS` 六个具名键：`bill_no/ph_id/project_name/approve_status/doc_date/amount_approved` |
| 入口失败输出 | `except AppError` 里拼 `exc.message`／对任意异常打印原文 | 统一走 `_stop(exc.code, ...)`，输出受控类别（`_STOP_LABELS`）+ 固定文案；兜底只给 **异常类名**，不给原文 |
| `facts()` | 直接输出 `base_url` 与 `declared_target` 内容 | 只输出 `session_origin`（协议/主机/端口，**去掉用户信息、路径、查询串**）+ `declared_target_present` 布尔 |
| 继承的 `get_json/post_json` | 非 JSON 失败时 `logger.warning` 记 `resp.text[:200]` 响应片段 | 严格模式**覆写**这两个方法走 `_json_or_stop()`：只抛固定 `I8_TAKE_FAILED`，不记片段、不拼原始报错 |
| 会话材料 | — | `cookie_header` / `transport` 均 `field(repr=False)`；`facts()` 只给 `cookie_present: bool` |
| 会话材料 JSON 解析失败 | `json.JSONDecodeError` 原文可能带出输入片段 | 改成固定提示「会话材料不是合法 JSON（未回显内容…）」，`from None` 掐掉链式上下文 |

### 2.4 目标约束覆盖实际请求与重定向（复核第 3 条后半）

- `_origin_of(value)`：只留 `协议://主机[:端口]`，去 userinfo / 路径 / 查询 / 片段；解析失败或端口非法 ⇒ 返回 `""`（与任何配置都不等 ⇒ 保守停止）。
- `_ensure_session()`：会话站点 origin 必须等于 `i8_base_of(get_settings())` 的 origin，不等 ⇒ `StrictTargetMismatch`，**0 次请求**。
- `request()`：**每一条**请求发出前 `_assert_allowed(_resolve_target(path))` —— 绝对地址、`//host/path` 协议相对地址、相对路径
  都先解析成完整 URL 再比 origin；不等 ⇒ `StrictTargetMismatch(_STOP_FOREIGN_TARGET)`，那次请求**不发**。
- `follow_redirects=False`；响应若 `status_code in {301,302,303,307,308}` 或 `resp.is_redirect` ⇒
  `_redirect_blocked += 1` 并抛 `StrictRedirectStopped`（**不跟随**，Cookie 不会被带去未核实的地址）。
- 全是**行为级**验证（发了几次请求、扣了几个计数器、有无抛错），不检查私有函数文本。

## 3 · 控制流与数据流依据

- **会话只注入一处**：`I8BrowserSessionClient` 重写 `_ensure_session()`（建 `httpx.Client(base_url=注入站点, transport=注入适配, follow_redirects=False)`）、
  `_ensure_cookie()`（只取注入 Cookie 头，**不读** `cookie_store`）、`_login()`（**永不登录**：`_login_blocked += 1` 后抛 `StrictSessionEnded`）。
- **解析链零改动**：i8 全部 HTTP 调用点（`client.py`、`contract_source.py`、`notice_source.py`、`payable_source.py`、
  `report_export.py`、`sources.py`）最终都走 `I8Client.request()`，替换会话来源即全链复用，不存在平行取数系统。
- **单号精确查**：复用既有 `LIST_FORM` + 双层 `queryfilter`（`{"queryFilter": json.dumps({"BillNo*string*eq*1": 单号})}`、`limit=5`，
  与 `tools/probe/print_bills.py` 同口径），空结果按既有 `EMPTY_RETRY=1` 复核一次，字段映射走既有 `_map_record`。
- **失效判据复用**：`_is_session_invalid()` 仍是既有三条（HTTP 401 / `Code=="401"` / `Msg` 含 `No SessionInfo`），
  但严格模式下命中后走 `_login()` ⇒ 立即停止（不重发、不清缓存、不重登）。
- **产品策略未变**：`I8Client` 仍是原类原实现（缓存命中不登录、失效至多一次重登、仍失败清缓存），
  严格子类只覆盖上述三个方法；用例 `test_产品原有缓存与重登策略未被这层改动` 守这一点。
- **计数器即证据**：`request()` 里"先验目标、后 `_attempts += 1`"，所以 `requests_attempted == 0` 可证"未发请求"。

## 4 · 离线验证（本轮实际执行；全部离线：不连 i8、不读 `.env`、不连库、不读浏览器会话）

```
cd backend
./.venv/Scripts/python.exe -B -X utf8 -m pytest tests/test_i8_browser_session_reuse.py
→ 16 passed in 0.30s                                            EXIT=0

./.venv/Scripts/python.exe -B -X utf8 -m pytest \
    tests/test_i8_browser_session_reuse.py tests/test_i8_cookie_cache.py
→ 23 passed in 0.46s                                            EXIT=0   # 原缓存/重登契约未破

./.venv/Scripts/python.exe -B -X utf8 -m pytest \
    tests/test_i8_browser_session_reuse.py tests/test_i8_cookie_cache.py tests/test_layering.py
→ 38 passed in 6.93s                                            EXIT=0   # 加工程分层守卫

cd ..
./backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/i8_browser_session_reuse.py --plan
→ 计划 + 通道契约 7 行（含"⛔ 当前未接入任何真实通道…按未验证记"）   EXIT=0

# 边界停止路径（无会话材料 / 缺 --bill-no / 会话材料不是 JSON）
... --execute --bill-no X1  < 空 stdin     → EXIT=2（"没有可复用的会话…未发出任何请求"）
... --execute（缺 --bill-no）               → EXIT=2
... --execute --bill-no X1  < 截断的 JSON    → EXIT=2（"不是合法 JSON（未回显内容…）"，不回显输入片段）
```

入口端到端离线（假传输 `httpx.MockTransport`，零真实请求；**只证明接线正确，不证明真实复用**）：

```
正常回包        → EXIT=0  facts: requests_attempted=1 login_blocked=0 redirect_blocked=0
                           product_session_cache_used=false session_origin=https://i8.example.test
                           checked 仅六具名键（bill_no/ph_id/project_name/approve_status/doc_date/amount_approved）
                           假记录里额外塞的 SensitiveColumn 未出现在输出里
                           末两行分别为"响应解析完成：…"与"⚠️ 以上**只**证明解析链跑通；…"
查无单          → EXIT=2  requests_attempted=2（既有 EMPTY_RETRY 复核一次）
会话失效        → EXIT=2  requests_attempted=1 login_blocked=1（停止，无重发）
重定向到外站    → EXIT=2  requests_attempted=1 redirect_blocked=1（未跟随）
非 JSON 回包    → EXIT=2  类别"i8 那边的这次取数没成功（未重登、未强踢）"，响应原文未出现
```

16 条用例覆盖（行为级，不验私有实现）：

1. 有效会话经既有解析链完成一次单号精确查（`row == _map_record(REC)`；1 次请求；表单含单号、`limit=5`、既有组织常量；登录与缓存零调用）
2. 无会话材料 ⇒ `StrictSessionUnavailable`，0 次请求
3. 会话站点与配置不一致 ⇒ `StrictTargetMismatch`，0 次请求
4. 会话失效（`{"Code":"200","Success":false,"Msg":"No SessionInfo found"}`）⇒ `StrictSessionEnded`，**只发 1 次**、未登录、未清缓存
5. 站点不成形（缺协议）⇒ 停止，0 次请求
6. 未给单号 ⇒ 停止，0 次请求
7. 会话材料不进 `facts()` / 不进 `repr()` / 不进日志
8. 站外绝对地址与 `//host/path` 协议相对地址 ⇒ 停止且 0 次请求
9. 同主机不同端口 ⇒ 视为不同站点，停止
10. 显式写成默认端口（`https://host:443`）⇒ 仍判同站点（`session_origin` 无空端口）
11. 重定向 ⇒ 立即停止、不跟随、只发 1 次
12. 非 JSON 失败 ⇒ 固定文案，响应片段既不在用户文案也不在运行日志（用 loguru sink 断言）
13. `facts()` 只给站点 origin，不含声明内容与查询串
14. 入口成功时不含"核对通过"字样、只留具名字段、原始列不外泄
15. 入口停止时只报受控类别，不报异常类名/原文
16. 产品原缓存与重登策略未被这层改动

已知未跑/未通过（**改动前即红或属其它票，不构成本票验收要求**）：
`tests/test_ux_text.py::test_用户可见串里不许拼异常正文` 报 `backend/app/mod02_i8/router.py:239` 与
`backend/app/mod08_inv/adjustment_values.py:27`（两文件 `git diff HEAD` 为空，未被我修改）；
`tests/test_i8_manual_safety.py` 4 条需 `rollback_db` ⇒ 需 `--source-env`，本轮未运行（非通过、非失败）。

## 5 · 浏览器通道接线：最小可复现方案与当前限制（复核第 1、4 条）

**现状**：主控侧可用的是 Edge 扩展 CDP / 只读页面能力，**不能**凭空让后台导出 Cookie；
本票**没有**新造服务、没有猜端点、没有复制浏览器配置、没有改安全设置。

**已交付的最小契约**（`tools/dev/i8_browser_session_reuse.py::_CHANNEL_CONTRACT`，`--plan` 逐行打印）：

- 实现形式 = 一个 `httpx.BaseTransport` 子类，`handle_request(request) → httpx.Response`；
- 把请求送到宿主浏览器里**同一个** i8 会话上发出（同源页面 fetch 自动带 Cookie，或等价通道）；
- 本入口**不要求、也不假定** Cookie 可导出；
- 通道**不得**自行跟随重定向、不得重试、不得登录、不得写任何会话文件 ⇒ 3xx 原样返回，由入口判停；
- 拿不到可判读响应时（例如浏览器只给不透明响应）**必须让本次调用失败**，不许伪装成 200；
- 不得打印/记录 Cookie、Authorization 或响应原文；
- 只接受与本入口相同的 i8 站点（`httpx.Client` 已带 `base_url`）。

**为什么本轮不实现它**：实现通道需要在真实已登录会话上跑（发请求、验回包），
而现场没有这样的会话；离线写一个"看起来能用"的通道实现无法被证伪，反而会误导成"已接线"。
故本轮停在"契约 + 注入点 + 明确未接线"，这是**能力缺口**，如实记录，不用离线通过掩盖。

**接线后可复现的最小步骤**（由主控在现场执行，本票不执行）：
1. 现场确认该 Edge 标签是本人账号、组织、服务器都在核过的 i8 业务页；
2. 按上面的契约实现通道（约一个 `httpx.BaseTransport` 子类，几十行），模块路径经 `--transport` 传入；
3. `--execute --bill-no <已核单号>`，核对 §6 判据。

## 6 · 无秘密的调用接口与结果核对判据

**接口 A（代码）**

```python
from app.mod02_i8.browser_session import (
    ReusedBrowserSession, I8BrowserSessionClient, strict_payment_notice_by_bill_no,
)
session = ReusedBrowserSession(
    base_url="<会话所在 i8 站点>",       # 必填；origin 与产品配置不一致 ⇒ 一条请求都不发
    cookie_header="<当次会话 Cookie 头>", # 与 transport 至少给一个；不打印、不落盘
    transport=None,                      # 或注入转发到宿主浏览器的 httpx.BaseTransport
    declared_target="<本人·组织·服务器，仅记忆，不参与机器判定>",
)
client = I8BrowserSessionClient(session)
row = strict_payment_notice_by_bill_no(client, "<付款通知书单号>")
client.close()
client.facts()   # 去敏计数：requests_attempted / login_blocked / redirect_blocked / ...
```

**接口 B（具名入口）**：`tools/dev/i8_browser_session_reuse.py`，
`--plan`（不连 i8）或 `--execute --bill-no <单号> [--transport 模块:函数]`，
会话材料经 **stdin** 传 JSON：`{"base_url", "cookie_header", "declared_target"}`。
退出码：`0` = 响应解析完成且单号一致、字段齐全（**不等于**整体验收通过）；`2` = 按边界停止（未验证）；`1` = 入口自身失败。

**结果核对判据（全部满足才算"已验证可复用"）**

- `facts.requests_attempted >= 1` 且 `facts.login_blocked == 0`（没有触发登录，更没强踢）；
- `facts.redirect_blocked == 0`（会话没被带去未核实地址）；
- `facts.product_session_cache_used == false`（没有持久导入后端会话缓存）；
- `checked.bill_no` 与所查单号完全一致，且 `ph_id` / `project_name` / `approve_status` 齐全；
- 上述字段与操作者**独立**说出的预期值一致（不是"看着像"）；
- 账号 / 组织 / 服务器 / 页面对象由**人工**交叉核对一致（`identity_cross_checked` 永远是 `false`，不会自动为真）；
- i8 侧该账号其它在线会话**未被顶掉**。

**不算成功**的情形：HTTP 200、拿到 Cookie、空结果、重新登录后的成功、离线测试通过、后端缓存命中、
新增了会话文件、`requests_attempted == 0`。

## 7 · 未验边界与风险

- **未验**：真实浏览器会话能否被复用（通道未实现）；真实 i8 是否接受该会话；真实解析链对真实回包的字段映射；
  账号/组织是否真为本人；入口的真实退出码从未产生过。
- **风险 1（最大、即复核第 1 条）**：能力缺口 —— 若现场只能读页面、既导不出 Cookie 也做不出转发通道，
  严格模式无路可走；届时须如实记为「已验证不可用」或「仅在具名条件下可复用」，不得记通过。
- **风险 2**：站点比对只比规范化后的 `协议://主机[:端口]`，不做 DNS/证书校验；现场若用别名/反代地址，
  会出现"同一台机器但不相等"的误停（保守方向，可接受，需现场知悉）。
- **风险 3**：严格模式与产品常态路径共用 `I8Client._lock` 与 `serialize_fetch` 同表锁；
  与产品抓取并发时最多等同表锁释放（600s），不串数据但可能等待。
- **未做（票面 Out of Scope）**：自动登录、强踢、复制完整浏览器配置、持久导入会话、生产入口推广、
  业务写入/打印/导出、连接真实 i8、读写 `.env`、读取浏览器会话。

## 8 · 环境与产物

- Python：`D:/dev/mtrl-workbench/backend/.venv/Scripts/python.exe -B -X utf8`（未安装、未改环境）。
- 本轮未走 `tools/dev/backend_verify.py --source-env <来源.env>`：来源参数由主控提供，本轮未提供 ⇒ **未运行**
  （不算通过）。上述用例本身不连库、不读 `.env`，`conftest.py` 的数据库守卫不阻断；本轮也**没有**绕过或改动守卫。
  若主控要求走规定入口复核，请对 `backend/tests/test_i8_browser_session_reuse.py` 跑一次即可（只读、离线）。
- 本轮未重跑全仓 audit、未跑无关测试；`--plan` 与两轮离线用例即够用范围。
- 未连接真实 i8、未读 `.env`（仓内只有 `.env.example`）、未读取浏览器会话、未连数据库、未提交/推送 Git。
- 本票未产生受管二进制产物（无截图/报告/导出）；唯一新增文本证据即本件。
