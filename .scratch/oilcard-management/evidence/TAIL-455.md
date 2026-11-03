# TAIL-455 验证记录

2026-10-31，分支 `codex/oilcard-management-20261031`，实施起点 `959ab2f0d46e2b57091457e62932b9b7e1488e62`。范围为共用值筛选、充值表实际接入、筛选合计及全量已保存台账下载。共用接口只接字段类型、取值、格式及候选/草稿可见策略，没有油卡API或金额公式依赖；后续发票票仍需真实复用。

## 实现与自动检查

复用AG Community原生列定义、模型、筛选浮层、排序及CustomFilterModule，Ant Design Tree/Input/Button承载候选UI；金额使用现有Decimal.js精确比较。没有引入新依赖或修改锁文件。参考：[AG自定义筛选](https://www.ag-grid.com/react-data-grid/component-filter/)、[筛选能力](https://www.ag-grid.com/react-data-grid/filtering/)、[许可](https://www.ag-grid.com/license-pricing/)、[Ant Tree](https://ant.design/components/tree/)。实际依赖为AG36.2.0、AntD6.6.7，按实际声明核扩展接口。

- 后端 `backend_verify.py --source-env .env --test tests/test_oilcard_export.py --test tests/test_layering.py -- -q -o addopts=`：17 passed in4.95s，父控直接核日志/JSON回执。AgentArtifacts组 `105045-502453-7552`，schema `backend_verify_2faf9925aff44762b86f1dda60c64109`及pytest临时目录均清理，returncode=0。实际工作簿覆盖全量范围、文字日期、卡号文本、数字金额、负退款及公式样式文字按文本保存。
- 前端4项筛选语义、4项连续编辑及1项保存队列定向检查：9 passed；覆盖日期分支/文字/空白、候选计数与搜索、空选/最后取消、独立列条件、负数/零及大额分位数值比较。复用有效的身份与未知结果保障。
- 父控以正式预览入口生成 `work/build-01`，Corepack类型检查及构建退出码0；构建完成后registered_preview核实实际运行的源指纹、构建和目标schema，再进行页面验收。

## 真实页面与下载

使用完整产品的专用可丢弃副本。仅通过已有API准备5条合成已保存记录，金额10000、200、-50、0、5，合计10155；日期包含两个2026年10月日期、往年日期、“原始数据”及空白。页面代表路径如下：

1. 通过原生日期列头打开浮层，年/月/日逐层复选框、文字及空白候选存在；勾2026年后剩2条、合计10200，浮层保持打开。取消最后分支恢复5条、合计10155；搜索“原始”仅缩小候选，表格仍5条。
2. “仅此项”选择原始数据后只剩-50记录并关闭浮层；“清除筛选”恢复全部并关闭浮层。
3. 金额升序实际显示-50、0、5、200、10000，降序反向，排序后浮层仍打开；只选200后合计200并关闭。
4. 在金额200条件上再只选原始数据日期，结果0条、合计0；只清日期后恢复200记录，金额条件保留。
5. 原生手调日期列从190增至230px；新建仅填2030-01-01的未完成草稿，再选2025年使已保存数据无匹配，草稿及其文字保留，未进入候选，筛选过程中手调宽度保持230。
6. 在已保存结果0条且仍有未完成草稿时，点击“导出全部已保存台账”，浏览器实际下载 `reports/full-ledger-filtered.xlsx`。以只读ZIP/XML解析核得5条明细+表头+合计10155；日期原文/空白、完整前导零卡号及数值金额正确，未完成草稿未导出。不是只验证导出函数或文件存在。
7. 点击本表“恢复自动列宽”回190px，金额/日期条件、降序及草稿均保持。已查看最终日期浮层截图，完成后的自有未保存草稿通过页面取消。

浏览器脚本round-41～61、截图和实际下载位于 `.artifacts/active/oilcard-implementation/20261031-455`。过早读取异步合计、失效快照引用及最小化窗口截图失败的回合不计通过；观察新状态后完成上述路径。窗口问题经任务标签实际targetId恢复，仅操作已确认agent-owned任务窗口；没有让用户承担内部完成通知。

## 资源与边界

预览 `127.0.0.1:8065`，PID29484，`mtrl_workbench_test` schema `frontend_rewrite_397_515fed3ecef7425b9755c9d53c1c0cdd`，迁移 `oil454261031`，synthetic=false/disposable=true。页面核验后正常stop，进程退出码0，终端确认schema已清理。8801原型和生产服务保持原任务归属。

未执行生产迁移/部署、真实账务导入或其他页面推广。发票侧当前仍为后续入口；两表实际复用与独立性由458继续验证。最终累计Standards/Spec独立审查仍待统一收尾。
