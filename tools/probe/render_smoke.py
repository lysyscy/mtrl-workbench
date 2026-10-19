#!/usr/bin/env python
"""M0-0B · 渲染冒烟（**验证性脚本，不是交付代码**）。

目的：钉死《技术栈选型分析》**§5 风险 13** —— 「本地渲染 PDF」在本机（含服务环境）能否跑通。
本机实况：playwright 缓存**只有 `chromium_headless_shell`**（无完整 chromium ⇒ `headless=False` 必失败）。

用法：
    python tools/render_smoke.py                       # 交互式会话直接跑
    python tools/render_smoke.py --out artifacts/x.pdf

⚠️ **收尾策略**：**不调 `browser.close()` / `playwright.stop()`**
   —— 旧实现实测这两处在 Windows 上会**永久挂住**（§2.4）。
   打完汇总计时后直接 `os._exit(0)` 快退。

退出码：0 = 渲染成功 · 1 = 失败（附原因）
"""

from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir

import argparse
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / _run_dir() / "render_smoke.pdf"

HTML = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>渲染冒烟</title>
<style>
  @page { size: A4; margin: 12mm; }
  body { font-family: "Microsoft YaHei", "SimSun", sans-serif; font-size: 12px; color: #000; }
  h2 { font-size: 16px; margin: 0 0 8px; }
  table { border-collapse: collapse; width: 100%; margin-bottom: 8px; }
  th, td { border: 1px solid #333; padding: 4px 6px; text-align: left; }
  th { background: #f0f0f0; width: 22%; }
  .slot { height: 40px; vertical-align: bottom; color: #666; }
  .empty { }
</style></head>
<body>
  <h2>付款通知书 · 渲染冒烟件（非真实单据）</h2>
  <table>
    <tr><th>付款项目</th><td colspan="3">百通宏达热力（泗阳）有限公司热电联产项目#4锅炉建筑及安装工程（XMCB2025080001）</td></tr>
    <tr><th>单据名称</th><td colspan="3">泗阳百通 4#锅炉 — 辅材付款</td></tr>
    <tr><th>审批金额</th><td>1,234,567.89</td><th>已付金额</th><td>0.00</td></tr>
    <tr><th>统计结算金额</th><td>1,234,567.89</td><th>统计付款金额</th><td>-0.01</td></tr>
  </table>
  <table>
    <tr><td class="slot">项目经理</td><td class="slot">分公司非集采主管经理</td><td class="slot empty">核算部项目会计</td></tr>
  </table>
</body></html>
"""


def _browsers_dir() -> Path:
    """playwright 浏览器缓存目录（受 `PLAYWRIGHT_BROWSERS_PATH` 影响）。"""
    env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env:
        return Path(env)
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "AppData" / "Local" / "ms-playwright"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--html", default="", help="改用指定的 HTML 文件（默认用内置样例）")
    parser.add_argument(
        "--browsers-path",
        default="",
        help="显式指定 PLAYWRIGHT_BROWSERS_PATH（服务 / SYSTEM 身份下必需 —— 见 M7 部署清单）",
    )
    parser.add_argument(
        "--log", default="", help="把输出写入该文件（计划任务/服务下拿不到 stdout）"
    )
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # ⚠️ 必须在 import playwright / launch **之前**设置
    if args.browsers_path:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = args.browsers_path

    if args.log:
        log_path = Path(args.log)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        sys.stdout = open(log_path, "w", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stderr = sys.stdout

    print("[0-B] 渲染冒烟开始")
    print(f"      python      = {sys.executable}")
    print(f"      cwd         = {os.getcwd()}")
    print(f"      USERPROFILE = {os.environ.get('USERPROFILE', '(无)')}")
    print(
        "      PLAYWRIGHT_BROWSERS_PATH = "
        f"{os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '(未设置 → 用默认用户缓存)')}"
    )

    t0 = time.perf_counter()
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] 无法 import playwright：{exc}")
        return 1

    try:
        with sync_playwright() as p:
            t_launch = time.perf_counter()
            browser = p.chromium.launch(headless=True)
            print(f"[OK] 浏览器已启动（{time.perf_counter() - t_launch:.2f}s）")
            print(f"      browser.version = {browser.version}")
            # ⚠️ `p.chromium.executable_path` 是**名义路径**，未安装 full chromium 时它
            #    仍然返回一个**并不存在**的路径 ⇒ **不能**当"浏览器是否可用"的判据。
            #    这里改为**实测存在的浏览器目录**。
            print(f"      名义 executable_path = {p.chromium.executable_path}")
            print(f"      （存在？ {Path(p.chromium.executable_path).exists()}）")
            print(f"      浏览器缓存目录 = {_browsers_dir()}")
            for entry in sorted(_browsers_dir().glob("chromium*")):
                exes = list(entry.rglob("*.exe"))
                print(f"        - {entry.name}: {[e.name for e in exes]}")

            page = browser.new_page()
            t_render = time.perf_counter()
            if args.html:
                page.goto(Path(args.html).as_uri(), wait_until="load")
            else:
                page.set_content(HTML, wait_until="load")
            page.pdf(
                path=str(out_path),
                format="A4",
                print_background=True,
                prefer_css_page_size=True,
            )
            print(f"[OK] PDF 已生成（渲染 {time.perf_counter() - t_render:.2f}s）")
            # ⚠️ 刻意不关浏览器 / 不 stop（会挂死 —— 见模块 docstring）
    except Exception as exc:  # noqa: BLE001
        print(f"[FAIL] 渲染失败：{type(exc).__name__}: {exc}")
        print(f"      累计耗时 {time.perf_counter() - t0:.2f}s")
        _flush_and_exit(1)

    total = time.perf_counter() - t0
    ok = out_path.exists() and out_path.stat().st_size > 0
    size = out_path.stat().st_size if out_path.exists() else 0
    print(f"[{'OK' if ok else 'FAIL'}] 产物 = {out_path}")
    print(f"      大小 = {size} 字节")
    print(f"      总耗时 = {total:.2f}s")
    _flush_and_exit(0 if ok else 1)
    return 0


def _flush_and_exit(code: int) -> None:
    """快退（不等待 playwright 收尾线程 —— 那会挂住）。"""
    sys.stdout.flush()
    sys.stderr.flush()
    print(f"[0-B] 以退出码 {code} 快退（不调 browser.close）", flush=True)
    os._exit(code)


if __name__ == "__main__":
    raise SystemExit(main())
