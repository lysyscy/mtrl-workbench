"""**假改动检出**（`/retro` 候选② · 2026-10-07）——「`git status` 说改了，`git diff` 说没改」的那几件。

- **症状**：`git status --porcelain` 报某件 ` M`，而 `git diff --name-only HEAD` **没有它**；
  索引里的 blob 与 `HEAD` 的 blob **同一个哈希** ⇒ 内容一模一样，只是 **mtime/stat 缓存**对不上。
- ⛔ **它不影响闸门**：`_pytestscope.changed_paths()` 用的是 `git diff --name-only HEAD` ＋
  `ls-files --others` ⇒ **选测范围是对的**。受影响的只有**人读 `git status` 时被带偏**
  （本轮为它白花 6 次工具调用，还差点去"修"一个没改过的文件）。
- ⚠️ **处置**：⛔ 别去 `checkout-index -f`（`core.autocrlf=true` 会把工作区的 LF 改成 CRLF
  ⇒ **真的**动了文件）；也别 `add`（那是提交，不是清缓存）。**先当它不存在**，本件只负责报出来。

用法（两种都行）：
    python tools/oneoff/_fakedirty.py            # 有人假改动 ⇒ 逐行列出；没有 ⇒ 一行 ✅
    python tools/oneoff/_fakedirty.py --json     # 给别的件读（清单 ＋ 空/非空）
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _git(*args) -> list:
    p = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    # 只想保留状态码前的那两个空格：porcelain 每行是 `XY<空格>路径`。
    return [] if p.returncode else [x.rstrip() for x in (p.stdout or "").splitlines() if x.strip()]


def fake_dirty() -> list:
    """git status 说改了的集合 减去 git diff HEAD 说改了的集合（未跟踪件不算：那是真新件）。"""
    said = set()
    for ln in _git("status", "--porcelain"):
        code, path = ln[:2], ln[3:].strip()
        if code == "??" or not path:
            continue
        said.add(path.replace("\\", "/"))
    return sorted(said - set(_git("diff", "--name-only", "HEAD")))


def main() -> int:
    bad = fake_dirty()
    if "--json" in sys.argv:
        print(json.dumps(bad, ensure_ascii=False))
        return 0
    if bad:
        print("⚠️ **假改动 %d 件**（`git status` 说改了，`git diff HEAD` 说没改 —— 内容与 HEAD 逐字节相同）"
              % len(bad))
        for p in bad:
            print("   · %s" % p)
        print("   ⇒ ⛔ **别去「修」它们**（没改）· 也别 `git checkout -f`"
              "（`core.autocrlf=true` 会把 LF 改成 CRLF ⇒ 那才是真改动）· 当作不存在即可")
        print("   ⇒ ⛔ 闸门不受影响（选测读的是 `git diff --name-only HEAD`，不是 `status`）")
        return 0                       # ⭐ **报告型，不判红**：它不影响任何判据，只影响人读 status
    print("✅ 没有假改动（`git status` 与 `git diff HEAD` 说的是同一批件）")
    return 0


if __name__ == "__main__":
    sys.exit(main())