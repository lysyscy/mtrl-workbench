# 当前活动工作

## 当前正式运行

| finished_at | run_id | action | product_commit | pid |
| --- | --- | --- | --- | ---: |
| 2026-11-27T11:50:42.262641+08:00 | `115016-512457-3216` | `restart` | `bfdbc414350545f39f477832a692bae3426e3067` | 10332 |
| 2026-11-27T11:17:05.736138+08:00 | `111634-953768-31776` | `publish` | `bfdbc414350545f39f477832a692bae3426e3067` | 19344 |

较早的正式运行可从 Git 中的本页历史及本机 `.artifacts/runs/*/reports/deployment.json` 追溯。表中 PID 为 HTTP 监听进程。

<!-- BEGIN:DERIVED_ACTIVE_WORK -->

## 活动任务

- [TAIL-497: 设备三账协同决策地图](tasks/TAIL-497.md) · 状态 needs-info · 待验收 完成设备三账实际接续与业务流程验收 · 下一步 按 TAIL-501、TAIL-502、TAIL-510 各自的待办核实。
- [TAIL-501: 怎样从现有三账接续并验收](tasks/TAIL-501.md) · 状态 needs-human · 待验收 核对 11 月 128 行租赁底稿、半年盘点打印出口和南靖待核项 · 下一步 逐笔验收 11 月接续结果，确认后作为 12 月期初底稿。
- [TAIL-502: 设备台账日常入口怎么做](tasks/TAIL-502.md) · 状态 ready-for-human · 待验收 用正式入口试走新增、调拨、月租例外与盘点导出 · 下一步 核实 Edge 扩展 0.1.7 已加载，并按现场验收边界回读结果。
- [TAIL-510: 纠正现有设备编号并同步 Excel 调拨记录与 i8](tasks/TAIL-510.md) · 状态 ready-for-agent · 待验收 核实现存 Excel 编号与调拨引用，继续确认遗留待核项 · 下一步 以已完成的正式库和 i8 回读为基线，先只读核对 Excel。
- [全站前端打磨](tasks/mtrl-site-polish-plan-20261127.md) · 状态 waiting-user · 待验收 从 A 精工深墨松绿、B 清透浅雾松绿、C 沉稳暖石松绿中选定一个方向 · 下一步 用户选定方向后，按原计划先推进 Wave 0，共用底座通过后再进入后续波次。
- [付款通知书抓取与集采关联](tasks/notice-fetch-261126.md) · 状态 needs-human · 待验收 正式登录态真实 i8 抓取及自动关联尚未验收 · 下一步 现场验收沿正式入口和当次授权；独立复核证据到期后，确认旧 T3 线程与本地内容去向，再复核工作树退出。

## 工作树状态

- `t3-3fd7b200-13d2a726b4842e50` · in-use · 付款核对台账探索工作树 · 保留付款台账恢复与项目归属实验，供技术栈同题比较。
- `t3-a0519f43-082597183e4816c2` · blocked · [付款通知书抓取与集采关联](tasks/notice-fetch-261126.md) · 开发已合入；独立复核证据按原登记保留至 2026-12-26，旧 T3 线程结案待核。
- `前端打磨-d5c483635c4ec129` · in-use · [全站前端打磨](tasks/mtrl-site-polish-plan-20261127.md) · 多波计划等待样板方向，主检出受管证据仍在用。
- `feat-equipment-ledger-2422e3af65ee03f8` · retired · [TAIL-497: 设备三账协同决策地图](tasks/TAIL-497.md) · Git 工作树和分支已退出。接续回退与业务验收沿各票保留。

<!-- END:DERIVED_ACTIVE_WORK -->
