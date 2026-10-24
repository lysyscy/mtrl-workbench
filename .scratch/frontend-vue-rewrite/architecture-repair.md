# 架构审查修复回执

2026-10-25用户授权直接修复，技术方案由Agent安排。输入为临时报告`architecture-review-20261025-073421.html`；固定源码基点`d0b1496f90310fc3112839ba6e91f628340d5339`，工作分支`codex/react-frontend-rewrite`。

## 本阶段完成

1. `tests/preview_select.py`集中当前antd弹层、精确文本/复合标签匹配、虚拟滚动及候选重读关闭弹层后的有限重开。库存、收发结存、过程、大表、合同、发票、导出和外观测试复用。报告提到的ledger已无antd调用，保留原实现；外观测试则补入统一范围。
2. `tests/conftest.py`的`make_preview_seed`统一`MTRL_PREVIEW_TEST_BUILD`；11个模块原有接线归入共享默认/工厂，业务造数原样保留。三份Session的测试库/schema断言及engine释放收进`preview_session`，子进程造数形式继续保留。
3. `main.tsx`的`pages`统一派生导航、标题、路由、懒加载和已访问页面保活。账号树/QueryClient、离页blocked/active与台账/机械特殊props仍保留。新增公共回归逐页进入13个入口并核同账号状态保留及账号失效重建。

架构与预览指南同步更新。自查覆盖上述调用者、夹具和导出入口；采用定向浏览器验证与原业务载荷比对，未启动累计独立双轴审查（归422）。8件保护dirty开工/收尾SHA256完全一致，未纳入本次提交。未改变8060在用资源、未操作真实i8/打印/业务写入或生产服务。

## 验证与实际边界

- `corepack pnpm typecheck`退出0；独立目录生产构建退出0（原有大chunk及运行时theme URL提示保留）。现有测试初次收集109条，新增注册表回归后最终收集以pytest为准。
- 主批25条：16通过、9失败（443.75s）。其中7条停在修复前已经失配的项目搜索/状态、单据时间、旧台账选择项目、机械定位控件；未降低其断言或声称通过。另两条为本次选择器迁移暴露：提取状态标签已修；付款引用保留候选重读后的重开恢复，均最终复验通过。
- 最终标签/注册表批4条全过（40.11s）：注册表、外观、提取状态筛选、未知回执核对。
- 最终共享工具批5条全过（51.78s）：付款引用、库存期间/项目/方向/列筛选、注册表、外观、集采打印版项目顺序和真实文件。各批有重复覆盖，不将数量相加；合计19个不同节点有通过证据，仍有下述7个旧测试未通过。
- 首次主批因工作树`.env`缺测试库配置被守卫拒绝，25个setup error，不记产品测试通过。随后使用主线已有配置中的专用测试库目标，只在随机独占合成schema验证；未复制源库。
- 所有子进程业务造数程序与基点字符串载荷逐项相同；3份直接Session业务体只机械减少缩进，原commit保留。

本机原始日志在`.artifacts/archive/react-architecture/`，沿既有30天保留策略：`074602-733510-27744/logs/validation.log`为环境拦截；`074628-980549-4652/logs/validation.log`为主批；`075104-583713-30508/logs/targeted.log`为新回归定位器修正前失败；`075226-100991-20624/logs/targeted.log`为4条通过；`075459-350562-28640/logs/final-regression.log`为最终5条通过。临时构建、runtime及schema由各自父运行退出清理，自动截图/文件仅留本机证据。

## 422接续项

报告候选4（公共回执/金额请求工具归位）及5（ledger三写出口收敛）按原报告留到422后单独实施，端点校验差异和保护文件兼容re-export要求继续有效。本阶段不启动421/422，也不签正式切换/退役。

7个旧测试的未通过节点（不是产品缺陷结论）：

- `test_shared_controls.py::test_routes_keep_filters_selection_draft_and_refresh_resets`：项目旧名`项目`，当前基点已为`项目搜索`；后续旧控件断言仍需按现行功能逐项核。
- `test_shared_controls.py::test_time_modes_and_modal_discard_keep_input`：仍寻找旧`单据时间：`触发按钮，基点组件已有`aria-label=单据时间`及新日期控件。
- `test_preview.py::test_switch_account_drops_old_scope_and_late_response`：停在同一项目旧名；旧切换账号按钮等后续断言亦未验证。
- `test_preview.py::test_error_loading_forbidden_and_expiry`：旧原生`状态`选择，基点为antd`项目状态筛选`。
- `test_ledger.py::test_continuous_edit_real_save_and_readback`、`test_identity_pause_preserves_real_edit_draft_and_blocks_saves`：停在`选择项目`旧按钮；基点接入FlowPage及`付款项目`控件。
- `test_mechanical_reports.py::test_grid_freeze_virtualization_scroll_locate_and_ime`：停在旧`定位项目`输入；当前源码使用机械项目定位控件。种子已完成，浏览器后续交互未验。

初查workspace_check已存在419的历史产物分类错误：`.artifacts/archive/frontend-vue-rewrite/tail419-20261024/rules-preview-logs`，本轮不改他人证据；最终全根生命周期检查可能继续非零。本轮自有run另核已退出active，无常驻进程或在用产物。

保存边界：本地提交，不推送、不部署；本回执不替代422全站人工复核与性能累计核验。
