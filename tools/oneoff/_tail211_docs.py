"""`TAIL-211` **立·办·销**的台账改动（§15 §一→§四 ＋ 计数两处 ＋ §14.3）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail211_docs.py`          # 干跑
      `… --apply`
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / ".codebuddy" / "plans" / "开发计划-主文档.md"

ROW4 = (
    "| `TAIL-211` | 💬 **后端的「用户可见串」没有机器眼**（现役源码扫查**靶全是壳** ⇒ "
    "后端拼进**回执 / 报错 / 说明**的串**谁都不守**） "
    "| **销号依据** = 用户 2026-10-01「提交；继续」（承接 `TAIL-210` 改词轮撞出的三例：`（API-06）` · `链路 A` · `（M5 未开工）`）"
    "⇒ **当日立 · 当日办 · 当日销**：① **先量** = `tools/oneoff/_text_ctx9.py --codes`（`ast` 取**字符串常量** · 跳过文档字符串）⇒ **11 处**命中；"
    "② **判据的两条边界**（都是量出来的）：**跳过「裸字符串语句」**（module / class / function 的 docstring ＋ **属性 docstring** ＋ "
    "拿字符串当注释 —— 值**无处可去**，不是上屏文字）＋ **代号被反引号包住不算**（本仓工程侧笔记的记号；真例 = 守卫表 "
    "`FORBIDDEN_TEXTS` 的墓碑值「（业务上无此数据，`DEV-R-03`）」）⇒ 11 → **9 处真缺陷**；"
    "③ **清 9 处**（`tools/oneoff/_tail211_codes.py`）：`（决策 1 兜底）` · `（决策 2：…）`×2"
    "（⚠️ **口径公式「普通项目 ↔ 仓库 = 1 : 1」保留** —— `test_acc_prj_auto` 钉着它，删代号别把口径一起删） · `（DEV-P-04）` · `（链路 A）` · "
    "`（API-05）`×2 · `（R1）` · 以及 `report_export/resources.py` 那句给用户看的 `_RETRY` 里写着的 `ops/模板法导出-实测结论.md` "
    "＋ 交付面 / 仓内两条路径（改成「请让维护人重新部署导出模板…」）；"
    "④ **判据** = `tests/test_ux_text.py::test_后端的用户可见串里也不许出现工程代号`（`@acc()` ⇒ **判据点仍 644**）＋ "
    "**自证** `tools/oneoff/_tail209_mark_proof.py` **4 → 5 条**（新增 `T5`：写进后端**字符串**必红 ＋ ⭐ **注释 / 裸字符串语句不算** ＋ "
    "**两件**逐字节还原）；⑤ **闸门** = pytest **1403 / 0** · 16 把尺子 `rc=0 / BAD: []` · 四态 **644 / 0** · 服务**已重启**（改过后端 `.py`）；"
    "⚠️ **本轮没动壳** ⇒ 壳基线**不重盖**；⚠️ **余项**（登记不办）：`resources.py` 里 `MustReportError` 的模板**文件路径**仍上屏"
    "（判据靶外 —— 那是「报错不人话」的另一类）| 2026-10-01 |"
)

NOTE15 = (
    "> ⭐ **2026-10-01（深夜之六）**：新尾巴 `TAIL-211`（**后端的用户可见串没有机器眼**）**当日立 · 当日办 · 当日销**"
    "（判据已立 ＋ 当场清 **9 处** ⇒ 依据见 §四）⇒ A 类 **2 → 1 条**、已销号 **212 → 213**（**两处计数同改**：本节顶部 ＋ §0.2）。"
)


def _read(p: pathlib.Path) -> str:
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def _write(p: pathlib.Path, text: str) -> None:
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main() -> int:
    apply = "--apply" in sys.argv
    lines = _read(P).split("\n")
    bad: list[str] = []

    def idx_of(pred, why: str) -> int:
        hits = [i for i, x in enumerate(lines) if pred(x)]
        if len(hits) != 1:
            bad.append(f"{why} —— 命中 {len(hits)} 次（要 1）")
            return -1
        return hits[0]

    i_one = idx_of(lambda x: x.startswith("| `TAIL-211` | 💬 **后端的"), "§15 §一 的 TAIL-211 行")
    i_four = idx_of(lambda x: x.startswith("| `TAIL-210` | 💬 **第二轮前端审计的两件余项**"), "§15 §四 的 TAIL-210 行（插在它前面）")
    i_top = idx_of(lambda x: x.startswith("A 类 **2** 条 · B 类 **0** 条"), "§15 顶部计数")
    i_02 = idx_of(lambda x: x.startswith("A 类 **2** 条 · B 类 0 · C 类 **0** · 已销号 **212**"), "§0.2 计数")
    i_143 = idx_of(lambda x: x.startswith("| `TAIL-211` **后端的"), "§14.3 的 TAIL-211 排期行")
    i_note = idx_of(lambda x: x.startswith("> ⭐ **2026-10-01（深夜之五）**"), "§15 顶部的「深夜之五」注")
    if bad:
        print("不达标：")
        for x in bad:
            print("   ✗", x)
        return 1

    new: list[str] = []
    for i, x in enumerate(lines):
        if i == i_top:
            x = "A 类 **1** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **213** 条"
        elif i == i_02:
            x = "A 类 **1** 条 · B 类 0 · C 类 **0** · 已销号 **213**"
        elif i == i_143:
            x = x.replace("| `TAIL-211` **后端的", "| ✅ `TAIL-211` **后端的", 1)
            x = x.replace("| **随时**（⚠️ 先量再立", "| ✅ **已办 · 2026-10-01 销号（⇒ §15 §四）**｜原建议时机 **随时**（⚠️ 先量再立", 1)
        if i == i_one:
            continue                                   # ⛔ 从 §一 删掉（做掉的移进 §四）
        if i == i_four:
            new.append(ROW4)
        new.append(x)
        if i == i_note:
            new.append(NOTE15)
    out = "\n".join(new)
    assert "本轮改词时**撞出来的**" not in out, "§一 那行没删掉"
    assert out.count(ROW4) == 1 and out.count(NOTE15) == 1
    assert "A 类 **1** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **213** 条" in out
    assert "A 类 **1** 条 · B 类 0 · C 类 **0** · 已销号 **213**" in out
    print("§15 §一 删 1 行 · §四 加 1 行 · 计数 2 处 · §14.3 标已办 · 顶部加 1 行注")
    if not apply:
        print("（干跑 —— ⛔ 没写盘）")
        return 0
    _write(P, out)
    print("✅ 已写", P.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
