"""**逐页对齐核对器**（原型 → 实现）· **纯 Python · 不依赖浏览器**。

**为什么有它**（2026-09-17 用户裁定）：计划 §5/§125 明写「交互规格 → `demo/` 原型本身」
「前端**照 `demo` 原型做**」，但工程验收（`ACC-*`）**全部**来自《说明书》的业务口径
⇒ **页面结构漂了既不报红也没人知道**（实测：`/m03` 付款通知书连「合计 / 折叠说明 / 筛选栏 / 排序」
都没有，而它是定义了 `R1`–`R19` 的**全站参照页**）。

**用户裁定（2026-09-17）**：
1. **结构 / 布局 / 交互必须照原型**；**纯视觉**（配色 / 字号 / 圆角 / 间距微调）由实现方发挥（§1.3 授权范围）；
2. **先补齐已做页面**，再往前走；
3. **阻断式**：不对齐 ⇒ 非零退出码，不补齐不许合入。

**口径（本节即定义，别处不要另立）**：
- 真源 = **原型源码**（切片 `V.<视图>` 到下一个 `V.` / `BIND.` 定义之间）—— **静态抽取**，
  可复现、不依赖手抄（⚠️ 导读 §2.1 那几个"表N 筛N 卡N"是**运行时**数字，二者可能有条件分支差异；
  本工具以**源码**为准，因为它可复现且能定位到行）。
- 实现侧 = **服务端渲染的页面 HTML**（`/m03` 这类路由）。
- **结构件**（逐项计数，口径写死）：
  | 键 | 原型里的形态 | 说明 |
  |---|---|---|
  | `表` | `<table` | 数据表 |
  | `筛` | `class="fbar"` | `R4` 筛选栏 |
  | `卡` | 类名含 `kpis` | `R2` 指标卡区（**只在"域级总览"页该有**） |
  | `折` | `<details` | `R1` 页首说明折叠 |
  | `合计` | `sumrow` / `sumRowOf` | 用户 2026-09-13 口径「求和一律落在表内」 |
  | `排序` | `data-sort` | `R13` 表头排序 |
  | `共用项目面板` | `pjwrap` | `§8.2 复用点`：项目选择器**唯一出口** |

⚠️ **本工具以"原型类名/结构"为准** —— 实现换个名字起等价物 ⇒ **仍判不对齐**
（因为用户要求的就是"结构照原型"；换名会让后续所有核对与维护失去共同语言）。

跑法：
  `backend/.venv/Scripts/python.exe tools/ui_parity.py`            # 人读表（阻断式：有必须对齐项不符 ⇒ rc=1）
  `backend/.venv/Scripts/python.exe tools/ui_parity.py --json`     # 机读
⚠️ 需先起服务（默认 `http://127.0.0.1:8000`，可用 `--base` 改）。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROTO = pathlib.Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\demo\材料报表自动化工作台-交互原型.html")

# 视图 → 实现路由（未实现的视图照样列出来，标「未开工」——不是失败）
PAGES: list[tuple[str, str, str]] = [
    ("home", "/", "看板 · 待办"),
    ("m01", "/m01", "项目档案"),
    ("m02", "/m02", "i8 接入层"),
    ("m03", "/m03", "付款通知书"),
    ("m04", "/m04", "付款计划"),
    ("m05", "/m05", "付款流水与欠款统计"),
    ("m06", "/m06", "过程资料"),
    ("m07", "/m07", "收发结存与活动大表"),
    ("m08", "/m08", "库存单据与调整单"),
    ("m09", "/m09", "特殊费用月报表"),
    ("m11", "/m11", "集采台账"),
    ("m12", "/m12", "差异登记"),
    ("m13", "/m13", "跨域能力"),
    ("m14", "/m14", "规则配置"),
    ("m15", "/m15", "用户管理"),
]

# 结构件口径：键 → (原型侧正则, 实现侧正则)  —— 两侧同口径，避免"数法不同"的假差异
PROBES: list[tuple[str, str]] = [
    ("表", r"<table"),
    ("筛", r'class="fbar"'),
    ("卡", r"kpis"),
    ("折", r"<details"),
    ("合计", r"sumrow|sumRowOf"),
    ("排序", r"data-sort"),
    ("项目面板", r"pjwrap"),
]

# ⚠️ **所有结构件都要求对齐**（用户 2026-09-17 裁定：结构 / 布局 / 交互必须照原型，纯视觉才由实现方发挥）
#   ⇒ 任一结构件不符且**未登记** ⇒ 报红。下面这个元组只是**修补优先级**（先修表/筛/卡）。
BLOCKING = ("表", "筛", "卡")

# ⭐ **已登记缺口**（豁免清单）—— 与 `tools/t7_expected.txt`（`doc_audit` 的 `T7a`）同款做法：
#   · 在清单里 ⇒ **只提示"待补"**（不报红，否则 10 页全红 ⇒ 什么都合不进去）；
#   · 不在清单里 ⇒ **报红（rc=1）** ⇒ 挡住"新产生的漂移"；
#   · 清单里的项**已对齐** ⇒ 提示"可消号"（防清单变成永久挡箭牌）。
# 格式：每行 `视图:结构件`，`#` 开头 = 注释。
EXPECTED = ROOT / "tools" / "ui_parity_expected.txt"


def load_expected() -> set[str]:
    if not EXPECTED.exists():
        return set()
    out: set[str] = set()
    for line in EXPECTED.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def slice_view(src: str, view: str) -> str:
    """切出 `V.<view>=…` 到下一个 `V.` / `BIND.` 定义之间的源码（找不到 ⇒ 空串）。"""
    m = re.search(rf"^V\.{view}\s*=\s*", src, re.M)
    if not m:
        return ""
    rest = src[m.end():]
    nxt = re.search(r"^(?:V|BIND)\.\w+\s*=", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def count(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text))


def fetch(base: str, route: str) -> str | None:
    """取实现页面 HTML；404 ⇒ `None`（= 未开工）。"""
    req = urllib.request.Request(base + route, headers={"User-Agent": "ui-parity"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="逐页对齐核对（原型 → 实现）")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not PROTO.exists():
        print(f"⛔ 找不到原型：{PROTO}", file=sys.stderr)
        return 2
    src = PROTO.read_text(encoding="utf-8")
    expected = load_expected()

    rows: list[dict] = []
    for view, route, label in PAGES:
        proto_slice = slice_view(src, view)
        if not proto_slice:
            rows.append({"view": view, "route": route, "label": label,
                         "state": "原型里没有该视图", "dims": {}, "gaps": []})
            continue
        try:
            html = fetch(args.base, route)
        except Exception as exc:                                # noqa: BLE001
            rows.append({"view": view, "route": route, "label": label,
                         "state": f"取页面失败：{type(exc).__name__}", "dims": {}, "gaps": []})
            continue
        if html is None:
            rows.append({"view": view, "route": route, "label": label,
                         "state": "未开工（404）", "dims": {}, "gaps": []})
            continue
        dims: dict[str, dict] = {}
        gaps: list[str] = []
        pending: list[str] = []          # 已登记 ⇒ 只提示
        blocking: list[str] = []         # 未登记 ⇒ 报红
        for key, pattern in PROBES:
            p, i = count(proto_slice, pattern), count(html, pattern)
            ok = p == i
            known = f"{view}:{key}" in expected
            dims[key] = {"proto": p, "impl": i, "ok": ok, "known": known}
            if not ok:
                gaps.append(f"{key}(原型 {p} / 实现 {i})")
                (pending if known else blocking).append(key)
        stale = [k for k, d in dims.items() if d["ok"] and f"{view}:{k}" in expected]
        rows.append({"view": view, "route": route, "label": label,
                     "state": "不对齐" if gaps else "✅ 对齐",
                     "blocking": blocking, "pending": pending, "stale": stale,
                     "dims": dims, "gaps": gaps})

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        print("=" * 96)
        print("逐页对齐核对（真源 = demo/ 原型源码 · 比对 = 实现页面 HTML）")
        print("=" * 96)
        head = "".join(f"{k:>9}" for k, _ in PROBES)
        print(f"{'视图':<6}{'路由':<7}{'页面':<22}{head}")
        print("-" * 96)
        for r in rows:
            if r["state"] in ("未开工（404）",) or r["state"].startswith(("原型里", "取页面")):
                print(f"{r['view']:<6}{r['route']:<7}{r['label']:<22}{r['state']}")
                continue
            cells = "".join(
                f"{(str(d['proto']) + '/' + str(d['impl'])).rjust(9) if not d['ok'] else '✓'.rjust(9)}"
                for _, d in r["dims"].items()
            )
            print(f"{r['view']:<6}{r['route']:<7}{r['label']:<22}{cells}")
        print("-" * 96)
        print("说明：单元格 = 原型/实现（不等就显数字，相等显 ✓）· 阻断项 =", "、".join(BLOCKING))
        bad = [r for r in rows if r.get("blocking")]
        pend = [r for r in rows if r.get("pending")]
        stale = [(r["view"], k) for r in rows for k in (r.get("stale") or [])]
        print(f"\n🚫 必须修（**未登记**的阻断项不符）：{len(bad)} 页 —— "
              + (", ".join(f"{r['view']}({r['route']})：{'、'.join(r['blocking'])}" for r in bad)
                 if bad else "无 ✅"))
        print(f"⏳ 已登记待补（不阻断）：{len(pend)} 页 —— "
              + (", ".join(f"{r['view']}({'、'.join(r['pending'])})" for r in pend) if pend else "无"))
        if stale:
            print(f"♻️ 可消号（已对齐但还在清单里）：{', '.join(f'{v}:{k}' for v, k in stale)}")
        detail = [r for r in rows if r.get("gaps")]
        if detail:
            print("\n全部差异明细：")
            for r in detail:
                print(f"  · {r['view']:<5}{r['route']:<7}{r['label']:<20}{'；'.join(r['gaps'])}")

    return 1 if any(r.get("blocking") for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
