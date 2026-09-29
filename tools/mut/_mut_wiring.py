"""反向灵敏度（`wiring_audit` —— 「口径说了要做的事，代码里接上了吗」）—— 证明它**真有区分力**。

⚠️ 本件为什么必需（2026-09-28 · `P0-a`）：`wiring_audit` 此前**一条 `_mut_*` 都没有**，
   而 `artifacts/变异覆盖台账.md` 的「表 B」却写着"**每一把尺子都有反向灵敏度**" ⇒
   同族老毛病：**"记着有" ≠ "真的有"**。本件把这句话填实 —— 且它同时钉住本批新修的两条规则。

四靶（每处改完**立刻按 bytes 复原** ＋ 收尾 MD5 校验）：
- `M1` **别名引用**（`scan` 的别名表）：把 `main.py` 里那行**经别名调用** `domains_router` 的
  `app.include_router(_imp_domains_router())` 拿掉 ⇒ `W2` 必须重新报 `domains_router`。
- `M2` **局部 router 的 HTTP 方法装饰器**（`Def.framework_wired`）：把 `import_kit/api.py` 里
  `api_schema` 头上那行 `@r.get(base + "/schema")` 拿掉 ⇒ `W2` 必须报 `api_schema`
  （⭐ 这条是**本批新规则**的专用眼：规则生效时它**不报**，拿掉装饰器后才报）。
- `M3` **白名单确实在兜**：从 `tools/wiring_expected.txt` 删掉一条**有效**登记
  （`W2 backend/app/core/money.py:try_money`）⇒ `W2` 必须重新报 `try_money`。
- `M4` **「可消号」判定的新逻辑**（本批修掉的 bug：旧版只比 `W1`/`W2` 前缀 ⇒ 所有 `W1b` 行恒被
  误报成"该删行了"）：往白名单**加回**一条**已漂**的行（`W2 …/mod03_notice/page.py:render_list_page`
  —— 该函数已由 `TAIL-06` 切到 `list_page.py`）⇒ 「可消号」必须列出它。

用法：python tools/mut/_mut_wiring.py
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
RULER = ROOT / "tools" / "audit" / "wiring_audit.py"
EXPECTED = ROOT / "tools" / "wiring_expected.txt"
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"

MAIN = ROOT / "backend" / "app" / "main.py"
API = ROOT / "backend" / "app" / "import_kit" / "api.py"

#: `M1` 靶：**经别名**调用 `domains_router` 的那一行（⚠️ 用正则，容忍 CRLF）
M1_RE = re.compile(r"[ \t]*app\.include_router\(_imp_domains_router\(\)\)")
#: `M2` 靶：局部 router 上的 HTTP 方法装饰器
M2_RE = re.compile(r"[ \t]*@r\.get\(base \+ \"/schema\"\)")
#: `M3` 靶：要摘掉的**有效**白名单行
M3_RE = re.compile(r"^W2 backend/app/core/money\.py:try_money\r?$", re.M)
#: `M4` 靶：要加回的**已漂**行（该函数已切到 `list_page.py` ⇒ 原路径必然是"可消号"）
M4_LINE = "W2 backend/app/mod03_notice/page.py:render_list_page"
M4_RE = re.compile(r"^W2 backend/app/mod03_notice/page\.py:render_list_page\r?$", re.M)
#: 「可消号」里要看到的那条
M4_EXPECT = "W2 backend/app/mod03_notice/page.py:render_list_page"

BASE_RE = re.compile(r"W1 必须修 (\d+).*?W1b 必须修 (\d+).*?W2 待清理 (\d+)", re.S)


def _env() -> dict[str, str]:
    return {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def run_ruler() -> tuple[tuple[int, int, int], str]:
    """→ ((W1, W1b, W2), 全输出)。⚠️ 解析不到 ⇒ `(-1, -1, -1)`（子进程没起来 = 全假红）。"""
    r = subprocess.run([str(PY), str(RULER)], cwd=str(ROOT), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=_env())
    out = (r.stdout or "") + (r.stderr or "")
    m = BASE_RE.search(out)
    return ((int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (-1, -1, -1)), out


def w2_has(out: str, name: str) -> bool:
    """`W2` 节里有没有这个名字（⚠️ 行形如 `⚠️  <文件>:<行号>  <名字>  [kind]`）。"""
    return bool(re.search(rf"⚠️\s+\S+:\d+\s+{re.escape(name)}\s", out))


def stale_has(out: str, frag: str) -> bool:
    """「可消号」节里有没有这条。"""
    return bool(re.search(rf"✔\s+{re.escape(frag)}", out))


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def main() -> int:
    (w1, w1b, w2), _ = run_ruler()
    print(f"基线（未改坏）wiring_audit = W1 {w1} · W1b {w1b} · W2 {w2}（三者都应为 0）")
    if (w1, w1b, w2) != (0, 0, 0):
        print("  ⛔ 基线就不干净 ⇒ 先清红再来跑本件")
        return 1

    main_before = MAIN.read_bytes()
    api_before = API.read_bytes()
    exp_before = EXPECTED.read_bytes()

    hits, total = 0, 4

    # ---- M1 别名调用被拿掉 ⇒ W2 必须报 domains_router ----
    txt = main_before.decode("utf-8")
    assert M1_RE.search(txt), "M1 靶串没找到（main.py 变了）—— 先修本件的锚点"
    try:
        MAIN.write_bytes(M1_RE.sub("\n", txt, count=1).encode("utf-8"))
        _, out = run_ruler()
    finally:
        MAIN.write_bytes(main_before)
    ok = w2_has(out, "domains_router")
    hits += ok
    print(f"  {'✅' if ok else '⛔ 未命中'} M1 拿掉**别名调用**那行 ⇒ W2 应报 `domains_router`")

    # ---- M2 局部 router 的装饰器被拿掉 ⇒ W2 必须报 api_schema ----
    txt = api_before.decode("utf-8")
    assert M2_RE.search(txt), "M2 靶串没找到（api.py 变了）—— 先修本件的锚点"
    try:
        API.write_bytes(M2_RE.sub("\n", txt, count=1).encode("utf-8"))
        _, out = run_ruler()
    finally:
        API.write_bytes(api_before)
    ok = w2_has(out, "api_schema")
    hits += ok
    print('  ' + ('✅' if ok else '⛔ 未命中')
          + ' M2 拿掉 `@r.get(base + "/schema")` ⇒ W2 应报 `api_schema`')

    # ---- M3 白名单摘掉一条有效登记 ⇒ W2 必须重新报它 ----
    txt = exp_before.decode("utf-8")
    assert M3_RE.search(txt), "M3 白名单行没找到 —— 先修本件的锚点"
    try:
        EXPECTED.write_bytes(M3_RE.sub("", txt, count=1).encode("utf-8"))
        _, out = run_ruler()
    finally:
        EXPECTED.write_bytes(exp_before)
    ok = w2_has(out, "try_money")
    hits += ok
    print(f"  {'✅' if ok else '⛔ 未命中'} M3 白名单摘掉一条有效登记 ⇒ W2 应重新报 `try_money`")

    # ---- M4 加回一条已漂的行 ⇒ 「可消号」必须列出它（本批修掉的 bug 的专用眼）----
    txt = exp_before.decode("utf-8")
    assert not M4_RE.search(txt), "M4 那行已经在了 —— 先修本件的锚点"
    try:
        EXPECTED.write_bytes((txt + "\n" + M4_LINE + "\n").encode("utf-8"))
        _, out = run_ruler()
    finally:
        EXPECTED.write_bytes(exp_before)
    ok = stale_has(out, M4_EXPECT)
    hits += ok
    print(f"  {'✅' if ok else '⛔ 未命中'} M4 加回**已漂**登记 ⇒ 「可消号」应列出它"
          f"（旧版把 `W1b` 行全误报成可消号 ⇒ 这条专打新逻辑）")

    # ---- 复原校验：三个靶件必须逐字节复原 ----
    restored = (
        md5(MAIN.read_bytes()) == md5(main_before)
        and md5(API.read_bytes()) == md5(api_before)
        and md5(EXPECTED.read_bytes()) == md5(exp_before)
    )
    print()
    print(f"  靶件逐字节复原：{'✅' if restored else '❌'}")
    print(f"  反向灵敏度：**{hits}/{total} 命中**")
    return 0 if (hits == total and restored) else 1


if __name__ == "__main__":
    sys.exit(main())
