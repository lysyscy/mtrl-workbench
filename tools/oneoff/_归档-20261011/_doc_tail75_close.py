"""一次性：把 §15 台账里的 **`TAIL-75`** 行从「A 类」搬进「已销号」（`TAIL-75` 销号 · 2026-09-23）。

为什么用脚本：那一行有 **4k+ 字符**（B1→B5d 全过程的流水），逐字复制进编辑工具不现实。
本件只做**三件事**（⛔ 不动其它任何行）：
1. 删掉 A 类表里那一行（以 `| TAIL-75 |` 开头 —— 本仓台账里那个名字外面套着反引号；
2. 在「### 四、已销号」的表头下方插入新的销号行；
3. 打印前后行数 + 校验（A 类少 1 行、已销号多 1 行）。
⚠️ 计数（§0.2 / §15 顶部那两处「A 类 N 条 · 已销号 M 条」）由**人读的编辑**另行改，本件不碰。
"""

from __future__ import annotations

import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DOC = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
HEADER = "| # | 事项 | 销号依据 | 日期 |"

ROW = (
    "| `TAIL-75` | ⭐⭐ **映射式通用导入**（`D23`）：`mapping.py` ＋ 通用 API 面 ＋ **全站导入面替换** ＋ "
    "壳侧统一入口 | ✅ **已销号（2026-09-23）—— `B1`~`B5d` 全落 ＋ 旧导入面**连件删除**（用户裁定）。**"
    "**最终形态**：四个真域挂在通用面（`m04_plan` / `m05_flow` / `m06_proc` / `m11_jc`，"
    "`/api/imp/{域}/{schema,parse,preview,commit,rollback}`），壳「全局 → 数据导入」是**唯一入口**；"
    "**页内导入向导全撤**：`m05imp`（用户裁定 `B`）· `m06imp`（`B5c`）· `m08imp`（2026-09-22 用户裁定「不要了」）· "
    "**`m11` 的页内向导 ＋ `m04` 的旧端点**（2026-09-23 用户裁定：「导入基本上只在刚开始用系统时导入一次，"
    "之后就实时更新了」⇒ **只留通用面**）。<br>**判据**：`ACC-IMP-MAP-001`（001-01~001-13）＋ "
    "`ACC-PLAN-IMPORT-001`（001-08/09，落点已改指通用面、**判词未改**）＋ `ACC-PROC-IMPORT-001`（4 点）＋ "
    "`ACC-FLOW-IMPORT-001`（001-01 同批改写 · 001-04 判词未改）。<br>**旧端点删除的代价已记账**：`m05` 旧页按"
    "**源表列位置**读（无表头也读得动）那条入口没了（用户拍板时知情）；域内解析出口**保留**"
    "（`m05` 留 `parse_rows` · `m06` 留 `parse_sheet` · `m04` 留 `parse_workbook` 等）。<br>"
    "**闸门**：全套 pytest rc=0 · 四态 **555 全绿** · 13 把尺子全 0 · 交付面四检全 0 · 真机 `_shell_smoke` rc=0 · "
    "反向灵敏度 `_mut_mapping` 7/7 · `_mut_impkit`（靶已改到通用面）有区分力。 | 2026-09-23 |"
)


def main() -> int:
    raw = DOC.read_bytes()
    md5_before = hashlib.md5(raw).hexdigest()
    text = raw.decode("utf-8")
    lines = text.split("\n")

    hit = [i for i, ln in enumerate(lines) if ln.startswith("| `TAIL-75` |")]
    if len(hit) != 1:
        print(f"❌ 期望 A 类里**恰好一行** `| \\`TAIL-75\\` |`，实得 {len(hit)} ⇒ 先看文档再改")
        return 1
    i = hit[0]
    n_before = len(lines)
    del lines[i]

    h = [j for j, ln in enumerate(lines) if ln.strip() == HEADER]
    if len(h) != 1:
        print(f"❌ 已销号表头 `{HEADER}` 命中 {len(h)} 次（期望 1）⇒ 先看文档再改")
        return 1
    lines.insert(h[0] + 1, ROW)

    DOC.write_text("\n".join(lines), encoding="utf-8")

    after = DOC.read_text(encoding="utf-8").split("\n")
    ok = (len(after) == n_before and
          not [ln for ln in after if ln.startswith("| `TAIL-75` |") and "销号" not in ln[:80]] and
          sum(1 for ln in after if ln.startswith("| `TAIL-75` |")) == 1)
    print(f"搬行：A 类删 1 行（原第 {i + 1} 行）· 已销号插入 1 行 ⇒ 总行数 {n_before} → {len(after)}"
          f"（应相等）")
    print(f"改前 MD5 {md5_before}")
    print("✅ 完成 —— ⚠️ 计数（A 类 / 已销号）请另行手改并跑 `doc_audit` 核对" if ok else "❌ 校验未过，请看上面")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
