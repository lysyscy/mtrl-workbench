"""`TAIL-209` 余项 ①（同类 3 处工程代号）＋ ③（`m06_proc` 那条 127 字的域自报文案）。

## ① 3 处（用户可见但不在"弹窗说明块"扫描面里的）
`actions.js` 按钮「从付款域引用（R8）」· `actions.js` 弹窗内「发票子表（ENT-07）」·
`core.js` 卡头「待人工建档（链路 A · 多仓库）」。

## ③ 只动 `m06_proc.note`（127 字）
⚠️ **`m11_jc.note`（171 字）⛔ 不动** —— 它是**判据钉着的**：
已归档历史：`tests/test_acc_jc_import_batch.py::test_导入页覆盖语义文案在位` 要求它含「只动这 6 列」＋ 6 个列名 ＋
「合同价 / 供应商 / 合同日期 / 甲方单位」「不会被覆盖」「整批回滚」「覆盖语义」——
依据 = 用户 2026-09-25 原话「界面没说清哪些列会被覆盖 ⇒ 易误操作」⇒ **那是用户要的那句话，⛔ 不是冗余**。
（本条正是"先核判据再删"的一次实例：量出 171 字想瘦，核完发现**不该瘦**。）

⚠️ 每条断言**命中恰好 1 次**（含 CRLF 变体）⇒ 不命中**整批不写**；被 §13.6 入门口令点名 ⇒ 必有 `main()`。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
W = ROOT / "backend" / "app" / "web"
BACK = ROOT / "backend" / "app"

EDITS: list[tuple[str, str, str]] = [
    # ① 三处工程代号（都在"用户可见串"里）
    ("web/shell/actions.js",
     ">从付款域引用（R8）</button>",
     ">从付款域引用</button>"),
    ("web/shell/actions.js",
     "<b>发票子表（ENT-07）</b>：一合同",
     "<b>发票子表</b>：一合同"),
    ("web/shell/core.js",
     "<h4>待人工建档（链路 A · 多仓库）<span class=\"sp\">",
     "<h4>待人工建档<span class=\"sp\">"),
    # ③ `m06_proc` 的域自报文案：删「机制交代」（历史段/正式段怎么切、来源），留"会做错"的那几句
    ("mod06_proc/imp_spec.py",
     "    note=\"必须有「核算月」（真模板里那列叫「时间」，也认 Excel 序列号）与至少一列材料列\"\n"
     "         \"（**只填了机械列的行也算数据**）；落库时要选**项目**（仓库名）—— 过程资料按项目分别存。\"\n"
     "         \"机械 6 列**照样导入**（进历史段；那之后它们的来源就按截止核算月切：历史段 = 导入值、正式段 = 手录）。\",",
     "    note=\"必须有「核算月」（真模板里那列叫「时间」，也认 Excel 序列号）与至少一列材料列；\"\n"
     "         \"**只填了机械列的行也算数据**。落库前要选**项目**（按项目分别存）—— 机械 6 列**照样导入**。\","),
]


def main() -> int:
    files: dict[str, str] = {}
    bad: list[str] = []
    for name, old, new in EDITS:
        if name not in files:
            files[name] = (BACK / name).read_text(encoding="utf-8", newline="")
        for o, w in ((old, new), (old.replace("\n", "\r\n"), new.replace("\n", "\r\n"))):
            if files[name].count(o) == 1:
                files[name] = files[name].replace(o, w, 1)
                break
        else:
            bad.append(f"{name}: 命中 {files[name].count(old)} 次 ⇒ {old[:52]!r}")

    if bad:
        if all(files[n].count(new) >= 1 for n, _, new in EDITS):
            print(f"✔ 本批 {len(EDITS)} 处**已经改过**（幂等）")
            return 0
        print("⛔ 以下没命中（整批不写）：")
        for b in bad:
            print("   ", b)
        return 1

    for name, text in files.items():
        (BACK / name).write_text(text, encoding="utf-8", newline="")
        print(f"✅ 已改 backend/app/{name}（{len(text)} 字节）")
    print(f"\n共 {len(EDITS)} 处替换 · 全部命中 1 次 ✔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
