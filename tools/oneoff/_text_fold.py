"""**只读**量测：每页那个**折叠的「口径说明 · N 条」块**里到底装了什么（`TAIL-213` 立项量测 · 2026-10-01）。

用户原话（2026-10-01）：「每页折叠的口径说明里的也简化或者删除吧？说实话我一次也没进去看过」。

它量什么（⛔ 一个字都不改）：
  · 每页（`CALIB({items:[…]})` 调用点）**几条** · **合计多少字**（剥标签 · 空白不计 —— 与真机 ㉖ 同口径）
  · 每条的**前 N 字**（给人眼判"这条是业务常识、还是系统特有行为"）
  · 全站合计

为什么单写一件：这些块**没有条数上限**（真机 ㉖ 明确把折叠区排除、离线 `_DETAILS` 也整段剥掉）
⇒ 它是**唯一"想量只能现量"**的那一面（同族：`_text_audit7/8/9.py`）。
⚠️ 它只量**壳自己拼的**那些 `CALIB` 调用点；原型（交付面）不动、也不在靶内。
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = ROOT / "backend" / "app" / "web"

_TAG = re.compile(r"<[^>]+>")
_HEAD = 46


def _parts() -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    out.append(("index.html", (WEB / "index.html").read_text(encoding="utf-8")))
    for p in sorted((WEB / "shell").glob("*.js")):
        out.append((f"shell/{p.name}", p.read_text(encoding="utf-8")))
    return out


def _scan_items(text: str, at: int) -> tuple[list[str], int]:
    """从 `CALIB({` 之后扫出它的 `items` 里每个**反引号串**（一条）⇒ `(条目, 结束下标)`。

    反引号串里可能带 `${…}`（里面还有引号 / 反引号）⇒ 用"括号深度 + 反引号"两态小状态机。
    """
    i = at
    depth = 1                      # 已吃掉的 `CALIB({` 那个 `{`
    while i < len(text) and depth:
        c = text[i]
        if c == "`":               # 反引号串：一路吃到配对的反引号（`${…}` 里的花括号要配平）
            i += 1
            brace = 0
            while i < len(text):
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == "$" and i + 1 < len(text) and text[i + 1] == "{":
                    brace += 1
                    i += 2
                    continue
                if brace and text[i] == "{":
                    brace += 1
                elif brace and text[i] == "}":
                    brace -= 1
                elif text[i] == "`" and not brace:
                    break
                i += 1
            i += 1
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        i += 1
    span = text[at:i]
    items = re.findall(r"`([^`]*)`", span, flags=re.S)
    return items, i


def _len(html: str) -> int:
    return len(re.sub(r"\s+", "", _TAG.sub("", html)))


def main() -> int:
    total_items = total_chars = 0
    for name, text in _parts():
        for m in re.finditer(r"CALIB\(\{", text):
            items, _ = _scan_items(text, m.end())
            if not items:
                continue
            line = text[:m.start()].count("\n") + 1
            chars = sum(_len(it) for it in items)
            total_items += len(items)
            total_chars += chars
            print(f"\n=== {name}:{line} · {len(items)} 条 · 合计 {chars} 字 "
                  + "=" * max(0, 40 - len(name)))
            for k, it in enumerate(items, 1):
                n = _len(it)
                head = re.sub(r"\s+", " ", _TAG.sub("", it)).strip()
                print(f"  [{k}] {n:>4} 字  {head[:_HEAD]}{'…' if len(head) > _HEAD else ''}")
    print(f"\n\u2500\u2500 全站合计：**{total_items} 条 · {total_chars} 字** \u2500\u2500")
    return 0


if __name__ == "__main__":
    sys.exit(main())
