"""`TAIL-210` 余项之一：**技术词上屏**（`D29` ＋ 守则 §2.5 用业务术语 / §3.3 黑话不入界面）。

## 本批动的是**口径已定、无需再判**的那一类

| 类 | 例 | 改法 |
|---|---|---|
| **兜底句里的技术词 ＋ 没有下一步** | 「没能保存：**后端未返回原因**」 | ⇒「系统没有给出原因，**请重试**」（守则 §3.7 要求"人话 ＋ 下一步"，原句两条都没有） |
| **黑话「幂等」**（守则 §3.3 **点名**列过） | 「（§9.5 幂等）」·「重复的会被幂等挡掉」·「按 phid **幂等建档**」 | ⇒ 去黑话；⭐ "重复的会改成同一条、不会重复建"这类**系统特有行为**用人话留着 |
| **实现细节** | 「（与全站其它导入走**同一套管线**）」·「（**后端**没写进去）」·「由**后端**重算」·「**后端**报出 N 行影响」 | ⇒ 删 / 去"后端"（用户不需要知道有前后端） |
| **写给未来维护者的条目** | `m12` CALIB 的 `<dt>未来怎么改</dt>`（「若源头改到…只需改**后端取数**那一处」） | ⇒ **整条删**（那是答给改代码的人，不是答给用户的） |

⛔ **本批不动**（需你定尺度，见 `TAIL-210`）：`接口`（9 行）· `落库`（43 行）· `解析`（7 行）· `phid`。
⚠️ 每条断言**命中恰好 N 次**（`N=0` = **全量替换**，用于那句兜底）⇒ 不达标**整批不写**；
   被 §13.6 入门口令点名 ⇒ 必有 `main()`。
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tools.audit.shell_source import SHELL_PARTS  # noqa: E402

W = ROOT / "backend" / "app" / "web"

def _rel(p: pathlib.Path) -> str:
    return str(p.relative_to(W)).replace("\\", "/")


#: (件名, 旧串, 新串, 期望命中次数) —— `件名=""` ＋ `期望=0` 表示**全量**
EDITS: list[tuple[str, str, str, int]] = [
    # ── 兜底句：全量（1 个「后端」＋ ⭐ 补上"下一步"）────────────────────────
    ("", "后端未返回原因", "系统没有给出原因，请重试", 0),
    # ── 黑话「幂等」────────────────────────────────────────────────
    ("shell/actions.js", "<b>手工值与调整单不被覆盖</b>（§9.5 幂等）",
     "<b>手工值与调整单不被覆盖</b>（§9.5）", 1),
    ("shell/actions.js", "已保存（按「月 + 项名」幂等写入）",
     "已保存（同一格重提交 ＝ 更新，不会重复）", 1),
    ("shell/actions.js", "重复的会被幂等挡掉", "重复的会<b>自动挡掉</b>", 1),
    ("shell/legacy.js", "（按 phid 幂等建档；", "（按 phid 建档，重复的不会重复建；", 1),
    ("shell/legacy.js", "（按 phid 幂等建档）", "（按 phid 建档，重复的不会重复建）", 1),
    ("shell/core.js", "会按 phid <b>幂等建档</b>，并把",
     "会按 phid <b>建档，重复的不会重复建</b>，并把", 1),
    # ── 实现细节 ────────────────────────────────────────────────────
    ("shell/actions.js",
     "降级路径要有对应页面的导入入口（与全站其它导入走同一套管线）—— 在此之前",
     "降级路径要有对应页面的导入入口 —— 在此之前", 1),
    ("shell/actions.js", "这一格已还原成原来的值（后端没写进去）",
     "这一格已还原成原来的值", 1),
    ("shell/actions.js", ">后端报出 ${impList.length} 行影响 · 涉及表：",
     ">受影响 ${impList.length} 行 · 涉及表：", 1),
    ("shell/actions.js", "欠款与台账已由后端重算", "欠款与台账已重算", 2),
    # ── 写给未来维护者的 CALIB 条目：整条删 ────────────────────────────
    ("index.html",
     "<dt>未来怎么改</dt><dd style=\"font-family:var(--fs)\">若源头改到<b>机械费台账</b>，"
     "只需改后端取数那一处 —— 别处（看板 / 本页 / 台账 / 欠款）都不用动</dd>",
     "", 1),
]


def main() -> int:
    files = {_rel(p): p.read_text(encoding="utf-8", newline="") for p in SHELL_PARTS}
    done: list[str] = []
    bad: list[str] = []

    for name, old, new, want in EDITS:
        targets = list(files) if want == 0 else [name]
        hit_total = 0
        for rel in targets:
            for o, w in ((old, new), (old.replace("\n", "\r\n"), new.replace("\n", "\r\n"))):
                cnt = files[rel].count(o)
                if cnt and (want == 0 or cnt == want):
                    files[rel] = files[rel].replace(o, w)
                    hit_total += cnt
                    break
        if hit_total == 0 or (want != 0 and hit_total != want):
            bad.append(f"{name or '（全量）'}: 命中 {hit_total} 次（期望 {want or '≥1'}）⇒ {old[:52]!r}")
        else:
            done.append(f"{name or '（全量）'} × {hit_total}")

    if bad:
        print("⛔ 以下没达标（整批不写）：")
        for b in bad:
            print("   ", b)
        return 1

    for rel, text in files.items():
        (W / rel).write_text(text, encoding="utf-8", newline="")
    print("✅ 已写：" + " · ".join(done))
    print(f"\n共 {len(EDITS)} 条规则全部命中 ✔（改动件 {len(files)} 个）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
