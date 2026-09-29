"""`TAIL-193` 量测 / 对账：把「同一件事 N 份实现」的现状摊开（只读 · ⛔ 不改任何文件）。

⭐⭐ **登记册的唯一主人 = `backend/tests/test_dup_guards.py` 的 `DUP_FAMILIES`** —— 本件**直接 import 它**，
⛔ 不在这儿再写一份族定义（写了就有两个主人，改一处漏一处 —— 那正是 `TAIL-193` 要防的病）。

用途两个：
① **量测**（当初怎么得到那张清单的：逐族把 `backend/app/**/*.py` 里命中函数定义行的都摊出来）；
② **对账**（现在还剩多少副本、每族的唯一出口是谁）—— 汇报 / 写台账时跑它，⛔ 别手抄数字。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail193_measure.py`
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))          # ⭐ 让 `tests.test_dup_guards` 可 import（唯一登记册在那儿）

from tests.test_dup_guards import DUP_FAMILIES  # noqa: E402

APP = BACKEND / "app"


def main() -> int:
    total_copies = 0
    for f in DUP_FAMILIES:
        rx = re.compile(f.pattern)
        skip = set(f.owner_files) | set(f.forward_files)
        rows: list[tuple[str, str]] = []
        for p in sorted(APP.rglob("*.py")):
            rel = p.relative_to(ROOT).as_posix()
            if rel in skip:
                continue
            for line in p.read_text(encoding="utf-8").splitlines():
                m = rx.match(line)
                if m:
                    rows.append((rel, m.group(1)))
        total_copies += len(rows)
        print("=" * 78)
        print(f" {f.fam}")
        print(f"   唯一出口：{f.owner}")
        print(f"   存量副本：{len(rows)} 处（登记册里也是 {len(f.copies)} 处）")
        for rel, fn in rows:
            flag = "（未登记 ⚠️）" if (rel, fn) not in f.copies else ""
            print(f"     · {rel}::def {fn}{flag}")
        for rel, fn in f.copies:
            if (rel, fn) not in rows:
                print(f"     · ~~{rel}::def {fn}~~（已消失 ⇒ 登记册该销号了）")
    print("=" * 78)
    print(f"合计：{len(DUP_FAMILIES)} 族 · 存量副本 **{total_copies}** 处（⛔ 本轮一个都不改 —— 只防新增）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
