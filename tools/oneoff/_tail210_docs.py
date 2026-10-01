"""`TAIL-210` **销号**的台账改动（计划 §15 §一→§四 ＋ 计数两处 ＋ §14.3）。

⚠️ 为什么落成脚本：`§15 §一` 那一行有 5000+ 字，用编辑器工具手搓 `old_str` 极易错；
   这里按**行首标记**定位、**逐条断言**（命中必须恰好 1 次），⛔ 不达标整批不写盘。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail210_docs.py`          # 干跑
      `… --apply`
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / ".codebuddy" / "plans" / "开发计划-主文档.md"

#: §15 §四 的新行（销号依据）
ROW4 = (
    "| `TAIL-210` | 💬 **第二轮前端审计的两件余项**（① **技术词上屏** ② **重复句**） "
    "| **销号依据** = 用户 2026-10-01 三句（「都按推荐」·「继续简化」·「**按建议继续**」＋ 本轮「123 按推荐」·「3.交付面说明书跟着改」）"
    "⇒ 两批全办完、各自闸门全绿：① **第 3 批①「用词统一」** —— **170 处 / 26 件**（脚本 `tools/oneoff/_front4_words.py` · "
    "**逐条定点断言命中数**、不达标整批不写盘）：`落库`/`写库` ⇒ **`写入`**（⛔ 不用「入库」—— 与业务词「入库 5 类 / 出入库方向」撞）· "
    "`落不了库` ⇒ `写不进去` · `后端` ⇒ 人话 · `接口` ⇒ **`抓取`**（执行记录表头 ⇒ `动作`）· `phid` ⇒ **`信息化编号`** · `解析` **保留**；"
    "覆盖 = 壳（**0 残留**）＋ 后端会直接上屏的串（4 域 `imp_spec` · `fetch_task` · `notice/router` · `jc_ignore_api` 等）＋ "
    "**交付面《说明书》24 处** ＋ 逐字引用界面文案的 claim/规格 6 处；同批改**判据/探针 9 处**（`IMP_STEPS` 整串 · m06 块标题 ×3 · "
    "i8 降级文案 ×2 · 真机探针期望串 ×2）；顺手清掉**同一条字符串里**的工程代号（`（API-06）` / `链路 A` / `（M5 未开工）`）；"
    "② **第 3 批②「重复句」** —— **8 项**抽成壳内共用常量（`I8_LOGIN_TIP` / `IMP_DEGRADE_TIP` / `OWN_KW_LABEL` / `OWN_KW_HINT` 声明在 `core.js`；"
    "`DRAFT_HINT` / `DRAFT_CANCEL_MSG` / `I8_ACC_LABEL` 在 `actions.js`；`IMP_PJ_LABEL` 在 `legacy.js`）＋ **删一处**"
    "（`index.html:1503` 卡头把 CALIB 已说过的话又念一遍）⇒ 脚本 `tools/oneoff/_front5_dup.py`；⭐ **刻意不并的都写了理由**："
    "`class=\"tip\"` 块里的两处（抽成 `${CONST}` 会被 `_JSX` 剥掉 ⇒ **离线那条长度判据对它们失明**，而弹窗那两处**离线是唯一守卫**）· "
    "`pages-a`/`pages-b` 那条（共同片段只有 19 字）· `m12`（已撤页残片）6 处（⛔ 规矩：要清就整体清 ⇒ 另一件大事）；"
    "③ **闸门** = pytest **1403 / 0** · 16 把尺子 `rc=0 / BAD: []` · 真机 `_shell_smoke` `rc=0` · `doc_audit --ui` 四检 rc=0 · "
    "四态 **644 / 0** · 壳基线盖章 `20261001-2049` / **`-2110`** · 服务已重启（改过后端 `.py`）；"
    "⚠️ 同轮**撞出新尾巴 `TAIL-211`**（后端的用户可见串没有机器眼）| 2026-10-01 |"
)

NOTE15 = (
    "> ⭐ **2026-10-01（深夜之五）**：`TAIL-210` **两批全办完 ⇒ 已销号**（第 3 批①「用词统一」170 处 / 26 件；"
    "第 3 批②「重复句」8 项抽共用常量 ＋ 1 处删重复 ⇒ 依据见 §四）⇒ A 类 **3 → 2 条**、已销号 **211 → 212**（**两处计数同改**：本节顶部 ＋ §0.2）。"
)


def _read(p: pathlib.Path) -> str:
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def _write(p: pathlib.Path, text: str) -> None:
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main() -> int:
    apply = "--apply" in sys.argv
    text = _read(P)
    lines = text.split("\n")
    bad: list[str] = []

    def idx_of(pred, why: str) -> int:
        hits = [i for i, x in enumerate(lines) if pred(x)]
        if len(hits) != 1:
            bad.append(f"{why} —— 命中 {len(hits)} 次（要 1）")
            return -1
        return hits[0]

    i_one = idx_of(lambda x: x.startswith("| `TAIL-210` | 💬 **第二轮前端审计的余项**"), "§15 §一 的 TAIL-210 行")
    i_four = idx_of(lambda x: x.startswith("| `TAIL-209` | 💬 **界面说明文字瘦身**（含弹窗"), "§15 §四 的 TAIL-209 行（插在它前面）")
    i_top = idx_of(lambda x: x.startswith("A 类 **3** 条 · B 类 **0** 条"), "§15 顶部计数")
    i_02 = idx_of(lambda x: x.startswith("A 类 **3** 条 · B 类 0 · C 类 **0** · 已销号 **211**"), "§0.2 计数")
    i_143 = idx_of(lambda x: x.startswith("| `TAIL-210` 第二轮审计余项"), "§14.3 的 TAIL-210 排期行")
    i_note = idx_of(lambda x: x.startswith("> ⭐ **2026-10-01（深夜之四）**"), "§15 顶部的「深夜之四」注")
    if bad:
        print("不达标：")
        for x in bad:
            print("   ✗", x)
        return 1

    new: list[str] = []
    for i, x in enumerate(lines):
        if i == i_top:
            x = "A 类 **2** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **212** 条"
        elif i == i_02:
            x = "A 类 **2** 条 · B 类 0 · C 类 **0** · 已销号 **212**"
        elif i == i_143:
            x = x.replace("| `TAIL-210` 第二轮审计余项", "| ✅ `TAIL-210` 第二轮审计余项", 1)
            x = x.replace("| **随时**（用户正推", "| ✅ **已办 · 2026-10-01 销号（⇒ §15 §四）**｜原建议时机 **随时**（用户正推", 1)
        if i == i_one:
            continue                                   # ⛔ 从 §一 删掉（做掉的移进 §四）
        if i == i_four:
            new.append(ROW4)                           # §四 的新行排在最新一行前面
        if i == i_note:
            pass
        new.append(x)
        if i == i_note:
            new.append(NOTE15)
    out = "\n".join(new)
    assert "| `TAIL-210` | 💬 **第二轮前端审计的余项**" not in out, "§一 那行没删掉"
    assert out.count(ROW4) == 1 and out.count(NOTE15) == 1
    assert "A 类 **2** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **212** 条" in out
    assert "A 类 **2** 条 · B 类 0 · C 类 **0** · 已销号 **212**" in out
    print("§15 §一 删 1 行 · §四 加 1 行 · 计数 2 处 · §14.3 标已办 · 顶部加 1 行注")
    if not apply:
        print("（干跑 —— ⛔ 没写盘）")
        return 0
    _write(P, out)
    print("✅ 已写", P.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
