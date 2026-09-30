# -*- coding: utf-8 -*-
"""收尾：把本轮（`m07` 接线 ＋ `TAIL-38`）写进**执行情况‑主文档**（版本行 / §⑥ / §⑦）。

⚠️ 幂等：已是目标状态就直接退出 0。
⚠️ 一律**按行首标记定位 + 整行替换**（长中文行不做精确全文匹配 —— 太脆）。
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / ".workbuddy" / "plans" / "执行情况-主文档.md"
text = DOC.read_text(encoding="utf-8")
if "本轮任务（2026-09-18 01:1" in text or "`TAIL-38` 录机械费" in text:
    print("已是目标状态（本轮条目已写入）—— 无需重复执行")
    sys.exit(0)

lines = text.splitlines(keepends=True)
NOW = dt.datetime.now().strftime("%Y-%m-%d %H:%M")


def find_one(prefix: str, start: int = 0) -> int:
    hit = [i for i, l in enumerate(lines) if l.startswith(prefix) and i >= start]
    if len(hit) != 1:
        raise SystemExit(f"⛔ 行首标记 `{prefix}` 命中 {len(hit)} 次（应 1）")
    return hit[0]


# ---- ① 版本行
v = find_one("> **当前版本**：")
lines[v] = (
    f"> **当前版本**：{NOW}（实测）· ⭐⭐ **`TAIL-27` 第 7 页 `m07` 接线 ＋ `TAIL-38` 录机械费入口**"
    "（材料域最后一页接通；`m06` 的机械 6 列从此**在壳里可录**）· ⭐ **后端新增 `mod07_setl/api.py`（7 个 JSON 端点）**"
    "＋ `POST /api/m06/mech` · ⭐ **`V.m07` 只改了 1 行**（演示基线文案 ⇒ 已登记 `ui_parity` 漂移）· "
    "⚠️ **反向灵敏度首跑抓出 4 处假绿断言**（已改紧）· ⏭️ 下一轮 = `TAIL-35`（`m04` 导入 / 手动行）＋ 其余页接线\n"
)
print("① 版本行已更新")

# ---- ② §⑥ 插入本轮条目
j = find_one("## ⑥ 当前状态")
lines.insert(j + 1, f"""
- **⭐⭐ 本轮（{NOW} · 实测）`TAIL-27` 第 7 页 `m07`（收发结存与活动大表）＋ `TAIL-38`（录机械费入口）**
  · **① `m07` 整页接线**（材料域最后一页）：新增 **`backend/app/mod07_setl/api.py`（7 个 JSON 端点）** ——
    读 `GET /api/m07/settlement`（按月取数 ＋ 按仓汇总 · **唯一取数出口 = `domain.warehouse_rows`**）·
    `/api/m07/extract`（**提取口径唯一出口 = `extract.extract_amounts`**）·
    `/api/m07/big`（行装配 ＋ **全量**手填值 ＋ 选题顺序 ＋ `manual_keys`/`manual_fmts`（**列序与列型的唯一主人 = 后端**）＋ `mat_available`）；
    写 `POST /api/m07/big/cell`（手填一格）· `/api/m07/big/selection`（选题）· `/api/m07/fetch`（**`confirm` 缺省为假** ⇒ 防静默顶号）。
    ⚠️ **本层不写任何判定** —— 一律调 `service` / `big_service` / `fetch_service`（下游是域内核），同 `m08` 的 API 段。
  · **壳侧**：删演示容器 `WHM`（3 个月）/`EXTM`（3 个月）/`BIGVAL`（3 个月）＋已失效的 `EXTRACT` 别名；
    `BIGSET` 改「空数组 ＋ 后端填充」；新增 `adaptWh` / `adaptExtract` / `adaptManual` / `reloadM07` / `bgFailed` / `whFetchBackend`；
    写动作 `bigEdit` / `bigPickOk` / `fetchNtOk`(wh) / 月份切换 全部改走后端；`zipSfjc` 由**假成功**改为**如实标注属 `TAIL-04`**。
    ⭐ **`V.m07` 只改了 1 行**（原「已验收基线」文案引用演示块 `WHM['2026-08']` ⇒ 删块后会 `TypeError` **整页崩**，
      且原文案写「本页数据为模拟值」= 接线后的**假话**）⇒ 改为用真数据说同一件事，并**登记** `ui_parity_expected.txt`（理由已写明）。
  · **② `TAIL-38`：录机械费入口**：新增 **`POST /api/m06/mech`**（复用 `mech_ui.parse_mech_values` ＋ `repository.save_mech`，
    与 PRG 端点**同一份判定**）；⛔ **不改 `V.m06` 一行** —— 走原型自己的 **`BIND.m06` 钩子**在渲染后往页首注入工具栏；
    列名从后端 `columns` 取（前端只留兜底，⛔ 不硬编码）。
  · ⭐ **真机证据**：`m07` 三张表全通 —— 收发结存「表内渲染 == 后端行数 ＋ 合计行」· **大表行数 == 后端选题数 10**（演示是 8 ⇒ 确证换了源）·
    `mat_available=False` ⇒ 主材累计列显「—」而非 0 · **零 console / page 错误**；
    录机械费「**写** → **回读** `[0,1234.56,0,0,0,0]` → 负数 / 非法月份**双 400 拒** → **复原（表内 0 行）**」全通。
  · ⚠️ **`M()` 的改动（要记住）**：加 `if(n==null) return '—'` —— 「主材累计」取数口未接入时后端给 `null`，
    原实现 `Number(null)||0` 会显示「0.00」= **冒充"确实没有"**（`TAIL-25` 明令禁止）。⭐ **对数字入参行为完全不变**（已断言钉住）。
  · ✅ **验证**：断言 **19（`test_wired_m07.py`）＋ 4（`test_wired_m06.py` 追加）** 条 ·
    ⭐⭐ **反向灵敏度 15/15**（**首跑即抓出 4 处假绿**：① `in:\\s*N0\\(` 正则被 `begin:` 里的子串喂饱 ② `boot()` 断言被**注释里**的
    `reloadMech` 喂饱 ③ 列名断言被同函数的 `d.columns.forEach` 喂饱 ④ 端点断言被 PRG 端点的同名调用喂饱 —— **四条都已改紧并复测**）·
    MD5 逐字节复原 · 四态 **487 不变**（接线不新增判据点）· **六把尺子全 0**（`chain_audit` 仍红 = `TAIL-04`/未开工，**与本轮无关**：
    R 链路 3 条红 = zip 打包 / 按模板导出 / 三账比对）。
  · ⏭️ **下一轮**：① `TAIL-35`（`m04` 的 Excel 导入 ＋ 手动行壳侧入口 —— 后端 `manual_row_payload` 与判据**已就绪**，只差 JSON 端点 ＋ 壳）；
    ② 其余页接线（`m02`/`m09`/`m10`/`m12`/`m13`/`m14`/`m15`）；③ ⚠️ 本文件 §⑥ 已偏长（>500 行）⇒ 该把旧条目下沉到 `归档-历史单元条目.md`。

""")
print("② §⑥ 已插入本轮条目")

# ---- ③ §⑦：把「本轮任务」段换成新一轮（顺带去掉重复的两段）
#     ⚠️ 该段在文件里**重复了两遍**（上一轮编辑的副作用）⇒ 取「第一个起点 + 最后一个终点」，一并去重。
starts = [i for i, l in enumerate(lines) if l.startswith("> ⭐ **本轮任务（2026-09-18 00:23")]
if not starts:
    raise SystemExit("⛔ §⑦ 找不到本轮任务的起点锚")
s = starts[0]
ends = [i for i, l in enumerate(lines)
        if l.startswith("> ⏭️ **下一轮**：") and "TAIL-38" in l]
if not ends:
    raise SystemExit("⛔ §⑦ 找不到本轮任务的结尾锚")
e = ends[-1]
if not (s < e and e - s < 30):
    raise SystemExit(f"⛔ §⑦ 区间异常：{s} → {e}")
lines[s:e + 1] = [
    f"> ⭐ **本轮任务（{NOW} · 实测）—— `TAIL-27` 第 7 页 `m07` ＋ `TAIL-38`（录机械费入口）**\n",
    "> ✅ **`m07` 收发结存与活动大表接线**：后端新增 `mod07_setl/api.py`（**7 个 JSON 端点**，见 §⑥）；\n",
    "> 壳侧删演示容器 `WHM`/`EXTM`/`BIGVAL` ＋ `EXTRACT` 别名、`BIGSET` 改后端填充、写动作全走后端。\n",
    "> ⚠️ **`V.m07` 只改 1 行**（演示基线文案 ⇒ 会 `TypeError` 崩页 ＋ 原文案是「模拟值」的假话）⇒ 已**登记** `ui_parity` 漂移。\n",
    "> ✅ **`TAIL-38` 录机械费**：新增 `POST /api/m06/mech`；⛔ **不改 `V.m06` 一行**，走原型的 `BIND.m06` 钩子注入入口。\n",
    "> ⭐ **真机**：`m07` 三张表全通（大表行数 == 后端选题数 10 · 主材累计显「—」· 零 console 错误）· 录机械费写/回读/双 400 拒全通并**复原**。\n",
    "> ✅ **验证**：断言 **19 ＋ 4** 条 · **反向灵敏度 15/15（首跑抓出 4 处假绿，已改紧）** · MD5 复原 · 四态 **487 不变** · 六把尺子全 0。\n",
    "> ⏭️ **下一件**：`TAIL-35`（`m04` 的 Excel 导入 ＋ 手动行壳侧入口）；其后是其余页接线，再回主线 M5/M6。\n",
]
print("③ §⑦ 已换成新一轮（并去掉重复段）")

DOC.write_text("".join(lines), encoding="utf-8")
print(f"\n写好：{DOC.name}")
print("下一步：跑 tools/doc_audit.py 复核（T3/T4 会查路径与状态数字）")
