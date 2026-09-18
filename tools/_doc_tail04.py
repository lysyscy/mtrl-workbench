"""`TAIL-04`（收发结存切片）落地后的三处文档更新：
① `ops/模板法导出-实测结论.md` 追加 §六 / §七（**实测纠正** `refreshOnLoad` 的位置 ＋ 数据来源选择）
② 计划 §15 A 类 `TAIL-04` 行的状态更新（部分落地 ＋ 余下是什么）
③ 计划 §14.3 `TAIL-04` 排期行的「前置 / 触发」补一句

断言每处唯一命中；不命中就抛错。
"""

from __future__ import annotations

import pathlib

ROOT = pathlib.Path(r"D:\dev\mtrl-workbench")
OPS = ROOT / "ops" / "模板法导出-实测结论.md"
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"

steps: list[str] = []


def sub(path: pathlib.Path, old: str, new: str, what: str) -> None:
    t = path.read_text(encoding="utf-8")
    n = t.count(old)
    if n != 1:
        raise SystemExit(f"⛔ [{what}] 锚命中 {n} 次（要求恰好 1 次）")
    path.write_text(t.replace(old, new, 1), encoding="utf-8")
    steps.append(what)


# ============================================================== ① ops 文档
APPEND = """

---

## 六、本仓接入时的**实测纠正**（2026-09-18 · `TAIL-04` 落地）

接入工程仓时用 `openpyxl` **读回**成品工作簿（**不带 `read_only`**，会解析透视），发现 §一 第 6 处
那一步**加错了位置** —— 原实现（以及本工程移植的第一版）往 `<pivotTableDefinition>` 上加
`refreshOnLoad="1"`，读回时当场报：

```
TypeError: TableDefinition.__init__() got an unexpected keyword argument 'refreshOnLoad'
```

`refreshOnLoad` 的**唯一合法归属** = `xl/pivotCache/pivotCacheDefinition1.xml` 的
**`<pivotCacheDefinition>`** 元素（依据 = OOXML 的 `CT_PivotCacheDefinition`；
openpyxl 把它建模在 `openpyxl.pivot.cache.CacheDefinition.refreshOnLoad`）。
放到 `workbook.xml` 的 `<pivotCache>` 上**同样不合 schema**（`PivotCache … unexpected keyword`）
—— 两个位置都实测试过。

> ⚠️ **为什么原核对没发现**：`kcdj_process.verify_output()` 只做 `'refreshOnLoad="1"' in 字符串`
> —— **字符串在、属性位置错，照样通过**。「存在性检查」看不见结构错（同族坑：只查"有没有那个字"，
> 不查"结构对不对"）。
> ⇒ **本工程的做法**（`app/report_export/`）：位置按上述订正，并且**把「用 openpyxl 读回成品
> （不带 `read_only`）」作为一道结构闸门** —— 它当场就能抓出这类错
> （`tools/_verify_tail04.py` 的第 ② 步就是这个作用）。

## 七、导出**数据来源**的落地选择（2026-09-18）

素材包那两个 process 脚本的数据来源是 **i8 导出件（xlsx 文件）**；本工程的明细在**库**里
（`setl_detail` 的 17 列与导出表头**一一对应**）⇒ 接入时改成「**从库重建 DataFrame**」
（`report_export/setl_export.py::frame_from_rows`），理由：

- 生产环境的数据主人在库；⛔ 不让导出依赖一份原始文件 ——
  否则**历史月份**与**手动导入（§3.6 降级路径）**来的月份根本导不出来；
- **端到端交叉印证**（2026-09，两条路径互证而非同源一致）：

  | 口径 | 库 → DataFrame → 成品 | §二 那次（i8 文件路径） |
  |---|---|---|
  | 收金额总计 | **1,218,821.92** | **1,218,821.92** |
  | 行数 / 仓库数 | 480 / 8 | 480 / 8 |

⇒ 两条**独立实现**逐分相同 ⇒ 说明「库 17 列 → 导出表头」的映射是对的（若映射错一列，
只会静默产出一份"看着正常、数是错的"成品）。

**另外两处本仓适配**（都写在代码里、带 `⭐ 本仓适配` 注释）：

1. **对账不过 ⇒ 硬失败**。素材包把 `verify_cache` 的问题**打印出来给人看**；生产里必须
   `raise` —— ⛔ 绝不允许静默交付一个数字对不上的成品（那是最坏的失败形态：文件看着正常、数是错的）。
2. **删掉模块级 `warnings.filterwarnings('ignore')`**：那是**库**，`import` 就全局静音全站告警。
"""

if "## 六、本仓接入时的**实测纠正**" in OPS.read_text(encoding="utf-8"):
    print("① ops 文档已含 §六，跳过")
else:
    with open(OPS, "a", encoding="utf-8") as fh:
        fh.write(APPEND)
    steps.append("① ops 文档追加 §六 / §七（refreshOnLoad 位置纠正 ＋ 数据来源选择）")

# ============================================================== ② §15 TAIL-04 状态
sub(
    PLAN,
    "| 立刻（用户 2026-09-18 裁定「现在就做」· 原排 M6） | **进行中**（2026-09-18 起：模板本体已在仓、方法已实测、素材包实现现成 ⇒ 只差移植 ＋ 接线） |",
    "| 立刻（用户 2026-09-18 裁定「现在就做」· 原排 M6） | **进行中**（2026-09-18）："
    "✅ **收发结存切片已落地并真机验收** —— 移植引擎 ＋ `app/report_export/` ＋ "
    "`GET /api/m07/settlement/export` ＋ 壳侧 `zipSfjc` 真下载；"
    "真机：480 行 / 8 仓 → zip（8 分仓库 ＋ 总表），**库 SQL ↔ 成品透视 逐分对平**（第三条独立路径）；"
    "⭐ 顺带**实测纠正**素材包一处：`refreshOnLoad` 原加在 `<pivotTableDefinition>` 上**不合 schema** "
    "（正确位置 = `pivotCacheDefinition`，见 `ops/模板法导出-实测结论.md` §六）。"
    "⏭️ **余下**：① 库存单据明细表（`kcdj`，引擎已同步修好、只差接）② 其余页面的路径①模板填充 ｜",
    "② §15 TAIL-04 状态 → 收发结存切片已落地",
)

# ============================================================== ③ §14.3 排期行
sub(
    PLAN,
    "| 切片 6 · 实测结论见工程仓 ops/模板法导出-实测结论.md |",
    "| 切片 6 · 实测结论见工程仓 ops/模板法导出-实测结论.md。"
    "⭐ **2026-09-18 起按报表拆切片**：收发结存**已落**，库存单据明细表与其余页面的路径①模板填充待做 |",
    "③ §14.3 TAIL-04 排期行补切片状态",
)

print("✅ 文档更新完成，共", len(steps), "处：")
for s in steps:
    print("   ·", s)
