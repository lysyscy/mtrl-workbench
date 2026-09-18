"""本轮收尾的三处记忆写入：日志 append ＋ 主册 §十二 一条通法 ＋ 细则 §二十。"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
LOG = ROOT / ".workbuddy" / "memory" / "2026-09-18.md"
MAIN = ROOT / ".workbuddy" / "memory" / "MEMORY.md"
DETAIL = ROOT / ".workbuddy" / "memory" / "MEMORY-细则.md"

# ============================================================== ① 日志
LOG_BLOCK = """

## 2026-09-18 · 轮次：`m14` 壳侧接线 ＋ `TAIL-04` 收发结存切片（用户裁定「先完成第 1、2 项」）

**① `m14` 规则配置接线**（`TAIL-40` 余下的壳侧部分）
- 删演示常量 `RULE_EX` 的 4 条演示值 ⇒ `let RULE_EX = []` ＋ `RULE_RAW`（写动作要 id）＋ `RULE_KINDS` ＋ `RULE_SRC`；
  `reloadM14()` 从 `/api/m14/rules` 落定；三个写动作走后端；**规则类别由自由文本改成后端 `kinds` 撑起的下拉**。
- `V.m14` **只改 1 行**（「命中值为演示值」接线后是假话）⇒ 登记 `ui_parity_expected.txt`；
  `ui_parity.py` 的 `U2b` 登记表加 `m14`（否则这页没人看管"演示数据清没清"）。
- ⭐ 绑 `ACC-CFG-RULE-001` **五个判据点全绿**（5/5）。断言 `test_wired_m14.py` 5 条 ·
  反向灵敏度 `_mut_m14.py` **14/14**（首跑抓出 **1 处假绿**：`data-act="editKw"` 被 `editKwX` 前缀喂饱）。
- 真机：壳自检 ⑫ 全绿（条数 == 后端 · 类别不含「收款单位」· 来源如实显示 · 卡头条数实时算）
  ＋ ⑫b **写路径净零往返**（新增探针 ⇒ 条数 +1 ⇒ 按 **id 差集**删掉 ⇒ 回原样，库无残留）。

**② `TAIL-04` 收发结存切片落地**（导出成品 · 模板法）
- 新包 `backend/app/report_export/`（**中立件**，两条导出链路共用）：`tpl_engine.py`/`schema_cols.py`/`setl_export.py`
  **逐字移植**；`resources.py`（模板路径唯一出口 ＋ 缺失/损坏 **SHA256 闸门**）、`service.py`（从库读明细 → 生成）新写。
- 数据来源改**从库重建 DataFrame**（`setl_detail` 17 列与导出表头一一对应）⇒ 历史月份 / 手动导入的月份都导得出。
  ⭐ **交叉印证**：库侧算出的 **收 1,218,821.92** 与实测结论里 **i8 文件路径**逐分相同，480 行 / 8 仓一致。
- `GET /api/m07/settlement/export` ＋ 壳侧 `zipSfjc` **假成功 → 真下载**（JSON ⇒ 弹中文原因，否则下载；
  文件名由后端 `X-Export-Filename` 带出，⛔ 前端不自己拼）。`xlsxwriter==3.2.9` 补进 `requirements.txt`。
- ⭐⭐ **实测纠正素材包一处**：`refreshOnLoad` 原加在 `<pivotTableDefinition>` 上**不合 schema**
  （openpyxl 读回 `TypeError`）。**唯一合法位置 = `pivotCacheDefinition1.xml` 的 `<pivotCacheDefinition>`**
  （`workbook.xml` 的 `<pivotCache>` 也试过，同样不合）。根因 = 原核对只做 `'refreshOnLoad="1"' in 字符串`
  ⇒ **存在性检查看不见结构错**。已同步纠正 `ops/模板法导出-实测结论.md`（§六/§七）。
- ⭐⭐ **假绿被自己的检查抓出**：`ACC-SETL-001/001-08` 原只查 `manifest`（**清单自己说自己**）⇒
  **导出根本没实现也照绿**；补成「清单 == **真产出**」后当场抓出**两处命名不一致**
  （清单 `…2026-08…` vs 真产物 `…2026年8月…`）⇒ 命名统一到 `domain.period_label` 唯一出口。
- 主题色值守卫扫到移植来的 **xlsx 表头底色** ⇒ 按 §十一「打印件颜色不属于站点主题」同一理由加豁免
  （`report_export/`），并**正反两面实测**（非豁免目录塞色值仍变红 · 豁免目录塞色值仍绿）。
- 断言 `test_tail04_export.py` 5 条；反向灵敏度 `_mut_tail04.py` **11/11**（MD5 复原）。

**③ 一条要带走的教训**：**钉「临时状态」的断言要跟着状态走** ——
`test_wired_m07.py::test_导出如实标注未落地` 在 `TAIL-04` 落地后**当场变红**，
那是「该改断言」的信号，不是实现错（已改成「导出已落地为真下载」）。

**数字**：四态 **487 = 绿 411 · 红 0 · 待建 10 · 未绑定 66**（本轮起点 405）· 六把尺子**全 0** ·
`chain_audit` 认领 102 条**已接 72 → 73**（R 链路「打包 zip 交资产处」转正）。

**下一轮**：`TAIL-04` 余下（库存单据 `kcdj` → 其余页路径①）· `TAIL-30`-③ 指认入口 · `TAIL-41` · `m02` 接线。
"""

t = LOG.read_text(encoding="utf-8")
if "TAIL-04 收发结存切片" in t:
    print("① 日志已含本轮，跳过")
else:
    LOG.write_text(t.rstrip("\n") + LOG_BLOCK, encoding="utf-8")
    print("① 日志已追加")

# ============================================================== ② 主册一条通法
MAIN_OLD = "- ⚠️ **「该有输出的命令返回空」≠ 绿灯** —— 先 `cat` 输出文件看是否报错。"
MAIN_NEW = (
    "- ⚠️ **「该有输出的命令返回空」≠ 绿灯** —— 先 `cat` 输出文件看是否报错。\n"
    "- ⚠️⚠️ **「清单说自己」是假绿** —— 断言只查 `manifest`/声明而不验**真产物** ⇒ **功能没实现也照绿**"
    "（实测：`ACC-SETL-001/001-08` 一直绿，而导出按钮拿不到文件；补成「清单 == 真产出」后**当场抓出两处命名不一致**）。"
    "⭐ 通法：**让「声明」与「真产出」对账**，别让声明自证。\n"
    "- ⚠️⚠️ **存在性检查看不见结构错** —— `'xxx=\"1\"' in 字符串` 通过 ≠ 那个属性放对了地方"
    "（实测：`refreshOnLoad` 加在 `<pivotTableDefinition>` 上不合 schema，字符串检查照样过）。"
    "⭐ 通法：**用解析器把产物读回来**（`openpyxl.load_workbook` 不带 `read_only`）—— 结构错当场报 `TypeError`。"
)
m = MAIN.read_text(encoding="utf-8")
if "清单说自己" in m:
    print("② 主册已含该通法，跳过")
elif m.count(MAIN_OLD) != 1:
    raise SystemExit(f"⛔ 主册锚命中 {m.count(MAIN_OLD)} 次")
else:
    MAIN.write_text(m.replace(MAIN_OLD, MAIN_NEW, 1), encoding="utf-8")
    print("② 主册 §十二 已补两条通法")

# ============================================================== ③ 细则 §二十
DETAIL_BLOCK = """

## §二十 「产物类」检查的两条通法（2026-09-18 实测 · 导出成品）

> 触发场景：**任何"生成一个文件/包"的功能**（导出、打包、生成的 xlsx / pdf / zip）。
> 两条都是"看起来验过了、其实没验"的形态，各踩过一次。

1. ⚠️⚠️ **「清单（声明）自己说自己」= 假绿。**
   实测：`ACC-SETL-001/001-08` 的判据点原文是「**产出物** = 分仓库工作簿 ＋ 1 个总表」，
   而断言只查了 `service.build_page_data()["manifest"]`（一张**清单**）——
   **导出功能一行都没实现时，本条照样是绿的**（导出按钮按下去拿不到任何文件）。
   ⇒ ⭐ **通法**：断言必须**让"清单"与"真产出"对账** ——
   拿同一份数据**真跑一次**产物生成，再核对「包内成员 == 清单条目」。
   本次补紧后**当场抓出两处命名不一致**（清单写 `…2026-08…`、真产物写 `…2026年8月…`
   —— 两处各写一份命名规则）⇒ 命名统一到 `domain.period_label` **唯一出口**。
   ⭐ 这与 §十二 的「断言要钉住那条逻辑本身，不要钉它的可观测结果」是同一条：**清单就是"可观测结果"**。

2. ⚠️⚠️ **存在性检查看不见结构错。**
   实测：素材包核对 `refreshOnLoad="1"` 用的是 `'refreshOnLoad="1"' in 字符串` ——
   字符串**在**、但那个属性**加错了元素**（`<pivotTableDefinition>` 上不合 OOXML schema），
   检查照样通过；而**用 `openpyxl` 把产物读回来**（不带 `read_only`，会解析透视）**当场报**
   `TypeError: TableDefinition.__init__() got an unexpected keyword argument 'refreshOnLoad'`。
   ⇒ ⭐ **通法**：产物类检查至少要有一步「**用正经解析器读回产物**」——
   它比任何正则/字符串检查都强，因为它替你把 schema 校验过了。
   ⚠️ 附带：`read_only=True` 会**跳过**这些解析 ⇒ 别用 read_only 当结构闸门。
"""
d = DETAIL.read_text(encoding="utf-8")
if "§二十 「产物类」检查的两条通法" in d:
    print("③ 细则已含 §二十，跳过")
else:
    DETAIL.write_text(d.rstrip("\n") + DETAIL_BLOCK, encoding="utf-8")
    print("③ 细则已追加 §二十")

for p, name in ((LOG, "日志"), (MAIN, "主册"), (DETAIL, "细则")):
    print(f"   {name}: {p.stat().st_size} 字节")
