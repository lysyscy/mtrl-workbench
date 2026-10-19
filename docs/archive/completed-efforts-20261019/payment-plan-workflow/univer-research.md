# Univer 付款计划编辑接入评估依据

核实日期：2026-10-15。范围：嵌入系统的 Univer Office SDK / Sheets；只做官方资料核查，未安装、未运行、未修改产品。当前主文档标记 v1.0.4，部分 API 参考仍标记 v1.0.0-beta.2，实际接入必须锁定同一协调发行线后核验 API。

## 结论

Univer 可以作为现有页面中的局部表格编辑器，不需要把原生 JavaScript 网站整体迁移成 React/Vue。开源表格核心可独立使用；但官方 XLSX 导入导出属于 Pro，仍要接服务端格式转换和商业许可边界，不能按“装一个前端开源库就完整替代 Excel”估算。[官方仓库](https://github.com/dream-num/univer#-open-source-and-pro)、[文件交换集成](https://docs.univer.ai/server/import-export)

用户明确要求计划与通知书同时可见，便于复制粘贴。单独一个 Univer 计划页仍会迫使用户切页面；改善此问题的关键是独立窗口或同屏核对区，而非替换编辑器。基于这个需求，保留桌面 Excel、通知书页面提供核对和选单是优先候选；完整区域粘贴尚未通过真实剪贴板验证。是否继续做 Univer 小样，应比较系统内直接编辑和选区联动的收益与接入成本。此段是结合用户使用方式作出的工程判断，并非厂商能力保证。

## 许可、接入与服务成本

| 问题 | 已核实结论 | 来源 |
| --- | --- | --- |
| 开源核心许可 | 官方核心及 OSS 插件为 Apache-2.0；Pro 是另行开发的商业扩展层。开源 Facade、公式、筛选排序、样式等不因存在 Pro 而强制付费。 | [官方仓库开源/Pro边界](https://github.com/dream-num/univer#-open-source-and-pro) |
| 是否全站迁移框架 | 官方支持 React、Vue、Web Components；README 也给出普通 JS 初始化到指定 DOM 容器的方式。内部视图层使用 React，不代表宿主网站必须整体改写。 | [官方仓库接入和兼容性](https://github.com/dream-num/univer#-compatibility) |
| XLSX 导入导出 | 浏览器使用 @univerjs-pro/exchange-client 和 @univerjs-pro/sheets-exchange-client；必须有转换后端。浏览器可导入 xls/xlsx/csv/tsv，导出 xlsx/csv/tsv；其 API 不接受 xlsm。 | [当前 Sheets 导入导出](https://docs.univer.ai/guides/sheets/features/import-export) |
| 不做协同能否纯前端 XLSX | 不能据官方方案作此判断：snapshot 方案不需要协同，但仍需要服务端转换。服务端转换模块为 @univerjs-pro/exchange-node。 | [文件交换集成](https://docs.univer.ai/server/import-export) |
| 最小部署边界 | 无协同时，浏览器上传文件→服务端转换→返回快照→页面编辑→上传当前快照→服务端导出。应用负责存储、上传/查询/下载接口、权限、大小限制、失败和超时处理。无需为这一流程额外部署协同服务。 | [文件交换集成](https://docs.univer.ai/server/import-export) |
| 授权如何配置 | 许可内容配置到客户端的 UniverLicensePlugin 或 preset；覆盖功能和发行版、有效期均会影响限制。许可决定功能，不代替应用自身访问权限。 | [当前 License 文档](https://docs.univer.ai/server/license) |
| 免费限制与价格 | 本次当前官方主文档没有可核实的免费额度表或公开金额；当前官网 /pro、/pricing 未能成功取得。商业购买被引导到官网联系渠道。不能把旧资料中的“1MB导入、1万单元格导出、5文档/3人”等数字作为当前承诺，也不能把未知报价写成免费。 | [许可配置](https://docs.univer.ai/server/license)、[官方仓库商业询问入口](https://github.com/dream-num/univer#-open-source-and-pro) |

无需导入/导出 XLSX、仅用业务数据生成和保存 Univer 快照时，可只采用开源核心编辑能力，避开官方 XLSX 转换链；代价是应用自行维护业务数据与表格快照映射。这是从组件边界推导出的可选架构，尚未对本项目实现或验证。[官方仓库](https://github.com/dream-num/univer#-open-source-and-pro)

## 公式、批注、合并、格式与图片：编辑能力不等于无损往返

| 内容 | 官方能力与明确边界 | 本项目尚须验证 |
| --- | --- | --- |
| 公式 | 核心支持公式，当前公式文档列出 528 个函数。跨工作簿公式不会自动读取另一个本地 Excel 文件；核心要求相关工作簿载入同一计算环境，稳定源 ID 绑定等属于 Pro 扩展。保存只有公式字符串会丢失相关绑定资源；异步计算后需等待结果。 | 真实计划使用的每个函数、金额精度、公式结果缓存、外链、导出后 Excel 重算结果。 |
| 批注/备注 | 核心仓库区分 comments 与 notes，并列为 OSS 能力；Pro 另有协同/历史等能力。支持编辑并不能证明旧式批注、线程批注及作者/时间/回复往返完整。 | 真实文件里批注类型、作者和内容保留；只导出文字数据是否可接受。 |
| 合并 | 选区 API 提供 merge、breakApart、mergeAcross、mergeVertically、getMergedRanges。 | 导入导出后合并位置、被合并单元格内容及行高/列宽。 |
| 格式 | 核心包括数字格式、条件格式和绘图集成；CSV/TSV 明确不保留工作簿格式或多工作表。 | 本项目日期、币种、小数、边框、字体、颜色、行列尺寸、打印分页和模板视觉效果。 |
| 图片 | 官方核心包含 drawing，Pro 还列出 in-cell graphics；这不是所有 Excel 图片形式皆可无损转换的证明。 | 浮动图/单元格内图、锚点、尺寸、资源权限以及导出图片是否保留。 |

公式依据：[当前公式文档](https://docs.univer.ai/guides/sheets/features/core/formula)。批注/格式/图片分层依据：[官方核心/Pro清单](https://github.com/dream-num/univer#-open-source-and-pro)。合并依据：[选区与单元格](https://docs.univer.ai/guides/sheets/features/core/range-selection)。格式转换边界：[Sheets导入导出](https://docs.univer.ai/guides/sheets/features/import-export)。

本次所读当前官方页面未给出上述所有对象“任意 XLSX 导入→编辑→导出完整无损”的保证。官方要求用真实应用文件往返，再在 Office 中检查编辑结果、公式、图片与布局。因此不能据功能清单断言完整替代桌面 Excel；这也是后续最小验证应覆盖的内容。[官方集成验收要求](https://docs.univer.ai/server/import-export)

## 对业务 API 的接线能力

- 读取选区：getSelection().getActiveRange() 可获取活动区域，FRange 可读取 getValues/getRawValues/getDisplayValues/getCellDatas；须明确业务取原始值还是显示值。[选区与单元格](https://docs.univer.ai/guides/sheets/features/core/range-selection)
- 监听变化：Facade 事件包含 SelectionChanged、SheetValueChanged、SheetEditEnded 和 CommandExecuted 等，能感知选区、值和编辑结束；这些事件本身不替应用完成校验、身份关联或数据库事务。[官方事件列表](https://docs.univer.ai/reference/facade/events)
- 自定义动作：createMenu 支持 action 回调，appendTo 可放到菜单位置或右键菜单。可在回调中读选区、展示校验结果，再调用本项目业务接口；这部分调用与提交语义由本项目负责。[官方 Menu & UI API](https://docs.univer.ai/reference/facade/ui)
- 当前事件与菜单参考页标记为 v1.0.0-beta.2，主指南为 v1.0.4；这里只核实存在相应接线能力，未验证具体签名与当前打包组合。

这能减少人工复制某些区域的动作，却不会自动识别合同/收款方，也不会自动提供“生成通知书”的业务能力。系统仍需稳定的行/合同身份、金额及字段校验、异常反馈、重复提交与保存边界。

## 不混淆产品

本评估针对嵌入式 Web SDK。univer-cli、Codex 或其他 Agent 插件是基于 SDK 构建的不同产品/集成；它们的安装状态、许可证、导出表现与定价不能直接证明本项目嵌入库的条件。官方 README 将核心 SDK、CLI 和其他生态应用分开列出，并提示各项目有自己的设置与 SDK 许可要求。[官方仓库生态说明](https://github.com/dream-num/univer)

未实测：所有真实付款计划文件往返、浏览器粘贴兼容、菜单接业务 API、性能、当前实际可购买的许可和报价、免费部署限额。没有安装 Univer，没有修改业务代码、配置或数据库。

## 与原生Excel路线的本项目代价比较

以下是依据当前代码与样表作出的范围判断，不是实测工期或报价。

| 事项 | 原生Excel编辑＋系统核对/打印 | Univer官方XLSX路线 |
| --- | --- | --- |
| 共用工作 | 项目分段、重复表头与汇总行识别；核对预览；通知书页选单和打印衔接；输入与保存范围 | 同样需要，编辑器不负责业务识别 |
| 特有新增工作 | 剪贴板HTML/文本读取与验证，或原文件读取；明确每次刷新所核版本 | SDK打包与页面生命周期、编辑保存恢复、转换后端接FastAPI、许可证与发行版对齐、真实xlsx往返 |
| 编辑与同屏 | 保留桌面Excel和浏览器双窗口 | 需要同屏布局或独立浏览器窗口；仍须用户验收操作体验 |
| 主要代价 | 更改后重新提交数据；仅文本不能保留完整文件结构，真实复制行为尚待验证 | 接入及运维面更广，许可价格未知，原模板往返不能预先保证 |
| 相对规模 | 样表调查后应归为中等适配，不能按一个粘贴框的小改估算 | 相对更高；不需要为本需求再加入协同功能 |

如果用户不能接受重新复制粘贴，还可评估原生Excel加载项：官方支持任务窗格、读取选区与监听变更，可调用现有核对逻辑；其代价是加载项安装、HTTPS、认证和现场兼容验证，并非零成本方案。[Excel选区示例](https://learn.microsoft.com/en-us/office/dev/add-ins/quickstarts/excel-quickstart-vs)、[工作表变更事件](https://learn.microsoft.com/en-us/office/dev/add-ins/excel/excel-add-ins-worksheets)、[官方加载项教程及HTTPS要求](https://learn.microsoft.com/en-us/office/dev/add-ins/tutorials/excel-tutorial)

浏览器授权读取本地文件是另一种输入方式，要求安全上下文和用户手势；文件保存后需重新取得文件内容。它不等于自动感知Excel尚未保存的修改，也不能在未验证部署前承诺一键实时同步。[Chrome File System Access官方说明](https://developer.chrome.com/docs/capabilities/web-apis/file-system-access)
