---
version: 1
slug: "wave1-shell-and-admin"
primary_target: "apps/frontend/src/projects.tsx"
related_targets: ["apps/frontend/src/projects.css", "apps/frontend/src/i8.tsx", "apps/frontend/src/i8.css", "apps/frontend/src/i8-session.tsx", "apps/frontend/src/i8-fetch.tsx", "apps/frontend/src/i8-kick-confirmation.tsx", "apps/frontend/src/i8-fetch-receipt.tsx", "apps/frontend/src/i8-receipt-summary.tsx", "apps/frontend/src/jc-fetch-receipt.tsx", "apps/frontend/src/rules.tsx", "apps/frontend/src/jc-rules.tsx", "apps/frontend/src/rules.css", "apps/frontend/src/users.tsx", "apps/frontend/src/users.css"]
---

# 基础维护四页（项目档案、i8 接入层、规则配置、用户管理）

模式为 Operate。PR-W1b 承接 PR-W1a 确立的方向 A「精工深墨松绿」外舒内紧桌面标杆，将基础维护其余四页收拢到统一表面层次、单行横排工具栏与无裁切焦点契约下。主题与业务依据见[设计规范](../../DESIGN.md)、[前端设计与文案](../../docs/guides/frontend-design.md)、[标杆简报](benchmark-home-and-contracts.md)和[当前需求](../../docs/requirements.md)。

## 桌面四档与 2K 限宽口径

| 视口 | 界面大小 | 主要核对内容 |
| --- | --- | --- |
| 2560 × 1440 | 大一点 1.12× | `/i8`、`/rules`、`/users` 居中限宽 `1520px`（`.wb-flow-width`）；`/projects` 为 10 列密集档案表，按 `DESIGN.md` 保留可用全宽（实测 `2291px`），避免 2K 下强行挤出横向滚动。四页工具栏均保持单行（`35.8~45.8px`）。 |
| 1920 × 1080 | 标准 1.0× | `/i8`、`/rules`、`/users` 宽 `1520px`，`/projects` 宽 `1649px`。四页工具栏均单行（`32~41px`），`/rules` 四列及全部「编辑／删除」操作同屏完整可见。 |
| 1440 × 900 | 最大 1.4× | 打开外观面板，四页 `docOverflowX` 均为 `0px`，控件与表区随 `--fscale` 缩放且横向滚动留在表内。 |
| 960 × 1000 | 标准 1.0× | 默认 `56px` 图标侧栏，支持一键展开；展开与收起两态四页 `docOverflowX` 均为 `0px`。 |

## 四页结构与精修约束

- **项目档案（`/projects`）**：保留可用全宽 10 列档案表。`.project-tools` 与筛选标签改为左标签横排 `.wb-toolbar` 节奏，主操作靠右；表格按内容高度收紧并仍以 `65dvh` 为长表上限（2K 13 行由 `936px` 收到 `645px`，消除末行与「修改留痕」间空白带，且首读占位到实表切换高度差 `0px`）。保存异常参与行高测量，避免「重读核对」按钮被表格行遮挡；列宽恢复按钮留在列头末端，不干扰原生排序与整行拖拽。
- **i8 接入层（`/i8`）**：去掉与 `.wb-flow-width` 冲突的 `1080px` 限宽与嵌套 `.i8-block` 卡片，改为单一 `.wb-surface.wb-flow-width` 表面配合水平分隔线；服务器配置条与执行记录筛选条改为横排单行；浏览器会话区保留浅底分带，缺扩展时用暖色语义提示强调原因。回执样式由 `i8.css` 统一承接，不影响集采与报表等跨波次调用方。
- **规则配置（`/rules`）**：接入 `.wb-flow-width` 并移除嵌套卡片；修复「付款通知书」「集采台账」页签及「搜索全部规则」按钮的边框对比度（均 `>= 3:1`）；跨页定位 `.rules-located` 取消单侧彩条，改为整行柔和底色与描边高亮；「命中值」列允许换行并设合理起始占比，2K 与 1080P 下四列与行内「编辑／删除」均零裁切可见，仍保留表头手动拖宽；全站规则搜索窗补齐 `.dialog-actions` 关闭页脚，规则表单样式排除 `.jc-receipt-dialog` 防止串扰回执弹窗。
- **用户管理（`/users`）**：接入 `.wb-flow-width` 并移除嵌套卡片；整理账号计数、当前登录信息、操作按钮与底注层级；「密码与 i8 绑定」弹窗复用 `.users-warning` 区分「系统密码留空会清空」与「i8 密码留空会保留」两种相反语义；修复弹窗原生输入与表内按钮焦点环裁切。
- **404 与路由错误边界**：`/preview/__not_found_check__` 返回统一 `flow` 空态页（「没有找到这个页面」），`docOverflowX === 0`。

## 业务护栏

| 编号 | 本波守住的业务约束 |
| --- | --- |
| R01 / R02 | 业务 CSS 零硬编码色值，全走主题变量；实拍最低文字对比度 `5.13:1`、最低控件边框对比度 `3.38:1`；数字与日期随 `--fscale` 缩放无截断。 |
| R03 / R04 | 12 个弹窗沿用 `compact` / `scroll-body` / `pane` 与 `.dialog-actions`；手调列宽及表头恢复入口完整保留。 |
| R05–R10 | 四页不启用 `singleLine`；自动保存与未知结果重读、原文字段复制粘贴、20 步全局撤销重做、切页保活与首读占位均保持原行为。 |
| R20 | 项目类型只读、整行拖排、含归档关键词搜索、规则双标签跨页定位（`#rule-{page}-{id}`）、末位在用管理员保护及 i8 读回/外部取数分离全部通过 Playwright 回归。 |

## 验收证据

主检出受管目录 `.artifacts/runs/mtrl-site-polish-plan-20261127/w1b-evidence/` 保存改前基线（`before/`）、首轮实拍（`after-pass1/`）、终验实拍（`after-final/`，25 张 PNG + `after-metrics.json` + `after-comparison.json` + `rules-bounds.json`）及采集脚本 `measure_w1b.py`。

- **自动化验证**：`typecheck` 0 错误、`test:unit` 302/302、`build` 通过、Playwright 50/50（主回归 28/28 + 首读样式 18/18 + 字体恢复 4/4）。
- **Impeccable 闭环**：双代理独立评审（A：`codex/gpt-6.2-astra` 28/40；B：`grok/grok-4.7` 源码+实机 detect 与 Playwright）发现的问题已全部精修关闭；最终 11 份 TSX + 4 份 CSS 源码与 `/preview/projects`、`/preview/i8`、`/preview/rules`、`/preview/users` 四条实机路由 `impeccable detect --json` 均返回 `[]`（0 告警）。
- **性能与几何**：路由切换对比基线 `pass: true`（2K 均值 `-21.24%`、p95 `-53.78%`；1080P 均值 `-15.48%`、p95 `-2.67%`；两档新增 `>100ms` 长任务均为 `0`，热切换长任务均为 `0`）。四档与 960 展开态 `docOverflowX === 0`，`/rules` 2K 与 1080P 四列及 8 个操作按钮裁切 `0px`。
- **独立审查**：跨模型独立代码审查（`grok/grok-4.7`）`APPROVE (0 blockers)`。
