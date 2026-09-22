"""给 .ps1 补 UTF-8 BOM（Windows PowerShell 5.1 读 .ps1 默认按 ANSI/GBK 解码）。

⚠️ 为什么必须有这个脚本：源文件若存成「UTF-8 无 BOM」，而脚本里含中文，
PS 5.1 会把 UTF-8 字节按 GBK 解码 —— 解码出的**尾字节会吞掉紧跟的 ASCII 引号**，
症状是**一堆莫名其妙的 ParserError**（`Unexpected token` / `Missing closing '}'`），
而文件本身一点没错。2026-09-21 实测踩过（`ops/nssm_install.ps1` / `ops/server_ctl.ps1`）。

用法：`backend/.venv/Scripts/python.exe tools/_ps_bom.py ops/*.ps1`
（不带参数 ⇒ 默认给 `ops/` 下全部 .ps1 补）
幂等：已有 BOM 的文件跳过。
"""
from __future__ import annotations

import sys
from pathlib import Path

BOM = b"\xef\xbb\xbf"


def fix(path: Path) -> str:
    raw = path.read_bytes()
    if raw.startswith(BOM):
        return "skip"
    text = raw.decode("utf-8")           # 先确认它确实是 UTF-8
    path.write_bytes(BOM + text.encode("utf-8"))
    return "fixed"


def main(argv: list[str]) -> int:
    root = Path(__file__).resolve().parent.parent
    targets = [Path(a) for a in argv] or sorted((root / "ops").glob("*.ps1"))
    if not targets:
        print("no .ps1 found")
        return 0
    for t in targets:
        if not t.is_file():
            print(f"{t}: NOT FOUND")
            continue
        print(f"{t.name}: {fix(t)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
