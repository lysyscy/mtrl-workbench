# 油卡管理接续

<!-- OILCARD-HANDOFF-BEGIN PH-20261031-oilcard-02 -->

## 交接登记

- 编号：PH-20261031-oilcard-02。
- 源对话：01a18f5d-d023-7661-99ca-e35eb7963a16。
- 项目：D:\dev\mtrl-workbench，同一原目录接续。
- 用户已确认：收完当前TAIL-457、核验并保存后自动新建对话，继续剩余开发。
- 接手对话：01a19021-8c69-7053-a749-65fc1cb7b4bd（hostId=local）。
- 状态：本接续开发范围已完成。2026-10-31源对话登记并推送c5510c57后由本对话接手，从458持续完成至463及最终累计双轴审查；源码/证据正常推送，真实业务接续及正式加载未执行。
- 修改权：接手对话01a19021-8c69-7053-a749-65fc1cb7b4bd持有；源对话只观察，不再改业务文件或交接正文。
- 运行核对：接手方因当前权限限制未独立重验端口；源对话已直接核457 stop退出0、schema清理及owner stopped-disposable，必要时按项目入口再核，不盲目操作8000/8801。

## 目标、版本与进度

完成已批准的TAIL-453～TAIL-463开发、隔离验证及最终累计审查。总票TAIL-452保持不动，不新增依赖或逐批审批点。各原票持有当前状态；执行批次只是建议。

- 分支：codex/oilcard-management-20261031；累计基点e296e816ed13a05e7572bae6bc6e88fb5a3dda66。起点尚含未提交规格/原型，最终范围不能假定HEAD已含全部目标文件。
- 453～458技术验证、保存并done；证据在本目录evidence/TAIL-453.md至TAIL-458.md。458源码及证据450d8e80、状态b2dbc55c已正常推送，远端HEAD b2dbc55c68df97c6cbaca2c967fa29b1fca5b971已核一致。先前自动审批拦截已由用户明确答复“允许正常推送”解决，授权目的地为lysyscy/mtrl-workbench的codex/oilcard-management-20261031分支，范围为本次已批准油卡开发的代码、测试及验证文档。
- 458的34项后端及最终受影响14项、4项前端、正式构建、PG原件恢复、IAB收票/去重/冲突/独立双表/刷新与实际文件下载通过；自有预览schema已退出。457共享history顺序缺陷已有有效回归，不再是待修缺项。
- 453～463均技术验收、保存推送并done。460源码646d64a1、459源码84daeead、461源码60a8deb1、462源码b1d3957c、463源码66bb4d30均核远端一致，证据见各evidence原文件。累计Standards/Spec独立双轴审查已闭环：Standards0，Spec1个P1已修、未关闭0，详见evidence/final-review.md。
- 接手从458持续推进剩余票，既有完成票的有效证据继续复用。

## 恢复入口与下一步

先核AGENTS.md、CONTRIBUTING.md、分支/工作树、本交接编号和原票。目标读[spec](spec.md)、[当前需求](../../docs/requirements/oil-cards.md)及[map](map.md)。原票在.scratch/tails/issues；原依赖为453→454，454→455/456/457，455→458，458→459/460，456→461→462，457/460/462→463。

本次开发无剩余实施票。463保留原标记及稳定来源身份，缺票号/日期留待核，已有PDF只补关联不重复记金额；170项核对工作簿在463本机忽略run/outputs/本对话ID/油卡接续核对.xlsx，309真实来源证据全待确认，未正式入账。后续先由用户核期间/归属/旧总额，真实接续与正式加载各按当次授权，不自动继续。每票源码及证据先保存推送再关闭；累计审查包含原基点后全部提交、未提交与新增内容，已排除他人工作。

## 有效决定及授权边界

- 充值、调整、转入转出统一一个金额；开票另列，不扣减充值。报表用需求正文现行月度/累计公式，不恢复净充值和纯平账两套口径；消费流水不在范围内。
- 实体卡、当前账户关联和每笔核算快照分开；同卡可有多账户，主卡只作信息不计金额。换卡保留旧卡和旧账，录错另作更正；主卡、账户、账务备注独立。
- 左右两表均分且筛选、排序、选择、滚动、合计独立，不加临时展开。沿现有AG Grid/Ant Design和付款通知书适配方式，优先复用成熟实现。
- 共用筛选按列配置，不绑定油卡字段、API或金额公式；充值已接，发票需实际复用，不做全站推广。筛选即时，空选及取消最后项为全部；日期年/月/日复选并容文字/空白，无起止日期；金额仅数值候选和排序。仅此项/清除关闭浮层，其他列条件保留。合计随本表筛选，台账导出全量已保存数据。
- 转账为独立次级按钮；正数录入、转出负/转入正、类型固定。金额和日期双边更正，归属/备注单侧更正，全局HistoryControls整笔撤销/重做。普通保存静默自动，未知结果可靠核对后续办。
- 用户已停止Ego Lite；后续仅用Codex内置浏览器，任何Ego CLI/任务空间接口都不调用。此前453～455证据仍有效；浏览器句柄不能跨对话复用。
- Uiverse仅作为有收益的局部样式参考，用户未要求替换现有功能控件或重做已验页面。
- 授权为开发、专用隔离验证及正常保存。生产业务写入、真实初始导入、生产迁移/部署、i8及外部开票均未授权。463只做来源核对和专用副本演练，未知期初截至月、归属和旧总额不得猜配。

## 输入、原件及资源

- 原台账：D:\工作\材料\台账\油卡\外租机械加油汇总清单（第四工程公司）.xlsx；只取油卡、油卡充值、油卡开票、转账四张活动表，排除存档及临时核对区。详见[research](research.md)。原件不修改、不提交Git。
- PDF及旧脚本在同级开票目录；旧处理脚本会重命名原件，只借鉴流程，不对原件直接运行。float金额、当前映射及备注末个长数字不能照搬为可靠入账规则。
- 代表PDF：开票/20260916/237 慧能 56997.84.pdf有完整卡号，也含银行账号；开票/2025/20251016/大连.pdf只有短卡尾号，应待确认。pypdf已声明并锁定6.21.4。已有PDF接续优先补关联，不重复记金额；永久原件已在数据库bytea随台账备份，不能借临时缓存。
- 459完整私有输入仅在忽略文件.artifacts/active/oilcard-implementation/20261031-459/work/delivery-input.json。当前聊天人类已直接确认“允许本次隔离下载测试”：令牌回送https://invoice.sinopec.com/api/invoice-digital-download-cos/delivery/getInvoiceDetail并按返回地址下载PDF，仅专用隔离验证；原件及完整链接/token不提交Git、不写正式账务。新批次API实链专项通过（组133606-586725-25880，PDF65864字节与基线相同、跨批次下载仅1次）；实际IAB混合结果、跨批次重复、重载、旧批次、发票定位及上传/下载通过，原件逐字节一致。最终预览PID25964/revision oil459261031/schema frontend_rewrite_397_5aa399e7c9124ef78899fcd81dbe10a7正常stop退出0并cleaned，标签已关/视口已重置。
- 463只读准备在.artifacts/active/oilcard-implementation/20261031-463/reports：source-inventory/source-rows-private/pdf-facts-private/legacy-totals/project-candidates-private。29唯一完整卡、49充值1414851.25、101开票1126037.70、7转账、65PDF哈希未变；21PDF可靠识别，23份有唯一同卡日期金额候选但均未确认关联。源库revision mechauto261028，27费用项/52月值，7个工程用油名称候选共18月值，均未认定业务身份；大表旧oil非空0条。24个源归属名称仅6个有唯一精确名称候选，未据此确认或入账。待463实施时核输入变化并续用证据。
- 456及457自有8065预览均已stop并清schema。457 PID37268、schema frontend_rewrite_397_c14318e3b82341ed8437f5aa5af20c39、revision oil457261031、stopped-disposable；本地证据在.artifacts/active/oilcard-implementation/20261031-457/reports。后续构建完成才启动，核源、构建和目标schema一致。
- 458及460自有预览也已停并清schema；460最终PID22764、schema frontend_rewrite_397_bbda716cc5a543dd9dd7190344f1472d、revision oil460261031，owner stopped-disposable且已只读确认schema不存在。即时作废/撤销/重做及红冲标签无需刷新复验通过。
- 461两预览已正常stop/cleaned；最终PID34556/revision oil461261031/schema frontend_rewrite_397_7c5e06f94b24415c90fedfe6b2173d4d。实际UI十月10250及备注重载、十一月不沿用、负数撤销/重做、原费用只读和实际九月三表Excel10250/排除十月通过；源码冻结后补回执检查导致初始副本退出重建，最终仅build-02用于验收。证据在461/reports。
- 462预览PID28288/revision oil462261031/schema frontend_rewrite_397_3cfe89e90a4247d4bebeaf039f1e8683正常stop退出0并cleaned，标签关闭/视口重置；源码b1d3957c。实际GUI及下载证据在462/reports；原件未改，未接续真实旧数据。
- 463首轮PID31508/schema frontend_rewrite_397_c014df19808c4160a13ee630db34fe68及最终PID35924/schema frontend_rewrite_397_4f8fc879d6524a899b4b8cfe65b13f42均revision oil463261031，正常stop退出0/cleaned，标签关闭、视口重置。合成接续两次重跑、公司15670/10000/5670、旧费12000/大表13000及11月17900、实际三Excel通过；独立审查修复后实际无PDF读取/右键/补档核对/下载同字节通过。人工原件核对后来源重跑拒绝覆盖现值，真实309证据仍全pending。证据在463与463-final/reports，见evidence/TAIL-463.md。
- 8000为其他在用服务，8801为仍保留的用户原型，不因交接清理或接管；原型owner在.artifacts/active/oilcard-interaction/20261030-dsh/reports/owner.json，需用时重核。
- 保护docs/guides/frontend-design.md改动及未跟踪.impeccable/、.tmp-fees-width.py、DESIGN.md、PRODUCT.md、debug.log；不全量暂存、reset、clean或stash。
- 总票452基准SHA256：a1d9e8c048f77fff041fee3333235ca956c7ea42aa2e457dd43a753930b47290。

<!-- OILCARD-HANDOFF-END PH-20261031-oilcard-02 -->
