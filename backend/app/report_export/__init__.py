"""成品文件写出（**模板法**）—— `MOD-07` 收发结存 / `MOD-08` 库存单据明细表 共用。

## 为什么单独立一个包（而不是塞进 mod07 / mod08）

两条导出链路**共用同一套引擎、同一份模板目录、同一套闸门**；按本仓纪律（§八）
「多路由共用件必须抽**中立件**，否则不是循环 import 就是两份实现」——
放在 `mod07` 里会让 `mod08` 反向依赖材料域，放 `mod08` 同理。故中立成包。

## 成员与职责

| 文件 | 职责 | 来源 |
|---|---|---|
| `xl_common.py` | 最底层原语（`NS` / `fmt_num` / `norm_num` / `parse_shared_items`）· **中立件** | 2026-09-18 从 `tpl_engine` 拆出 |
| `pivot_cache.py` | 透视缓存两件重建 ＋ **缓存级对账** | 2026-09-18 从 `tpl_engine` 拆出 |
| `sheet_display.py` | **透视显示区**重建 ＋ 显示区对账（`TAIL-43`） | 新写（2026-09-18） |
| `tpl_engine.py` | 编排（`rebuild()`）＋ 数据侧（读数据 / sharedStrings / 数据 sheet / pivotTable） | **逐字移植**自交付面 `PRD素材包-20260911/input/common_tpl.py` |
| `schema_cols.py` | 两张表的**列定义**（`SFJC_HEADER` / `KCDJ_COLS` 等） | 逐字移植自 `input/schema_cols.py` |
| `resources.py` | 模板路径**唯一出口** ＋ 缺失/损坏闸门（SHA256） | 新写（依据 = `docs/reference/template-export.md` §五） |
| `setl_export.py` | 收发结存：分仓库 xlsx ＋ 总表 → **zip** | 移植自 `input/sfjc_process.py`（数据源已换成库） |
| `kcdj_export.py` | 库存单据明细表：1 个 xlsx（`报表1` ＋ 两张真透视） | 移植自 `input/kcdj_process.py`（数据源 = i8 源字节） |
| `service.py` | **中立编排**：从库里读明细行 → 生成 → 返回产物路径 | 新写 |

⚠️ **三个中立件是从 `tpl_engine.py` 拆出来的**（2026-09-18：它加完 `TAIL-43` 显示区后 **934 行 > 600
= 禁合入**）⇒ 拆法 = 「**只搬代码**」，并在 `tpl_engine` 里**再导出**（全站引用都是 `tpl_engine.X`
形式 ⇒ 调用方**零改动**）。拆件后四个文件均 < 400 行。

## ⚠️ 三条口径（回 `docs/reference/template-export.md` 与《说明书》）

1. **成品 = 以「用户手作成品 xlsx」为基底做 `zip` 字节替换** —— ⛔ 不用 openpyxl 去"画"透视表；
   透视表**原样留在模板里**，只把背后的缓存与行列范围换成本月的，并置 `refreshOnLoad="1"`。
2. ⛔ **§7.1 那两条（`DATA_START` / 尾部行块派生）管的是路径①，不管这两份报表** —— 别照抄错。
3. ⚠️ `sfjc_process.update_sheet_data()` 的 `ws.delete_rows()` 与 `gen_data_sheet()` 的整块
   `<sheetData>` 替换，**只对"数据区下面没有脚注/合并块"的 sheet 安全**；
   将来给这两份表加脚注必须改走 §7.1 的派生写法（否则静默抹掉）。
4. ⭐⭐ **透视的「显示区」必须自己重建**（`TAIL-43` · 2026-09-18 真机实测根因）：
   模板法只换缓存/定义**不够** —— 本月数据比模板少时，透视 `location` 收缩，模板旧渲染行
   落到新 `location` **之外**，**任何应用都不会去清它们** ⇒ 用户读到**上个月**的数。
   ⚠️ `refreshOnLoad` 只保证刷新**缓存**，**不保证**清 `location` 之外的残留 ⇒ 靠不住。
   ⇒ 显示区重建 + 显示区对账见 `sheet_display.py`；收发结存那张 `Sheet1` 同理（走 openpyxl 那条路）。
"""

__all__: list[str] = []
