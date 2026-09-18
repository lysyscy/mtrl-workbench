"""成品文件写出（**模板法**）—— `MOD-07` 收发结存 / `MOD-08` 库存单据明细表 共用。

## 为什么单独立一个包（而不是塞进 mod07 / mod08）

两条导出链路**共用同一套引擎、同一份模板目录、同一套闸门**；按本仓纪律（§八）
「多路由共用件必须抽**中立件**，否则不是循环 import 就是两份实现」——
放在 `mod07` 里会让 `mod08` 反向依赖材料域，放 `mod08` 同理。故中立成包。

## 成员与职责

| 文件 | 职责 | 来源 |
|---|---|---|
| `tpl_engine.py` | 通用重建引擎（sharedStrings / 数据 sheet / 透视缓存 / pivotTable / 对账） | **逐字移植**自交付面 `PRD素材包-20260911/input/common_tpl.py` |
| `schema_cols.py` | 两张表的**列定义**（`SFJC_HEADER` / `KCDJ_COLS` 等） | 逐字移植自 `input/schema_cols.py` |
| `resources.py` | 模板路径**唯一出口** ＋ 缺失/损坏闸门（SHA256） | 新写（依据 = `ops/模板法导出-实测结论.md` §五） |
| `setl_export.py` | 收发结存：分仓库 xlsx ＋ 总表 → **zip** | 移植自 `input/sfjc_process.py`（数据源已换成库） |
| `service.py` | **中立编排**：从库里读明细行 → 生成 → 返回产物路径 | 新写 |

⏳ **`kcdj_export.py`（库存单据明细表）尚未移植** —— 属 `TAIL-04` 的**下一片**。
   搬运要点与 `setl_export` 相同：把 `common_tpl.read_data(src, col_count=28)` 换成
   「从 `inv_detail` 建 `data`」（`cfg['data']` 已支持），并把 `TEMPLATE` 指向 `resources.KCDJ_TEMPLATE`；
   ⚠️ 移植前**别把原样拷贝的文件放进树里**（`import` 会因裸名 `common_tpl` 失败 —— 实测踩过）。

## ⚠️ 三条口径（回 `ops/模板法导出-实测结论.md` 与《说明书》）

1. **成品 = 以「用户手作成品 xlsx」为基底做 `zip` 字节替换** —— ⛔ 不用 openpyxl 去"画"透视表；
   透视表**原样留在模板里**，只把背后的缓存与行列范围换成本月的，并置 `refreshOnLoad="1"`。
2. ⛔ **§7.1 那两条（`DATA_START` / 尾部行块派生）管的是路径①，不管这两份报表** —— 别照抄错。
3. ⚠️ `sfjc_process.update_sheet_data()` 的 `ws.delete_rows()` 与 `gen_data_sheet()` 的整块
   `<sheetData>` 替换，**只对"数据区下面没有脚注/合并块"的 sheet 安全**；
   将来给这两份表加脚注必须改走 §7.1 的派生写法（否则静默抹掉）。
"""

__all__: list[str] = []
