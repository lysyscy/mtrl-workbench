"""**反向灵敏度**（`U5` · `TAIL-65`）：证明 `ui_parity` 的 `U5` 真守得住「壳公共件 ⇄ 原型同段」。

三条：
- `M1` 改**壳侧**一个字节（`CAP_TOL` 口径常量）⇒ 红；
- `M2` 改**原型侧** —— ⚠️ **用一份临时副本 ＋ `--proto`**，⛔ **绝不打开写交付面那份**；
- `M3` 登记表里塞一个**幽灵名字**（件改名/删了却没同步本表）⇒ 红。

⚠️ 每条跑完**立即按 bytes 复原**；收尾核 MD5（逐字节）。
⚠️ **本件只动工程仓里的文件**（壳的某一件 ＋ 本尺子自己）；交付面那份**只读**。
⚠️ 与 `_mut_chain` 同款：`atexit` **兜底复原**（脚本中途崩了也不许把变异留在文件里）。
"""

from __future__ import annotations

import atexit
import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "audit"))
from shell_source import resolve  # noqa: E402  ← 锚点在哪一件就改哪件

PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
TOOL = ROOT / "tools" / "audit" / "ui_parity.py"
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")
COPY = ROOT / "artifacts" / "_u5_proto_copy.html"

#: 变异点：`U5` 登记表里的一条**口径常量**（两边逐字一致 ⇒ 改任一侧都该红）
ANCHOR_OLD = "const CAP_TOL=0.005;"
ANCHOR_NEW = "const CAP_TOL=0.006;"
#: 登记表里的一个名字（`M3` 把它改成不存在的名字 ⇒ 幽灵条目）
NAME_OLD = '"ARC_TEXT",'
NAME_NEW = '"ARC_TEXT_TYPO",'

#: 兜底：{路径: 原字节}（`atexit` 里逐字节写回）
_BACKUP: dict[pathlib.Path, bytes] = {}


def _restore_all() -> None:
    for p, b in list(_BACKUP.items()):
        try:
            if p.exists() and p.read_bytes() != b:
                p.write_bytes(b)
                print(f"  ↩︎ 复原：{p.relative_to(ROOT)}")
        except Exception as e:                                     # noqa: BLE001 — 兜底不许再抛
            print(f"  ❌ 兜底复原失败 {p}：{e}")


atexit.register(_restore_all)


def _md5(p: pathlib.Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _run(*extra: str) -> int:
    r = subprocess.run([str(PY), str(TOOL), *extra], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode


def _mutate_bytes(p: pathlib.Path, old: str, new: str) -> bool:
    """按 bytes 改一处（LF/CRLF 都能命中）；改前记原字节。"""
    src = p.read_bytes()
    _BACKUP[p] = src
    for a, b in ((old.encode("utf-8"), new.encode("utf-8")),
                 (old.replace("\n", "\r\n").encode("utf-8"),
                  new.replace("\n", "\r\n").encode("utf-8"))):
        if a in src:
            p.write_bytes(src.replace(a, b, 1))
            return True
    return False


def main() -> int:
    if not PROTO.exists():
        print(f"⛔ 找不到原型（交付面）：{PROTO}")
        return 1

    base = _run()
    print(f"基线（未改坏）ui_parity ⇒ rc={base}（期望 0）")
    if base != 0:
        print("⛔ 基线非零 ⇒ 后面每一条都会'看起来变红'（**全假红**）—— 先修基线再跑本件。")
        return 1

    hit = 0
    # ── M1 · 壳侧漂移（锚点在哪一件就改哪件）
    part = resolve(ANCHOR_OLD)
    before_part = _md5(part)
    ok1 = _mutate_bytes(part, ANCHOR_OLD, ANCHOR_NEW)
    rc1 = _run() if ok1 else base
    _restore_all()
    red1 = ok1 and rc1 != 0
    print(f"{'✅' if red1 else '⛔'} M1 壳侧 `CAP_TOL` 口径常量被改 ⇒ rc={rc1}"
          + (f"（{part.name}）" if ok1 else "  ← **锚点没命中**"))
    print(f"      复原 MD5 一致 = {_md5(part) == before_part}")

    # ── M2 · 原型侧漂移（⚠️ 临时副本 ＋ `--proto`；交付面那份从不打开写）
    COPY.write_bytes(PROTO.read_bytes())
    _BACKUP[COPY] = COPY.read_bytes()
    _mutate_bytes(COPY, ANCHOR_OLD, ANCHOR_NEW)
    rc2 = _run("--proto", str(COPY))
    _restore_all()
    COPY.unlink(missing_ok=True)
    _BACKUP.pop(COPY, None)
    red2 = rc2 != 0
    print(f"{'✅' if red2 else '⛔'} M2 **原型侧**漂移（临时副本）⇒ rc={rc2}")
    print(f"      交付面那份**全程只读**（本件从未以写模式打开它）")

    # ── M3 · 登记表里的幽灵名字
    before_tool = _md5(TOOL)
    ok3 = _mutate_bytes(TOOL, NAME_OLD, NAME_NEW)
    rc3 = _run() if ok3 else base
    _restore_all()
    red3 = ok3 and rc3 != 0
    print(f"{'✅' if red3 else '⛔'} M3 登记表塞幽灵名字 ⇒ rc={rc3}"
          + ("" if ok3 else "  ← **锚点没命中**"))
    print(f"      复原 MD5 一致 = {_md5(TOOL) == before_tool}")

    hit = sum((red1, red2, red3))
    ok = _md5(TOOL) == before_tool and _md5(part) == before_part and not COPY.exists()
    rc_final = _run()
    print(f"\n  命中 {hit}/3 · 复原校验（MD5 逐字节）：{'✅ 已复原' if ok else '❌ 没复原'}")
    print(f"  末了再跑一次基线 ⇒ rc={rc_final}（期望 0）")
    return 0 if (hit == 3 and ok and rc_final == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
