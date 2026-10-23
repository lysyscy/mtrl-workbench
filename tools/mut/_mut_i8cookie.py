# -*- coding: utf-8 -*-
"""反向灵敏度（变异测试）—— `§7.8 i8 凭据` 这一片（**cookie 磁盘缓存复用** ＋ **未绑即拒**）的断言
**是否真有区分力**。

⚠️ 2026-09-30 扩了一次（`TAIL-202`）：本件从"只盯 cookie 缓存"扩成"盯**整片 i8 凭据口径**"——
   新增两靶 = **有身份却没绑 ⇒ 拒绝**（`core/identity.py`）＋ **壳上那两处"未绑定"的说法**
   （`shell/actions.js`）。⛔ 别因为文件名还叫 `i8cookie` 就以为它只管缓存。

做法：把实现**故意改坏**若干处，确认**对应断言确实变红**；每次立刻按 bytes 复原，最后核对 MD5。

用法：`cd D:\\dev\\mtrl-workbench && backend/.venv/Scripts/python.exe tools/_mut_i8cookie.py`

⚠️ 本仓纪律（memory §十七）：bytes 写入 / 行尾按目标文件归一 / 变异点必须唯一命中 /
   跑完必须再跑一次全套 `pytest`。
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
FILES = {
    "client": ROOT / "backend" / "app" / "mod02_i8" / "client.py",
    "cookie": ROOT / "backend" / "app" / "mod02_i8" / "cookie_store.py",
    "gitignore": ROOT / ".gitignore",
    # ⭐ `TAIL-202`（2026-09-30）扩进来的两件（身份层 ＋ 壳上那两处说法）
    "identity": ROOT / "backend" / "app" / "core" / "identity.py",
    "actions": ROOT / "backend" / "app" / "web" / "shell" / "actions.js",
}

T_HIT = "test_缓存命中则不登录"
T_SAVE = "test_无缓存则登录一次且写进缓存"
T_LEGACY = "test_旧纯文本格式兼容"
T_GIT = "test_缓存文件不进git"
T_UNBOUND = "test_i8凭据取当前登录用户绑定且未绑拒抓取"
T_SHELLTXT = "test_壳上关于未绑定的说法跟新口径一致"

MUTATIONS: list[tuple[str, str, str, str, str]] = [
    # ---- ⭐ 核心：优先读缓存（去掉 ⇒ 又回到「每次导出都撞单会话」）
    ("去掉「优先读缓存」（缓存命中仍去登录）",
     "client", "        if cached:", "        if False:", T_HIT),
    # ---- 登录成功后必须落盘
    # ⚠️ 2026-09-30 订正靶：原写 `source="http_login")` —— 而实现在 2026-09-2x 给这行加了
    #    `, user=user`（"cookie 按账号分"那批）⇒ **靶从那天起就没再命中过**（一直被 SKIP，
    #    而 SKIP 不算失败 ⇒ 这条"登录后必须落盘"其实**一直没人守**）。本仓老课：判词/实现一变，
    #    变异件不会自己跟着变。⛔ 别再写"少一个尾巴"的靶 —— 带上 `user=user` 才是现在的形态。
    ("登录成功后不落盘（下次还得再登一次）",
     "client", '        cookie_store.save(result.cookie, source="http_login", user=user)',
     "        _ = result.cookie", T_SAVE),
    # ---- 旧纯文本格式兼容（素材包有先例）
    ("旧纯文本格式不再兼容（整文件就是一行 cookie）",
     "cookie", '        return raw, "", "legacy"', '        return None, "", ""', T_LEGACY),
    # ---- cookie 是凭证 ⇒ 必须被 .gitignore 挡住
    ("缓存规则从 .gitignore 挪走（凭证会进 git）",
     "gitignore", "var/state/i8_cookie/", "var/state/__i8cookie_off__/", T_GIT),
    # ---- ⭐ 2026-09-30（`TAIL-202`）：**有身份却没绑 i8 ⇒ 拒绝**（《说明书》§7.8「未填即拒绝抓取、不回落」）
    #      ⚠️ 这条靶打的是"**不再拒绝**" ⇒ 会悄悄回落去用共享账号（i8 登录含强踢：顶掉同事的在线会话）。
    ("有身份却没绑 i8 时**不再拒绝**（悄悄回落用共享账号 ⇒ 顶掉同事的在线会话）",
     "identity", "            raise MustReportError(",
     "            if False: raise MustReportError(", T_UNBOUND),
    # ---- ⭐ 同批：壳上那两处「未绑定」的说法退回**旧口径**（界面上说"回落"，而后端其实会拦 ⇒ 说错话）
    ("壳上「未绑定」的说法退回旧口径（界面上说「回落」，而后端其实会拦 ⇒ 说错话）",
     "actions", 'placeholder="留空 = 解绑（解绑后抓取会被拦下，提示你先填）"',
     'placeholder="留空 = 解绑，抓取回落 .env 的 I8_USER"', T_SHELLTXT),
]


def _child_env() -> dict:
    """给子进程（`pytest`）的环境：**显式 UTF-8** ＋ 四态写回**局部档**（⛔ 不冲权威档）。"""
    return {**os.environ,
            "PYTHONIOENCODING": "utf-8"}


def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


def main() -> int:
    orig = {k: p.read_bytes() for k, p in FILES.items()}
    md5_before = {k: hashlib.md5(v).hexdigest() for k, v in orig.items()}
    for k, v in orig.items():
        print(f"{k}: {len(v)} 字节 · MD5 {md5_before[k][:12]}")

    hit = miss = 0
    for i, (label, fkey, old, new, test_name) in enumerate(MUTATIONS, 1):
        target = orig[fkey]
        o = _fit(old.encode("utf-8"), target)
        n = _fit(new.encode("utf-8"), target)
        cnt = target.count(o)
        if cnt != 1:
            print(f"  {i:2d}. ⚠️ SKIP（变异点命中 {cnt} 次）—— [{fkey}] {label}")
            miss += 1
            continue
        FILES[fkey].write_bytes(target.replace(o, n))
        # ⭐⭐ **复原走 `finally`**（2026-09-30 实测教训）：本轮把子进程输出改成显式 UTF-8 之前，
        #    `subprocess.run(..., text=True)` 在父进程被 `-X utf8` 跑时会在**解码**上抛
        #    `UnicodeDecodeError` ⇒ 那句 `write_bytes(target)` **根本不执行** ⇒
        #    **靶件被留在变异态**（`client.py` 停在 `if False:`，而我下一轮才发现）。
        #    ⇒ 规矩：**改字节的变异件，复原一律放 `finally`**（同 `MEMORY.md` 那条"别掐断上游"）。
        try:
            r = subprocess.run(
                [str(PY), "-m", "pytest", "-q", "-k", test_name, "tests/"],
                cwd=ROOT / "backend", capture_output=True,
                encoding="utf-8", errors="replace", env=_child_env(),
            )
            bad = r.returncode != 0
        finally:
            FILES[fkey].write_bytes(target)
        print(f"  {i:2d}. {'✅ 变红' if bad else '⛔ 仍绿（假绿！）'} —— [{fkey}] {label}  [{test_name}]")
        if bad:
            hit += 1

    md5_after = {k: hashlib.md5(p.read_bytes()).hexdigest() for k, p in FILES.items()}
    ok_md5 = all(md5_after[k] == md5_before[k] for k in FILES)
    print(f"\n命中 {hit}/{len(MUTATIONS) - miss} · SKIP {miss} · "
          f"MD5 {'逐字节复原 ✅' if ok_md5 else '⛔ 不一致'}")

    print("重跑全套 pytest（复原态）…")
    full = subprocess.run([str(PY), "-m", "pytest", "-q", "tests/"],
                          cwd=ROOT / "backend", capture_output=True,
                          encoding="utf-8", errors="replace", env=_child_env())
    print("  全套 pytest 退出码 =", full.returncode)
    return 0 if (ok_md5 and miss == 0 and hit == len(MUTATIONS) and full.returncode == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
