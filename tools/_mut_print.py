"""打印链路（`TAIL-46` ②③）的**反向灵敏度** —— 把实现**故意改坏**，确认对应断言**真的变红**。

三条纪律（本仓既定）：
1. 每处只改**一处**、只跑**定向断言** ⇒ 变红才算这条判据**有区分力**；
2. 改前存字节、测后**逐字节复原**并用 MD5 自证（⛔ 不许把仓留在改坏的态）；
3. ⛔ **一个字节都不发**：只动源码文本、只跑断言 ⇒ **不碰打印机**（自检不碰真实设备的规矩）。

用法：`backend\\.venv\\Scripts\\python.exe tools\\_mut_print.py`
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / "backend" / ".venv" / "Scripts" / "python.exe"
DISPATCH = ROOT / "backend" / "app" / "mod03_notice" / "print" / "dispatch.py"
STORE = ROOT / "backend" / "app" / "mod03_notice" / "settings_store.py"
SERVICE = ROOT / "backend" / "app" / "mod03_notice" / "service.py"
from shell_source import SHELL_PATH as SHELL  # noqa: F401  ← `P4`① 读取点收敛
#: 变异跑的**结果另写**一处（⛔ 别冲掉全套的 `artifacts/acc_results.json` —— 见 `_run` 里的告警）
MUT_RESULTS = ROOT / "artifacts" / "_mut_acc_results.json"

MUTS: list[dict[str, str]] = [
    {
        "file": str(DISPATCH),
        "old": 'AUTO_ORDER: tuple[str, ...] = ("ipp", "driver", "raw")',
        "new": 'AUTO_ORDER: tuple[str, ...] = ("driver", "ipp", "raw")',
        "test": "tests/test_print_dispatch.py::test_auto_试法顺序是_ipp_驱动_raw",
        "why": "自动档的试法顺序改错 ⇒ 换台没装驱动的机器就先撞墙（口径是 IPP → 驱动 → RAW）",
    },
    {
        "file": str(DISPATCH),
        # ⚠️ 锚点只取**代码行**（不带注释）——注释里有引号，抄错一个字符就 0 命中
        "old": '        return f"自动选「{label}」：{note}" if m == "auto" else note',
        "new": (
            '        # MUT：说"已投递"也继续试 ⇒ 会重复出纸\n'
            '        fails.append((label, note))\n'
            '        continue'
        ),
        "test": "tests/test_print_dispatch.py::test_auto_前一档说已投递就停住_绝不重复出纸",
        "why": "⭐ 最要紧那条被判据抓住：前一档说「已投递（未核实）」还往下试 ⇒ 同一张纸打两遍",
    },
    {
        "file": str(DISPATCH),
        "old": '_RAW_PORT = 9100',
        "new": '_RAW_PORT = 631',
        "test": "tests/test_print_dispatch.py::test_raw_端口固定9100_地址里的端口不照抄",
        "why": "RAW 端口照抄了地址里那个（631 是 IPP 的）⇒ 投错门、必然超时",
    },
    {
        "file": str(DISPATCH),
        # ⚠️ 只改"记理由"那一行（改法等价于"全失败时不告诉用户为什么"）
        "old": '            fails.append((label, str(exc)))',
        "new": '            fails.append((label, ""))  # MUT：不记理由 ⇒ 用户只看到通道名',
        "test": "tests/test_print_dispatch.py::test_auto_全失败要把三档理由都带上",
        "why": "`001-08`：全失败时把三档理由压成一句「打印失败」⇒ 现场完全不知道从哪改",
    },
    {
        "file": str(DISPATCH),
        "old": '    m = validate_print_mode(mode if mode is not None else (s.print_mode or "auto"), name)',
        "new": '    m = validate_print_mode(mode if mode is not None else (s.print_mode or "auto"), name or "任意")  # MUT',
        "test": "tests/test_print_dispatch.py::test_系统驱动不给打印机名_当场拒",
        "why": "「系统驱动」不给打印机名也放行 ⇒ 会悄悄打到**系统默认打印机**上（不是用户选的那台）",
    },
    {
        "file": str(STORE),
        "old": 'PRINT_MODES: tuple[str, ...] = ("auto", "ipp", "driver", "raw")',
        "new": 'PRINT_MODES: tuple[str, ...] = ("auto", "ipp", "driver")',
        "test": "tests/test_print_channel_settings.py::test_四条通道都认_别的都不认",
        "why": "少认一条通道 ⇒ 用户在有 PDF 解释器的机器上想固定用 RAW 时被无理由拒掉",
    },
    {
        "file": str(STORE),
        "old": '    if value == "driver" and not (printer_name or "").strip():',
        "new": '    if False:  # MUT',
        "test": "tests/test_print_channel_settings.py::test_选系统驱动必须给打印机名",
        "why": "「系统驱动」不填名字也能存 ⇒ 存下去的是一条**打不到目标机器**的设置",
    },
    {
        "file": str(SHELL),
        "old": "  printerList: () => API.get('/api/m03/settings/printers'),",
        "new": "  printerList: () => Promise.resolve([]),  // MUT",
        "test": "tests/test_print_dispatch.py::test_壳侧有本机打印机名可选",
        "why": "弹窗拿不到本机打印机名 ⇒ 用户只能手打，而这个名字**必须一字不差**",
    },
    {
        "file": str(SERVICE),
        "old": "unverified=bool(note)",
        "new": "unverified=False  # MUT：把「说不清」当成「已核实完成」",
        "test": "tests/test_print_receipt_semantics.py",
        "why": "① 的命门：把「已投递但说不清」报成**已核实** ⇒ 人会以为打完了（假成功的孪生兄弟）",
    },
]


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _run(test: str) -> int:
    proc = subprocess.run(
        [str(PY), "-m", "pytest", test, "-p", "no:cacheprovider", "-q", "--tb=no"],
        cwd=str(ROOT / "backend"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env={
            **__import__("os").environ,
            "PYTHONDONTWRITEBYTECODE": "1",
            # ⚠️⚠️ **必须另写**：不设它 ⇒ 每跑一处变异就把**全套** `artifacts/acc_results.json`
            #     冲成"单条"（而且是在**改坏的代码**下写的）⇒ 之后 `acc_report` 会报"绿 0"，
            #     台账的四态数字全错。本仓实测踩过（`_mut_archpick.py` 早有同款注释）。
            "ACC_RESULTS_PATH": str(MUT_RESULTS),
        },
    )
    return proc.returncode


def main() -> int:
    bad = 0
    for i, m in enumerate(MUTS, 1):
        path = Path(m["file"])
        before = path.read_bytes()
        digest = hashlib.md5(before).hexdigest()
        text = before.decode("utf-8")
        if text.count(m["old"]) != 1:
            print(f"✗ M{i} 锚点不唯一（{text.count(m['old'])} 处）：{m['old'][:60]!r}")
            bad += 1
            continue
        path.write_text(text.replace(m["old"], m["new"]), encoding="utf-8")
        try:
            rc = _run(m["test"])
        finally:
            path.write_bytes(before)                       # ← 逐字节复原
        ok_restore = _md5(path) == digest and path.read_bytes() == before
        verdict = "✓ 变红" if rc != 0 else "✗ **没变红**（这条判据抓不住它）"
        if rc == 0 or not ok_restore:
            bad += 1
        print(f"M{i} {verdict}｜复原={'逐字节相同' if ok_restore else '✗ 不一致'}"
              f"｜{m['test'].split('::')[-1]}")
        print(f"    {m['why']}")
    print()
    print(f"结论：**{'全绿' if bad == 0 else f'有 {bad} 处不合格'}**（{len(MUTS)} 处变异）")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
