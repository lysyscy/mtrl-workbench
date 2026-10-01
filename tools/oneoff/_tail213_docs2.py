"""`TAIL-213` **销号** 的台账 / 交接 / README 刷新（一次性 · 2026-10-01）。

逐条（都**先断言命中**，一处不达标整批不写盘）：
  ① §15 §一 删掉 `TAIL-213` 那行（已办完 ⇒ 移到 §四）
  ② §14.3 删掉 `TAIL-213` 那条（登记即排期：销号要同步销排期）
  ③ §15 §四 插入销号依据行
  ④ 计数两处同改：A 类 **2 → 1** · 已销号 **214 → 215**（本节顶部 ＋ §0.2）
  ⑤ §15 顶部加一行「深夜之九」留痕
  ⑥ 根 `README.md` §〇② 的「顺手看一眼」表加一行（折叠抽屉撤了 ⇒ 改成页内一小段）
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".codebuddy" / "plans" / "开发计划-主文档.md"
README = ROOT / "README.md"

ROW4 = (
    "| `TAIL-213` | 💬 **每页折叠的「口径说明」块要不要撤 / 瘦**（现量 **14 块 / 74 条 / 5,828 字**；"
    "用户原话「我一次也没进去看过」） | **销号依据** = 用户 2026-10-01「**选甲**」＋「**提交并收尾**」⇒ **甲（撤块）办完**："
    "① **只读盘点 ＋ 审计件** = `work/10-designs/设计-口径说明折叠块-20261001.md`（现状逐块表 / 分档 **A ≈27 · B ≈30 · C ≈17** / "
    "判据牵连 **5 处** / 三个选项）；② **14 块全撤**（74 条 / 5,828 字 ⇒ 留下 **13 段页内默认展开的说明**，各 ≤160 字）——"
    "**批 1** `m03` · **批 2** `m07`/`m08`/`m13`/`m14` · **批 3** `m05`/`m01`/`m02`/`m09` · **批 4** `m04`/`m06`/`m11`/`m12`/`m15`"
    "（脚本 `tools/oneoff/_tail213_b1..b4.py`：逐块按**首条文字**定位 ＋ **断言命中 1 次**，不达标整批不写盘）；"
    "执行口径 = ⭐ **「会做错的后果」留 · 复述《说明书》的规则删**（复述必漂；本仓老毛病）；"
    "**B 档落点 = 页内一小段**（用户授权我定）· **`§节号` = 只在《说明书》里留**；"
    "③ **判据同批改（保留意图、改钉靶）**：`test_wired_m03_list` ⇒「本页仍有一段口径说明、且**不是**折叠块」· "
    "`test_ux_numbers` / `test_ux_brief` 那两条「数折叠块 ≥ 8」⇒ **改数页内 `<div class=\"tip\"`**（现量 **124** 处，下限沿用 8，"
    "判词一字未变：「过 ㉖ 只能靠压短 / 换地方，⛔ 不许靠把说明删干净」）；"
    "④ **收尾批**：撤 `CALIB` 内核（`shell/proj.js` ⇒ **墓碑注释**）＋ `calib_kernel()` / `with_calib()` / `CALIB_PAGES`"
    "（`tests/shell_src.py`）＋ `test_口径说明块走统一出口_CALIB` ＋ ⭐ **同批撤** `tools/mut/_mut_uxnum.py` 的 `M4/M5/M7`"
    "（本仓规矩：撤判据必须同批撤靶）＋ 真机 ㉖ 那句提示语（那条出路没了）；那条「条数墓碑」**改钉新意图** ⇒ "
    "`test_口径说明不许再收进折叠块`；"
    "⑤ ⚠️ **三次被判据当场抓住**（都留痕）：`m03` 撤块丢掉判据钉着的「任何情况下都不在此恢复」· "
    "`m02` 丢掉「自动同步一次常用项目列表」与「不单独导出」（**教训：撤块时「指路 / 去处」类的话最容易被一起删掉 —— "
    "它们看着像废话，其实是别的判据的靶**）· `title` 里写了 `**`（壳的悬停不渲染 Markdown）；"
    "⑥ **一条小尾巴（已登记在判据里）**：`shell/legacy.js` 的「设置」块仍是折叠 `<details>`（它渲染**后端自报**的 §7.8 四条）"
    "⇒ 本轮**不动**，已在 `test_口径说明不许再收进折叠块` 的 docstring 里写明它是**唯一例外** "
    "| 2026-10-01 |"
)

NOTE = (
    "> ⭐ **2026-10-01（深夜之九）**：⭐⭐ **`TAIL-213`（每页折叠的「口径说明」块）当日立 · 当日办 · 当日销** —— "
    "用户拍板 **甲（撤块）**：**14 块全撤**（74 条 / 5,828 字 ⇒ **13 段页内说明**，各 ≤160 字）＋ **收尾批**"
    "（撤 `CALIB` 内核与它那一整套钉子、**同批撤**变异 `M4/M5/M7`）⇒ 每批 pytest ＋ 真机 ＋ 盖章 ＋ 尺子全绿"
    "（盖 `20261001-2320` / `2327` / `2335` / **`2343`**）；口径落纸 = 审计件 **§七** ⇒ A 类 **2 → 1 条**、"
    "已销号 **214 → 215**（**两处计数同改**：本节顶部 ＋ §0.2）。\n"
)

README_ROW = (
    "| **折叠说明** | ⭐ **顺手看一眼**（2026-10-01 改的）：每页页首那个「**口径说明 · N 条**」抽屉**已经撤掉**了"
    "（你的原话「我一次也没进去看过」）—— 里面**「会做错的后果」那几句改成了页内直接看得见的一小段**（各 ≤160 字），"
    "复述《说明书》的规则删掉 | ✅ **不必专门验** —— 下次用的时候顺手看一眼：哪段还是多余、或哪句该留没留，直接说 |"
)


def _once(text: str, needle: str) -> None:
    n = text.count(needle)
    assert n == 1, f"锚点命中 {n} 次（要 1 次）：{needle[:70]!r}"


def _drop_line(text: str, prefix: str) -> str:
    lines = text.split("\n")
    hit = [i for i, ln in enumerate(lines) if ln.startswith(prefix)]
    assert len(hit) == 1, f"要删的行命中 {len(hit)} 次（要 1 次）：{prefix[:60]!r}"
    del lines[hit[0]]
    return "\n".join(lines)


def main() -> int:
    plan = PLAN.read_text(encoding="utf-8")
    readme = README.read_text(encoding="utf-8")

    plan = _drop_line(plan, "| `TAIL-213` | 💬 **每页折叠的「口径说明」块**")
    plan = _drop_line(plan, "| `TAIL-213` **折叠的「口径说明」块**")
    _once(plan, "| # | 事项 | 销号依据 | 日期 |\n")
    plan = plan.replace("| # | 事项 | 销号依据 | 日期 |\n",
                        "| # | 事项 | 销号依据 | 日期 |\n" + ROW4 + "\n", 1)
    _once(plan, "A 类 **2** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **214** 条")
    plan = plan.replace("A 类 **2** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **214** 条",
                        "A 类 **1** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **215** 条", 1)
    _once(plan, "A 类 **2** 条 · B 类 0 · C 类 **0** · 已销号 **214**")
    plan = plan.replace("A 类 **2** 条 · B 类 0 · C 类 **0** · 已销号 **214**",
                        "A 类 **1** 条 · B 类 0 · C 类 **0** · 已销号 **215**", 1)
    anchor = "⇒ A 类 **1 → 2 条**（**两处计数同改**：本节顶部 ＋ §0.2）。\n"
    # ⚠️ 这条锚点命中 **2** 次（「深夜之七」与「深夜之八」都以它收尾）⇒ 取**最后一处**（＝之八）
    assert plan.count(anchor) == 2, f"锚点命中 {plan.count(anchor)} 次（应为 2）"
    i = plan.rindex(anchor) + len(anchor)
    plan = plan[:i] + NOTE + plan[i:]
    # §0.2 位置块：把 TAIL-213 从"待你选"改写成"已办销号"
    old_cand = ("③ ⭐ **新 `TAIL-213`**（**每页折叠的「口径说明」块** —— 现量 **14 块 / 74 条 / 5,828 字**，"
                "用户「一次也没进去看过」⇒ 只读审计件已出、**待你选 甲/乙/丙**）。")
    _once(plan, old_cand)
    plan = plan.replace(
        old_cand,
        "③ ✅ **`TAIL-213`（折叠的口径说明块）当日已办销号** —— 用户拍板 **甲**：**14 块全撤**"
        "（74 条 ⇒ 13 段页内说明）＋ 收尾批（撤 `CALIB` 内核与它那一整套钉子）⇒ 依据见 §15 §四。", 1)

    anchor_r = "| **用词** | ⭐ **顺手看一眼界面用词 ＋ 报错**"
    _once(readme, anchor_r)
    lines = readme.split("\n")
    i = next(k for k, ln in enumerate(lines) if ln.startswith(anchor_r))
    lines.insert(i + 1, README_ROW)
    readme = "\n".join(lines)

    PLAN.write_text(plan, encoding="utf-8", newline="")
    README.write_text(readme, encoding="utf-8", newline="")
    print("✅ TAIL-213 销号：台账（§一 删 · §四 加 · §14.3 删 · 计数两处）＋ §0.2 ＋ README 都已刷新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
