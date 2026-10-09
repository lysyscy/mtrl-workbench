"""反向灵敏度（`bytes_guard` —— 行尾 / 坏字符 / BOM / 编码）—— 证明它**真有区分力**。

⚠️ 这四条规则是**散文纪律的机器化**（`MEMORY.md §四`："改已有文件按它自己的行尾"
  ＋ "坏字符静默落盘 ⇒ 写完必扫"）。⚠️ 本仓吃过 5 次「加了判据却没人跑」⇒ 判据一落地就要有证伪件。

五靶（靶件落 `tools/audit/` 下、**用完即删**）：`M1` 混行尾 · `M2` U+FFFD ·
`M3` `.ps1` 缺 BOM · `M4` GBK 落盘 —— 四条都必须红；`M5` **正常件必须放行**。
⚠️ `M5` 最容易被漏：没有它，四条规则可以"永远红"而没人发现（与哑靶同病、方向相反）。

用法：python tools/mut/_mut_bytesguard.py
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PY = pathlib.Path(sys.executable)
RULER = ROOT / "tools" / "audit" / "bytes_guard.py"
TDIR = ROOT / "tools" / "audit"
PFX = "_mut_tmp_bytesguard_"

#: (后缀, 造什么坏, 期望在输出里看到的字) —— 四条坏形态
#: ⚠️⚠️ **`fffd` 那行必须用字节转义构造，不能把 U+FFFD 字符本身写进源码** ——
#:   否则**本件自己**就是 `B2` 的命中件（`tools/mut/` 不在字节哨的豁免面里）⇒ 尺子一落地就报自己的红。
#:   （同族：`T8`「别写被判据钉住的字面」；这里是它在本尺子上的具体形态。）
BAD = (
    ("mixed.txt", b"AAA\r\nBBB\nCCC\r\n", "混排行尾"),
    ("fffd.txt", b"\xe5\xa4\xb4\n\xef\xbf\xbd\n\xe5\xb0\xbe\n", "U+FFFD"),
    ("nobom.ps1", "Write-Host \"没有 BOM 的 ps1\"\n".encode("utf-8"), "缺 BOM"),
    ("gbk.txt", "中文标题\n".encode("gbk"), "UTF-8"),
    ("rule.mdc", b"AAA\r\nBBB\n", "混排行尾"),
)


def run_ruler() -> tuple[int, str]:
    r = subprocess.run([str(PY), "-X", "utf8", str(RULER)], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _main() -> int:
    good = TDIR / (PFX + "good.txt")
    targets = [TDIR / (PFX + n) for n, _, _ in BAD]
    ruler_md5 = hashlib.md5(RULER.read_bytes()).hexdigest()
    cases: list[tuple[str, bool, str]] = []
    try:
        good.write_bytes("第一行\n第二行\n第三行\n".encode("utf-8"))
        rc, out = run_ruler()
        cases.append(("正常件（纯 LF· 无 BOM · 合法 UTF-8）必须**放行**", rc == 0,
                      f"rc={rc}（应为 0）· 报红 {out.count('⛔')} 条"))

        for (name, blob, want), p in zip(BAD, targets):
            p.write_bytes(blob)
            rc, out = run_ruler()
            ok = rc == 1 and p.name in out and want in out
            cases.append((f"{p.name}（{want}）⇒ 必须报红", ok,
                          f"rc={rc}（应为 1）· 报出它的名字={'是' if p.name in out else '否'}"))

        for p in targets:
            p.unlink(missing_ok=True)
        rc, out = run_ruler()
        cases.append(("撤掉坏靶件后必须回到全绿（rc=0）", rc == 0,
                      f"rc={rc} · 报红 {out.count('⛔')} 条"))
    finally:
        for p in [good, *targets]:
            p.unlink(missing_ok=True)

    left = [p.name for p in [good, *targets] if p.exists()]
    cases.append(("临时件清场（不留残件）", not left, "无残留" if not left else f"还在：{left}"))
    same = hashlib.md5(RULER.read_bytes()).hexdigest() == ruler_md5
    cases.append(("尺子本体未被本件改动（MD5）", same, "一致" if same else "不一致"))

    print()
    for name, ok, note in cases:
        print(f"  {'✅' if ok else '⛔ 未命中'} {name} —— {note}")
    hits = sum(1 for _, ok, _ in cases if ok)
    print(f"\n  反向灵敏度：**{hits}/{len(cases)} 命中**"
          f"（少一条 = 有判据是哑的、或有'永远红'的方向没被钉住 ⇒ 报出来，别当通过）")
    return 0 if hits == len(cases) else 1


def main() -> int:
    if '--in-copy' in sys.argv:
        return _main()
    import tempfile, shutil
    with tempfile.TemporaryDirectory(prefix='mtrl-bytes-proof-') as temp:
        root = pathlib.Path(temp)
        for source in (pathlib.Path(__file__), RULER):
            dest = root/source.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest)
        result = subprocess.run([str(PY), '-X', 'utf8', str(root/'tools/mut/_mut_bytesguard.py'), '--in-copy'],
                                cwd=root, capture_output=True, text=True, encoding='utf-8', errors='replace')
        print(result.stdout + result.stderr)
        return result.returncode


if __name__ == "__main__":
    sys.exit(main())
