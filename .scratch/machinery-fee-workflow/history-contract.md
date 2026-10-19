# TAIL-352/353/355 本机数据契约核对

本件保留实施前调查快照；当前实现、已验结果与剩余边界回[evidence.md](evidence.md)。

2026-10-19，只读核对既有证据；供主Agent实施使用。业务规则仍以 [spec.md](spec.md) 一至十一节为准。本件不授权真实导入或现场取数。

## 1. 可直接读的来源

以下均相对仓根 `D:/dev/mtrl-workbench/`；所有列出的JSON及九份原汇总已核存在。

| 用途 | 文件 | 有效入口 |
|---|---|---|
| 1966条完成汇总明细、原月采用额、最新年度参考、固定i6、原型事项 | `.artifacts/machinery-fee-workflow/prototype-20261017/jan-sep-seed.json` | 顶层 `names[24]`、`months[9]`、`data`；详见下节 |
| 九份来源路径、SHA、月条数、三条明细采用冲突和一条年度冲突 | `.artifacts/machinery-fee-workflow/prototype-20261017/jan-sep-source-verification.json` | `hashes`、`stats`、`detail_adoption_conflicts`、`historical_month_vs_latest_annual_conflicts` |
| i8完整最小字段快照 | `.artifacts/machinery-fee-workflow/live-capture-20261017/i8-lists.json` | `capturedAt`、`scope`、`lists.sbsy/xmxhd/jxxhd.{total,rows}`，307/69/129条 |
| i8周期可靠映射、字段观察 | `.artifacts/machinery-fee-workflow/technical-feasibility-20261017/i8-observed-summary.json` | `period_help.resolved` |
| 旧有效系统金额、项目、别名、导入批号快照 | `.artifacts/machinery-fee-workflow/technical-feasibility-20261017/history/system.json` | `effective[196]`、`projects[20]`、`rules[16]`、`batches`、`snapshots`、`cutoffs` |
| 表4来源坐标、固定i6、当时i8、旧差额 | `.artifacts/machinery-fee-workflow/technical-feasibility-20261017/history/cumulative.json` | 18项目，每项 `project/warehouse/total/team_total/i6_fixed/i8_total_snapshot/difference/consumption_snapshot` |
| 精确逐格历史比较 | 同上 `history/local-filled-comparison.csv`、`table4-filled-comparison.csv`、`comparison.json` | 保留每格来源与判定；概况用 `comparison-summary.json` |
| 原Excel读取值/公式/坐标 | 同上 `history/workbooks.json` | 14本工作簿快照；原件哈希 `sha256.json` |
| 国风约定、慧能附属行、实际源页选择 | `.artifacts/machinery-fee-workflow/august-verification-20261017/` | `comparison.json`、`preservation-preview.json`、`sources-a/decisions.json`、`sources-b/decisions.json`、`sources-huineng/decisions.json` |

## 2. seed字段与单位

`jan-sep-seed.json` 是已完成月汇总的原型派生数据，不是现场业务库；`data.saved` 与 `data.working` 各1966条是同批副本，初始化只读一份。不能将二者相加。

**金额陷阱：seed所有货币字段是元×100的数值，可能仍带小数精度；并非全部整数分。i8原快照为元，history系统快照为十进制元字符串。** 转入后端时以 `Decimal(str(value))/100` 恢复seed元，保留来源精度，按现有金额出口到项目合计再舍入。`rate` 是金额；`qty/plan/used` 是数量。源时间 `2026-10-17T14:29:46.355Z` = 上海时间22:29:46。

`names`位置是原型局部项目编号；`project/p` 不可直接充当正式项目ID。明确未配的第23项为 `i8：第四工程公司 2024小微项目(XMCB2024030001)`，不能硬配第1项 `2024年小微佰利`。

少量脱敏结构示例（seed单位为分）：

```json
{
  "id":"real-2026-01-zero-6", "project":5, "month":"2026-01", "cat":"zero",
  "device":"随车吊", "spec":"14吨", "unit":"台班", "qty":1, "plan":1, "used":1,
  "rate":150000.0, "amount":150000.0, "date":"2025-12-24",
  "tax":"专票13%", "rawTax":"0.13", "originalTax":"专票13%",
  "use":"材料倒运", "team":"某班组", "reviewer":"某审核人", "vendor":"某出租单位",
  "plate":"闽A*****", "memo":"", "oil":"", "rawNote":"",
  "source":"第四工程公司1月份外租机械费报表.xlsx / 零租设备月报表 / 第6行",
  "original":150000.0, "sourceNet":null, "manual":false
}
```

| `data`字段 | 含义与使用边界 |
|---|---|
| `records["项目索引|YYYY-MM"]` | 各月当时报送采用额；键 `zero/monthly/weekly/internal/company/zeroNet/monthlyNet`，另有 `reason/reasons`。null保留未知，0为显式0 |
| `baseline` | 上述初始采用额副本；不能当最新年度已含的月份分量 |
| `cumulativeAt[YYYY-MM][项目索引]` | 该月报表记录的各类别累计；各月累计不能重复求和 |
| `referenceAt[参考报表月份]["索引|费用月|类别"]` | 指定月年度报表里的历史月分量，用于旧月修订替换 |
| `latestMonthly["索引|费用月|类别"]` | 9月年度参考中的月分量；`latestCats[索引]`是9月分项累计 |
| `feeBase[索引] / feeBaseSource[索引] / baseMonth[索引]` | 逐项目最近可用年度总累计及来源、截止月。未取得可为null；不可统一填9月或0 |
| `i8[索引].i6` | 该项目固定历史i6；与当前i8三类累计分开 |
| `i8[索引].usage/x/approval` | 当前i8使用、项目结算、班组审批三类累计；无可靠对应为null |
| `i8[索引].projectId/readAt/source/billIds/fingerprints` | i8项目键、时点和逐单基线；fingerprint含结算额、审批额、版本、更新时点、周期、状态 |
| `ledger[505]` | `p/field/period/periodKey/amount/bill/id/title/status/updatedAt/version`；未知周期保留原键 |
| `billDifferences[3]` | `project/bill/period/settlement/approval`，审批减结算；独立于累计差额 |
| `quality[3] / monthConflicts[1]` | 已知采用额不同及年度回溯冲突，见下节 |
| `issues[1]` | 国风未完成约定。保留origin、due、amount、mode、note、evidence、flow、reply及status |
| `reported/selected/order` | 报送名单与用户显示顺序；不能用来限制全量i8来源范围 |

修订累计必须用最新累计已含的月分量作减项：`最新累计 + 已确认新月值 - 该累计参考所含旧月值`；反复确认替换同一覆盖额，不能累计再次加差。晋江2月例尤其不能用原月0作减项，因为最新年度已含4,850。

## 3. i8快照映射

原快照每行结构（元；脱敏）：

```json
{"id":"3700000000006558","projectId":"3700000000002880","projectName":"某项目",
 "bill":"SBSY2026100127","title":"项目9月班组设备使用","periodKey":"3700000000000426",
 "periodName":"09","amount":14000,"approval":null,"status":1,"workflow":2,
 "version":1,"updatedAt":"2026-10-11 11:43:15"}
```

来源类型 `sbsy`：amount = u_fyze；`xmxhd`：amount = u_bqjse；`jxxhd`：amount = u_bqjse、approval = u_bqspe。班组消耗累计采用approval，结算原值仍保存。129条中1条未审且两额null，不贡献累计但保留事实，不视为确认0。

可靠周期仅 `3700000000000422`～`0427` = 2026-05～10；旧0418/0419/0420/0421/0360尚未映射。不能从月份短名称、录单日、单号、ID排序猜年月。title与周期冲突按可靠周期，另留异常。

已知11项报表↔i8映射代码在 `.scratch/machinery-fee-workflow/prepare-jan-sep.py` 的 `mapping`；第12个i8项目故意独立保留。正式系统↔报表项目仍要按 `history/system.json` 的项目与alias核对，原型索引不承担此契约。

### 正式客户端筛选契约仍缺失

对本effort脚本/原型/证据、backend、docs/reference的定向检索未找到三类 `customServer/getList` 的 `clientfilter/queryfilter` 已保存值或生成器。技术报告只有自然请求参数名，`i8-observed-summary.json`没有原请求体；`i8-lists.json`只有响应规范字段。无法凭当前材料建立经证实的组织筛选、项目筛选或加密筛选请求，不能猜空值、照搬其他端点或把快照回放称实时实现。

可复用的是 `backend/app/mod02_i8/client.py` 的 `I8Client`、`serialize_fetch`，承担当前用户身份、账号隔离Cookie缓存、会话失效一次重登、默认allow_kick=False等；它不生成业务筛选。`sources.py:WH_PARAMS`与 `contract_source.py:CLIENT_FILTER`已持有第四工程公司组织ID `3700000000000014` 的ORG串；`notice_source.py:LIST_FORM`有 `phidOrgList`。这三种均是其他API经过验证的专属契约，不证明customServer支持相同值。`sm2_crypto.py`是登录加密，亦不证明可用来生成customServer筛选。

实施可先完成依赖注入客户端、解析和分页编排的隔离测试，并让缺少已证筛选契约的现场入口明确报未配置；若要正式实时可用，仍须将来获准读取该列表完整请求及组织选择/筛选生成依据，再验证。当前禁止现场请求，不能在本次补证。

## 4. 必须原样保留的冲突

金额以下均为元：

- 沭阳1月：明细27,800，月报采用4,800；2月明细23,000，采用0；3月明细23,000，采用null。`quality`三条，不能按明细初始化覆盖。
- 晋江2月零租：当时报送0，9月年度记录4,850。两者分别保存；最新累计已含4,850。
- 国风8月核实4,500、最终采用5,000、约定下月少做500（下月4,000只是约定）。`issues`为未完成，未取得执行依据；不能按9月总额认定已抵补。
- 龙源9月已有mech_1 = 14,000；本地过程Excel空白不得覆盖。晋江工程公司内租2,283.29、龙源181.42为覆盖候选；慧能本地13,046.1863、表1 14,320.5228、系统0为三方冲突。
- 表4↔本地24个冲突格：晋江14、普康9、大唐1；系统全部与表4一致。160个本地非零／系统0且无列来源是覆盖待核，不能认定系统0为未发生。另4格普康2026-02系统无月行、原报显式0，也要区分无记录和0。
- 灵宝一期、焦作武陟县、广州水泥、广东郁南四历史项目未精确匹配系统/别名，不硬配在建项目。
- 慧能8月同页主行和附属“明细”重复：通用extract 31条450,866.68，已审核选择16条226,933.34；不能再次无选择全量提取。9月慧能目录含国风表、宜化同本不同项目页亦须保留来源判断。
- 结算/审批3单：晋江4,996/5,000；慧能60,499.80/65,000；南平12,816.08/12,816。南平累计0.12与单据-0.08是独立事项。
- 表4旧差额、旧i8快照与当前i8分别保存；晋江旧差24,080恰被当前新增使用覆盖只是观察，不能自动注销历史事项。

六列固定：`mech_0`=工程公司内租（company）；`mech_1`=租赁公司内租（internal）；`mech_2/3`=零租/包月含税；`mech_4/5`=零租/包月不含税。工程公司内租不参加两条核对，租赁公司内租参加第一条。

## 5. 原四页模板与可复用入口

模板原件：`D:/工作/材料/材机报表/9月/第四工程公司9月份外租机械费报表.xlsx`。1—8月同根 `N月/第四工程公司N月份外租机械费报表.xlsx`；本轮只读核存在，未重算、保存或重新证明历史SHA。

四页依次：工程公司汇总表、零租设备月报表、包月外租设备月报、年度汇总。9月原件维度分别A1:O21、A1:Q293、A1:O30、A1:BD92；前三页横向、年度纵向；纸型8/9/9/9。重复表头分别表1第5行、表2/3第4行；现未定义Print_Area或手工分页。真实打印分页仍需实际导出验证。

- 表2 A:P：序号、设备、规格、单位、数量、单价、含税合价、税率、不含税、日期、用途、班组、审核、出租、车牌、备注。不能照旧两页试跑布局多插列。
- 表3 A:M：序号、设备、规格、单位、计划月数、已包月数、单价、含税合价、入场日期、出租、审核、税率/含油、原附加信息；O原有净额公式/缓存列、O4无标题。1—5月M按备注，不能擅改车牌；6月以后仍保留原备注。

已从9月原件ZIP直接回读表头，未启动Excel：表1 A4/B4为序号/项目，C4“开工日期”、E4“开工累计费用（元）”、J4“本月产生费用（元）”、O4备注；第5行 C/D年份/月，E/F/G/H/I零租/包月/周材/租赁公司内租/工程公司内租累计，J/K/L/M/N相应本月数。年度第1行 A项目、B费用、C往年合计，D:O上年1—12月，P:AA为2026年真实Excel日期序列46023至46357，AB合计、AC总班组使用、AD i6、AE i8、AF表头空、AG信息化消耗结算；AH:BD还保留2023/2024历史列（含数值2023.1/2024.1表示10月的已知旧表写法）。不能把同名“1月”跨年度合并。

未生成原生行列截图；已有原型PNG是网页视觉证据，不能充作Excel排版/分页验收。上述原文件可供主Agent在隔离导出后实际渲染核对。

复用入口与边界：

1. `backend/app/mod06_proc/mech_report.py`：`read_months(data, selected)`、`available_months(data)`、`read_file(data, ym)`已供现有机械月值导入使用；SUMMARY_FIELDS不写mech_0，历史净额不倒算。复用金额含义与预览机制，保留原入口。
2. `skills/machinery-fee-consolidation/scripts/extract_reports.py --plan ... --output ...`：计划period、显式sheets[{path,sheet,project,kind,reason,exclude_rows}]；保留fields/raw_cells/tax/source。只提取已审核页，不决定权威版本或主行/附属行；xls没有BIFF公式读取。
3. `skills/machinery-fee-consolidation/scripts/apply_template_edits.py --plan ... --output ...`：模板SHA及sources SHA校验、输出拒覆盖、只改第2/3页且仅已有第5行后单元格，保护其他ZIP成员；支持number/text/formula_cache。**它不是完整新月生成器**，不插行、不修改汇总/年度、不重建公式范围、不做计算引擎重算，不能直接满足TAIL-355全部验收。
4. `.scratch/machinery-fee-workflow/prepare-jan-sep.py`记录seed来源映射；`interaction-prototype.html`中 `cumulative/appliedDelta/catSum/netOf`提供展示契约参考。仅检查文本；未运行这些会覆盖证据/原型的构建脚本。

完成核对边界：无i8请求、无业务库访问、无Git操作、无源文件保存；只新增本件。正式接口、初始化预览、业务持久化和四页导出由主Agent实施并隔离验证。
