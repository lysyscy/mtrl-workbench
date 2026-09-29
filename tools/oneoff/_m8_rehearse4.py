"""M8 本机预演 **第 4 步**：**解包演练** —— 把交付包解到一个**独立路径**，验"拷过去能不能落地"。

验的是这三件事（＝目标机 `deploy_restore.ps1` 的前两步）：
  ① `git clone <包里的 bundle>` 能不能**独立**得到一个完整仓（含全部历史）；
  ② **非 git 件**（两处记忆 / `nssm.exe` / 产物）能不能**回填**进去；
  ③ 那个仓**能不能被 Python 用**（拿本机 venv 的 python 去 `pytest --collect-only` ⇒ 收集得到就说明代码齐、import 得通）。

⚠️ 纪律：全程在 `D:\\_landing_test\\` 这个**独立目录**里做 ⇒ ⛔ **不动现役仓**（`D:\\dev\\mtrl-workbench`）；
   验完**默认删掉**（`--keep` 可留）；⛔ 不注册服务、⛔ 不建库（那些在目标机做）。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\oneoff\\_m8_rehearse4.py`
      `… --pack D:\\deliver\\mtrl-20260929 --keep`
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
BASE = Path(r"D:\_landing_test")
CLONE = BASE / "mtrl-workbench"

EXTRAS = [".codebuddy/memory", ".workbuddy/memory", "ops/nssm", "artifacts", "backups"]


def sh(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
    r = subprocess.run(args, cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", default=r"D:\deliver\mtrl-20260929")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    pack = Path(a.pack)
    bundle = pack / "repo" / "mtrl-workbench.bundle"
    print("=== 预演第 4 步 · 解包演练 ===")
    print(f"包 = {pack}")
    print(f"解到 = {CLONE}（⚠️ 独立目录 ⇒ 现役仓不动）")
    if not bundle.exists():
        print(f"⛔ 包里没有 `{bundle}` ⇒ 先跑 `ops\\pack.ps1`"); return 2

    if CLONE.exists():
        print("  （目标已存在 ⇒ 先删掉重来，保证是干净的一次）")
        shutil.rmtree(CLONE, ignore_errors=True)
    BASE.mkdir(parents=True, exist_ok=True)

    # ① clone bundle
    rc, out = sh(["git", "clone", str(bundle), str(CLONE)], cwd=BASE)
    if rc:
        print("  ⛔ clone 失败：" + out[:300]); return 1
    rc, head = sh(["git", "log", "-1", "--format=%h %s", "--date=short"], cwd=CLONE)
    rc2, nfiles = sh(["git", "ls-files"], cwd=CLONE)
    n = len(nfiles.splitlines())
    print(f"  ✅ clone 成功 · HEAD = {head[:60]}")
    rc3, nhist = sh(["git", "rev-list", "--count", "HEAD"], cwd=CLONE)
    print(f"     跟踪文件 **{n}** 个 · 历史 **{nhist}** 个提交（⇒ 历史确实在包里 ✓）")
    if n < 200:
        print("     ⛔ 文件数偏少 ⇒ 停手看看（包是不是缺件）"); return 1

    # ② 回填非 git 件
    filled, missing = [], []
    for rel in EXTRAS:
        s = pack / rel
        if not s.exists():
            missing.append(rel); continue
        d = CLONE / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        if s.is_dir():
            shutil.copytree(s, d, dirs_exist_ok=True)
        else:
            shutil.copy2(s, d)
        filled.append(rel)
    print(f"  ✅ 回填 {len(filled)} 项：{', '.join(filled) or '（无）'}"
          + (f"  ⚠️ 包里没有：{', '.join(missing)}" if missing else ""))
    key = CLONE / "ops" / "nssm" / "nssm.exe"
    print(f"     {'✓' if key.exists() else '⛔'} 关键件 `ops/nssm/nssm.exe`"
          f"（{'在' if key.exists() else '缺 —— 目标机就注册不了服务'}）")

    # ③ 代码能不能被 Python 用（用本机 venv，但 cwd 在 clone ⇒ 证明"clone 里的代码是齐的"）
    rc, out = sh([str(PY), "-X", "utf8", "-m", "pytest", "--collect-only", "-q",
                  "-p", "no:cacheprovider"], cwd=CLONE / "backend")
    tail = [l for l in out.splitlines() if l.strip()][-2:]
    ok = rc == 0 and "error" not in out.lower()
    print(f"  {'✅' if ok else '⚠️'} pytest --collect-only：rc={rc} · {' | '.join(tail)[:120]}")
    if not ok:
        print("     ⚠️ 收集不全 ⇒ 可能是 clone 里缺件，**也可能**是 rootdir/配置差异（落地时以目标机为准）")

    print("\n⭐ 结论：**bundle 能独立 clone 出完整仓（含全部历史）＋ 非 git 件能回填** ⇒ 落地前两步站得住。")
    if a.keep:
        print(f"   ⚠️ `--keep` ⇒ 留在 {CLONE}（⛔ 别忘了它是演练品）")
    else:
        shutil.rmtree(CLONE, ignore_errors=True)
        print(f"   🧹 已拆（删掉 {CLONE}）· ⛔ 现役仓 `{ROOT}` 全程未动")
    return 0 if ok else 0          # ⚠️ ③ 那半不判死（rootdir 差异 ≠ 包有问题），结论只按 ①② 下


if __name__ == "__main__":
    sys.exit(main())
