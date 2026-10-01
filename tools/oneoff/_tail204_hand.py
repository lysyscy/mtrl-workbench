"""`TAIL-204` 第 6 步（② 执行情况瘦身）：把 `执行情况-主文档.md` **原文全文**搬成归档件。

⭐ 为什么用脚本而不是手抄：留痕件必须与被归档件**逐字节一致**，手抄必然出错 ⇒ 脚本搬 ＋ 当场校验。

⚠️ 本件只做「搬成归档件」；搬完由 `delete_file` 删掉原活文档
   （⛔⛔ `.codebuddy/` 下**绝不 `git rm`** —— 实测会让**整个目录**从工作区消失，见 `细则.md` §廿三）。

用法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail204_hand.py`
      `--check` 只校验不写；幂等（归档件已在位且内容一致 ⇒ 报 OK）。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / ".codebuddy" / "plans" / "执行情况-主文档.md"
DST = ROOT / ".codebuddy" / "plans" / "archive" / "归档-执行情况-已完成叙述-20261001.md"

HEADER = """# 归档 · `执行情况-主文档.md` 全文（2026-10-01 · `TAIL-204` 第 6 步）

> ⭐ **本件 = 留痕**：`.codebuddy/plans/执行情况-主文档.md` 的**原文全文**，**逐字节照搬**（脚本搬的，见
> `tools/oneoff/_tail204_hand.py`）。
> ⛔ **别当现状读** —— 2026-10-01 用户裁定「`执行情况` 算给人看的，但…已不需要里面的大部分文字，
> 可将绝大部分归档，**只留待办**」（出处 = `.codebuddy/memory/journal/2026-10-01.md` §5）⇒
> 该件的**待办 / 要你验的清单**已**压缩后**接进根 `README.md` 的 **§〇**（那里是**现役**口径），本件只留痕。
> ⚠️ 因此下面「④ 需要你做什么」与 `README.md` §〇 的「② 要你验的清单」是**同一件事的两代写法**：
> **现役看 README**；本件保留**当时的完整措辞**（现状叙述、逐条判读细则、"暂时测不了"的原话）。
> ⭐ 想知道那份东西的**最新**状态 ⇒ `README.md` §〇 ＋ `.codebuddy/plans/开发计划-主文档.md`。

---

"""


def main(argv: list[str]) -> int:
    check_only = "--check" in argv
    if not SRC.exists():
        print(f"[跳过] 活文档已不在（{SRC.relative_to(ROOT)}）—— 若归档件在位，本步已办完。")
        print(f"[检查] {DST.relative_to(ROOT)} 在位 = {DST.exists()}")
        return 0
    src_text = SRC.read_text(encoding="utf-8")
    src_n = len(src_text.splitlines())
    if SRC.read_bytes()[:3] == b"\xef\xbb\xbf":
        print("[警告] 源件带 BOM —— 本仓别处不带，先确认。")
    body = HEADER + src_text
    if DST.exists() and DST.read_text(encoding="utf-8") == body and not check_only:
        print(f"[幂等] 归档件已在位且内容一致：{DST.relative_to(ROOT)}")
        return 0
    if check_only:
        print(f"[check] 会写 {DST.relative_to(ROOT)}：头部 {len(HEADER.splitlines())} 行 ＋ 原文 {src_n} 行")
        return 0
    DST.parent.mkdir(parents=True, exist_ok=True)
    DST.write_text(body, encoding="utf-8")
    # 当场校验：把头部剥掉后必须与源件**逐字节**一致
    back = DST.read_text(encoding="utf-8")
    assert back.startswith(HEADER), "头部丢失"
    assert back[len(HEADER):] == src_text, "正文与源件不一致（逐字节校验失败）"
    dst_n = len(back.splitlines())
    print(f"[写好] {DST.relative_to(ROOT)}")
    print(f"       头部 {len(HEADER.splitlines())} 行 ＋ 原文 {src_n} 行 ⇒ 共 {dst_n} 行")
    print("       ✅ 剥离头部后与源件**逐字节一致**")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
