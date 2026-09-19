"""**反向灵敏度**：证明 `tests/test_wired_boot.py`（性能 `P2` 分组并行 ＋ `P3` 页级按需取数）**真有区分力**。

做法：逐条把实现**改坏** → 确认**对应的那条断言变红** → 全部复原（**MD5 逐字节校验**）。
⚠️ 若某条变异**没能让断言变红** ⇒ 那条断言是**假绿** ⇒ 脚本报错退出。

⚠️ 一律走 **bytes**（`index.html` = **CRLF**）：按目标文件行尾归一后再替换，还原也用**原 bytes**
   —— 用 `write_text(newline=…)` 会把 CRLF 静默换成 LF ⇒ MD5 假 BAD。
⚠️ 子进程必须设 `ACC_RESULTS_PATH`（否则每处变异把权威 `acc_results.json` 冲成单条）
   与 `PYTHONIOENCODING=utf-8`（否则 Windows 上 GBK 解码假红）。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BE = ROOT / "backend"
SHELL = BE / "app" / "web" / "index.html"
PY = BE / ".venv" / "Scripts" / "python.exe"
TEST = "tests/test_wired_boot.py"


def _b(s: str) -> bytes:
    """把源码片段编成 **LF** bytes（脚本里一律按 LF 写片段，匹配前再按目标文件归一）。"""
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(fragment: bytes, sample: bytes) -> bytes:
    """把 LF 片段转成**与目标文件一致**的行尾（目标含 CRLF ⇒ 转 CRLF，否则原样）。"""
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


# (说明, 文件, 原文（LF）, 改成（LF）, 应变红的用例名)
MUTS: list[tuple[str, Path, bytes, bytes, str]] = [
    (
        "M1 依赖组被拆掉（`收发结存与大表`/`付款域` 与前置路并行 ⇒ 大表机械列取空）",
        SHELL,
        _b("  await Promise.all(fresh.filter(l => !LOAD_DEP.has(l)).map(l => soft(l, LOADERS[l])));\n"
           "  await Promise.all(fresh.filter(l => LOAD_DEP.has(l)).map(l => soft(l, LOADERS[l])));\n"),
        _b("  await Promise.all(fresh.map(l => soft(l, LOADERS[l])));\n"),
        "test_依赖路必须等机械与库存",
    ),
    (
        "M2 `m07` 的清单里漏掉「机械 6 列」（吃大表却不等机械 ⇒ 那一列会取空）",
        SHELL,
        _b("  m07: ['机械 6 列', '库存单据', '收发结存与大表'],\n"),
        _b("  m07: ['库存单据', '收发结存与大表'],\n"),
        "test_依赖路必须等机械与库存",
    ),
    (
        "M3 逐路容错被破（失败不再记进 fails ⇒ 横幅点不了名）",
        SHELL,
        _b("  try { await fn(); } catch (e) { fails.push(`${label}：${String((e && e.message) || e)}`); }\n"),
        _b("  try { await fn(); } catch (e) { /* 吞掉 */ }\n"),
        "test_逐路容错未破",
    ),
    (
        "M4 `m05Sync` 的两道闸被拿掉（启动期 / 该页没取过数时又会白白连拉）",
        SHELL,
        _b("  if (BOOTING || m05Refetching || !LOADED.has('付款域')) return;\n"),
        _b("  if (m05Refetching) return;\n"),
        "test_没到位就不补拉",
    ),
    (
        "M5 `boot()` 退回「全量拉 13 路」（`P3` 白做 —— 首屏又变成秒级）",
        SHELL,
        _b("  await loadPaths(PAGE_LOAD[VIEW] || []);\n"),
        _b("  await loadPaths(Object.keys(LOADERS));\n"),
        "test_boot只拉初始视图而go按需拉",
    ),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(case: str) -> bool:
    env = {**os.environ,
           "ACC_RESULTS_PATH": "../artifacts/_mut_acc_results.json",
           "PYTHONIOENCODING": "utf-8",
           "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run(
        [str(PY), "-m", "pytest", "-q", f"{TEST}::{case}"],
        cwd=str(BE), capture_output=True, text=True, encoding="utf-8",
        errors="replace", env=env,
    )
    return r.returncode == 0


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old_lf, new_lf, case in MUTS:
        src = path.read_bytes()
        old, new = _fit(old_lf, src), _fit(new_lf, src)
        n = src.count(old)
        if n != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {n} 次（期望 1）⇒ **未验证**")
            continue
        path.write_bytes(src.replace(old, new, 1))
        red = not run_one(case)
        path.write_bytes(src)                      # 逐条按原 bytes 还原
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc + f"  → `{case}` " + ("变红" if red else "**仍是绿的**"))
        hit += red

    print()
    ok = all(md5(p) == h for p, (_, h) in before.items())
    print(f"  命中 {hit}/{len(MUTS)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if ok else '❌ 有文件没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
