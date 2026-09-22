"""更新交接文件 `执行情况-主文档.md`：§⑥ 追加本轮记录、§⑦ 换成下一轮任务。"""

from __future__ import annotations

import pathlib

P = pathlib.Path(r"D:\dev\mtrl-workbench\.workbuddy\plans\执行情况-主文档.md")
src = P.read_text(encoding="utf-8")

HEAD6 = "## ⑥ 当前状态（**每次更新这一段**）\n"
NEW6 = """
- **⭐⭐ 本轮（2026-09-18 · 用户裁定「先完成第 1、2 项」）`m14` 壳侧接线 ＋ `TAIL-04` 收发结存切片落地**
  · **① `m14` 规则配置接线完成**：壳侧删演示常量 `RULE_EX` 的 4 条演示值 ⇒ 改由 `reloadM14()` 从
    `/api/m14/rules` 填；三个写动作走后端（`API.m14RuleAdd/Set/Del`）；
    ⭐ **规则类别由自由文本改成后端 `kinds` 撑起的下拉**（填「收款单位」后端必拒、填错别字更看不出问题）。
    `V.m14` **只改 1 行**（那句「命中值为演示值」接线后是假话）⇒ 已登记 `ui_parity_expected.txt`。
    ⭐ **`ACC-CFG-RULE-001` 五个判据点全转绿**（5/5）。
  · **② `TAIL-04` 收发结存切片落地（真机验收）**：新包 `backend/app/report_export/`（**中立件**）——
    `tpl_engine.py` / `schema_cols.py` / `setl_export.py` **逐字移植**自交付面素材包；
    `resources.py`（模板路径**唯一出口** ＋ 缺失/损坏 **SHA256 闸门**）与 `service.py`（从库读明细 → 生成）新写。
    新增 `GET /api/m07/settlement/export`；壳侧 `zipSfjc` 由**假成功改为真下载**
    （按 `content-type` 分流：JSON ⇒ 弹中文原因，否则下载；文件名由后端 `X-Export-Filename` 带出）。
    真机：**480 行 / 8 仓 → zip**（8 个分仓库表 ＋ 总表）；**库 SQL ↔ 成品透视 ↔ 分仓库文件 三条独立路径逐分对平**
    （`tools/_verify_tail04.py`，可复跑）；`xlsxwriter==3.2.9` 已补进 `requirements.txt`。
  · ⭐⭐ **顺手实测纠正素材包一处**：`refreshOnLoad` 原加在 `<pivotTableDefinition>` 上**不合 schema**
    （openpyxl 读回当场 `TypeError`），唯一合法位置 = `pivotCacheDefinition1.xml` 的 `<pivotCacheDefinition>`；
    根因 = 原核对只做 `'refreshOnLoad="1"' in 字符串`（**存在性检查看不见结构错**）⇒ 已同步纠正 `ops/` 文档（§六/§七）。
  · ⭐⭐ **两处假绿被自己的检查抓出**（都补紧）：① `ACC-SETL-001/001-08` 原来只查 `manifest`
    （**清单自己说自己**）⇒ **导出根本没实现也照绿**；补成「清单 == 真产出」后**当场抓出两处命名不一致**
    （清单 `…2026-08…` vs 真产物 `…2026年8月…`）⇒ 命名统一到 `domain.period_label` **唯一出口**。
    ② 主题色值守卫扫到移植来的 **xlsx 表头底色** ⇒ 按 §十一「打印件颜色不属于站点主题」同一理由加豁免
    （`report_export/`），并**正反两面实测**（非豁免目录塞色值仍变红 · 豁免目录塞色值仍绿）。
  · **数字**：四态 **487 = 绿 411 · 红 0 · 待建 10 · 未绑定 66**（本轮起点 405）；
    六把尺子**全 0**；`chain_audit` 认领 102 条**已接 72 → 73**（R 链路「打包 zip 交资产处」转正）。
    断言：`test_wired_m14.py` 5 条（绑 5 点）· `test_tail04_export.py` 5 条 ·
    反向灵敏度 `_mut_m14.py` **14/14** · `_mut_tail04.py` **11/11**（MD5 逐字节复原）。
  · ⚠️ **一条要带走的教训**：**钉「临时状态」的断言要跟着状态走** ——
    `test_wired_m07.py::test_导出如实标注未落地` 在 `TAIL-04` 落地后**当场变红**，
    那是「该改断言」的信号、不是实现错（已改成「导出已落地为真下载」）。
  · ⚠️ **`TAIL-17` 提醒（每次都要看一眼）**：交付面文档不自动打开预览。
"""

if "本轮（2026-09-18 · 用户裁定「先完成第 1、2 项」）" in src:
    raise SystemExit("⑥ 已含本轮记录，未重复追加")
if src.count(HEAD6) != 1:
    raise SystemExit(f"⛔ §⑥ 标题锚命中 {src.count(HEAD6)} 次")
src = src.replace(HEAD6, HEAD6 + NEW6, 1)

# ---------------------------------------------------------------- §⑦
HEAD7_RE = "## ⑦ 本次任务"
i = src.index(HEAD7_RE)
j = src.index("## ", i + 5)
NEW7 = """## ⑦ 本次任务（**替换成你要做的这一件**）

> ⭐ **本轮任务（2026-09-18 · 继续推进「不需要用户裁定」的那些）**
> ① **`TAIL-04` 剩余切片** —— 下一件是**库存单据明细表**（`kcdj`）：引擎已同步修好，
>    只差把 `kcdj_export.py` 的 `read_data(src)` 换成「从 `inv_detail` 建 `data`」＋ 端点
>    ＋ 壳侧 `m08` 的「导出 Excel（R1）」；之后才是**其余页面的路径①模板填充**
>    （⚠️ 与模板法**两类做法不同、别混做**，见 `ops/模板法导出-实测结论.md` §一/§三）。
> ② **`TAIL-30`-③ 指认入口** —— 语义已确认（计划 §17：只查本地档案表 · 归一化全名精确相等 ·
>    命中里先判壳 · 落点 `m01` · 本轮只指定行）⇒ 后端「候选清单 ＋ 指定扶正」＋ `m01` 壳入口
>    ＋ 材料侧抓取回执补一句「待人工 N 条，去 `m01` 处理」（**现状缺口：壳侧抓取没露 `recovery`**）。
> ③ **`TAIL-41`**（未命中清单在抓取成功后不清空）—— 随时可做、成本低。
> ④ 其余页接线：**`m02`**（后端已有 JSON API，只差壳侧适配）。
>    `m10`/`m12`/`m13`/`m15` 后端仍是空模块 ⇒ 属未开工阶段，**不动**。
> ⛔ 交付文档（**主要是 `.md`**）不自动打开预览 —— 给绝对路径 ＋ 一句话摘要。
"""
src = src[:i] + NEW7 + src[j:]

P.write_text(src, encoding="utf-8")
print("✅ 交接文件已更新：§⑥ 追加本轮 · §⑦ 换成下一轮")
