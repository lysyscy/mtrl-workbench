"""把 `#1`（面板注册表）**同改到交付面原型** —— `ui_parity` 的 `U1`/`U5` 要求「原型 ⇄ 壳 **同句**」。

⚠️ 为什么必须同改（不是"顺手"）：`ui_parity` 逐行比"同名视图切片"与"公共件段"，
   壳改了、原型没改 ⇒ U1 报 `pjOpen` vs `pjIsOpen('pj')` 不一致、U5 报公共件段哈希不同
   —— 本仓对这类差异的既定处置就是**壳与原型同改同句**（`TAIL-97` 那次 15 处同款做法）。

⭐ 复用 `_apply_pj_registry` 的同一张表（⛔ 不另抄一份改法 —— 两处各写一份必然漂）。
⚠️ 原型是**单文件 mock**：它**没有**委托层那段（click 委托 / 点外面收起 / Esc 收面板）
   ⇒ 那三处按"**允许 0 处**"处理（⛔ 不硬造），其余（声明 / 读写 / 注册表 / `projPanel` 派生 key）照改。

跑法：`backend\\.venv\\Scripts\\python.exe tools/oneoff/_apply_pj_registry_proto.py [--apply]`
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import _apply_pj_registry as R  # noqa: E402  —— 同一张表（`FLAGS` / `DECLS` / `REGISTRY` / …）

#: 交付面原型（`ui_parity` 读的就是它；`D:` 开头 = 仓外，⛔ 别改路径）
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")


def _one(text: str, old: str, new: str, where: str, *, at_most: int = 1) -> tuple[str, int]:
    """原型侧的替换：**允许 0 处**（原型没有那段/那个变量），但**不许出现 2 处**（形态变了要人看）。"""
    got = text.count(old)
    assert got <= at_most, f"{where}：命中 {got} 处（期望 ≤{at_most}）\n  找的是：{old[:110]}"
    return (text.replace(old, new, got), got)


def main(argv: list[str]) -> int:
    assert PROTO.exists(), f"找不到交付面原型：{PROTO}（路径变了就同批改本件）"
    text = PROTO.read_text(encoding="utf-8")
    before = text

    # ① 声明（原型里有的才改）
    done = []
    for _, old, new in R.DECLS:
        text, n = _one(text, old, new, "原型(声明)")
        done.append(n)
    assert sum(done) >= 8, f"只改到 {sum(done)} 处声明 —— 太少，形态八成变了（⛔ 别硬写）"

    # ② 注册表 ＋ `projPanel` 派生 key ＋ 输入元素带 key
    text, n = _one(text, R.PANEL_OLD, R.REGISTRY + R.PANEL_NEW, "原型(projPanel)")
    assert n == 1, "原型的 `projPanel` 定义没找到（U5 就是比它）"
    text, _ = _one(text, R.INPUT_OLD, R.INPUT_NEW, "原型(面板输入)")

    # ③ 委托层那三处：原型**没有**就跳过（⛔ 不硬造）
    for old, new, name in ((R.DELEGATE_OLD, R.DELEGATE_NEW, "click 委托"),
                           (R.CLOSER_OLD, R.CLOSER_NEW, "点外面收起"),
                           (R.ESC_OLD, R.ESC_NEW, "Esc 收面板")):
        text, n = _one(text, old, new, f"原型({name})")
        print(f"   原型·{name}：{'已同改' if n else '（原型没有这段，跳过）'}")

    # ④ 逐变量迁移（只迁原型里真有的）
    for flag, key in R.FLAGS:
        if re.search(r"\b" + flag + r"\b", text):
            text = R._migrate(text, flag, key, "原型")
    for flag, _ in R.FLAGS:
        assert not re.search(r"\b" + flag + r"\b", text), f"原型里 `{flag}` 还没迁干净"

    if before == text:
        print("⚠️ 原型一字未改 —— 说明形态已经一致（或全都对不上，去看 U1 的明细）")
    if "--apply" not in argv:
        print(f"dry-run ✅ 断言通过（⛔ 未写盘）：原型 {len(text.splitlines())} 行，"
              f"`PJ_OPEN` 出现 {text.count('PJ_OPEN')} 次")
        return 0
    PROTO.write_text(text, encoding="utf-8", newline="")
    print(f"✅ 已写盘：{PROTO.name}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv))
