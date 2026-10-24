# 当前活动工作

## React 前端独立重做

唯一React分支codex/react-frontend-rewrite（生产master另置，未合并）。2026-10-24用户人工验收落地：原ready-for-human 11票（398、400–409）按票协议签done，验收对象为8060真实只读副本，各票Comments留依据；397/399原done，411 wontfix。同日419规则配置页经用户验收签done（实施、隔离技术验证与实看证据在其票Comments）。同日分支收拢：五条付款分支核实为master祖先后删除（提交仍由master保有），tail-415候选7个独有提交由tag `archive/codex-tail-415-candidate`归档后删分支及其干净worktree；未推送、未上线。

**票务导航。** 活动票：410、412–415、417、418、420实施已有但缺真实写链/权限/文件链验证；421前置已满足、未实施；422累计验收；423/424需独立授权。419、416已按代验收授权签done（证据在各票Comments）。逐票Status/验收/依据归`.scratch/tails/issues/`，列票用仓根`backend/.venv/Scripts/python.exe -X utf8 tools/oneoff/_list_tails.py`；协议回[票协议](agents/issue-tracker.md)，范围/48故事归[共同规格](../.scratch/frontend-vue-rewrite/spec.md)，A–E技术回执指针在各票Comments。技术完成不代签done，缺验证留原票。

**工作树保留件。** 8件dirty保持原字节、不得以HEAD覆盖：性能C在途六源码`apps/frontend/src/{flow,notice-payment,notices}.tsx`、`backend/app/mod03_notice/{list_data,list_view,notice_api_router}.py`，及旧协调资料`.scratch/frontend-vue-rewrite/{evidence,handoff}.md`。恢复依据在task-22 `archive/react-final-handoff/run-01/`（75件原字节/哈希与`reports/final-state.json`）及task-13 `component-coverage/recovery/{baseline.json,baseline.patch}`（task-N均在`D:/UserData/Documents/Codex/2026-10-24/`）。性能收口与同条件新旧比较归422，保留不阻止其他有界后续工作。

**8060与恢复。** 当前`react-c-preview-e-v6-8f1204a8f9f5-real-copy`保留运行、不重启：真实库隔离只读副本，独立schema `frontend_rewrite_397_68b8838c875e4985a8656faeaca9b205`，PG强只读＋精确GET白名单，业务写/导出/旧/app被403屏障。在用run为task-19 `react-e-fit/run-01`（`exports/build-e6`，身份`reports/real_owner.json`）；仅当获服务恢复授权且进程确实退出时，用项目venv按同schema运行其`work/resume_real_preview_e6.py`恢复，不用普通启动器新建/复制schema。E视觉回执同run `reports/delivery.md`：九项目1440×900、20列1186/1186px金额全显，1438宽差1px，旧/app像素403未验；不能替代422累计。

**已定事项与下一步。** C为全站方向（10主题/4字号、语义危险色、旧版有效布局/工具顺序；窄屏/大字号以完整金额与操作可达为底线）；费用年度按原项名汇总不物理合并；409已恢复、411撤销，旧八尾工339/340/344–349不复活；通用导入/旧机械Excel不迁（408仅JSON）；i8页不动、Excel式筛选取消；React/MiniApp的425重号由422正式集成核身份；发号高水位434。**用户2026-10-24授权代验收**：剩余票由会话agent完成实施＋隔离技术验证后直接签done，票内注明"agent按用户授权代验收＋证据＋未验边界"；用户改在422累计关口以可运行预览做一次全站人工复核；金额/权限现场项、真实外部动作授权门不变。下一步（本对话串行推进，416/419已完成）：420→验证批（410、412–415、417、418）→421→422累计→425最后工程清理→另获423正式切换授权→日常确认后另获424退役授权。真实i8、付款外发、物理打印、生产写入仍按每次明确授权。

原外部交接PH-20261024-react-final-01与状态票图已于2026-10-24按用户指示退役：持久事实吸收进本页与票仓，原件删除；票仓与`_list_tails.py`为唯一状态源。

## Mini App 付款原表核对台

主线[固定规格及七票](https://github.com/lysyscy/mtrl-workbench/blob/e55ff04822c78338d130e0fd914835ce60deaa2b/.scratch/miniapp-payment-plan-audit/spec.md)已确认、尚未实施；原身份、依赖、验收及授权由主线持有，本分支未复制其票仓。核对口径归 skills/payment-plan-audit；真实拟方式回写、会话与宿主边界按原规格，建票/文档同步不代表实施或真实回写授权。

单票真实依据直接查原文件或 tools/oneoff/_list_tails.py；本页不复制票表、排期或历史关闭计数。当前服务配置/加载按[部署](guides/deployment.md)现场核实。

## 机械费现有具体跟进

Git基点94c0021的机械费history-contract/evidence保有国风8月核实4500、采用5000和约定下月少做500的分别依据；下月4000只是约定，未取得执行证明，不能按9月项目总额自动核销。该事实沿现有机械费跟进事项处理，本轮未读取或改写真实数据库；不将个案金额设为普遍规则。
