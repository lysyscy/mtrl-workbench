"""**推送前敏感件审计**（口径 = `TAIL-88`：推送前必须审，要求 **0 命中**）。

⭐ 为什么落成脚本：这是**每次 push 都要做**的动作 —— 靠"我记得"迟早漏（本仓的规矩：反复要跑的一串
命令就落成脚本）。它**只读**，不改任何东西。

三件事：
1. **版本库里跟踪了哪些"名字敏感"的件**（`.env` / cookie / nssm 实例配置 / `.venv` / scratch / backups …）
   —— ⚠️ 命中**不等于**有问题（本仓有 `.env.example` / `cookie_store.py` / `ops/nssm_*.ps1` 这类**本来就该跟踪**的），
   所以要**逐条人看**；
2. **这些"本该不进版本库"的东西确实没被跟踪**（`.env` / `.venv` / `logs/` / `artifacts/` 里的运行产物 /
   `.workbuddy/backups/` / `00-scratch/`）；
3. **待推送的 diff 里有没有真凭据**（私钥块 / cookie 串 / 带非空值的 `password=` / `secret=`）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_prepush_sensitive.py`
       `… --diff <A>..<B>`（默认 = `origin/master..HEAD`）
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[2]

#: ① 名字敏感（⚠️ 命中要人看：本仓有些**本来就该跟踪**）
NAME_PATTERNS = (
    r"(^|/)\.env",            # `.env` 本体（⛔ 不该跟踪）· `.env.example`（✓ 该跟踪）
    r"cookie",                # `cookie_store.py`（✓）· 真 cookie 文件（⛔）
    r"nssm",                  # `ops/nssm_*.ps1`（✓）· nssm 实例配置（⛔）
    r"\.venv/",
    r"scratch",
    r"backups",
    r"\.pem$|\.key$|\.pfx$|\.p12$",
)

#: ② 这些**必须**是"未跟踪"（`git ls-files` 命中即红）
MUST_NOT_TRACK = (".env",)          # 精确文件名（根 `.env`）

#: ③ diff 里的真凭据形态
DIFF_PATTERNS = (
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "私钥块"),
    (r"(?i)\b(password|passwd|pwd)\s*=\s*[\"']?[^\s\"'#]{3,}", "带值的口令"),
    (r"(?i)\b(session_secret|secret|token|api_key)\s*=\s*[\"']?[A-Za-z0-9+/=_\-]{8,}", "带值的密钥"),
    (r"(?i)cookie\s*[:=]\s*[^\s]+=[^\s;]+;", "cookie 串"),
)


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--diff", default="origin/master..HEAD", help="要审的提交区间（默认 origin/master..HEAD）")
    args = ap.parse_args()

    print("=" * 78)
    print(f" ① 版本库里「名字敏感」的跟踪件（⚠️ 命中要人看，不是自动红）｜range = {args.diff}")
    print("=" * 78)
    files = [f for f in _git("ls-files").splitlines() if f.strip()]
    bad_names = 0
    for rx in NAME_PATTERNS:
        hits = [f for f in files if re.search(rx, f)]
        for f in hits:
            print(f"   · {f}")
            bad_names += 1
    print(f"   （共 {bad_names} 条命中 —— 逐条确认「本来就该跟踪 / 真凭据」）")

    print()
    print("=" * 78)
    print(" ② 本该「不进版本库」的**未跟踪**确认")
    print("=" * 78)
    #: ⚠️ `.gitkeep` 是**空占位件**（用来把空目录带进 git）⇒ ⛔ **不算命中** ——
    #:    第一版没排除它 ⇒ 把 `logs/.gitkeep` / `00-scratch/.gitkeep` 报成"⛔ 被跟踪"（**误报**）。
    #:    ⭐ 本仓的规矩：**别喊狼来了**（噪声一多，真命中就没人看了）。
    def _real(d: str) -> list[str]:
        return [f for f in files if f.startswith(d) and not f.endswith(".gitkeep")]

    untracked_ok = True
    for name in MUST_NOT_TRACK:
        hit = [f for f in files if (f == name or f.endswith("/" + name))]
        print(f"   {'⛔ 被跟踪！' if hit else '✅ 未跟踪'}  {name}" + (f"  → {hit}" if hit else ""))
        untracked_ok = untracked_ok and not hit
    for d in (".venv/", "logs/", ".workbuddy/backups/", ".workbuddy/work/00-scratch/", ".git/"):
        hit = _real(d)
        note = "" if not hit else f"  → {len(hit)} 件：{hit[:5]}"
        print(f"   {'⛔ 被跟踪！' if hit else '✅ 未跟踪'}  {d}*（`.gitkeep` 不算）{note}")
        untracked_ok = untracked_ok and not hit

    print()
    print("=" * 78)
    print(f" ③ 待推送 diff（{args.diff}）里的真凭据形态")
    print("=" * 78)
    diff = _git("diff", args.diff)
    stat = _git("diff", "--stat", args.diff)
    print("   " + (stat.strip().splitlines()[-1] if stat.strip() else "（无改动）"))
    clean = True
    for rx, label in DIFF_PATTERNS:
        hits = [ln.strip()[:120] for ln in diff.splitlines() if re.search(rx, ln)]
        # `.env.example` 里的空值不算（`KEY=`）；这里只报**带值**的命中（正则已要求非空）
        if hits:
            clean = False
            print(f"   ⛔ {label}：{len(hits)} 条")
            for h in hits[:8]:
                print(f"       {h}")
        else:
            print(f"   ✅ {label}：0 条")

    print()
    verdict = "✅ 可以做推送前的人眼复核（看上面 ① 那几条是不是本来就该跟踪）" if (clean and untracked_ok) \
        else "⛔ 有命中 ⇒ **先查清再推**（⛔ 别硬推）"
    print("=" * 78)
    print(f" 结论：{verdict}")
    print("=" * 78)
    return 0 if (clean and untracked_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
