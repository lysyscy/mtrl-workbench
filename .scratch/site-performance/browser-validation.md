# TAIL-465 live 批次：两版冻结工作树真实副本浏览器验证

批次 2026-11-03 05:03–06:45，主控授予唯一 preview/真实副本/浏览器窗口，执行者 dsh-tail465。
未启动正式 8000、未写源库、未外部 i8、未改冻结源码、未 git add/commit/push。

本文保留05:03–06:45批次原结果。其后首显修复及最终验收见[首显交接](readiness-handoff.md)、[build-08终验](readiness-final.md)和[收敛结果](completion.md)。浏览器ResourceTiming记录的字节是`transferSize`（含响应头及编码后的正文，缓存可为0）；它与直接读回JSON的解码字节数不同。特别是§9的36832→961B为传输计数，360598→661B为该次直接JSON读取，早期TAIL-471探针382081→3102B属于另一个选中对象样本，不混为同一次测量。

## 1. 版本与固定条件

| 项 | baseline | candidate |
|---|---|---|
| 冻结工作树 | `var/worktrees/site-performance-base-20261103` | `var/worktrees/site-performance-check-20261103` |
| commit | `3c5712ed79d7790e818f5b2476e44fef971c6b73` | `78c79c8abfd94507e194a348a77cb212bbb2329c` |
| run / build | `base-run` / `work/build-01` | `check-run` / `work/build-02`（本轮新准备） |
| index_sha256 | `b161ce3e63e077ca36fe132054f5812d683e623abbaaad4e2c0d80bfaef8f1e4` | `0400d38977313857abf59fe2cf74975b0b171fcf6aff375ff5e8a357727bdc16` |
| product_digest | `ca738d626531f2261231264804da64e361da1db0f35a68ed49746eb8954423c3` | `1fc5dd9a1e40c67481be05fad8e9d542c64a6c4c7679c846048b947530c08eff` |
| frontend_sources / files | 115 输入 / 39 产物 | 同（逐产物 sha256 经 `verify_build` 通过） |
| pnpm / revision | 声明 pnpm@12.15.0，实际 12.15.0 / `mechauto261028` | 同 |

3c到78的前端源码差异为5个：`apps/frontend/src/process.tsx`、`contracts.tsx`、`settlement-api.ts`、`flow-api.ts`、`notice-flows.tsx`；旧prepare批次3c到867仅3个，不能混用。
副本输入指纹先核后测：两版 `logs/preview-copy-verification.json` 各 37 表逐表 rows+sha256 **0 差异**
（`inv_detail` 18287、`setl_detail` 1839、`proc_mech_import_change` 324、`user_account` 2 行）。
采集条件 1920×1080、`--fscale`=1.12、默认主题、zh-CN、Asia/Shanghai；`preview-admin` 仅在**本轮自建 disposable 副本**内
`POST /api/m15/ui-scale {"ui_scale":"large"}`，每次结束还原 standard（已核 `GET /api/m15/theme` 为 standard），未触碰真实/既有试用账号。
两版**顺序**执行（baseline 全采 → `--stop` → candidate 同参数），非并发。

## 2. 实际命令与退出码

启动（各自工作树内，源 `.env` 只由工具内存读）：
`D:/dev/mtrl-workbench/backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --source-env D:/dev/mtrl-workbench/.env --run .artifacts/active/site-performance-tail465-20261103/<base-run|check-run> --copy-source --disposable --port 8065`
停止 `... --stop --run <run>`；candidate 构建 `... --prepare-build .../check-run/work/build-02` → `CANDIDATE_BUILD02_EXIT=0`（`✓ built in 1.67s`）。
采集脚本（受管 group `site-performance-tail465-20261103`，均经 `artifact_lifecycle.py lease` 包裹）：`tail465-preview-ab.py`（465）、
`tail465-pages.py`（15 页）、`tail465-domain.py`（471/468/469/470）、`tail465-big.py`（470 专项）、`tail465-inventory.py`（466）、`tail465-notices.py`（通知书首进）。
pytest：`cd <worktree> && export PYTHONPATH="<wt>;<wt>/apps/frontend/tests" PYTHONDONTWRITEBYTECODE=1 && <venv>/python.exe -B -X utf8 -m pytest -p no:cacheprovider -o addopts= <nodes>`
退出码：`AB_BASE=0`、`AB_CAND=0`、`PAGES_BASE=0`、`BASE_OTHER2=0`、`DOMAIN_BASE=0`、`DOMAIN_CAND=0`、`BIG_BASE=0`、`BIG_CAND=0`、
`INV_BASE=0`、`INV_CAND=0`、`NOTICES_BASE=0`、`PAGES_CAND_OTHER=0`、`STOP_BASE=0`、`STOP_CAND=0`；
`PAGES_CAND_DOMAIN=2`、`BASE_DOM7=2`（唯一错误均为 notices 超时，见 §11）；candidate pytest `2 failed, 8 passed` + `1 passed` + `5 passed`。

## 3. 465 过程资料：首显 / 切项目 / 输入保存（同脚本同参数，4+4+3 轮）

| 指标 | baseline | candidate |
|---|---|---|
| firstDisplayMedianMs | 576.05（554.7/597.4/823.1/546.6） | 626.55 |
| 首显 layoutTiming | 全 `measured:0, reused:true, rows:14, width:1739` | 全同 |
| projectSwitchMedianMs | 4649.7 | 3862.4 |
| measuredPerStep | `[0,0,0,0,112,336,368,336,0,0,0]` | `[0,0,0,0,201,134,201,134,0,0,0]` |
| prepareMsPerStep | `[0,0,0,0,672.1,1770.2,1840.1,1729.2,0,0,0]` | `[0,0,0,0,1075.6,1166.5,1200.1,1092.7,0,0,0]` |
| fontsWaitMsPerStep | ≤0.9 | ≤1.4 |
| 切项目期间 `/api/` 请求 | 0/0/0/0 | 0/0/0/0 |
| 击键 ready_ms | 3397.5 / 3221.4 / 3078.2 | 3016.2 / 3471.1 / 2952.0 |

阶段分离（同源同参数）：
- **首显**：两版都走 `apps/frontend/src/grid-layout.ts:105-110` 复用分支（`reused:true, measured:0`），`prepareMs`=0、字体等待 0.6ms 级
  ⇒ 此场景没有进入465改动的重测分支；576→627ms仅为本批观察，样本不足以建立噪声带，不作收益/回归结论。
- **切项目**（唯一真正重测量路径），同项目对比以消除轮次与项目交替耦合：
  广东茂名 id244 measured 368→201（−45.4%）、prepare 1840.1→1200.1ms（−34.8%）；新疆普康 id3 measured 336→134（−60.1%）、prepare 1770.2→1166.5ms（−34.1%）；
  4 轮 prepare 合计 6011.6→4534.9ms（−24.6%）。
- **单格成本未下降**：prepare/measured 每格 5.0–5.3ms（base）vs 6.0–8.7ms（cand）；收益来自**待测格数下降**，
  `prepareMs` 含 flushSync portal 提交与行高应用，本轮不据它推断单格经济性。
- **signature 阶段**（离线 probe5，非浏览器）：0.7456→0.1239ms（6.0×）、观测字节 73264→4671；8000 格测量格 8000→4559（1.755×）。
  浏览器内同视图 key 集 `baselineKeys 260 → candidateKeys 96`、批次 `3 → 1`（`ab` 快照，两版 rows 16 / cells 260 相同）。
- **DOM/portal** 阶段未被消除，只被减少（批次 3→1）；字体等待两版 ≤1.4ms，不是瓶颈。
- **业务等值**：11 个快照（4 首显 + 4 切项目 + 3 击键）逐格比较 `(column,text,input,marker,weight)`，
  `per-snapshot equal=[True×11]`；行 `[16,16,16,16,21×7]`、格 `[260,260,260,260,345×7]` 两版一致
  ⇒ 完整金额/分组/固定合计/长文/错误标记/输入框内容逐格未变。

## 4. 464 过程接口投影（不扩成机械明细工作台全测）

`/api/m06/mech-screen` **93288B / 379.9ms**（`count=205`、`columns=6`、`sections` 16 仓、`sources` 16 仓、`detail_signatures=9`）
vs `/api/m06/matrix` **465795B / 929.6ms**；**逐格等值 205×6=1230 格与 `matrix[wh].raw` 同 ym 的 `mech_0..5` 比较 mismatches=0**（null 归一 0.0）。
保存后权威回读/history 由既有真实副本节点覆盖（§9 process 5 条含保存读回、unknown 回执、后续草稿）。

## 5. 466 库存：零 HTTP 本地筛选与合计

默认月 2026-10 = 0 行（`0 / 18287 行`，`noRowsTemplate=当前筛选条件下没有库存单据`）；`/api/m08/inventory` 恒返 **18287 行 / 1722125B**，
前端 `apps/frontend/src/inventory-api.ts:64-66` `coarseRows` 本地筛。切 2026-01 后两版逐字相同：`newApiRequests=0`、`newApis=[]`，
rows 0→10、cells 0→209、`pinned=1`、`pinnedText=['合计918,700.2333,625,954.6637,916,105.64']`、`moneySample=['120.00','4.17','4.17','500.00','','500.00']`。
首进 ready 5089.4（base）/4851.0（cand）。**未验**：`.inventory-grid .ag-body-viewport` 未命中，单据定位只由行数+合计行支持。

## 6. 467 欠款 / 逐月台账

页面：欠款 29 行 201 格 / 8195B；付款流水 2 行 27 格 / 40241B（两版一致）。API：`/api/m05/debt` 19495B / 133.8ms，
`total='19360115.44'`，`by_category` 辅材 2089175.20 + 机械 3338643.58 + 集采 13932296.66 = **内部精确自洽**，`mech_settle_ready=True`；
`/api/m05/ledger?project_id=1` 17336B / 857.6ms（缺参 422），`sides` 辅材 12 行 / 机械 14 行，`historical_cutoff='2025-11'`，
辅材 2026-10 `debt=128471.00`、`sum=350791.00`。**口径声明**：debt 是跨类别当前欠款快照，ledger 是单项目逐月双侧台账（含 opening/token/editable），
两者不逐值对齐；本批只证「同源读取连通、各自内部自洽」。

## 7. 468 集采台账：勾选 / 全选 / 搜索后勾选 / 贸易列 / 手调宽

两版 rows 18 / cells 361 / 18 列表头 / `moneyCount=95` 一致；`filterCount='已勾选 1 行 ｜ 显示 79 条'`。

| 步骤 | baseline | candidate |
|---|---|---|
| 全选到下一帧 | 657.6ms | **330.5ms（−49.7%）** |
| 搜索后勾选一帧 | 464.0ms | **176.3ms（−62.0%）** |
| afterSelectAll | `{headChecked:true,rowChecked:18,rowBoxes:18}` | 同 |
| afterSearchPick | `{headChecked:false,rowChecked:1}` | 同 |
| widthsStableOnSelect / widthsChanged | `true` / `[]` | `true` / `[]` |
| 贸易列 before→after | `[]→[trade_co,trade_contract_amt,trade_inv_sum]` | 同（文案「隐藏贸易公司列」） |

`widthsChanged=[]` 只证明勾选后列几何未跳动，不能证明baseline没有执行测宽。330.5/176.3ms 是选择提交到下一帧的当次实测，
非canvas桩或单独测宽耗时；测宽调用减少另由源码依赖及离线计数证明。手调宽恢复由既有真实副本节点覆盖（§9）。

## 8. 469 收发结存与提取 / 470 月度会大表

469：settlement ready 3891.5/3952.6，9 行 70 格，7 列表头一致；选 2026-09 后 `/api/m07/settlement?period=2026-09` 925B
（默认 2026-10 为 397B/0 行，属数据分布非缺陷）。本域成品：月报 `第四工程公司2026年9月收发结存表.zip` **254430B/254403B**；
提取 `/api/m07/extract-screen?year=2026&status=在建` **1618B**（确认 469 新端点），三网格 9/10/9 行，
下载 `焊材气体提取表_2026年12月.xlsx` **14497B/14495B**。等值：`extract-screen` 4655B（`annual/balances`）vs 完整 `/api/m07/extract` 9052B
（含 `amounts/annual_totals/kinds`），`annual`、`balances` 逐值相等 True，screen仅保留full的这两键，导出与既有脚本仍走完整出口。

470：big ready 2350.8/1971.7，9 行 200 格，8 列表头一致，`count='9 个项目'`；切月 `switchMs` 2706.1/2728.8（`?period=2026-08` 1998B），
保活 `backMs` 620.0/2049.5（噪声，两版均命中缓存仍发一次请求）；`month_kept='big-month'`、`input_values=['','','']`、
`col_widths=[['seq',45],['display',52],['open_ym',76],['hw_cum',90]]` 两版一致；手调宽 `note` 93→149 切月后与离开返回后均保持
（`localStorage` 键 `mtrl:grid-widths:v1:["3:preview-admin","monthly-big"]`）。草稿语义实测：未 blur 后离开再回输入框仍保留，服务端 `manual` 该格仍 null。
成品 `经济活动分析大表_2026年8月.xlsx` **9405B/9406B**。`keptScroll/backScroll=null`：`apps/frontend/src/big.tsx:154` 用 `domLayout:'autoHeight'`，
该页无网格内滚动容器 ⇒ 滚动保持无法经此路径验证，如实记为未验，未改源码。

## 9. 471 通知书流水弹窗与付款预览 + 真实副本 pytest

471 两版：notices ready 3246.2/3083.0，18 行 342 格 17 列；点「查看流水」`flowsDialogMs` 1485.6/1445.1。
**请求差异即本票范围内下推的直接证据**：baseline `GET /api/m05/flows?year_month=` **36832B**（全量后客户端过滤）→
candidate `GET /api/m05/flows?notice_id=1186` **961B（−97.4%）**；弹窗标题 `FKTZS2026101521，付款流水`、8 列表头、
行文本 `FL20261027170556065A 生效 2026-10-27 20,000.00 现汇 — 陈书曼 —` **两版完全相同**（same title/rows/grid 全 True），撤销原因列可见（空值 `—`）。
付款预览（只读连通，**未付款**）：勾 1 行→「付款（1 条）」→`openMs` 2553.3/2611.9；`/api/m03/payment-preview?ids=1235` 957B +
`/api/m03/payment-context` 452B；标题「批量付款」，含「不可付原因」列，行 `FKTZS2026102316 晋江污泥项目 未批 43,090.00 0.00 43,090.00 现汇 审批状态「未批」非「已批」`，
合计 43,090.00；`closed=true, submitted=false`（只点取消）。等值：`flows?notice_id=1186` 1 行/661B 与 `flows?year_month=` 512 行/360598B 客户端过滤结果完全相等 True。

pytest（candidate 工作树，真实副本）：主批 `2 failed, 8 passed in 199.81s`；补充 `1 passed, 3 deselected in 20.43s` + `5 passed, 5 deselected in 83.10s`。
上述原始pytest回执累计14项通过；主要代表涵盖process的raw/adjusted、分组、回车保存、后续草稿与unknown保护，contracts搜索/行内读回/手调窄列保存，
inventory本地筛选，settlement提取年度状态与首帧，以及合同点击和原生拖宽跨重载；完整node及分类以各次原日志为准，不据本段概述重复计数。
**2 条失败均「默认月无数据」既有数据前提**：`test_settlement.py:10`（2026-10 为 0 行，真实副本仅 2026-09 有 9 行）、`test_inventory.py:66`（默认月 0 行）。
两版 `default_month` 代码 `git diff 3c5712ed 78c79c8a` 为空 ⇒ 与本票改动无关，未改断言、未包装成通过。

## 10. 其余 7 页与业务域页（只读首进 / 保活返回）

热态重测修掉早前 baseline 冷启动伪影（曾报 773.3 vs 1884.9）：首页 1654.8/1402.2、项目档案 3020.1/2973.8、i8 1839.3/1771.2、
特殊费用 2366.4/1779.6、规则配置 2417.5/2449.4、用户管理 1803.0/1899.9、机械费 2663.7/2934.5、
项目档案·保活 1817.3/1833.8、机械费·保活 2082.5/2068.0（base/cand ready ms）；**readyMedian 2082.5 vs 1899.9**。
两版 `errors:[]`、`emptyPages=['home']`，逐页 api/bytes/rows/cells 完全一致（项目档案 4/3287B 20行196格、机械费 2/79504B 10行150格等）
⇒ 保留各页实际读数；本轮样本不足以建立噪声带或证明统计意义下无回归，不由单一路由收益外推15页。
业务域页（base `tail465-pages-baseline-domain7.json` vs cand `-domain.json`，均热态 ready ms）：process 3950.5/3927.2、
inventory 5619.9/6282.4、debt 3011.5/2834.7、ledger 2146.7/2131.2、contracts 2281.3/2299.1、settlement 2796.4/2855.5、big 2349.0/2012.7、
process·保活 3115.1/2700.9、contracts·保活 2315.2/2209.1；行/格/字节逐页一致，最长长任务 75–423ms 两版同带。
完整逐页清单见 `.scratch/site-performance/browser-15page-matrix.md`（本批素材，供 472 收敛，不改票状态）。

## 11. 失败、未验与既有缺陷（如实）

1. **付款通知书首进卡死（既有缺陷，两版同因，非本票改动）**：`tail465-notices.py` 复现——`首页→付款通知书` ready **1208.6ms**；
   `项目档案→付款通知书` **20081.6ms 超时**，此时 `.page-view` 有 `inert`、`visibility:hidden`、`.page-loading='正在读取付款通知书…'`、
   `[data-page-loading]` 同文本。与 `tail465-pages.py` 的 `notices:TimeoutError` 一致（`PAGES_CAND_DOMAIN=2`、`BASE_DOM7=2` 唯一错误）。
   已排除：字体全部 resolve、无 pending request、无 pageerror、chunk 均 200、强制 DOM 变更与改 viewport 无效、从首页再进即 ready。
   本批只缩小到「保留页 + 惰性 chunk」组合，尚未确定根因，未改冻结源码。后续隔离证明为保留页归零尺寸引发AG布局自旋，并非字体准备本身；见首显交接。无节流不稳定，4× CPU节流为确定性红入口，build-08已补针对性绿证。
2. 466 单据定位未命中滚动容器 → 未完全验证。3. 470 网格内滚动保持不可验（autoHeight）。4. 469 `hasField=0` 探测为 0 但实际点选可用（925B 请求可证）。
5. 两版 pytest 各 2 条默认月无数据失败（§9），非缺陷、不计通过。6. 页面为单轮顺序采集，中位数只作同环境对照，不作跨日基线。
7. 本批 ready/`prepareMs`/`longtask`/选择帧均为**浏览器实测代理指标，不是 INP**，也不代表生产全页提升；
   `frontend_measure.py` 只读门（`tools/dev/frontend_measure.py:210-217`）未被绕过或改写，屏幕阶段漏斗仍不可用（见 `preview-preparation.md` §4）。

## 12. 资源退出与证据去向

两版均 `--stop`（`STOP_BASE_EXIT=0`、`STOP_CAND_EXIT=0`），日志尾 `应用停止` + `ISOLATION cleaned schema=...`。
核验：`var/state/react-writable-preview/current.json` 不存在；`:8065` LISTENING 计数 **0**（仅 TIME_WAIT/FIN_WAIT_1）；
两 `reports/real_owner.json` 均 `status='stopped-disposable'`、`disposable=True`、`preserve_schema_on_stop=False`（schema 已 drop）。
正式 8000 未操作；两冻结工作树 `git status --porcelain` 为空、HEAD 未变；Junction 未进入删除；`preview-admin` 已还原 standard。
证据全在受管 group `site-performance-tail465-20261103`（owner `dsh-tail465`，state=active，待主控判 close/hold）：
`files/` 8 个采集脚本 + 6 个 probe `.mjs`；`files/reports/` 22 个 JSON；`files/screenshots/` 134 个文件（67 组 png+json）。
未归档：源 `.env`、DSN、cookie/token、账号凭据、两 run 私有目录整体。active build 与两工作树保留给主控退出。
