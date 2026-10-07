"""**选测范围的反向灵敏度**（`TAIL-241` 第 4 步）—— 证明 `_pytestscope` 那道选测判据**真的有牙**。

守什么：`tools/oneoff/_pytestscope.py` 的 `plan()` / `REPO_WIDE` / `SELF_ONLY` ——
「按改动范围选测」这条判据**不会漏跑**，且它的缺口自检**真的会红**。

做法（三个方向都**造得出红**；⛔ 只跑一遍看它说 OK 等于没验 —— `MEMORY` 哑靶三形态）：
    ① **漏跑方向**：改坏 `mod09_fee` 的一个模块 ⇒ ① 见证测试**必须在选测集合里**
       ② 真跑它**必须红**；复原后**必须不红**（这就是「造得出来的红」）。
    ② **跳过方向**：给一条 `backend/` 改动 ⇒ 判据**不许**说「跳过」；给一组只动
       `.codebuddy/` 的改动 ⇒ 判据**必须**说「跳过」（缺一个方向就是恒真）。
    ③ **缺口方向**：把 `SELF_ONLY` 里的一行摘掉 ⇒ 缺口自检**必须报红并点名**；
       再塞一个不存在的件名 ⇒ **必须报陈旧**（那半边最容易是死代码）。

⚠️ **本件只证明「集合里有一件会因这次改动而红」**，⛔ 不证明「集合之外的件都不会红」
   —— 那要跑全量（分钟级），属按需 `--all`。写在这儿是为了不让下一个人**过度解读**。

⚠️⚠️ **故意不给 `ACC_RESULTS_PATH`**：只跑一支子集时若写进权威四态档，会把全量那份
   冲成十几条 ⇒ `doc_audit` 的 `T4` 立刻报红（本仓为这件事栽过多次，次数见当日日志）。
   不给 ⇒ `acc_plugin` 写局部的 `_partial_acc_results.json`。

跑法：`backend\\.venv\\Scripts\\python.exe -X utf8 tools\\mut\\_mut_pytestscope.py`
"""
from __future__ import annotations

import hashlib
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")
SCOPE = ROOT / "tools" / "oneoff" / "_pytestscope.py"

#: ① 改坏的靶：`backend/app/mod09_fee/service.py` 里「空格子整格跳过」那一行
TARGET_REL = "backend/app/mod09_fee/service.py"
#: 见证件：它的 docstring 自认「把『空 ⇒ 0』改回去本件必红」⇒ ⛔ 别改它的断言来迁就本件
WITNESS = "test_acc_fee_mon.py"
#: 缺口方向的临时件名（**必须匹配 `tests/test_*.py` 的通配**，否则造出来的缺口不成立）
PROBE_NAME = "test__mut_pytestscope_probe.py"
#: 往 `SELF_ONLY` 里临时塞的一个**不存在**的件名（用后即删 ⇒ 证明「陈旧」那半边不是死代码）
STALE_LINE = '    ("_mut_pytestscope_never_existed.py", "本件自己临时塞的，用后即删"),\n'
#: 「改了 tools 侧那件 ⇒ 必须选中它自己」的见证件（它读的就是那件）
WITNESS_TOOL = "test_shell_api.py"

ENV = {"PLAYWRIGHT_BROWSERS_PATH": r"C:\ProgramData\ms-playwright",
       "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def _mutate(src: bytes) -> bytes:
    """把「空格子整格跳过」那一行改成「空 ⇒ 写 0」⇒ 见证件必红。

    ⚠️ **按行改、且沿用它自己的行尾**（本仓老坑：写死 `\\r\\n` 会给 LF 件埋雷）。
    ⛔ 锚点没命中就**直接退出**（不静默通过 —— 那会变成一件永远绿的哑靶）。
    """
    lines = src.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if b"continue" in ln and "整格跳过".encode("utf-8") in ln:
            nl = b"\r\n" if ln.endswith(b"\r\n") else b"\n"
            # ⚠️ **缩进沿用原来那一行**（`/code-review` 2026-10-06 抓出）：写死空格数的话，
            #   哪天靶件改了缩进，本件会**改出行尾/缩进错** ⇒ 语法错 ⇒ 「必红」是假证明。
            pad = ln[: len(ln) - len(ln.lstrip())]
            lines[i] = pad + b'plan.append((ym, nm, D.parse_amount("0")))' + nl
            return b"".join(lines)
    raise SystemExit("⛔ 靶件里找不到变异锚点（那一行被改过了？）⇒ 本件不作通过")


def _run(args: list, cwd=ROOT) -> tuple:
    p = subprocess.run([PY, "-X", "utf8"] + args, cwd=str(cwd), env=dict(os.environ, **ENV),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def _pytest(files: list) -> tuple:
    return _run(["-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=line"] + files, BACKEND)


def _plan(paths: list) -> tuple:
    """问那道判据「这些改动该怎么跑」→ `(该跑吗, 件名集合, 理由)`（子进程问，避免同进程污染）。"""
    rc, out = _run([str(SCOPE), "--explain", "--"] + list(paths))
    files = set()
    for ln in out.splitlines():
        if ln.startswith("件名（"):
            files = {x for x in ln.split("：", 1)[1].split() if x.endswith(".py")}
    return ("跑 pytest：是" in out), files, out


def _env_for(paths):
    """问「跑这些改动时，pytest 的 ACC_RESULTS_PATH 会是哪个」—— 让判据自己答，不看代码。

    做法：起一个子进程跑 `plan(...)` 再打印 `pytest_env(...)` 的那一个键（⛔ 不在本件里
    重算一遍 —— 那样测的就是本件的复制品，不是真件）。
    """
    code = ("import sys; sys.path.insert(0, %r); import _pytestscope as s;"
            " pl = s.plan(%r); print(s.pytest_env(pl)['ACC_RESULTS_PATH'])"
            % (str(SCOPE.parent), list(paths)))
    p = subprocess.run([PY, "-X", "utf8", "-c", code], cwd=str(ROOT), env=dict(os.environ, **ENV),
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (p.stdout or "").strip().splitlines()[-1] if (p.stdout or "").strip() else ""

def _cover() -> tuple:
    rc, out = _run([str(SCOPE), "--cover-only"])
    return rc, out


def _edit_scope(src: bytes) -> bytes:
    """往 `SELF_ONLY` 元组体里塞一行（⛔ 不许 append 到文件末尾 —— 那里永远执行不到）。"""
    i = src.index(b"SELF_ONLY: tuple[tuple[str, str], ...] = (") + len(
        b"SELF_ONLY: tuple[tuple[str, str], ...] = (")
    nl = b"\r\n" if src[i:i + 2] == b"\r\n" else b"\n"
    return src[:i] + nl + STALE_LINE.encode("utf-8") + src[i:]


def main() -> int:
    cases: list = []
    scope_bytes = SCOPE.read_bytes()
    scope_md5 = hashlib.md5(scope_bytes).hexdigest()
    target = ROOT / TARGET_REL
    tgt_bytes = target.read_bytes()

    # ---- ① 漏跑方向：改坏一个模块 ⇒ 见证件必在选测集合里，且真跑必红 ----
    run_it, files, _ = _plan([TARGET_REL])
    cases.append(("动了 backend/app 的模块 ⇒ 判据不许说「跳过」", run_it,
                  "判据说跑=%s" % ("是" if run_it else "否（⛔ 那就是漏跑的方向被写反了）")))
    cases.append(("见证件 `%s` **在选测集合里**（选测漏了它 ⇒ 这次改动没人守）" % WITNESS,
                  WITNESS in files,
                  "集合 %d 件；%s" % (len(files), "在里面" if WITNESS in files else "⛔ 不在里面")))
    try:
        target.write_bytes(_mutate(tgt_bytes))
        rc, out = _pytest(["tests/" + WITNESS])
        red = rc != 0
        why = [x for x in out.splitlines() if x.strip()][-1][:120] if out.strip() else "<无输出>"
        cases.append(("改坏那个模块（空 ⇒ 写 0）⇒ 见证件**必须红**", red,
                      "rc=%d（应非 0）｜%s" % (rc, why)))
    finally:
        target.write_bytes(tgt_bytes)                    # ⭐ 复原走 finally
    rc, out = _pytest(["tests/" + WITNESS])
    cases.append(("复原后见证件**必须不红**（这就是「造得出来的红」）", rc == 0,
                  "rc=%d（应为 0）" % rc))
    ok_md5 = hashlib.md5(target.read_bytes()).hexdigest() == hashlib.md5(tgt_bytes).hexdigest()
    cases.append(("靶件逐字节复原（MD5）", ok_md5, "一致" if ok_md5 else "⛔ 不一致"))

    # ---- ② 跳过方向：只动 `.codebuddy/` ⇒ 必须说跳过（缺这一向 ⇒ 判据恒真）----
    run_skip, f2, out2 = _plan([".codebuddy/memory/MEMORY.md", ".codebuddy/plans/x.md"])
    cases.append(("只动 `.codebuddy/` ⇒ 判据**必须**说跳过（第 0 批的省时就在这一向）",
                  not run_skip, "判据说跑=%s" % ("是（⛔ 白跑一轮）" if run_skip else "否")))
    run_out, _, _ = _plan(["tools/audit/shell_api.py"])
    cases.append(("动了 pytest 在仓外也真读的那件（`shell_api.py`）⇒ **必须**说跑", run_out,
                  "判据说跑=%s" % ("是" if run_out else "否（⛔ 那是漏跑）")))
    run_doc, files_doc, _ = _plan(["tools/audit/doc_audit.py"])
    total = len(list((ROOT / "backend" / "tests").glob("test_*.py")))
    cases.append(("改一把尺子 ⇒ 说跑，但**只跑读它的那部分**（⛔ 不许退化成全套，"
                  "否则改尺子的轮次一点都省不下）",
                  run_doc and 0 < len(files_doc) < total,
                  "判据说跑=%s · 选 %d / 全套 %d 件"
                  % ("是" if run_doc else "否", len(files_doc), total)))
    run_shell, files_shell, _ = _plan(["tools/audit/shell_api.py"])
    cases.append(("动了 pytest 真读的那件（`shell_api.py`）⇒ 必须说跑，**且选中它自己**",
                  run_shell and WITNESS_TOOL in files_shell,
                  "判据说跑=%s · 选中 %d 件 · 含它=%s"
                  % ("是" if run_shell else "否", len(files_shell),
                     "是" if WITNESS_TOOL in files_shell else "⛔ 否")))
    run_cf, files_cf, _ = _plan(["backend/tests/conftest.py"])
    cases.append(("动了 pytest **自动加载**的件（`conftest.py`）⇒ **必须全跑**"
                  "（它没有 import 边 ⇒ 算不出 ⇒ 漏跑比慢跑坏）",
                  run_cf and not files_cf, "判据说跑=%s · 选测件=%d（应为 0 ＝ 全套）"
                  % ("是" if run_cf else "否", len(files_cf))))

    # ---- ②之二 权威四态档只许全套刷新（本轮真踩：子集跑把权威档写成「绿 138」）----
    sub_env = _env_for([TARGET_REL])
    full_env = _env_for(["backend/tests/conftest.py"])   # 自动加载的件 ⇒ 判据判它全跑
    cases.append(("子集跑 ⇒ ACC_RESULTS_PATH 不许指向权威四态档"
                  "（否则闸门自己把权威档冲成子集 ⇒ 下一轮 T4 报红）",
                  sub_env.endswith("_partial_acc_results.json"),
                  "子集那轮写的是 %s" % sub_env.rsplit("\\", 1)[-1]))
    cases.append(("全套跑 ⇒ 必须写权威四态档（否则四态永远不刷新）",
                  pathlib.Path(full_env).name == "acc_results.json",
                  "全套那轮写的是 %s" % full_env.rsplit("\\", 1)[-1]))
    # ---- ③ 缺口方向：造一件「谁都够不着」的测试件 ⇒ 必须报红并点名；
    #       往名单塞一个不存在的名字 ⇒ 必须报陈旧（那半边最容易是死代码） ----
    probe = BACKEND / "tests" / PROBE_NAME
    try:
        probe.write_text("# 临时件（`_mut_pytestscope.py` 用后即删）\n", encoding="utf-8", newline="")
        rc, out = _cover()
        named = PROBE_NAME in out
        cases.append(("造一件谁都够不着的测试件 ⇒ 缺口自检**必须报红并点名它**"
                      "（「新加一件没人登记」那个病）",
                      rc == 1 and named, "rc=%d（应为 1）· 点名了=%s" % (rc, "是" if named else "否")))
    finally:
        probe.unlink(missing_ok=True)
    try:
        SCOPE.write_bytes(_edit_scope(scope_bytes))
        rc, out = _cover()
        named = "_mut_pytestscope_never_existed.py" in out
        cases.append(("往 `SELF_ONLY` 塞一个不存在的件名 ⇒ **必须报陈旧**（那半边最容易是死代码）",
                      rc == 1 and named, "rc=%d（应为 1）· 报出了=%s" % (rc, "是" if named else "否")))
    finally:
        SCOPE.write_bytes(scope_bytes)
    rc, _ = _cover()
    cases.append(("复原后缺口自检**必须回到绿**", rc == 0, "rc=%d（应为 0）" % rc))
    ok2 = hashlib.md5(SCOPE.read_bytes()).hexdigest() == scope_md5
    cases.append(("`_pytestscope.py` 逐字节复原（MD5）", ok2, "一致" if ok2 else "⛔ 不一致"))
    cases.append(("临时件清场（不留残件）", not probe.exists(),
                  "✅ 无残留" if not probe.exists() else "⛔ 还在：%s" % PROBE_NAME))

    print()
    for name, ok, note in cases:
        print("  %s %s —— %s" % ("✅" if ok else "⛔ 未命中", name, note))
    hits = sum(1 for _, ok, _ in cases if ok)
    print("\n  反向灵敏度：**%d/%d 命中**（⛔ 少一条 = 选测判据有一半是死的 ⇒ 报出来，别当通过）"
          % (hits, len(cases)))
    return 0 if hits == len(cases) else 1


if __name__ == "__main__":
    sys.exit(main())