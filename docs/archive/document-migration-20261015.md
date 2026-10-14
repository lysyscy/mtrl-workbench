# 专项文档迁移总清单与来源（2026-10-15）

本轮起点 `7c37f89b3787a053e87debfa70dac768c2ffe846`。首两批来源与SHA见docs/adr/0033-document-layout.md；本件记录最后阶段的全部处置。原文字节和原索引快照在本机恢复现场，跟踪文件也可由固定SHA逐路径恢复；忽略文件保持原地。恢复仅还原本批拥有的路径，保护之后出现的新内容。

## 现行权威实际迁移

| 旧位置 | 目标位置 | 理由与独有信息 | 活动引用 | 机器消费者 | 验证方式 | 恢复依据 |
|---|---|---|---|---|---|---|
| `delivery/PRD/00-总览.md` | `docs/requirements/PRD/00-总览.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/01-需求索引.md` | `docs/requirements/PRD/01-需求索引.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-01.md` | `docs/requirements/PRD/02-功能规格/MOD-01.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-02.md` | `docs/requirements/PRD/02-功能规格/MOD-02.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-03.md` | `docs/requirements/PRD/02-功能规格/MOD-03.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-04.md` | `docs/requirements/PRD/02-功能规格/MOD-04.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-05.md` | `docs/requirements/PRD/02-功能规格/MOD-05.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-06.md` | `docs/requirements/PRD/02-功能规格/MOD-06.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-07.md` | `docs/requirements/PRD/02-功能规格/MOD-07.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-08.md` | `docs/requirements/PRD/02-功能规格/MOD-08.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-09.md` | `docs/requirements/PRD/02-功能规格/MOD-09.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-10.md` | `docs/requirements/PRD/02-功能规格/MOD-10.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-11.md` | `docs/requirements/PRD/02-功能规格/MOD-11.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-12.md` | `docs/requirements/PRD/02-功能规格/MOD-12.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-13.md` | `docs/requirements/PRD/02-功能规格/MOD-13.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-14.md` | `docs/requirements/PRD/02-功能规格/MOD-14.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/MOD-15.md` | `docs/requirements/PRD/02-功能规格/MOD-15.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/02-功能规格/README.md` | `docs/requirements/PRD/02-功能规格/README.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/03-非功能需求.md` | `docs/requirements/PRD/03-非功能需求.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/04-Non-goals.md` | `docs/requirements/PRD/04-Non-goals.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/05-任务分解.md` | `docs/requirements/PRD/05-任务分解.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/99-追溯表.md` | `docs/requirements/PRD/99-追溯表.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/验收/README.md` | `docs/requirements/PRD/验收/README.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/验收/用例索引.md` | `docs/requirements/PRD/验收/用例索引.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/PRD/验收/验收基线.json` | `docs/requirements/PRD/验收/验收基线.json` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/demo/原型导读.md` | `docs/requirements/demo/原型导读.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/demo/模板/模板清单.md` | `docs/requirements/demo/模板/模板清单.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/demo/设计规则-提炼自付款通知书页.md` | `docs/requirements/demo/设计规则-提炼自付款通知书页.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/交付说明书.md` | `docs/requirements/交付说明书.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/全自动建档-实施计划.md` | `docs/requirements/全自动建档-实施计划.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/技术栈选型分析.md` | `docs/requirements/技术栈选型分析.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `delivery/材料科业务全流程说明书.md` | `docs/requirements/材料科业务全流程说明书.md` | 唯一产品正文/判据，保留业务含义、字段与ID | 现行入口及消费者已切换；活动范围不变 | audit_common、acc_report、四检、_audit_face、claim及对应测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `ops/README.md` | `docs/guides/operations.md` | 运维正文及配置主人从脚本索引迁出；原脚本入口仍有实质职责 | 现行入口及消费者已切换；活动范围不变 | 环境配置测试、Agent入口与文档检查 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `ops/delivery-surface.md` | `docs/requirements.md` | 现行需求固定入口，旧资料清单的定位职责统一 | 现行入口及消费者已切换；活动范围不变 | Agent入口、文档路径检查 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `.codebuddy/plans/开发计划-主文档.md` | `docs/status.md` | 汇合当前状态，README恢复稳定导航；原§15和任务裁定保持 | 现行入口及消费者已切换；活动范围不变 | T6、开销票工具、影响分析、素材与claim读取器 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `.codebuddy/work/README.md` | `docs/guides/work-records.md` | 仍生效的工程依据或生命周期，旧原文可恢复；导航按当前职责重组 | 现行入口及消费者已切换；活动范围不变 | T3/T26、宿主指针、工程索引、相关工具和测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `.codebuddy/work/10-designs/设计-文件拆分必要性判据-20260924.md` | `docs/guides/file-splitting.md` | 仍生效的工程依据或生命周期，旧原文可恢复；导航按当前职责重组 | 现行入口及消费者已切换；活动范围不变 | T3/T26、宿主指针、工程索引、相关工具和测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |
| `.codebuddy/work/10-designs/设计-写动作标脏数据流图-20260924.md` | `docs/architecture/write-refresh.md` | 仍生效的工程依据或生命周期，旧原文可恢复；导航按当前职责重组 | 现行入口及消费者已切换；活动范围不变 | T3/T26、宿主指针、工程索引、相关工具和测试 | 原文/结构核对、真实扫描与相关测试 | 基线SHA旧路径及本机originals |

## 保留来源的历史归档

| 旧位置 | 目标位置 | 理由与独有信息 | 活动引用 | 机器消费者 | 验证方式 | 恢复依据 |
|---|---|---|---|---|---|---|
| `.codebuddy/memory/journal/2026-09-24.md` | `docs/archive/journal/2026-09-24.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-09-25.md` | `docs/archive/journal/2026-09-25.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-09-26.md` | `docs/archive/journal/2026-09-26.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-09-27.md` | `docs/archive/journal/2026-09-27.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-09-28.md` | `docs/archive/journal/2026-09-28.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-09-29.md` | `docs/archive/journal/2026-09-29.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-09-30.md` | `docs/archive/journal/2026-09-30.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-10-01.md` | `docs/archive/journal/2026-10-01.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-10-04.md` | `docs/archive/journal/2026-10-04.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-10-05.md` | `docs/archive/journal/2026-10-05.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-10-06.md` | `docs/archive/journal/2026-10-06.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-10-07.md` | `docs/archive/journal/2026-10-07.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-10-08.md` | `docs/archive/journal/2026-10-08.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-10-09.md` | `docs/archive/journal/2026-10-09.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-10-10.md` | `docs/archive/journal/2026-10-10.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-10-11.md` | `docs/archive/journal/2026-10-11.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/memory/journal/2026-10-12.md` | `docs/archive/journal/2026-10-12.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/import-wizard-mock.html` | `docs/archive/designs/import-wizard-mock.html` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/import-wizard-mock.shell.css` | `docs/archive/designs/import-wizard-mock.shell.css` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-agent阅读与核验减负整改-20261008.md` | `docs/archive/designs/设计-agent阅读与核验减负整改-20261008.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-主文档与D件二期治理-20261011.md` | `docs/archive/designs/设计-主文档与D件二期治理-20261011.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-分层门禁一般式-20261002.md` | `docs/archive/designs/设计-分层门禁一般式-20261002.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-前端系统性重构审计-20260928.md` | `docs/archive/designs/设计-前端系统性重构审计-20260928.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-剩余重构最小方案-20261012.md` | `docs/archive/designs/设计-剩余重构最小方案-20261012.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-口径说明折叠块-20261001.md` | `docs/archive/designs/设计-口径说明折叠块-20261001.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-工作流维护边界与整改-20261014.md` | `docs/archive/designs/设计-工作流维护边界与整改-20261014.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-库存与静态传输最小优化-20261012.md` | `docs/archive/designs/设计-库存与静态传输最小优化-20261012.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-开发治理整改-20261007.md` | `docs/archive/designs/设计-开发治理整改-20261007.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-文档治理归属与技能选型-20261014.md` | `docs/archive/designs/设计-文档治理归属与技能选型-20261014.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-架构候选3-异常原文-20261002.md` | `docs/archive/designs/设计-架构候选3-异常原文-20261002.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-统一导入模块-20260922.md` | `docs/archive/designs/设计-统一导入模块-20260922.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-识别样本-真实模板-20260922.md` | `docs/archive/designs/设计-识别样本-真实模板-20260922.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-集采台账打印导出-20261014.md` | `docs/archive/designs/设计-集采台账打印导出-20261014.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-首次载入最小优化-20261012.md` | `docs/archive/designs/设计-首次载入最小优化-20261012.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/30-troubleshooting/实验-首次载入性能基线-20261012.md` | `docs/archive/troubleshooting/实验-首次载入性能基线-20261012.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/30-troubleshooting/排查-尺子与规则的过期清单-20260924.md` | `docs/archive/troubleshooting/排查-尺子与规则的过期清单-20260924.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/30-troubleshooting/排查-收款账号印错-20260921.md` | `docs/archive/troubleshooting/排查-收款账号印错-20260921.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/plans/票索引-已销号.md` | `docs/archive/tickets/index.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | T6及开销票专用历史短索引 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/plans/archive/归档-留痕索引-20261005.md` | `docs/archive/legacy-plans/归档-留痕索引-20261005.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 旧归档工具专用索引 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-表格筛选配置化-20260924.md` | `docs/archive/designs/设计-表格筛选配置化-20260924.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |
| `.codebuddy/work/10-designs/设计-交付包与迁移-20260929.md` | `docs/archive/designs/设计-交付包与迁移-20260929.md` | 已结束过程、调查或来源索引；原文字节保留 | 必要引用切到实际归档位置 | 明确追溯与必要专用引用；退出默认内容扫描 | SHA256逐件相同、普通扫描不含archive | 基线SHA原路径、同字节归档与originals |

README的方法采用段、旧计划§14.4已办排期已拆入docs/archive/plans，旧整件仍可从基线恢复。这两份抽取件不再定义当前部署或方法版本。

## 已确认没有独有正文的退役入口

| 旧位置 | 现行主人 | 独有信息与理由 | 活动引用及机器消费者 | 验证 | 恢复 |
|---|---|---|---|---|---|
| `ops/architecture.md` | `docs/architecture.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/modules.md` | `docs/architecture/modules.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/deployment.md` | `docs/guides/deployment.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/docs-governance.md` | `docs/guides/document-governance.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/development/实现约束.md` | `docs/guides/implementation-constraints.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/development/开发与核验.md` | `docs/guides/development-and-verification.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/前端设计守则-以使用用户为中心.md` | `docs/guides/frontend-design.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/阈值表.md` | `docs/reference/thresholds.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/i8-接口契约-旁证摘要.md` | `docs/reference/i8-contract.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/M3-合计行置底实测结论.md` | `docs/reference/sticky-total-row.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/模板法导出-实测结论.md` | `docs/reference/template-export.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/素材包-索引.md` | `docs/reference/legacy-materials.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/changelog.md` | `docs/reference/changelog.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/agents/issue-tracker.md` | `docs/agents/issue-tracker.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/agents/domain.md` | `docs/agents/domain.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `ops/agents/triage-labels.md` | `docs/agents/triage-labels.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `.codebuddy/memory/细则.md` | `docs/guides/implementation-constraints.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |
| `.codebuddy/memory/IDE-细节.md` | `docs/guides/development-and-verification.md` | 仅迁移过渡或兼容指针；正文在前批已守恒迁移 | 活动资料与当前机器已直连新主人，旧历史按源SHA读取 | 薄入口原文核对、真实扫描/路径及缺失反例 | 基线SHA与originals；不恢复永久映射 |

## 明确保留，不作为待清理垃圾

| 原位置与本轮目标 | 理由与独有信息 | 活动引用与机器消费者 | 验证与退出条件 | 恢复依据 |
|---|---|---|---|---|
| .codebuddy/work/50-tickets原位 | 真实已采用tracker权威；117份票含活动和历史Comments | T6、开销票、覆盖/来源查询；内容检查只默认读在途票 | 全票仓状态与索引一致、原票字节不变；只有明确切换tracker再迁 | Git及本轮摘要 |
| .codebuddy/work/10-designs三份原件原位 | TAIL-284来源、TAIL-287暂缓依据、界面整改一项未决 | 原票、状态页与直接依赖；仅受控修引用，不改任务范围 | 原句与状态保留，原始版本另存；对应任务结束或未决裁定后归档 | 基线SHA及originals |
| .codebuddy/work/40-decisions原位 | 重要旧决定的原文与固定编号 | 领域/文案方法按条件读取；只修现行索引指针 | 除既有索引外D原件字节不变；新ADR在docs/adr | Git及摘要 |
| .codebuddy/memory/MEMORY.md、rules与仓内技能入口 | 宿主真实加载/项目配置 | 实际入口与本仓检查 | 专题正文切到docs；本轮不更新已安装技能；宿主退出后再退役 | Git、本机摘要 |
| delivery原型HTML、模板、JS及第三方原件；backend实际运行模板 | 可执行资源、运行输入、历史规格或上游原件 | 四检、原型对账、资源模块；当前Markdown已迁入docs | 原型和资源字节保持、JS切新正文根并做缺失反例；真实运行契约切换前保留 | 原路径Git及本机材料原位 |
| .codebuddy/backups、旧00-scratch、artifacts、logs及旧.workbuddy未知材料 | 活动接续、恢复或来源不明；日期/零引用不能证明无用 | 原任务、恢复、真实工具配置 | 本轮原地保持，不清理本机独有材料；用途确已结束再单独核对 | 忽略文件原位及4431份元数据摘要，Git不代替原件 |

## 验证与保存

实际检查原始日志及verification.json保存在本机专项恢复现场。本轮30项定向pytest、四检、归档恢复19项、相关结构/字节/语法/机器检查和隔离缺失反例分别记录；未将局部通过说成应用全套或生产验收。全选测自测的既有断言失败沿前批固定基线复现结论保留。

原四检有一条过期断言要求说明书重复字段计数，但基线正文已使用ENT-06→§6.4.1唯一字段清单；本轮修为实际所有者引用契约，并以删除该引用的隔离反例核红，字段与业务正文未改。原_links缺集采打印模板裸名，已指到实际backend资源；这两处均保留旧输入证据，未刷新验收基线遮蔽问题。

销号消费者已改为将原排期保存至已销号归档索引，状态页不积累关闭记录；隔离开销票实跑与历史写入失败回滚用例通过。修复前的空历史表失败复现日志保留在本机现场。


另删除两份仅含换行的旧目录占位，均无正文或机器消费者；原路径与字节可从基线SHA恢复：

- 旧路径 `.codebuddy/work/10-designs/.gitkeep`：空白占位，已无用途。
- 旧路径 `.codebuddy/work/30-troubleshooting/.gitkeep`：空白占位，已无用途。
