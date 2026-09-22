"""**反向灵敏度**：证明用户 2026-09-21 报的三件事所补的断言**真有区分力**。

覆盖：① 顶栏假身份（`001-11`）· ③ 主题切换器搬 `MOD-14` 且就地生效 · ② i8 按人绑定的 `None` 语义。
做法：逐条把实现**改坏** → 确认对应的那条断言变红 → 全部复原（**MD5 逐字节校验**）。

⚠️ 一律走 bytes（壳混着 LF / CRLF）；还原用**原 bytes**（`write_text` 会把 CRLF 静默换成 LF ⇒ 假 BAD）。
⚠️ 子进程必须设 `ACC_RESULTS_PATH`，跑完**必须再跑一次全套 pytest**（见 `MEMORY.md` §十七）。
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BE = ROOT / "backend"
sys.path.insert(0, str(ROOT / "tools"))
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录：shell_source 在 audit/
from shell_source import SHELL_PATH, pick  # noqa: E402
PY = BE / ".venv" / "Scripts" / "python.exe"

SHELL_HTML = SHELL_PATH
CORE = ROOT / "backend" / "app" / "web" / "shell" / "core.js"
ACTIONS = ROOT / "backend" / "app" / "web" / "shell" / "actions.js"
REPO_PY = ROOT / "backend" / "app" / "mod15_user" / "repository.py"
API_PY = ROOT / "backend" / "app" / "mod15_user" / "api.py"

T_LOGIN = "tests/test_acc_usr_login.py::test_当前登录用户是唯一出口且不得写死人名"
T_THEME = "tests/test_acc_theme_user.py::test_切换器住系统设置且清单由该页自取且不刷新页面"
T_I8 = "tests/test_acc_usr_i8.py::test_set_i8的三种写法省略密码不改解绑一并清空"


def _b(s: str) -> bytes:
    return s.replace("\r\n", "\n").encode("utf-8")


def _fit(fragment: bytes, sample: bytes) -> bytes:
    if b"\r\n" in sample:
        return fragment.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return fragment.replace(b"\r\n", b"\n")


def _locate(src: bytes, frag_lf: bytes):
    for cand in (frag_lf, _fit(frag_lf, src)):
        n = src.count(cand)
        if n >= 1:
            return n, cand
    return None


# (说明, 文件, 原文(LF), 改成(LF), 目标测试, 抓它的断言)
MUTS = [
    ("M1 ① 把**写死的假身份**放回壳（顶栏首屏又会出现「张伟」）", SHELL_HTML,
     _b("let CUR={id:'',acc:'',name:'',role:''};\n"),
     _b("let CUR={id:'U01',acc:'zhangwei',name:'张伟',role:'admin'};\n"),
     T_LOGIN, "⑤ 壳里 `CUR` 初值不得带写死的身份"),
    ("M2 ① `boot()` 不再取当前登录用户（顶栏第一帧会是空的）", CORE,
     _b("  const who = soft('当前登录用户', reloadWho);\n"),
     _b("  const who = Promise.resolve();\n"),
     T_LOGIN, "⑥ `boot()` 必须取身份"),
    ("M3 ③ 主题清单又只挂在「用户管理」那一路（系统设置页取不到 ⇒ 下拉恒为空）", CORE,
     _b("  set: ['系统设置', '外观主题'],\n"),
     _b("  set: ['系统设置'],\n"),
     T_THEME, "② 系统设置页必须自己取清单"),
    ("M4 ③ 换主题退回「整页刷新」（用户又会被扔回看板）", ACTIONS,
     _b("    applyThemeLive();          /* \u2b50 就地生效（\u26d4 不整页刷新 —— 那会把用户扔回看板） */\n"),
     _b("    location.reload();\n"),
     T_THEME, "③ 不许用整页刷新换主题"),
    ("M5 ② 壳把「密码框留空」当成「清空 i8 密码」（只改账号会静默毁掉密码）", ACTIONS,
     _b("const i8p = i8pRaw === '' ? null : i8pRaw;\n"),
     _b("const i8p = i8pRaw;\n"),
     T_I8, "② 空框 = 不改"),
    ("M6 ② 仓储把「省略密码」当成「清空密码」（同一件事的后端那半）", REPO_PY,
     _b("    elif i8_password is not None:\n"),
     _b("    elif True:\n"),
     T_I8, "② 省略密码 = 不改"),
    # ---- 2026-09-21 第二批（用户第 2 次报障：PDF / 主题卡片 / 回收站…）----
    ("M7 ⑤ `themeSet` **先读 `t.value`**（`<button>` 也有 value 且默认空串 ⇒ 写回空串、换了没反应）",
     ACTIONS,
     _b("  const name=(t.dataset&&t.dataset.theme)||t.value||'';\n"),
     _b("  const name=(t.value||(t.dataset&&t.dataset.theme))||'';\n"),
     T_THEME, "②b 必须先认 `data-theme`"),
    ("M8 ⑤ 配色标本全都取**默认套**的取值（13 套卡片长一样 ⇒ 看不出差异）", API_PY,
     _b("    css = P.render_theme(name)\n"),
     _b("    css = P.render_theme(P.DEFAULT_THEME)\n"),
     "tests/test_acc_theme_user.py::test_每套主题都给出一份配色标本且主色互不相同",
     "主色两两不同 / 深浅分得开"),
]


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def run_one(case: str) -> bool:
    env = {**os.environ, "ACC_RESULTS_PATH": "../artifacts/_mut_acc_results.json",
           "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    r = subprocess.run([str(PY), "-m", "pytest", "-q", case], cwd=str(BE),
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    return r.returncode == 0


def main() -> int:
    before = {p: (p.read_bytes(), md5(p)) for p in {m[1] for m in MUTS}}
    hit = 0
    for desc, path, old_lf, new_lf, case, which in MUTS:
        first = old_lf.decode("utf-8").strip().split("\n")[0].strip()
        path = pick(path, first, old_lf.decode("utf-8"), new_lf.decode("utf-8"))
        before.setdefault(path, (path.read_bytes(), md5(path)))
        src = path.read_bytes()
        found = _locate(src, old_lf)
        if found is None or found[0] != 1:
            print(f"  ⛔ {desc} —— 锚点命中 {0 if found is None else found[0]} 次（期望 1）⇒ **未验证**")
            continue
        old = found[1]
        new = new_lf if old == old_lf else _fit(new_lf, src)
        path.write_bytes(src.replace(old, new, 1))
        red = not run_one(case)
        path.write_bytes(src)
        print(("  ✅ " if red else "  ⛔ 未命中 ") + desc + f"  → {which} " + ("变红" if red else "**仍是绿的**"))
        hit += red

    print()
    ok = all(md5(p) == h for p, (_, h) in before.items())
    print(f"  命中 {hit}/{len(MUTS)}")
    print(f"  复原校验（MD5 逐字节）：{'✅ 全部复原' if ok else '❌ 有文件没复原'}")
    return 0 if (hit == len(MUTS) and ok) else 1


if __name__ == "__main__":
    sys.exit(main())
