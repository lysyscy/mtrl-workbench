"""**字节哨** —— 抓三类「写完才发现、而且机器看不出来」的落盘事故：行尾混排 / 坏字符 / BOM 装错地方。

## 守什么（为什么它必须存在）

`MEMORY.md §四` 早有两条纪律：**「新件 UTF-8 无 BOM ＋ LF；改已有文件按它自己的行尾」**、
**「坏字符（U+FFFD）静默落盘 ⇒ 写完必扫」**。⚠️ 但 2026-10-07 量下来：这两条**全是散文，全仓零机器眼**
（`syntax_audit` / `doc_audit` 都不判这三样）⇒ 那一轮我为此**手写了 3 遍**一次性检查脚本，其中两遍还是重复的。
⇒ 散文已经证明挡不住（人只在"想起来"时才扫），所以这里补成**每一次落盘都自动过一遍**的哨。

## 四条规则

| 规则 | 判红条件 |
|---|---|
| `B1` | **单个文件内部**混了 CRLF 与裸 LF（⛔ 不是"全仓统一"：`core.autocrlf=true` 下 CRLF 件是既有事实，判据只管**一件之内不许混**） |
| `B2` | 文件里有 **U+FFFD**（坏字符静默落盘；编辑器/脚本一旦写坏，尺子读出来是"看着能用"的垃圾） |
| `B3` | **`.ps1` 必须带 BOM**（PS 5.1 按 GBK 读中文 ⇒ 没 BOM 就解析错）· **其它文本件不许带 BOM**（⛔ `.ps1` 是唯一例外，两条别看反） |
| `B4` | 文本件**必须能严格按 UTF-8 解码**（GBK/UTF-16 落盘 ⇒ 尺子读出来是乱码，而你看着"有字"） |

⚠️ **`B3` 为什么把 `.ps1` 单列**：那是本仓唯一**必须**有 BOM 的后缀（`MEMORY §四` 坑 2-② · 工具 `tools/oneoff/_ps_bom.py`）⇒
把它跟其它后缀放同一条规则里判，等于把这条例外抹掉。

## 为什么 `B1` 不判"全仓统一行尾"

本机 `core.autocrlf=true` ⇒ 仓里 **CRLF 件与 LF 件各占一半**（`.ps1`/`.md` 多为 CRLF，`.py` 多为 LF）——
判"全仓统一"会一次性点红几十个存量文件，那是**存量债不是本轮的动作**（同 `syntax_audit Q4` 的取舍）。
⇒ 本哨只抓**一件之内混排**（那才是真事故：脚本按 `newline=""` 读写时最容易造出来）。

## 用法

    backend\\.venv\\Scripts\\python.exe tools\\audit\\bytes_guard.py# 全量（仓内）
    backend\\.venv\\Scripts\\python.exe tools\\audit\\bytes_guard.py --staged   # 只查本轮暂存（pre-commit 用）

⚠️ 本哨**只读字节**，⛔ 不改任何文件（修法在报红那行里写明）。
反向灵敏度：`tools/mut/_mut_bytesguard.py`（四条规则各造一次红 ＋ 正常件必须放行）。
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

#: 只管**文本件**（二进制件的行尾/编码规则无意义 ⇒ 进来就是噪音）
TEXT_SUFFIXES = {".py", ".md", ".mdc", ".js", ".html", ".css", ".json", ".sql", ".yml", ".yaml",
                 ".ps1", ".sh", ".txt", ".cfg", ".ini", ".toml", ".mjs", ".cjs"}
TEXT_NAMES = {".gitattributes"}


def is_text(path: Path) -> bool:
    return path.name in TEXT_NAMES or path.suffix.lower() in TEXT_SUFFIXES

#: 不是本仓手写的源码（虚拟环境 / 缓存 / 产物 / 备份）
SKIP_DIRS = {".venv", "__pycache__", "node_modules", "artifacts", ".git", ".pytest_cache", "logs"}

#: ⭐⭐ **`.scratch/local/` 整目录排除** —— 那不是"无人在意的源码"，而是
#:   **别的尺子故意造的坏样本存放处**（`_t233_eol.py` 里就写着 `U+FFFD` 两个字符当断言值、
#:   `_t235_*.txt` 是带 BOM 的样本）⇒ 把本哨扫进去，等于**逼尺子去报自己的粮食**。
#:   ⛔ 所以这不是"放宽判据"，是把"源码"与"样本"分开—— 两者不该用同一条判据。
SKIP_PREFIXES = (("var",), ("data",), ("exports",), ("dist",), (".scratch", "local"), (".artifacts",))

#: ⭐ **必须带 BOM** 的后缀（`B3` 的唯一例外）
BOM_REQUIRED = {".ps1"}

BOM = b"\xef\xbb\xbf"
FFFD = b"\xef\xbf\xbd"


def iter_text() -> list[Path]:
    out: list[Path] = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or not is_text(p):
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        # 一次性区与备份区：里面**故意**有坏样本 ⇒ 不在守什么范围内（见 `SKIP_PREFIXES`）
        # ⚠️ 必须拿**相对仓根**的分量比：`p.parts` 是绝对路径（`('D:\\', 'dev', …)`）⇒ 拿它比前缀永远不匹配。
        rel_parts = p.relative_to(ROOT).parts
        if any(rel_parts[:len(pre)] == pre for pre in SKIP_PREFIXES):
            continue
        out.append(p)
    return out


def staged_text() -> list[Path]:
    """暂存区里的文本件（`git diff --cached`）—— pre-commit 的输入。

    ⭐ 必须带 `-c core.quotepath=false`（`TAIL-239` 撞过一次：中文路径被转义成八进制 ⇒ 取不到）。
    """
    r = subprocess.run(["git", "-c", "core.quotepath=false", "diff", "--cached", "--name-only"],
                       cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    out: list[Path] = []
    for x in (r.stdout or "").splitlines():
        name = x.strip().replace("\\", "/")
        if not name:
            continue
        p = ROOT / name
        if p.is_file() and is_text(p):
            out.append(p)
    return out


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p)


def rule_b1_mixed_eol(files: list[Path]) -> list[str]:
    """`B1` —— 一件之内不许混 CRLF 与裸 LF。"""
    bad: list[str] = []
    for p in files:
        b = p.read_bytes()
        crlf = b.count(b"\r\n")
        lf = b.count(b"\n") - crlf
        cr = b.count(b"\r") - crlf
        if crlf and lf:
            bad.append(f"{_rel(p)}：**一件之内混排行尾**（CRLF {crlf} / 裸LF {lf}）"
                       f" ⇒ 修法：整份统一成它**多数**的那种（脚本读写用 `newline=\"\"`）")
        elif cr:
            bad.append(f"{_rel(p)}：有 {cr} 个**裸 CR**（老 Mac 换行）⇒ 修法：换成 CRLF 或 LF")
    return bad


def rule_b2_fffd(files: list[Path]) -> list[str]:
    """`B2` —— 不许有 U+FFFD（坏字符静默落盘）。"""
    bad: list[str] = []
    for p in files:
        b = p.read_bytes()
        n = b.count(FFFD)
        if n:
            i = b.find(FFFD)
            ctx = b[max(0, i - 40): i + 40].decode("utf-8", errors="replace").replace("\n", " ")
            bad.append(f"{_rel(p)}：**{n} 个 U+FFFD（坏字符）** ⇒ 它读出来是'看着能用'的垃圾"
                       f"｜附近：…{ctx}…")
    return bad


def rule_b3_bom(files: list[Path]) -> list[str]:
    """`B3` —— `.ps1` 必须带 BOM；其它文本件**不许**带。"""
    bad: list[str] = []
    for p in files:
        has = p.read_bytes().startswith(BOM)
        need = p.suffix.lower() in BOM_REQUIRED
        if need and not has:
            bad.append(f"{_rel(p)}：`.ps1` **缺 BOM** ⇒ PS 5.1 按 GBK 读中文会解析错"
                       f" ⇒ 修法：`tools/oneoff/_ps_bom.py` 加上去")
        elif not need and has:
            bad.append(f"{_rel(p)}：**不该有 BOM**（只有 `.ps1` 要；它会让 diff 首行多出"
                       f"`<feff>`、部分工具读出乱码）⇒ 修法：按 UTF-8 **无** BOM 重写")
    return bad


def rule_b4_utf8(files: list[Path]) -> list[str]:
    """`B4` —— 必须能严格按 UTF-8 解码（抓 GBK / UTF-16 落盘）。"""
    bad: list[str] = []
    for p in files:
        b = p.read_bytes()
        try:
            b.decode("utf-8")
        except UnicodeDecodeError as exc:
            bad.append(f"{_rel(p)}：**不是合法 UTF-8**（{exc.reason}，字节 {exc.start}）"
                       f" ⇒ 多半是 GBK/UTF-16 落盘 ⇒ 修法：按 UTF-8 无 BOM 重写")
    return bad


RULES = (
    ("B1", "一件之内不许混行尾（CRLF 与裸 LF）", rule_b1_mixed_eol),
    ("B2", "不许有 U+FFFD 坏字符", rule_b2_fffd),
    ("B3", "`.ps1` 必须带 BOM · 其它文本件不许带", rule_b3_bom),
    ("B4", "必须能严格按 UTF-8 解码", rule_b4_utf8),
)


def check(files: list[Path], title: str) -> int:
    print("=" * 78)
    print(" 字节哨 · bytes_guard —— 「行尾没混 / 没坏字符 / BOM 装对 / 能按 UTF-8 读」")
    print("=" * 78)
    print(f"（{title}：{len(files)} 件）")
    must = 0
    for code, what, fn in RULES:
        bad = fn(files)
        must += len(bad)
        print(f"\n─ {code} · {what}")
        if bad:
            for x in bad[:12]:
                print(f"   ⛔ {x}")
            if len(bad) > 12:
                print(f"   … 还有 {len(bad) - 12} 条")
        else:
            print("   ✅ 通过")
    print(f"\n结论：**必须修 {must}**" + ("（有红 ⇒ 非零退出）" if must else ""))
    return 0 if must == 0 else 1


def main(argv: list[str]) -> int:
    if "--paths" in argv:
        names = argv[argv.index('--paths') + 1:]
        if not names:
            # 无差异仍检查入口自己，不能空扫伪装成通过。
            names = ['tools/oneoff/_run_rulers.py']
        files = []
        for name in names:
            p = (ROOT/name).resolve()
            if not p.is_relative_to(ROOT) or not p.is_file() or not is_text(p):
                print('字节哨输入无法证明：', name)
                return 1
            files.append(p)
        return check(files, '实际改动文本')
    if "--staged" in argv:
        return check(staged_text(), "本轮暂存")
    return check(iter_text(), "全量 · 仓内文本件")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
