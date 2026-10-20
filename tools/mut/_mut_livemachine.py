"""**反向灵敏度**：`T23`（活机器口径六路）**真有区分力**。

守什么：`tools/audit/audit_meta.py` 的 `check_live_machine()` ＋ `LIVE_MACHINE_REQUIRED`
（判据的靶）＋ `tools/audit/audit_common.py` 的 `LIVE_MACHINE_GLOBS`（口径的唯一真源）。

为什么值得有（当天真翻过车）：清「零机器引用的死重」的第一版口径只扫后端与 `tools/` 下的
`.py` ⇒ **漏了运维脚本与规则档两路** ⇒ 差点把一份**被运维脚本引用**的设计件当死重搬走。
而**"命令自己测自己"不够** —— 翻车那版正是"口径只写在脚本里、没人钉"。

做法（五例，缺一不可）：
  ① **拿掉一路**必须报红（漏扫那一处却仍然全绿 ＝ 那天那场翻车）；
  ② **glob 写坏**（空命中）必须报红（扫空集却装作扫过 ＝ `T18` 同族的假绿）；
  ③ 命令件里**再抄一份口径**必须报黄（"只定义一次"要有牙）；
  ⑤ ⭐ **后缀白名单**改坏也必须报红（`/code-review` 当场指出首版只钉了 glob ⇒ 第三半边是哑的）；
  ⑥ **正常数据必须一条不报**（这一条比"会报"更要紧：只会误报的判据比没有判据更坏）。

⚠️ 一律 bytes ＋ 改完立刻按原 bytes 复原 ＋ 末尾 MD5 逐字节校验。
⚠️ 验判据走**子进程**（不是 import）—— 改完 `audit_common.py` 后本进程里的模块缓存
   还是旧的 ⇒ 同一进程里 import 会拿到"改坏前的值"＝ **假绿**。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
COMMON = ROOT / "tools" / "audit" / "audit_common.py"
REFS = ROOT / "tools" / "audit" / "refs_query.py"

#: `LIVE_MACHINE_GLOBS` 里那一行的**完整字面**（⛔ 必须是唯一的结构行，不是"含 ops 的第一行"）
LANE_PS1 = '("ops/*.ps1", "④ 运维脚本", (".ps1",)),'
LANE_PS1_BAD = '("ops/*.psX", "④ 运维脚本", (".ps1",)),'
#: 只把**后缀白名单**换掉（glob 保持能命中）⇒ 专打"判据只钉了 glob"那一半
LANE_PS1_BAD_SUF = '("ops/*.ps1", "④ 运维脚本", (".mdc",)),'

#: 在子进程里单跑 `T23`（⛔ 不在本进程 import —— 模块缓存会拿旧值，＝ 假绿）
PROBE = (
    "import sys;sys.path.insert(0,'tools/audit');import audit_meta as m;"
    "h=m.check_live_machine();print('HITS',len(h));"
    "[print('L',x['level'],x['what']) for x in h]"
)


def probe() -> tuple[int, str]:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([str(PY), "-X", "utf8", "-c", PROBE], cwd=str(ROOT),
                       capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    out = (r.stdout or "") + (r.stderr or "")
    n = -1
    for line in out.splitlines():
        if line.startswith("HITS "):
            n = int(line.split()[1])
    return n, out


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _restore(p: Path, src: bytes) -> None:
    p.write_bytes(src)
    assert p.read_bytes() == src, "复原后逐字节不一致：" + str(p)


def main() -> int:
    for p in (COMMON, REFS):
        if not p.exists():
            print("⛔ 靶件不在位：%s ⇒ 本件无法跑" % p.relative_to(ROOT))
            return 1
    common_src, refs_src = (p.read_bytes() for p in (COMMON, REFS))
    base_n, base_out = probe()
    print("基线（未改坏）`T23` 命中 %d 条（**应为 0**）" % base_n)
    if base_n != 0:
        print("  ⛔ 基线就不干净 ⇒ 先把 `T23` 红了再来跑本件")
        print("  " + "\n  ".join(base_out.splitlines()[:8]))
        return 1

    cases: list[tuple[str, str, Path, bytes, str, str]] = []
    # ① 拿掉一路（**注释行不许当靶** —— 那是"看着改了、其实没改"的老坑）
    cases.append(("L1", "拿掉一路（运维脚本）⇒ 必须报红", COMMON, common_src, "drop_lane", "red"))
    # ② glob 写坏 ⇒ 空命中必须报红（扫空集却装作扫过）
    cases.append(("L2", "glob 写坏（空命中）⇒ 必须报红", COMMON, common_src, "break_glob", "empty"))
    # ③ 命令件里再抄一份口径 ⇒ 必须报黄
    cases.append(("L3", "`refs` 件代码里复述活机器路径 ⇒ 必须报黄", REFS, refs_src, "restate", "yellow"))
    # ⑤ ⭐ 第三半边（`/code-review` 指出首版只钉了 glob）：**后缀白名单**改坏也必须报红
    cases.append(("L5", "**后缀白名单**改坏 ⇒ 必须报红（第三半边）", COMMON, common_src,
                  "break_suffix", "suffix"))

    hit = 0
    for tag, desc, path, src, mode, expect in cases:
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
            if mode == "drop_lane":
                # ⛔ 锚到**结构行**（那一行 tuple 逐字唯一）；⛔ 不删注释里提到它的那行 ——
                #    删注释不改行为 ⇒ "变异没生效"却看着是绿的（本仓同族坑）。
                # ⚠️⚠️ 锚点**必须按该文件自己的行尾拼**（`audit_common.py` 是 CRLF、其余是 LF）
                #    ⇒ 用 LF 拼会命中 0 次（本仓当天栽过这一下）。
                nl = "\r\n" if b"\r\n" in raw else "\n"
                assert text.count(LANE_PS1 + nl) == 1, (
                    "结构行锚点命中 %d 次（期望 1）⇒ 本件需重定靶" % text.count(LANE_PS1 + nl))
                path.write_bytes(text.replace(LANE_PS1 + nl, "", 1).encode("utf-8"))
            elif mode == "break_glob":
                assert text.count(LANE_PS1) == 1, "锚点不唯一 ⇒ 本件需重定靶"
                path.write_bytes(text.replace(LANE_PS1, LANE_PS1_BAD, 1).encode("utf-8"))
            elif mode == "break_suffix":
                # ⚠️ 只换**后缀**、glob 不动 ⇒ 若判据只钉 glob，这一半就是哑的（首版正是这样）
                assert text.count(LANE_PS1) == 1, "锚点不唯一 ⇒ 本件需重定靶"
                path.write_bytes(text.replace(LANE_PS1, LANE_PS1_BAD_SUF, 1).encode("utf-8"))
            elif mode == "restate":
                # ⚠️ 必须落在**代码**里：注释里的字面 `tokenize` 会剔掉 ⇒ 判据不会报（那是对的）
                add = ('\n\n#: 变异注入（L3）：命令件里再抄一份活机器口径。\n'
                       '_L3_RESTATED = ("ops/*.ps1",)\n')
                path.write_bytes((text + add).encode("utf-8"))
            n, out = probe()
        finally:
            _restore(path, src)
        if expect == "red":
            ok = n > 0 and "L 红" in out
        elif expect == "yellow":
            ok = n > 0 and "L 黄" in out
        elif expect == "suffix":
            ok = n > 0 and "L 红" in out and "后缀" in out
        else:                                     # empty
            ok = n > 0 and "一条都不命中" in out
        print("  %s %s %s  →  `T23` 命中 %d 条（期望 %s）"
              % ("✅" if ok else "⛔ 未命中", tag, desc, n, expect))
        hit += bool(ok)

    # ⑥ 正常数据一条不报（这一条比"会报"更要紧）
    n2, _ = probe()
    ok4 = n2 == 0
    print("  %s L6 正常数据**一条不报**（`T23` 命中 %d 条，期望 0）" % ("✅" if ok4 else "⛔", n2))
    hit += bool(ok4)

    dirty = [p.name for p, b in ((COMMON, common_src), (REFS, refs_src))
             if md5(p) != hashlib.md5(b).hexdigest()]
    print()
    print("  命中 %d/5" % hit)
    print("  复原校验（MD5 逐字节）：%s"
          % ("✅ 全部复原" if not dirty else "❌ 未复原：" + "、".join(dirty)))
    return 0 if (hit == 5 and not dirty) else 1


if __name__ == "__main__":
    sys.exit(main())
