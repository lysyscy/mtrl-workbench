"""**反向灵敏度**：证明「**2026-09-19 扩面后的 `T4`**」与「`T6` 的新落点检查」**真有区分力**。

背景（为什么非做不可）：
- `T4` 原实现只看「当前版本」行**后 8 行**里的**第一处**四态数字 ⇒ 实测漏过一次真漂移
  （简略版某处还写着 `521 = 绿 447`，而 `T4` 报"必须修 0"）。已改成**两份活文档的每一处**都核对。
- `T6` 原来查「简略版 §③ 必读清单里有没有计划名」；简略版改成**给用户看的一页**后那段没了
  ⇒ 检查落点改为「**简略版里必须指向计划**」。落点一改，就得重新证明它还能红。

做法：逐条把实现**改坏** → 确认 `doc_audit` **非零退出（有红）** → 全部复原（**MD5 逐字节校验**）。
⚠️ 一律走 bytes ＋ 按目标文件行尾归一（`.md` 可能是 CRLF，`write_text` 会静默换成 LF ⇒ MD5 假 BAD）。
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLANS = ROOT / ".workbuddy" / "plans"
HAND = PLANS / "执行情况-主文档.md"
PLAN = PLANS / "开发计划-主文档.md"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"


def _b(s: str) -> bytes:
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(frag: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return frag.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return frag.replace(b"\r\n", b"\n")


# (说明, 文件, 原文, 改坏成, 全部替换?)
MUTS: list[tuple[str, Path, bytes, bytes, bool]] = [
    ("M1 简略版的四态数字改错（原 T4 看不见这一处 —— 扩面后才抓得到）",
     HAND, _b("**528 = 绿 454 · 红 0 · 待建 9 · 未绑定 65**"),
     _b("**528 = 绿 453 · 红 0 · 待建 9 · 未绑定 65**"), False),
    ("M2 简略版里不再指向计划文档（台账就没人看得见）",
     HAND, _b("开发计划-主文档"), _b("某份计划文档"), True),
    ("M3 台账顶部计数与实际不符（人按错的数判断尾巴有多少）",
     PLAN, _b("A 类 **10** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **41** 条"),
     _b("A 类 **9** 条 · B 类 **0** 条 · C 类 **0** 条 · 已销号 **41** 条"), False),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def doc_audit_red() -> int:
    """→ 「必须修 N」里的 N（**不看退出码** —— `doc_audit` 的 rc 还含 `T5` 行数红，两回事）。"""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([str(PY), str(ROOT / "tools" / "doc_audit.py")],
                       cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", env=env)
    m = re.search(r"必须修 (\d+)", r.stdout or "")
    return int(m.group(1)) if m else -1


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    print("基线（未改坏）doc_audit 必须修 0 ⇒ 非零退出？", doc_audit_red(), "（应为 False）")
    hit = 0
    for desc, path, old_lf, new_lf, all_ in MUTS:
        src = path.read_bytes()
        old, new = _fit(old_lf, src), _fit(new_lf, src)
        n = src.count(old)
        if n == 0 or (not all_ and n != 1):
            print(f"  ⛔ {desc} —— 锚点命中 {n} 次（期望 {'≥1' if all_ else '1'}）⇒ **未验证**")
            continue
        path.write_bytes(src.replace(old, new))          # all_ 时全替换
        red = doc_audit_red()
        path.write_bytes(src)                            # 逐条按原 bytes 还原
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc + "  → doc_audit " + ("变红" if red else "**仍是绿的**"))
        hit += red

    print()
    ok = all(md5(p) == h for p, (_, h) in before.items())
    print(f"  命中 {hit}/{len(MUTS)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if ok else '❌ 有文件没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
