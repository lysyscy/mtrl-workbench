"""`backend/requirements.txt` = **依赖清单的唯一主人** —— 2026-10-05 立（出处：`M8 ①` 落地第一天实撞）。

⭐ **为什么要有本件**：`M8 ①` 那天走**入口 3（集采台账）**撞到 —— 用户手里三份台账**全是老 `.xls`**，
而 `app/import_kit/readers.py` 按**魔术字节**认 `.xls` 并 `import xlrd`（代码一直在）⇒ 可
**`requirements.txt` 里从来没登记过 `xlrd`** ⇒ 换机落地后 venv 里没有它 ⇒ 一导就
「解析失败 —— 请重试；一直不行请联系维护人」（`ModuleNotFoundError` 落进通用兜底，
⛔ 连代码里备好的「另存为 .xlsx 再导」那句下一步都走不到）。

⇒ 缺件这件事**本机测不出来**（开发机 venv 什么都有）⇒ **只有机器能挡**，这就是本件的意义。

⚠️ **能证伪**：从 `requirements.txt` 删掉任一行，本件必红（自证 = `tools/mut/_mut_deps.py`）。
⚠️ **口径**（别扩大）：本件只判「`app/` 里 import 的第三方模块，其发行包在清单里」这一条 ——
  ⛔ 不判该装什么版本（那是 `pip.ini` 镜像与 pip 自己的活）· ⛔ 不判有没有多装（多装无罪）。
"""

from __future__ import annotations

import ast
import pathlib
import sys

from tests.acc_plugin import acc

BACKEND = pathlib.Path(__file__).resolve().parents[1]
APP = BACKEND / "app"
REQS = BACKEND / "requirements.txt"

#: `import 名 ≠ 发行名` 的少数几个 —— ⭐ **量出来的，不是猜的**（2026-10-05 扫 `app/` 全量 import，差集只有这 1 个）。
#: ⚠️ 新增前先量测再登记；⛔ 别把它写成「随便填的同义词表」。
DISTRIBUTION_OF = {
    "win32print": "pywin32",     # pywin32 发行包里的打印模块
}


def _declared() -> set[str]:
    names: set[str] = set()
    for line in REQS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        names.add(line.split("==")[0].strip().lower().replace("_", "-"))
    return names


def _imported() -> dict[str, list[str]]:
    """`app/` 里 import 到的**第三方**模块 → 引用它的文件（相对仓根）。

    ⚠️ 用 `ast.walk` ⇒ **函数内的 import 也算数**（⛔ 别只扫模块顶层：`xlrd` / `openpyxl`
    都是在函数里 import 的，只扫顶层等于这条判据自己漏掉今天这条真缺陷）。
    """
    stdlib = set(sys.stdlib_module_names)
    out: dict[str, list[str]] = {}
    for py in sorted(APP.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        rel = py.relative_to(APP.parent.parent).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module.split(".")[0]]
            else:
                continue
            for mod in mods:
                if mod in stdlib or mod == "app":
                    continue
                out.setdefault(mod, [])
                if rel not in out[mod]:
                    out[mod].append(rel)
    return out


@acc()
def test_代码里用到的第三方库都在依赖清单里():
    """`app/` import 到的每个第三方模块，其**发行包**必须在 `requirements.txt` 里。

    ⛔ 判**发行包**（`DISTRIBUTION_OF` 换名）而不是 import 名 —— 两者不同时（`win32print`）
    判「import 名在不在清单里」会给出**假红**（清单里写的是 `pywin32`）。
    """
    declared = _declared()
    missing: dict[str, list[str]] = {}
    for mod, files in _imported().items():
        dist = DISTRIBUTION_OF.get(mod, mod)
        if dist.lower().replace("_", "-") not in declared:
            missing[mod] = files
    assert not missing, (
        "⛔ `app/` 里 import 了、而 `requirements.txt` 没登记的第三方库："
        + "；".join(f"`{m}`（{', '.join(f[:2])}…）" for m, f in sorted(missing.items()))
        + "\n  ⇒ 换机落地后 venv 里没有它 ⇒ 走到那条路就「解析失败 / 报错」，而**开发机测不出来**。"
        + "\n  ⇒ 修法：加进 `backend/requirements.txt`（并 `pip install` 一次验证），"
        + "⛔ 别改成 try/except 绕过去。")


@acc()
def test_老xls台账的读表件在依赖清单里():
    """**今天这条真缺陷的直接钉子**：`xlrd` 必须在清单里（老 `.xls` 台账靠它读）。

    ⚠️ 与上面那条**不是重复**：那条挡「任何漏登记」，这条把**今天撞到的那一个**点名 ——
    漏了它时上面那条会红但**看不出是谁**；本条让报错直指「老 `.xls` 读不了」。
    """
    assert "xlrd" in _declared(), (
        "⛔ `requirements.txt` 里没有 `xlrd` ⇒ **老 `.xls`（用户手里的集采台账就是这种）一律读不了**。\n"
        "  ⇒ `import_kit/readers.py::_read_xls` 是按魔术字节认 `.xls` 后 `import xlrd` 的；\n"
        "  ⇒ 缺它时报的是通用兜底「解析失败 —— 请重试」，⛔ 不告诉人「老格式读不了」。\n"
        "  ⇒ 修法：`pip install xlrd==2.0.1` ＋ 写进 `requirements.txt`（⚠️ `xlrd` 2.x **只读 .xls**，"
        "新格式仍归 `openpyxl` ⇒ ⛔ 别删 `openpyxl`）。")
