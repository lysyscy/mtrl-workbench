"""守什么：`TAIL-192`（结构审计 P0 四件）新挂的守卫**真会红**（⛔ 不是摆设）——
`tests/test_config_env_example.py` 的两条 ＋ `tests/test_shell_part_routes.py` 新加的三条。

**为什么单开一件**：本仓纪律 = 「新增/收紧判据 ⇒ 同批证明它**改坏了会红**」（反向灵敏度）。
这四条守的都是"**会默默过期**"那一类（件数 / 注释指路 / 配置键），
最典型的失败模式就是"判据在、但没牙齿"（`TAIL-165` / `TAIL-166` 两轮的教训）。

四靶（一次只碰一处、改完**立刻按 bytes 复原** ＋ 收尾 MD5 总校验）：
- `M1` `.env.example` 删掉 `SESSION_SECRET` 一行 ⇒ `test_样例必须覆盖配置的每一个字段` 必红。
- `M2` `actions.js` 的局部 `apiCode` 改回 `const API=` ⇒ `test_数据出口_API_只许在_api_js_里定义` 必红
  （证明那条"防同名遮蔽"的判据有牙齿 —— 它防的正是 2026-09-29 实测到的那两处）。
- `M3` `ops/architecture.md` 把指针换回**写死的件清单**（`shell/{core,actions}.js`）⇒ `test_活文档与注释不许写死壳件数` 必红。
- `M4` `core.js` 头注不再说 `API` 去哪了 ⇒ `test_core_js_头注要说清_API_去哪了` 必红。

跑法：`backend\\.venv\\Scripts\\python.exe tools\\mut\\_mut_tail192.py`（rc=0 = 全部按预期变红且已复原）
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
PY = str(BACKEND / ".venv" / "Scripts" / "python.exe")

ENV_EXAMPLE = ROOT / ".env.example"
ARCHITECTURE = ROOT / "ops" / "architecture.md"   # ⚠️ 2026-10-01 起文档落 `ops/`（`docs/` 已并入）
CORE_JS = BACKEND / "app" / "web" / "shell" / "core.js"
ACTIONS_JS = BACKEND / "app" / "web" / "shell" / "actions.js"

#: (说明, 靶件, 旧串, 新串, 判据节点)
MUTATIONS: list[tuple[str, Path, str, str, str]] = [
    (
        "M1 `.env.example` 少一个键（换机时没人知道要填它）",
        ENV_EXAMPLE,
        "SESSION_SECRET=\n",
        "",
        "test_config_env_example.py::test_样例必须覆盖配置的每一个字段",
    ),
    (
        "M2 局部映射表改回 `const API=`（遮蔽全局数据出口）",
        ACTIONS_JS,
        "const apiCode={nt:'API-01'",
        "const API={nt:'API-01'",
        "test_shell_part_routes.py::test_数据出口_API_只许在_api_js_里定义",
    ),
    (
        "M3 活文档把指针换回写死的件清单",
        ARCHITECTURE,
        "`shell/*.js`",
        "`shell/{core,actions}.js`",
        "test_shell_part_routes.py::test_活文档与注释不许写死壳件数",
    ),
    (
        "M4 `core.js` 头注不再说 `API` 去哪了",
        CORE_JS,
        "已切到 `api.js`",
        "见本件",
        "test_shell_part_routes.py::test_core_js_头注要说清_API_去哪了",
    ),
]


def run_one(node: str) -> bool:
    """跑一条判据 ⇒ True = **通过**（⚠️ "没跑起来"另判 —— 那正是"假绿"的一种）。"""
    r = subprocess.run(
        [PY, "-m", "pytest", "-q", f"tests/{node}"],
        cwd=str(BACKEND), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    out = (r.stdout or "") + (r.stderr or "")
    assert "no tests ran" not in out, f"判据节点没跑起来（名字写错了？）：{node}"
    return r.returncode == 0


def main() -> int:
    before = {p: p.read_bytes() for p in {t for _, t, _, _, _ in MUTATIONS}}
    hits = 0
    for name, target, old, new, node in MUTATIONS:
        raw = target.read_bytes()                        # ⭐ 每靶**写前重读盘**（别拿规划期那份拼第二处）
        text = target.read_text(encoding="utf-8")        # 归一 CRLF ⇒ LF（与下游替换串一致）
        if old not in text:
            print(f"⛔ {name}：**变异串没找到**（实现已改？）—— 本项作废")
            continue
        target.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
        passed = run_one(node)
        target.write_bytes(raw)                          # ⭐ 每条改完立刻复原
        if passed:
            print(f"❌ {name}：改坏了却**仍然全绿** ⇒ 该断言是假绿")
        else:
            print(f"✅ {name}：对应断言**变红**（有区分力）")
            hits += 1
    ok = all(
        hashlib.md5(p.read_bytes()).hexdigest() == hashlib.md5(b).hexdigest() for p, b in before.items()
    )
    print("\n  复原校验（MD5 逐字节）：", "✅ 已复原" if ok else "❌ 没复原！")
    print(f"\n结论：{hits}/{len(MUTATIONS)} 命中" + ("（rc=0）" if ok and hits == len(MUTATIONS) else "（需处理）"))
    return 0 if (ok and hits == len(MUTATIONS)) else 1


if __name__ == "__main__":
    sys.exit(main())
