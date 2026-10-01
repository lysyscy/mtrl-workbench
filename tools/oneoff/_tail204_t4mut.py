"""`TAIL-204` 第 6 步：**实测** `T4` 的 `must_have`（黄档）路径现在真的盯在**根 `README.md`** 上。

⭐ 为什么要单独实测：`HANDBOOK_REL` 从 `plans/执行情况-主文档.md` 换成 `README.md` ⇒
   「给予用户看的那一页**必须至少有一处**四态数字」这条义务**换了落点**。
   `_mut_docaudit.py` 的 `M1`/`M2` 已经证明「数字改错 ⇒ 红」「不指向计划 ⇒ 红」**跟着常量走**
   （它们的靶就是 `HAND`），但 `T4` 的**"一处都没有 ⇒ 黄"**（`audit_drift.check_status_line` 末段）
   **挂不了常规变异靶** —— 黄档命中进的是 `doc_audit` 按文件**聚合**的"疑似"节、**不打印明细**
   ⇒ 变异件那套 needle 断言没东西可抓。

做法：把 `README.md` 里的四态串**临时抹成不匹配**的写法 → 跑 `doc_audit` → 看 `T4` 是否报黄 → **逐字节复原**。
⚠️ `finally` 保证复原（⛔ 本件自己别接 `Select-Object -First N` —— 会掐断进程、`finally` 不跑，见 `细则.md` §廿三-6）。
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HAND = ROOT / "README.md"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
#: 与 `_mut_docaudit._四态PAT` / `audit_drift._STATUS_RE` **同形的串**（README 现在那一行）
PICK = re.compile(r"绿 \d+ · 红 \d+ · 待建 \d+ · 未绑定 \d+")


def run_doc_audit() -> str:
    r = subprocess.run([str(PY), "-X", "utf8", "tools/audit/doc_audit.py"],
                       cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8")
    return (r.stdout or "") + (r.stderr or "")


def main() -> int:
    src = HAND.read_bytes()
    text = src.decode("utf-8")
    m = PICK.search(text)
    if not m:
        print("[跳过] README 里找不到四态串 —— 判据（`T4` must_have）本来就该报黄，先去看基线。")
        return 0
    base = run_doc_audit()
    base_has = "README.md" in base.split("疑似")[-1] if "疑似" in base else False
    print(f"[基线] 抹之前：T4 认得出四态（命中串 = {m.group(0)}）")
    print(f"       基线「疑似」节里有没有 README.md ⇒ {base_has}（期望 False）")
    try:
        HAND.write_text(text.replace(m.group(0), "（数字见工具）", 1), encoding="utf-8")
        got = run_doc_audit()
    finally:
        HAND.write_bytes(src)
    assert HAND.read_bytes() == src, "⛔ 复原失败！"
    tail = got.split("疑似")[-1] if "疑似" in got else got[-800:]
    fired = "README.md" in tail
    print(f"[变异] 抹掉四态后：「疑似」节里出现 README.md ⇒ {fired}（期望 True）")
    head = next((ln for ln in got.splitlines() if "必须修" in ln), "")
    print(f"       {head.strip()}")
    print("       ✅ 已逐字节复原 README.md")
    if fired and not base_has:
        print("\n结论：**通过** —— `T4` 的黄档真的盯着 `README.md`（换件后义务没丢）。")
        return 0
    print("\n结论：**未通过** ⇒ 要么判据没跟上换件，要么本件的判定口径要改（别硬凑）。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
