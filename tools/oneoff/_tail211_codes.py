"""`TAIL-211`：清掉**后端拼进回执 / 报错的串**里的工程代号与工程侧路径。

口径 = 守则 §2.5 / §3.1（用业务术语 · 技术实现细节不上屏）＋ `D29`（内部编号 ⇒ 删）。
⭐ 这批是**先量后清**：`tools/oneoff/_text_ctx9.py --codes` 量出 **11 处**命中，
   其中 **2 处是假阳性**（① 属性 docstring ② 守卫表 `FORBIDDEN_TEXTS` 的墓碑值）⇒ 清 **9 处**、判据那边用
   「跳过裸字符串语句 ＋ 代号带反引号不算」两条边界把假阳性钉掉（见 `backend/tests/test_ux_text.py`）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_tail211_codes.py`          # 干跑
      `… --apply`
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
A = "backend/app"

#: (件, 行号, 原文, 新文, 该行命中次数)
LINES: list[tuple[str, int, str, str, int]] = [
    (f"{A}/mod01_projects/recovery.py", 179,
     "需人工确认类型（决策 1 兜底）", "需人工确认类型", 1),
    (f"{A}/mod01_projects/recovery.py", 196,
     "（决策 2：普通项目 ↔ 仓库 = 1 : 1）", "", 1),
    (f"{A}/mod01_projects/router.py", 370,
     "（决策 2：一条普通项目只挂一个仓库）", "", 1),
    (f"{A}/mod03_notice/notice_actions.py", 56,
     "（DEV-P-04）", "", 1),
    (f"{A}/mod03_notice/router.py", 167,
     "（链路 A）", "", 1),
    (f"{A}/mod07_setl/fetch_service.py", 75,
     "仓库名单（API-05）本次没取到", "仓库名单本次没取到", 1),
    (f"{A}/mod08_inv/fetch_service.py", 83,
     "仓库名单（API-05）本次没取到", "仓库名单本次没取到", 1),
    (f"{A}/mod08_inv/domain.py", 361,
     '"label": "导出 Excel（R1）"', '"label": "导出 Excel"', 1),
]

#: (件, 原文块, 新文块)
BLOCKS: list[tuple[str, str, str]] = [
    (f"{A}/report_export/resources.py",
     '_OPS_DOC = "ops/模板法导出-实测结论.md §五"\n'
     '_RETRY = ("请从交付面 `PRD素材包-20260911/data/templates/` 重新复制这一份进 "\n'
     '          "`backend/app/resources/templates/`（该目录进 git），并核对 SHA256（见 %s）。" % _OPS_DOC)',
     "#: ⚠️ `_RETRY` 是**给用户看的**（模板缺失 / 损坏 ⇒ 导出被拦时上屏）⇒ ⛔ 不许写工程侧路径 / 内部文件名。\n"
     "#:   2026-10-01（`TAIL-211`）：原先写着「见 ops/模板法导出-实测结论.md §五」＋ 交付面与仓内两条路径\n"
     "#:   —— 那是**写给维护者**的（守则 §3.1）；维护口径改走 `ops/` 那份文档，⛔ 别写回这里。\n"
     '_RETRY = "请让维护人重新部署导出模板（模板是成品文件的**基底**，缺失或损坏时无法导出）。"'),
]


def _read(p: pathlib.Path) -> str:
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def _write(p: pathlib.Path, text: str) -> None:
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def main() -> int:
    apply = "--apply" in sys.argv
    cache: dict[str, str] = {}
    bad: list[str] = []
    for rel, ln, old, new, cnt in LINES:
        cache.setdefault(rel, _read(ROOT / rel))
        lines = cache[rel].split("\n")
        got = lines[ln - 1].count(old) if ln - 1 < len(lines) else -1
        if got != cnt:
            bad.append(f"{rel}:{ln} —— 期望 {cnt} 次、实测 {got}：{old[:50]!r}")
    for rel, old, _ in BLOCKS:
        cache.setdefault(rel, _read(ROOT / rel))
        n = cache[rel].count(old)
        if n != 1:
            bad.append(f"{rel} —— 块命中 {n} 次（要 1）：{old.splitlines()[0][:50]!r}")
    print(f"行替换 {len(LINES)} 条 ＋ 块替换 {len(BLOCKS)} 块 ⇒ 不达标 {len(bad)}")
    for x in bad:
        print("   ✗", x)
    if bad or not apply:
        print("（干跑 —— ⛔ 没写盘）" if not apply else "（⛔ 不达标 ⇒ 整批不写盘）")
        return 1 if bad else 0

    for rel in sorted(cache):
        text = _read(ROOT / rel)
        lines = text.split("\n")
        for r, ln, old, new, cnt in LINES:
            if r != rel:
                continue
            assert lines[ln - 1].count(old) == cnt, f"写盘前复核失败 {rel}:{ln}"
            lines[ln - 1] = lines[ln - 1].replace(old, new, cnt)
        text = "\n".join(lines)
        for r, old, new in BLOCKS:
            if r != rel:
                continue
            assert text.count(old) == 1, f"写盘前复核失败（块）{rel}"
            text = text.replace(old, new, 1)
        _write(ROOT / rel, text)
        print(f"   已写 {rel}")
    print(f"\n✅ 落盘完成：{len(cache)} 件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
