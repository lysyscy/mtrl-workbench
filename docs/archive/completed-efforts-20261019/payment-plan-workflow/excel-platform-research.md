# Excel 任务窗格平台与部署核实

核实日期：2026-10-15。范围：Windows Microsoft 365 桌面 Excel，优先 add-in only XML manifest；评估“原生 Excel 编辑 + 任务窗格核对 + 浏览器通知书粘贴单号打印”的平台、安装、维护限制。只读研究，未实施加载项、安装证书、下载软件、改注册表、启动 Office 或调用 i8。不估工期。

## 先看会影响方案成立的条件

1. **共享文件夹目录可以用于两台 Windows 电脑试点，但微软明确不支持把它作为生产加载项部署方式。** XML 清单适合该测试路径，统一 manifest 不支持；功能区变化还会要求每位用户重装。因此不能把“放一个 XML 到共享目录”写成受支持的正式发布方案。[Windows 共享目录旁加载](https://learn.microsoft.com/en-us/office/dev/add-ins/testing/create-a-network-shared-folder-catalog-for-task-pane-and-content-add-ins)
2. **正式集中部署有组织账号与管理员门槛。** 微软推荐 Integrated apps portal；其兼容传统 add-in portal 的文档列明组织许可、Entra ID、Exchange Online 活跃邮箱等要求，并排除仅 Microsoft 365 Apps for Business/Enterprise 而无 Exchange Online 的部署。安装了桌面 Microsoft 365 不能证明租户具备集中部署条件。本项目租户、管理员及第二人账号资格均未核实。[部署资格](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/centralized-deployment-of-add-ins?view=o365-worldwide)、[管理中心部署](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/manage-deployment-of-add-ins?view=o365-worldwide)
3. **现有 HTTP 局域网 API 不应直接当作 HTTPS 任务窗格可用的后端。** Office 加载项遵守 WebView 的同源规则；跨域需要 CORS/代理等安排。微软 Edge 的新本地网络权限存在部分 HTTP 私网地址例外，但不证明本项目 Office WebView2 已具备相同行为。建议估算明确的同源 HTTPS 入口：同一主机名下提供任务窗格和 /api，网关服务端转发现有 HTTP。这样仍要处理证书、项目登录和代理配置。[同源与代理](https://learn.microsoft.com/en-us/office/dev/add-ins/develop/addressing-same-origin-policy-limitations)、[Edge 本地网络访问限制与例外](https://learn.microsoft.com/en-us/deployedge/ms-edge-local-network-access)
4. **“实现承诺不改原表”不等于“平台只授予只读权限”。** 主 Agent 已核实微软文档：application-specific Excel APIs 即便仅执行读取，也要求 manifest 的 ReadWriteDocument。需要在实现与验证层保证不写单元格，不能向使用者承诺 Office 平台强制阻止写表。[任务窗格 API 权限](https://learn.microsoft.com/en-us/office/dev/add-ins/develop/requesting-permissions-for-api-use-in-content-and-task-pane-add-ins)

## 结构：XML 是入口，网页是程序

共享目录存放 manifest XML，网页另由 Web 服务器托管；XML 的 SourceLocation 指向任务窗格网页 URL。目录的 UNC 地址（如 \\服务器\目录）不是网页地址。第二台电脑若沿用 localhost，指的是第二台自身，不能指向第一台服务；清单须使用双方可访问的稳定主机名/URL。后两句是部署设计推论。[清单与网页部署关系](https://learn.microsoft.com/en-us/office/dev/add-ins/testing/create-a-network-shared-folder-catalog-for-task-pane-and-content-add-ins)

技术上是网页加载 Office.js 再调用 Excel API，没有必须采用 React 的要求。可用既有 HTML/CSS/JavaScript；本轮不引入新前端框架。这个判断来自微软提供直接 script 引用和 JavaScript 调用方式，不表示已做过本项目原型。[Office.js 引用](https://learn.microsoft.com/en-us/office/dev/add-ins/develop/referencing-the-javascript-api-for-office-library-from-its-cdn)、[Excel 事件示例](https://learn.microsoft.com/en-us/office/dev/add-ins/excel/excel-add-ins-events)

## 安装：本机试点、第二台试点、正式部署分开算

| 路径 | 安装/配置工作 | 已知限制 |
|---|---|---|
| 本机开发/旁加载 | XML 指向开发网页；可用开发工具旁加载，也可按共享目录测试流程 | 开发工具不是终端用户必须安装的运行依赖；本轮不执行 |
| 本机与第二台共享目录试点 | 建立可访问的共享目录并放 XML；每位使用者在 Office 信任中心登记目录、勾选菜单显示、重启 Office，再添加加载项；两台均须能访问网页与 API | Windows 测试路径；不是微软支持的生产部署；共享目录权限和防火墙需现场验证 |
| 组织正式部署 | 管理员在 Microsoft 365 管理中心上传 XML/提供清单 URL，并分配到用户或组 | 需核租户、许可、邮箱、账号与管理员权限；不是两台电脑在同一局域网就自动可用 |

共享目录事实来源：[Windows 旁加载](https://learn.microsoft.com/en-us/office/dev/add-ins/testing/create-a-network-shared-folder-catalog-for-task-pane-and-content-add-ins)。正式部署事实来源：[资格](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/centralized-deployment-of-add-ins?view=o365-worldwide)、[部署步骤](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/manage-deployment-of-add-ins?view=o365-worldwide)。

正式部署不要许诺即时出现：微软部署步骤文档给出图标可能需重启 Office、24–72 小时出现；资格页另说最长 24 小时。两页口径不同，验收应允许传播等待并以实际租户为准。[部署步骤](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/manage-deployment-of-add-ins?view=o365-worldwide)、[资格页](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/centralized-deployment-of-add-ins?view=o365-worldwide)

## HTTPS、证书和项目登录

微软对 HTTPS 的精确表述是：并非所有桌面场景都绝对强制，但强烈推荐；不使用会有不安全内容警告和错误，Office 网页版/Marketplace 则必须 HTTPS；访问外部数据和服务应使用 HTTPS。开发测试可用本机已信任的自签名证书。**共享目录信任和 HTTPS 证书信任是两件事**；第二台电脑不会因第一台信任证书就自动信任。稳定主机名、证书匹配、两台信任、续期是拟采用 HTTPS 网关后的维护项，尚未实测。[共享目录与 HTTPS 要求](https://learn.microsoft.com/en-us/office/dev/add-ins/testing/create-a-network-shared-folder-catalog-for-task-pane-and-content-add-ins)

微软明确 Office 加载项默认可匿名，也可以自行要求登录，SSO 需要开发配置；因此 Office 已激活或已登录并不自动授予本项目 API 权限。应复用项目账号体系并在任务窗格建立项目会话。Office WebView2 与当前普通浏览器是否共享 cookie、本项目登录重定向能否直接工作，均不能预先保证。[认证与授权概述](https://learn.microsoft.com/en-us/office/dev/add-ins/develop/overview-authn-authz)

跨源方案还要处理 CORS、cookie/凭据和浏览器策略；同源入口可减少此类耦合，但不会自动解决身份、CSRF、退出及会话失效。这里是架构建议，不是已完成认证适配。主 Agent 本轮核实项目登录 cookie 为 HttpOnly、SameSite=Lax、Secure=False，尚未实现 HTTPS 入口下的 cookie 与代理适配。[同源限制与现代方案](https://learn.microsoft.com/en-us/office/dev/add-ins/develop/addressing-same-origin-policy-limitations)

特别边界：Edge 143+ 对私网 IP 字面值和 .local 等有基于 LNA 权限的混合内容例外，不能写成“HTTPS 绝对不能访问任何 HTTP 私网”。但本轮文档没有证明该例外在 Office WebView2 的集成、权限提示、企业策略中等同可用；不把此例外作为本项目默认架构。[LNA 官方说明](https://learn.microsoft.com/en-us/deployedge/ms-edge-local-network-access)

## 更新：页面更新与清单更新不同

| 变化 | 维护动作 |
|---|---|
| 核对规则、页面样式或 JS，URL 不变 | 更新 Web 服务器资源；manifest 可不变。需安排任务窗格重载及缓存版本验证，不能承诺打开中的旧页面自动热更新 |
| 图标、名称、启动 URL、功能区、权限等 manifest 配置 | 更新清单；集中部署 LOB 加载项由管理员上传新清单，Office 下次启动取得更新 |
| 共享目录测试时改功能区 | 官方明确要求每位使用者重新安装加载项；其他清单字段的刷新/缓存行为需用所选测试流程实测，不能一概许诺自动同步 |

事实来源：[管理中心更新机制](https://learn.microsoft.com/en-us/microsoft-365/admin/manage/manage-deployment-of-add-ins?view=o365-worldwide)、[共享目录功能区限制](https://learn.microsoft.com/en-us/office/dev/add-ins/testing/create-a-network-shared-folder-catalog-for-task-pane-and-content-add-ins)。页面重载和缓存验证为本项目建议。

## 联网与 Office.js

微软当前文档（2026-09-25 更新）使用正式 CDN：
`https://officeapis.public.onecdn.static.microsoft/1/office.js`。
首次加载下载并缓存 Office.js 与相关文件；旧 `appsforoffice.microsoft.com/lib/1/hosted/office.js` 是文档所列旧端点。21Vianet 环境另有专用端点，不能只因用户在中国就默认属于该云。[Office.js CDN 与云环境](https://learn.microsoft.com/en-us/office/dev/add-ins/develop/referencing-the-javascript-api-for-office-library-from-its-cdn)

因此默认方案应包含“任务窗格/API 的局域网可达 + 官方 CDN 的互联网可达”。缓存不能充当完整断网运行保证。文档允许内部、开发和调试场景使用本地引用，但这不等于复制一个 office.js 就能保证完整离线；若将来确有离线需求，须单独核相关文件、许可、更新和断网场景。本轮不下载、不验证离线包。[CDN 与本地引用边界](https://learn.microsoft.com/en-us/office/dev/add-ins/develop/referencing-the-javascript-api-for-office-library-from-its-cdn)

## Excel 读取与事件能覆盖什么

| 要做的事 | 官方能力与最低集合 |
|---|---|
| 单元格数据变化后重新核对 | Worksheet.onChanged，ExcelApi 1.7 |
| 公式重算后重读结果 | Worksheet.onCalculated，ExcelApi 1.8；不能只靠编辑事件代表公式结果已更新 |
| 随选区显示对应合同/错误 | Worksheet.onSelectionChanged，ExcelApi 1.7 |
| 用户排序后重新定位 | onRowSorted / onColumnSorted，ExcelApi 1.10 |
| 插入/删除行列或单元格后重建映射 | onChanged 的 DataChangeType 包含 RowInserted、RowDeleted、ColumnInserted、ColumnDeleted、CellInserted、CellDeleted，ExcelApi 1.7 |

事件最低集合：[Worksheet API](https://learn.microsoft.com/en-us/javascript/api/excel/excel.worksheet)。插删类型补充核对：[DataChangeType](https://learn.microsoft.com/en-us/javascript/api/excel/excel.datachangetype)。这里只采用标明编号的正式 API；API 页面会默认跳转 preview 视图，不能据页面中其他预览成员扩大承诺。

所列基本事件可暂以 ExcelApi 1.10 为目标，并在运行时用 isSetSupported 确认；这不是完整加载项的最终最低版本承诺，合并块等额外API要按实际选型另核。微软表列 Windows Microsoft 365 的 1.10 最低为 Version 1907 / Build 11929.20306；1.8 为 Version 1808 / Build 10730.20102。把更高集合写进 manifest 会让不支持的客户端不显示/不能运行加载项，必须按真正使用的 API 决定最低集合。[Requirement sets 与运行时检测](https://learn.microsoft.com/en-us/office/dev/add-ins/reference/requirement-sets/excel-api-requirement-sets)

事件有明确生命周期：加载项刷新、重载或运行时结束会销毁订阅，事件处理器不随工作簿保存。默认任务窗格运行时与另行配置的共享运行时生命周期不同，不能预设关闭侧栏后仍持续监听，也不能概括所有共享运行时都会随侧栏关闭而结束。推荐进入核对时全量重读，编辑时将结果标为过期并批量重读，生成/提交前重读再核；排序和插删后重建行映射，避免把旧行号当业务身份。后一组是设计建议，未实现。[事件生命周期](https://learn.microsoft.com/en-us/office/dev/add-ins/excel/excel-add-ins-events)

可读普通 Worksheet/Range，事件不要求先把原表改成结构化 Table；但原表合并单元格、总计/分组、隐藏行、公式、标题漂移如何识别属于适配器工作，官方 API 存在不能代替真实原表验收。多格粘贴也应重读区域，不能只使用单格变更详情冒充完整差异。[Worksheet API](https://learn.microsoft.com/en-us/javascript/api/excel/excel.worksheet)、[WorksheetChangedEventArgs 补充](https://learn.microsoft.com/en-us/javascript/api/excel/excel.worksheetchangedeventargs)

## 当前证据与未核实项

主 Agent 同轮只读核实后提供：本机 Excel ClickToRun 16.0.20430.20146；WebView2 156.0.4314.23；NSSM 参数为 uvicorn --host 0.0.0.0 --port 8000，无 TLS 参数（未排除另有代理）；项目登录 cookie HttpOnly / SameSite=Lax / Secure=False。本文没有再次运行这些检查，不能由版本号推断已通过 Office.js API 自检。

未实测：本机旁加载、证书与网关、CDN 可达、API requirement 运行时检测、登录会话、关闭/重开生命周期、原表插删排序回算。第二台：Office 版本、账号许可、共享目录、网络策略、证书和项目登录全部未核实。集中部署：租户与管理资格未核。浏览器粘贴单号打印只作为既定产品分工，本文不检验浏览器打印实现。

本报告只新增此文件；未更改生产程序或原始 Excel，没有执行安装与业务操作。共享目录正式部署资格、HTTPS 与项目会话是进入实施前应先收敛的三项平台条件。
