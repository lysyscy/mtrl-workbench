#!/usr/bin/env python
"""「壳的语义口径**认结构**、找得到、找不到会喊」的反向灵敏度 —— 证明 `tests/test_shell_api.py` 那几条判据**真的有牙**。

守什么（`backend/tests/test_shell_api.py` · ⭐ `TAIL-219` 批 1／2b · 2026-10-03）：
- 壳的"界面口径"原先**没有可调用的窗口** ⇒ 各件自写剪刀（实测 **48 把 / 33 件** ＋ 就地取片 103 处）。
  本批立了 `tools/audit/shell_api.py`（`page_slice` / `func_body` / `act_entry` / `const_obj`）
  ＋ 拆出 `tools/audit/jslex.py`（"认结构"的扫描器）。
- 要守的性质：① **认结构**（配平跳过字符串/模板串/注释/正则）② **找不到 ⇒ 必抛**（⛔ 不静默回空）
  ③ 定位**先剥注释** ④ `ACT` 成员**按同层深度找**（⛔ 不按缩进 —— 壳里 1/2 空格混用）
  ⑤ `act_entry` **两种形态都认**（对象字面量成员 / `ACT.<名> =` 赋值式 · 后者壳里 12 处）。

用法（在本仓根跑）：
    backend\\.venv\\Scripts\\python.exe -X utf8 tools\\mut\\_mut_shellapi.py

⚠️ 逐字节复原 + MD5 校验（本仓规矩）；⚠️ 靶有**三件**（`shell_api.py` ＋ `jslex.py` ＋ M8 的 `test_ux_states.py`），各自复原。

⚠️⚠️ **2026-10-06（`TAIL-233`）修：靶件全是 CRLF，而锚点是带 `\n` 的源码字面**
    ⇒ 8 个 case 里 7 个的锚点含换行 ⇒ **全部打空**、件死在**第一个** `assert`
    ⇒ 症状只有一句「变异① 锚点没命中」，而实际是**一条都没验过**（本仓"哑得最彻底"那一种：
    **不是某条没牙，是整件没跑**）。实测三件靶全是纯 CRLF（`jslex.py` 251/0 · `shell_api.py` 329/0
    · `test_ux_states.py` 150/0）。⇒ 比对前**行尾归一**（`_norm`）、写回**按该件原本的行尾**（`_fit`）
    —— 后半句是必须的：⛔ 否则一次变异就把 CRLF 件悄悄改成 LF ⇒ 收尾的 MD5 复原校验必红，
    而**报错指向复原、指向不到真正的原因**。`_fit` 是 `_mut_linewalls.py` 里那份现成配方的同族复用。
"""

from __future__ import annotations

import hashlib
import pathlib
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
# ⭐ 2026-10-06（`TAIL-233` · `/code-review` Standards 轴）：原先**写死绝对路径**
#    ⇒ 换机器/换盘就整支跑不起来，且症状是"锚点没命中"（伪装成"靶漂了"）。
#    ⇒ 与同批 `_mut_segments.py` 同一口径（`__file__` 上溯两级 = 仓根）。
R = pathlib.Path(__file__).resolve().parents[2]
PY = R / "backend" / ".venv" / "Scripts" / "python.exe"
API = R / "tools" / "audit" / "shell_api.py"
LEX = R / "tools" / "audit" / "jslex.py"
USTATES = R / "backend" / "tests" / "test_ux_states.py"   # ← M8 的靶：往它里面"长一把新剪刀"
TEST = "tests/test_shell_api.py"          # ← 台账「验的判据」列抓这一串

#: 变异①（`jslex.py`）：不认字符串 ⇒ 字符串里的 `}` 会被当成收尾
M1_OLD = "    if c in _QUOTES:\n        return skip_string(s, i)\n"
M1_NEW = "    if False and c in _QUOTES:   # 变异 M1：不认字符串\n        return skip_string(s, i)\n"
M1_TEST = "test_取函数体_认结构"

#: 变异②（`shell_api.py`）：找不到时静默回空（⛔ "看着绿、其实什么都没查"）
M2_OLD = """    if page not in m:
        raise LookupError(f"壳里没有 `V.{page}=` 切片（现有：{', '.join(sorted(m))}）")
"""
M2_NEW = """    if page not in m:
        return ""                            # 变异 M2：静默回空
"""
M2_TEST = "test_取不到必须抛_不许静默回空"

#: 变异③（`shell_api.py`）：定位**不先剥注释** ⇒ 注释里那份"列 0 的假定义"会被当成真的
M3_OLD = "    return source, blank_comments(source, html=True)\n"
M3_NEW = "    return source, source                     # 变异 M3：定位不剥注释\n"
M3_TEST = "test_取动作条_注释里列0的假定义不算数"

#: 变异④（`shell_api.py`）：`ACT` 成员改回"钉 2 空格" ⇒ 1 空格的成员（壳里占一半）漏掉
M4_OLD = '    key = re.compile(rf"[ \\t]*{re.escape(name)}[ \\t]*:")'
M4_NEW = '    key = re.compile(rf"  {re.escape(name)}[ \\t]*:")   # 变异 M4：钉死 2 空格'
M4_TEST = "test_取动作条_缩进混用也要取到"

#: 变异⑤（`shell_api.py`）：`BIND` 块**不封口**（一路吃到文件尾）⇒ 会把下一个 BIND / 别的块也吃进来
M5_OLD = ("        if cur is None:\n            continue\n"
          "        if _END_RE.match(ln):\n            cur = None\n            continue\n"
          "        cur.append(lines[i])\n")
M5_NEW = ("        if cur is None:\n            continue\n"
          "        if False and _END_RE.match(ln):   # 变异 M5：块不封口\n            cur = None\n            continue\n"
          "        cur.append(lines[i])\n")
M5_TEST = "test_取_BIND_块_三种写法都要收"

#: 变异⑥（`shell_api.py`）：`BIND` **多处命中也不抛**（静默挑第一处 ⇒ 换错块了照样绿）
M6_OLD = "    if len(bs) != 1:\n        raise LookupError(\n"
M6_NEW = "    if False and len(bs) != 1:   # 变异 M6：多处也静默挑第一处\n        raise LookupError(\n"
M6_TEST = "test_取_BIND_块_多处命中必须抛"

#: 变异⑦（`shell_api.py`）：`act_entry` **丢掉"赋值式"支路** ⇒ 壳里 12 处 `ACT.<名> =` 又看不见（= 退回批 2b 三之前的形态）
M7_OLD = ('    for m in re.finditer(rf"(?m)^ACT\\.{re.escape(name)}\\s*=", scan):\n'
          '        forms.append(src[m.start():scan_stmt(scan, m.end())])\n')
M7_NEW = ('    for m in []:   # 变异 M7：丢掉赋值式支路（只认对象字面量成员）\n'
          '        forms.append(src[m.start():scan_stmt(scan, m.end())])\n')
M7_TEST = "test_取动作条_赋值式也要取到"

#: 变异⑧（`test_ux_states.py`）：**往活区里"长一把新剪刀"** ⇒ "清单只许变短"那条必须红
M8_OLD = 'def _seg(marker: str, stop: str = "\\n}") -> str:'
M8_NEW = ('def _newScissor(x):\n'
          '    return SHELL.find(x)\n\n\n'
          'def _seg(marker: str, stop: str = "\\n}") -> str:')
M8_TEST = "test_壳的语义剪刀清单只许变短"

#: (标签, 靶件, 旧, 新, 该红的判据名)
CASES = (
    ("①", LEX, M1_OLD, M1_NEW, M1_TEST),
    ("②", API, M2_OLD, M2_NEW, M2_TEST),
    ("③", API, M3_OLD, M3_NEW, M3_TEST),
    ("④", API, M4_OLD, M4_NEW, M4_TEST),
    ("⑤", API, M5_OLD, M5_NEW, M5_TEST),
    ("⑥", API, M6_OLD, M6_NEW, M6_TEST),
    ("⑦", API, M7_OLD, M7_NEW, M7_TEST),
    ("⑧", USTATES, M8_OLD, M8_NEW, M8_TEST),
)


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def _norm(b: bytes) -> str:
    """靶件字节 → 文本，**行尾归一为 LF**（比对锚点用；见文件头 2026-10-06 那段）。

    ⚠️ `_mut_segments.py` 里有**逐字相同**的一份。**⛔ 别在本件改一份、忘了另一份** ——
    两处任一漂了，那一支就会重新变成"一件都没验过"（且症状是"锚点没命中"，极像别的问题）。
    """
    return b.decode("utf-8").replace("\r\n", "\n")


def _fit(text: str, orig: bytes) -> bytes:
    """把归一后的文本写回**该件原本的行尾风格**（⛔ 别把 CRLF 件写成 LF ⇒ 复原校验会背黑锅）。"""
    b = text.encode("utf-8")
    return b.replace(b"\n", b"\r\n") if b"\r\n" in orig else b


def run_test() -> tuple[int, str]:
    r = subprocess.run([str(PY), "-X", "utf8", "-m", "pytest", TEST, "-q", "-o", "addopts=",
                        "-p", "no:cacheprovider"],
                       cwd=R / "backend", capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def main() -> int:
    fail: list[str] = []
    orig = {p: p.read_bytes() for p in (API, LEX, USTATES)}

    rc0, out0 = run_test()
    print(f"基线：{TEST} ⇒ rc={rc0}")
    if rc0 != 0:
        print(out0[-900:])
        print("⛔ 基线就不是绿的 ⇒ 先把判据修绿（否则本件测不了东西）")
        return 1

    try:
        for tag, target, old, new, name in CASES:
            src = _norm(orig[target])                       # ⭐ 归一后再比对（靶件是 CRLF）
            assert old in src, f"⚠️ 变异{tag} 锚点没命中（`{target.name}` 变了？先核再改本件）"
            target.write_bytes(_fit(src.replace(old, new, 1), orig[target]))
            rc, out = run_test()
            hit = name in out
            print(f"  变异{tag}（{target.name}：{name}）⇒ rc={rc} · 命中该条={hit}")
            if rc == 0 or not hit:
                fail.append(f"{tag} 改坏了但没红/没命中（rc={rc}）—— 判据没牙")
            target.write_bytes(orig[target])
    finally:
        for p, b in orig.items():
            p.write_bytes(b)

    for p, b in orig.items():
        if p.read_bytes() != b:
            fail.append(f"{p.name} 没复原")
    if not fail:
        print(f"复原 ✅ shell_api {md5(orig[API])} · jslex {md5(orig[LEX])} · ux_states {md5(orig[USTATES])}")
    rcN, _ = run_test()
    if rcN != 0:
        fail.append(f"复原后判据仍红（rc={rcN}）—— 留下了坏态")

    if fail:
        print("❌ " + "；".join(fail))
        return 1
    print(f"✅ 有区分力：{len(CASES)} 条都必红 · 复原后 rc={rcN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
