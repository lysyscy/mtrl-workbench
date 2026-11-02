# 机械页性能诊断

2026-11-02；正式产品提交 `e822612e221b902ebd2ed8f69db9b7b89fdede22`，当前源码 HEAD `db3809f9` 仅追加部署记录。本文为本次调查结论，配套官方方案见 [research.md](research.md)。本轮没有修改产品代码、正式配置或业务数据，也没有调用 i8。

## 结论及优先级

目前有三个已复现的主要瓶颈：状态接口重复携带大块来源和历史版本；公司汇总首屏串行执行整套 Excel 生成；共享表头准备逐列交错写 DOM 和读几何。先修这三条，再测剩余编辑器/滚动成本。当前 SQL 执行和缺少行虚拟化不是这组证据中的主要矛盾。

| 场景 | 当前实测 | 已确认原因 | 优先改法 |
| --- | --- | --- | --- |
| 当前月状态 GET | 重复 1,662 / 1,582ms；仅改为上月仍 1,328ms。响应解压后 11,234,328B；浏览器观测该请求压缩传输约 1,057,067B | 只需当前月界面也返回 17 项目、30 月、213 月额、510 条累计以及整批来源/历史。`effective` 6.44MB，`details` 4.20MB | 按项目/月/用途返回轻量读模型，审计来源与修订历史按需取；持久依据留在服务端 |
| 公司汇总首屏 | 浏览器先等 state 约1.66s，再请求 preview 约1.02s | preview 再跑全量 `W.state`，用 openpyxl 生成四张表、383行、7,176格及样式，再转成 JSON，当前首屏只显示公司汇总 | 界面与 Excel 共用业务计算结果；界面直接读公司汇总模型，四表 workbook 延后到导出 |
| 切零租 | 无新 API 请求；一次工具端等待约3.16s；主线程任务增量1.566s、样式重算0.895s。准备元数据覆盖269业务行，实际 DOM 21行/347格/268个 input | `prepare` 内17列表头逐个 clone→append→读 rect→remove。CPU采样 B→getBoundingClientRect 自身约531ms | 所有表头统一写入再统一读取，按实际字体/列宽/表头结构复用测量结果，避免切表重挂载丢失可复用准备状态 |

工具端等待包含自动化调度/就绪等待，不是 INP；CPU采样也有观察脚本开销，不能直接当真实用户交互分位数。这里保留浏览器主线程、样式和调用栈证据，未宣称任何改法已使整页达到某个响应指标。

## 后端拆分证据

在与正式配置相同的数据源开启强制只读事务，仅调用现行状态逻辑，SQLAlchemy事件记录 **4次SQL，执行合计23.20ms**。取回JSON/ORM处理另有成本，不把23ms称为整个数据库链耗时。cProfile下 `W.state` 约966.67ms，其中 deepcopy 累计625.05ms、978,261次递归调用；profile本身有开销。正常状态计算在同源对照中约345–434ms。FastAPI `jsonable_encoder` 单独测得约531ms；另一轮同对象投影对照见下文。

- `backend/app/mod06_proc/workbench.py:979`：加载全部 Record/ProcMechManual，返回全部明细、历史、来源和项目×月份累计。
- `backend/app/mod06_proc/repository.py:34`：`mech_sources` 深拷贝各列来源；`:39` 的 `mech_effective` 同时返回 `sources` 与完整 `source_batches` 的副本。这两份来源在本轮月值响应中分别约3.21MB和3.18MB，六列实际数值仅约22.8KB。
- 明细顶层包含 `rows` 约1.03MB、`baseline_rows` 约1.02MB、`versions` 约1.58MB、`source` 约0.57MB。普通显示和自动保存没有消费这些完整顶层历史版本；浏览器保存目前仍发送完整行，后续设计不能顺手删掉行级溯源字段。

只在内存保留原行数据及金额、移去页面不用的明细顶层历史和月值完整来源、月值来源只留 mode：响应从 **11.23MB降到1.72MB**；同对象 `jsonable_encoder` 从 **665.04ms降到108.44ms**。这不是已实施的接口，亦不证明直接在 `W.state` 后裁字段就能消除前面的深拷贝；应在读取/投影主人处避免构造不需要的副本。

原始来源、固定i6、年度累计已含月分量、明细版本及幂等/采用依据仍须持久保留。接口精简必须保护金额签名和来源版本；如精简行级元数据，保存协议应改为带行ID/版本的业务字段更新，并由服务端保留来源，不能让客户端回传不全的行覆盖原事实。

## 串行首屏与 Excel 路径

`apps/frontend/src/mechanical.tsx:138–145`：state完成后才能得到当前项目范围，随后启用 report查询；tab没有进入该查询条件，打开明细也持有报表查询。

`backend/app/mod06_proc/workbench_api.py:28–51` 先构造工作区完整快照再调用 preview。`backend/app/report_export/mechanical_export.py:350–374` 的 preview 直接调用完整 build，遍历 workbook四表后转JSON。只读剖析中 snapshot约347.42ms；带cProfile的 preview约1,319.85ms，其中build约1,295.03ms，样式赋值/复制/去重占明显部分。此剖析时间不可与生产HTTP的约1.02s直接相加或计算比例。

推荐共用有金额口径的业务模型，不让界面依赖Excel对象和打印样式；Excel渲染只作为同一模型的另一个消费者。保持四表导出金额与界面一致，也保留按项目/月的正确缓存身份。

## 表头同步布局的对照实验

正式bundle `var/frontend/releases/e822612e221b/assets/business-grid-CU7MdUDr.js` 第19行第181278列的 `B` 已与 `apps/frontend/src/grid-layout.ts:88` 的 `prepare` 对应；关键表头循环在 `:208–216`。这不是仅依据压缩函数名猜测。

在本轮独立浏览器tab，用相同17个已显示表头、同宽度/样式、相同临时测量host，只改变DOM读写顺序，执行顺序为逐列/批量/批量/逐列：

| 方法 | 两次时间 | 测量结果 |
| --- | --- | --- |
| 每个表头插入→测量→移除 | 417.0 / 415.2ms | 17列表头高度数组一致 |
| 全部表头插入后统一测量 | 26.4 / 31.1ms | 与逐列结果全部一致 |

临时host、所有clone都已移除，产品脚本未修改。这个局部实验说明该交错读写链存在可避免成本，不等于完整页面提速十几倍。Chrome官方解释了写DOM后同步读取几何值造成强制布局，以及循环交错读写导致重复布局的机制；建议分批读写。[web.dev：避免布局抖动](https://web.dev/articles/avoid-large-complex-layouts-and-layout-thrashing)

本页细项已经使用 `ag-layout-normal`，实测269业务行只挂载21行，行虚拟化有效；不能给出“加虚拟化就解决”的结论。明细的 textOnly/singleLine 已跳过单元格克隆测量，`data-layout-timing.measured=0` 仅指单元格任务数，不包括表头测量。汇总首屏另有 AG 原生自动列宽成本，但不是零租这段热点的同一个调用。

切页条件挂载会新建网格，准备cache随实例退出。初次、ResizeObserver、完成列宽变化及最终宽度校正都能触发准备；没有统计出无限循环，不将这些机制直接定为死循环。也不删除已有数值变更复用、编辑中延迟重排、手动列宽和用户滚动保护。

## 保存与剩余边界

`apps/frontend/src/mechanical.tsx:206–215` 确认：自动保存重读先全局标旧，再重新取当前月完整state，并失效report/history；显式操作refresh会失效活跃查询。它会再次走上述重响应与Excel链，但本轮没有向正式库执行保存来测保存延迟。保存回执已经局部更新明细，后续可让回执同时返回可信的受影响月额/累计，或定向失效轻量依赖；不能为提速漏掉跨页金额联动、撤销、版本和未知回执保护。[TanStack官方：从mutation响应更新](https://tanstack.com/query/v5/docs/framework/react/guides/updates-from-mutation-responses)

React/AG Grid已有稳定行ID、不可变更新和部分布局复用；不能把每次新数组等同于重建全部行。保持未变对象引用，按证据缩小更新范围即可，不需要先更换框架。[AG Grid官方：更新行数据](https://www.ag-grid.com/react-data-grid/data-update-row-data/)

尚未测另一台电脑/远程链路、真实用户INP分位数或实际保存延迟，也没有证明现有可见输入控件是首要瓶颈。若三条首要链修正后仍慢，再有针对性剖析输入渲染、滚动及准备轮数。

## 与上次发布的对照及证据归属

同一 PostgreSQL repeatable-read、read-only 快照，交替运行 `8301cd54` 与 `e822612e` 的状态源码（不切换服务或检出）：旧版414.93/434.12ms，当前350.41/345.23ms；旧版11,222,083B，当前11,234,328B。说明大体积与主要链路是既有设计；小样不足以宣称新旧版本有稳定提速比例。

已运行的可失败信号：对正式 `/api/m06/workbench?ym=2026-10` 计时，并断言小于诊断阈值1000ms，实际1600ms失败；后续重复样本也均超过该阈值。1000ms仅用于本次定位信号，不是已接受的产品SLO。最小场景不需要编辑或i8取数，仅GET就能复现后端慢点；切零租的慢点在无新GET时也复现，区分了前后端。

本机已登记证据组 `mechanical-performance-20261102`：`backend-profile.json`、`backend-state.pstats`、`previous-current-state.json`、`projection-and-preview.json`、`browser-observations.json`（浏览器聚合读数，不是原始trace）。文件只保留函数、大小、次数、版本和耗时，不保存原业务响应或凭据；诊断结束后按30天证据规则结项。浏览器剖析已禁用、临时tab与测量DOM已退出。本文与research.md为本次结论及研究依据，不因目录名自动清理。
