#!/usr/bin/env python
r"""`TAIL-197` 收尾落纸（**同批**）：销号（§15 §一 → §四）＋ 计数 ＋ §14.3 标已办 ＋ 施工图 §7.10（`P5-d` 量测）。

⚠️ 规矩同 `_p5c_docs.py`：逐处先断言命中数、改完 round-trip 自校验；中文行文里的引号一律用「」。

用法：`python tools/oneoff/_t197_docs.py`（干跑）· `… --write`
"""

from __future__ import annotations

import argparse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
PLAN = ROOT / ".workbuddy" / "plans" / "开发计划-主文档.md"
DES = ROOT / ".workbuddy" / "work" / "10-designs" / "设计-表格筛选配置化-20260924.md"
NL = "\r\n"

#: §15 §四（已销号）那一行
ROW4 = (
    "| `TAIL-197` | 🚧 **交付面四检失败时，闸门不判红** —— `doc_audit --ui` 把四检的**非零退出码照实打印**，"
    "但**自己的 `rc` 仍是 0**（2026-09-30 实测：`_smoke` **606/1** 那一轮 `DOCUI_RC=0` · `BAD: []` · 四态全绿）"
    "⇒ 交付面回归**报得出来、却拦不住**（同族 = 「打印了红 ≠ 拦住了」） | 落点 = `tools/audit/doc_audit.py`："
    "`run_ui_checks()` 改成回传**非零的件名**（`(逐行输出, 非零件名)`），`main()` 把它**并进 rc**；"
    "⚠️ **三种「跳过」不算失败**（找不到 node ／ 拿不到交付面根 ／ demo 里没有四检脚本）—— 那是"
    "`docs/deployment.md` 写明的**目标机已知代价**，⛔ 并进 rc 会让目标机上**每轮闸门都红**（比不判还坏）。"
    "自证 = `tools/mut/_mut_uicheck.py` **`M5`**（交付面写坏 ⇒ `doc_audit --ui` **rc≠0** ＋ 输出里出现那句话）"
    "⇒ 该件 **4 → 5/5**；⚠️ 同批还修掉 `M1` 那个**方向反了**的旧靶（`#2` 2026-09-26 之后 `CHG` 名单"
    "**已从原型整份删除**、判词反转成 `N6′`「名单不许回来」⇒ 旧靶插的那句落在**注释**里 = **空动作**，"
    "摘了照样绿） | 2026-09-30 |"
)

#: 施工图 §7.10（`P5-d` 量测 ＋ 分批建议）
S710 = """### 7.10 ⭐ `P5-d` **量测**（2026-09-30 · ⛔ 定批之前必读）

**量测件** = `tools/oneoff/_p5d_survey.py`（⛔ 只读 · 读数落 `artifacts/_p5d_survey.json`）。
它量的是「`TBL({rows:html[]})` ⇒ `TBL({cols:[{t,r,s}]})` **要动多少、动哪几处**」：

| 量什么 | 读数 |
|---|---|
| `TBL({…})` **调用点** | **46 处** —— `index.html` **24** ／ `actions.js` **12** ／ `legacy.js` **7** ／ `core.js` **2**（另 1 处是 `proj.js` 的**定义**） |
| ⚠️ **`U1` 级联面**（落在 `V.*` 切片里 ＝ `ui_parity` **逐行对位**的那些） | **30 处**（`index.html` 24 ＋ `legacy.js` 的 `V.set` / `V.imp`） |
| `rows:` **写法** | 内联 `.map(…)` **31 处** · 变量/表达式 **14 处** |
| 规模（`cols` 化的面） | **`<td>` 274 个 · `<tr>` 53 个 · 行模板共 275 行** |
| ⚠️ 带**条件列 / 派生列 / 嵌套**的 | **17 处**（这些的 `r` 那格不是「取值」，得逐个看设计） |
| ⭐ 「**纯逐列取值**」＝可机械换的第一梯队 | **14 处**（最干净的：`m01` 那张 6 列 3 行的 · `actions.js` 的 `modal:procExp`〔2 列 1 行〕/ `modal:ledExp` / `jcInv` / `jcTInv` 等） |

**结论（⛔ 别跳步）**：

1. 这是**大件**：274 个格、**30 处在 `U1` 对位区**（每碰一行就是一条「换号 ＋ 幽灵」登记）
   ⇒ ⛔ **别一次铺开**（施工图原话：⚠️⚠️ **另一件大事，⛔ 别和上面混**）；
2. 它**零可见收益**（渲染字节不变 —— 换的是「**列定义住哪**」）⇒ 该在**真要加列 / 改列配置**时才做，
   ⛔ 至少**先做一处试点**（`P0` / `P4-a` 那套：出口先立 ⇒ 一处跑通 ⇒ 判据 ＋ 变异跟上）；
3. ⭐ **建议的分批**（与 §7.4 一致）：
   - **`P5-d-a`（试点）**：挑一处**不在 `V.*` 里**的（⇒ **零 `U1` 级联**）先立 `cols` 契约 ——
     首选 `actions.js` 的 `modal:procExp`（2 列 1 行）；⚠️ `TBL` 是 **`U5`（壳 ⇄ 原型逐字一致）件**
     ⇒ 试点也得**两侧同批同句** ＋ **原型改前备份** ＋ 跑 `doc_audit --ui`；
   - **`P5-d-b`（第一梯队）**：那 14 处「纯逐列取值」，先挑 `V.*` 里**两侧本来就逐行对齐**的
     （⇒ 换号最小）；
   - **`P5-d-c`（难的那批）**：那 17 处带条件 / 派生列 / 嵌套的（逐个设计 `r` 的写法）；
   - ⏭ 收尾之后才谈「**`mechYm` / `awfTbl` 那两张裸表并入 `TBL`**」（§四 里"按设计不动"的那 2 张）——
     ⭐ 那才是 `TAIL-64` 最初的动机。
"""


def _sub(t: str, old: str, new: str, what: str, n: int = 1) -> str:
    got = t.count(old)
    assert got == n, f"⛔ {what}：锚点命中 {got} 次（期望 {n}）"
    return t.replace(old, new, n)


def patch_plan(t: str) -> str:
    lines = t.split("\n")

    # ① §15 §一：删掉 TAIL-197 那一行（它要搬去 §四）
    for k, ln in enumerate(lines):
        if ln.startswith("| `TAIL-197` | 🚧 **交付面四检失败时，闸门不判红**"):
            del lines[k]
            break
    else:
        raise AssertionError("⛔ §15 §一 里找不到 TAIL-197 那一行")
    print("   ✅ ① §15 §一 · TAIL-197 行已摘")

    # ② §15 §四：插到表头行之后（⚠️ 该表**没有** `|---|` 分隔行 —— 现状如此，照它插）
    for k, ln in enumerate(lines):
        if ln.startswith("### 四、已销号"):
            for j in range(k, k + 6):
                if lines[j].startswith("| # | 事项 | 销号依据 | 日期 |"):
                    lines.insert(j + 1, ROW4)
                    break
            else:
                raise AssertionError("⛔ §四 里找不到表头行")
            break
    else:
        raise AssertionError("⛔ 找不到 §四「已销号」段")
    t = "\n".join(lines)
    print("   ✅ ② §15 §四 · TAIL-197 已销号（留痕）")

    # ③ 计数：§15 §一 顶部（T6 认的那一行）+ §0 那一行
    t = _sub(t, "A 类 **6** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **195** 条",
             "A 类 **5** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **196** 条", "§15 计数行")
    t = _sub(t, "A 类 **6** 条 · B 类 0 · C 类 **0** · 已销号 **195**",
             "A 类 **5** 条 · B 类 0 · C 类 **0** · 已销号 **196**", "§0 计数行")
    print("   ✅ ③ 计数：A 类 6 → 5 · 已销号 195 → 196（两处）")

    # ④ §14.3：那一行标「已办」
    t = _sub(t, "| `TAIL-197` 🚧 **交付面四检失败时闸门不判红**（只打印、不并入 `rc`） | ⏳ **随时**",
             "| ✅ `TAIL-197` 🚧 **交付面四检失败时闸门不判红**（只打印、不并入 `rc`） | "
             "✅ **已办（2026-09-30）** ⇒ 见 §15 §四（`run_ui_checks()` 回传非零件名、`main()` 并进 rc；"
             "自证 = `_mut_uicheck.py` **M5** · **5/5**） | ", "§14.3 TAIL-197 行")
    print("   ✅ ④ §14.3 · TAIL-197 标已办")
    return t


def patch_des(t: str) -> str:
    assert t.rstrip().endswith("（9 张「带标记却不在 `.tw` 里」的表 · 今天无害）。"), \
        "⛔ 施工图末尾不是 §7.9 那句话 —— 先人工看一眼（§7.10 要接在它后面）"
    t = t.rstrip("\n") + "\n\n" + S710
    print("   ✅ ⑤ 施工图 · 追加 §7.10（`P5-d` 量测 ＋ 分批建议）")
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    plan = PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    des = DES.read_text(encoding="utf-8", newline="").replace("\r\n", "\n")
    plan2, des2 = patch_plan(plan), patch_des(des)
    assert plan2 != plan and des2 != des, "⛔ 一个字都没改？"
    if not a.write:
        print("\n（干跑：⛔ 未写）")
        return 0
    PLAN.write_text(plan2.replace("\n", NL), encoding="utf-8", newline="")
    DES.write_text(des2.replace("\n", NL), encoding="utf-8", newline="")
    assert PLAN.read_text(encoding="utf-8", newline="").replace("\r\n", "\n") == plan2, "⛔ 计划写回不一致"
    assert DES.read_text(encoding="utf-8", newline="").replace("\r\n", "\n") == des2, "⛔ 施工图写回不一致"
    print("\n✅ 落纸完成（计划 ＋ 施工图）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
