# 与「文档」相关的尺子 —— 怎么跑 / 读哪行 / 黄档怎么处置

> ⚠️ **每把尺子"管什么"的权威表 = 各件脚本的头部注释**（`T1`–`T18` 在 `tools/audit/doc_audit.py` 头部）；
> 阈值与出处 = `ops/阈值表.md`；收工闸门清单 = `.codebuddy/memory/MEMORY.md §〇之二`。
> ⛔ 本件只写**读法**（审计时怎么用），⛔ 不复制任何条文（复制出来就是第二套口径）。

## 一、审计文档**只需这 5 条**（完整收工闸门是 13 把，别混）

```powershell
cd d:\dev\mtrl-workbench
backend\.venv\Scripts\python.exe tools\audit\doc_audit.py --ui   # 幽灵号/术语/路径/数字/行数/台账/覆盖/复活/预算/回执/分层/TTL/白名单 ＋ 交付面四检
backend\.venv\Scripts\python.exe tools\audit\audit_meta.py       # 单跑入口：T5/T6/T9/T10/T11/T12/T13/T17/T18
backend\.venv\Scripts\python.exe tools\audit\audit_drift.py      # 锚点漂移 / 计数锚 / 登记常量是否解析得到真东西
backend\.venv\Scripts\python.exe tools\audit\claim_audit.py      # 纪律的「口径出处」标记等
backend\.venv\Scripts\python.exe tools\audit\cover_gap.py        # 判据覆盖登记册（T7：登记档，**不判红**）
```

⚠️ 输出刷屏时**只抓汇总行**（在 PowerShell 里：`| Select-String -Pattern '必须修|疑似|退出码'`）。

## 二、输出怎么读（三档，含义完全不同）

| 档 | 含义 | 审计时怎么办 |
|---|---|---|
| **必须修 N** | 硬门槛（红了就是红的） | ⛔ **先修到 0 再往下审**；非 0 时**别继续** |
| **疑似 N** | **待你判的清单**（黄） | ⭐ **逐条解释**，不是忽略：要么证明是误报、要么承认它是真问题；三类必解释 —— `T5` 行数 · `T10` 读预算 · `T12` 布局 |
| **已豁免 N** | 行文本身就在说"它废了 / 这是旧写法"（±2 行弱豁免、文件级留痕白名单） | 抽查几条，确认豁免理由**不是硬凑**（⛔ 别拿豁免掩盖"该修没修"） |

**期望值（2026-09-28 实跑，供对照，⛔ 别当永久基线）**：`doc_audit` 必须修 **0**（疑似 144 / 已豁免 58）·
`audit_meta` 必须修 **0**（疑似 35）· `audit_drift` 必须修 **0**（疑似 141）· `claim_audit` **0** · `cover_gap` rc=0（清单 0 条）。

## 三、黄档的两类"常见脸"与处置

1. **`T5` / `T10`（长文档）** —— 不是"删到短"，而是**把过程叙事搬走**（口径留在 ①②层、过程下沉 ③层或 `work/`）；
   超 `HARD_LIMIT` 还要在 `ops/阈值表.md` **登记"为什么不拆"**（一行理由）。
2. **`T12` 布局** —— 布局问题**不挡合入**，但必须被看见：改名 / 搬家，或**先改根 `README.md` 的分层表与白名单**（⛔ 别绕过）。

## 四、两个与闸门同族的坑（拿旧证据当真）

- 跑 `pytest` 时**必须显式给 `ACC_RESULTS_PATH`**，否则权威四态（`artifacts/acc_results.json`）不刷新；判"红 / 未绑定"前**先看结果档的 `generated_at` 是不是刚跑那一次**（本仓因读到上一轮结果，白追过四步）。
- `T3`/`T18` 是**静态秒级**检查 ⇒ 改完任何文档**立刻跑**；别等收工才发现一片"扫空集"。
