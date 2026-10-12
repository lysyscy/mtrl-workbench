# TAIL-302: 报表筛选共用参数读取，保留各页业务差异

**What to build:** 报表筛选共用参数读取，保留各页业务差异

**Blocked by:** None (can start immediately)

**Status:** done

- [x] 共用读取保留首值、0、None、空列表、空格、重复值；四页默认/校验/多选差异不变。
- [x] 查清月份 date/字符串端点与实际查询字段；不因统一形态改行为，给明确暂缓理由。
- [x] 按调用者核验状态解析、列表/大表/导出入口；新判据同批隔离反例必红且基线绿。
- [x] 后端重启、真实读取通过；证据与未验边界记录并按协议销号。

---

## Comments

**2026-10-12 · 建票（agent）。** 来源：架构报告C及用户2026-10-12推进要求｜不做会怎样：相同取首值与查询扁平化分散维护｜落点：backend/app/core/query.py及mod06到mod11相关读取点｜阶段 / 时机：随时｜**排期四问**（`§14.3` 同源）：①实际重复已证实②修一处漏同族会静默改变筛选③纯函数收口不改业务④月份验证差异保留不强统


**2026-10-12 · 只读调查与推荐（agent）。** 基点 9420b13，开工无已有dirty。按AGENTS读README§〇/§三、主计划§13.6最新行/§15、MEMORY、issue-tracker§四、architecture§一/§二、modules包内分工、IDE§十一/十五/十六；工具操作读细则§廿三与tools/README，时间规格读说明书§9.2。使用 improve-codebase-architecture 与 codebase-design skill，并按前者要求让只读agent独立查月份及五页差异；用户已限定仅C、不重新访谈既定规格，因此没有执行泛化访谈或新增GLOSSARY。

报告C**部分成立**：原mod07/api、mod08/router、mod09/api、mod11/api四份查询扁平化完全同算法；mod06/router跨业务包借mod08的函数。原mod06/service、mod07/service、mod08/service、mod09/service四份单值读取也同契约。报告点到mod11/api的_s实为金额精度输出，不能混进参数抽象。推荐已实施：两条纯函数interface落core/query.py；各页业务状态仍原地。module删除测试成立：删掉共用件会把取首值/保0/扁平化重新散回调用者，因此locality与leverage有实际收益。代价是多一条core依赖和两条小interface；不建字段表框架、参数策略开关或新的业务验证器。mod08原扁平函数只被mod06借用，本页JSON库存入口本来全量；移除该死副本，不强给库存列表加后端筛选。mod07大表仍由big_service解析，焊材提取导出仍区分None/空串；实际调用者均核对。

保留差异（直接从现行实现与结果核对，不另立业务口径）：

| 点 | 结果与处理 |
|---|---|
| 共用单值 | 缺席才用default；list/tuple取首项，首项空不找后项；None/空序列为空；0→字符串0，False→字符串False；去两端空白，不校验是否合法。 |
| mod06 | service保0；导出router._one仍折叠0；多选exppj去空去重并折叠None/0。单项目、表签与展开状态交给本页。 |
| mod07 | 月页空值回默认上月；非法非空文本仍原样交下游。提取页ext_period缺席取默认年，显式空串/None保留全部期间；非法status回默认。大表月份验证仍在big_service。 |
| mod08 | 多选保重复，list内None→字符串None、0→字符串0；直接scalar 1仍TypeError，不扩充机器入参。空period回默认，非法非空period/dir继续下传；only_adj仅字符串1为真；列上下限0保留。 |
| mod09 | 月份为空/非法均回默认；单值项目取首项保0。但JSON入口原来先把重复pj列表整体str化，此差异保留。 |
| mod11 | arch/supplier/project单值不strip，重复键列表整体字符串化；tag另过滤合法值；不给筛选走现有全量行为。_s继续只处理金额输出。 |

月份建议：**本轮不收口**。timing.month_range_closed返回date，ym_to_closed_range是ISO适配且当前无外部运行调用者；period._month_bounds经period_range活用，返回ISO字符串/全部None；notice_source.month_range用于build_list_form的i8 BillDt*date*ge/le闭区间字符串。正常2024-02均首日到29日，2026-12均到31日；不会改成右开区间或引入datetime最后一秒。

实际使用者：mod03/list_view筛通知书doc_date前10位；mod08/domain拿核算ym拼-01比较（不是单据日期）；mod07/extract把端点截成月份比较，service取止月作为导出报告月；mod02/fetch_task用于抓取范围及回显；notice_source/build_list_form构造i8日期ge/le条件。纯形态统一不能统一这些查询字段。

只读运行三个入口的差异：2026-00依次TimeRangeError / (2026-00-01,2025-12-31) / IllegalMonthError；1899-02仅timing拒绝；2026-2为timing正规date、period拒绝、notice保原串；2026-02tail前两者拒绝，notice拼原文；空串为报错/全部None/报错；9999-12仅period次年溢出。合并验证会改变异常、年份范围或输入结果；端点算法很小，收益不足以抵偿行为改变与全调用者验证成本。既有非法期间缺口只记录，非本票等价重构目标，不为抽象顺手修业务行为。待办登记回执：参数收口登记本票；月份收口不另开票，理由如上；D–F未调查未实施。

**2026-10-12 · 核验落账（agent）。**

- `python -X utf8 .codebuddy/work/00-scratch/tmp-20261012-C-equivalence.py`：以HEAD旧四页实现和旧四份扁平化对当前实现，394组输入（0/False/None/空/list/tuple/重复/空格/非法年月及异常）结果一致；同脚本复现上述月份矩阵。该临时证据按scratch TTL，不作为永久判据。
- `python -X utf8 tools/oneoff/_run_rulers.py --since .codebuddy/work/00-scratch/tmp-20261012-C-entry.json`：119件相关pytest，rc=0、118.67s；工具检查与11条链路通过，总136.59s、BAD: []；局部四态隔离，没有覆盖权威四态。
- `python -X utf8 tools/mut/_mut_report_query.py`：最终7项真实interface/调用者判据基线绿；8个隔离靶全部造红（取末值、折叠0、塌缩多值、擅自strip、缺席/空值混同、多选去重、大表漏参数、提取导出漏参数），复原7项绿，正式文件字节未变。首次空格靶曾不红，原因是测试仅覆盖单值空格；已补多值带空格并重跑全部，不能拿首次结果当通过。
- 新增第7项后仅补跑该判据文件及对应8靶，不重跑未变的119件；相关代码只订正一处旧query_params注释。`py_compile`通过，新mut已由mut_cover重生成登记（表B无相应欠项）。
- `ops/server_ctl.ps1 -Action restart`：服务Running且/app=200；临时只读真实请求六条通过：m06/matrix、m07/settlement重复period取首月、大表重复period取首月、m08/inventory、m09/fee、m11/list非法tag。列表JSON之外，隔离调用者测试还穿过m06导出和m07提取导出（缺席/空串/重复值），不写生产业务数据。

未验边界：本轮未执行外部i8实际ge/le查询，未改也未重新核验生产抓取、日期非法值纠正、月份之外的业务写入及全站浏览器39段。没有改壳字节/布局/交互，不触发壳章；现有导出算法由相关回归覆盖，本轮隔离导出入口用于验参数传递，不声称新增真实模板下载证据。D–F不在范围。不存在留待用户裁定的本票业务选择。

**2026-10-12 · 销号与终轮（agent）。** `_tail_close.py --id 302` 干跑核对后 `--apply` 完成；状态done、活动行移除、排期迁历史及已销号索引同步。最终文档影响入口（README、ops架构/索引、计划、票、销号索引、旧交接留痕）rc=0，28项相关pytest通过，15.63s、BAD: []。随后只补本条回执与旧交接指针，以真实提交钩子复验最终文档；119件业务输入未变结果复用。提交推送按issue-tracker§四自主执行，SHA与远端结果以Git记录及交付回复为准。
