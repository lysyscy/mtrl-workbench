"""壳真机自检 · **第 ⑳ 段：四个暂留件收口后的壳内四页**（`§19` · 2026-09-21）。

覆盖：`set`（系统设置）· **`imp`（数据导入 · 通用导入面）**。
⚠️ `m08imp`（库存单据导入）已按用户 2026-09-22 裁定**整体删除**（`T8` 守卫）⇒ 不再覆盖。
⚠️ `m06imp`（过程资料历史导入）已随 `B5c` **下架**、⭐ `m05imp`（历史付款导入）已随 `B5b` 第三步
（2026-09-23 用户裁定 `B`）**下架** ⇒ 这两页改验 `imp`（同一页里选 `m06_proc` / `m05_flow` 域）。

**为什么单独立一个文件**：`tools/probe/_shell_smoke.py` 有 **400 行即黄**（`doc_audit` 的 `T5`）；⚠️ 连 `>600` 也只是**黄** —— `[用户·2026-09-21]` 把"红·禁合入"**降级**，只须在 `ops/阈值表.md` 登记"为什么不拆"
⇒ 与 `_shell_home.py` / `_shell_pend.py` 同款，由主自检**调一段**（`check(page, errors)`）。

**它验什么**（三件，都只在真机能看到）：
  ① **四页都渲染得出**、且**没有 console / page 错误**（⛔ 离线断言看不见这类崩）；
  ② ⭐ **无死控件**：页面上渲染出来的每个 `data-act` 都能解析到 `ACT`；**表单元素**（input/select）
     还必须在 `CHG` 里 —— 漏登记 ⇒ `change` 被**静默丢弃**（症状就是"选完文件按钮永远是灰的"）。
     本仓踩过三次（`jcAmt` / `jcPartySet` / `themeSet`）⇒ 这里是它的真机化落点；
  ③ **页面内容确实来自后端**（不是壳里另抄一份）：设置项条数 = `SPECS`；导入页的列契约 / 项目候选 /
     表头清单与各自 `/api/...` 端点一致。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import app.core.models_registry  # noqa: E402, F401

#: 页 → (中文名, 该页必须看得见的几个标志串)
PAGES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("set", "系统设置", ("连接参数", "变更留痕", "与直觉相反")),
    # ⭐ `TAIL-75` `B5`（2026-09-22）：通用导入面 —— 「数据导入」页（域清单 ＋ 四步向导）。
    #    ⚠️ 标志串取**进页就能看见**的（"列映射"要选完文件才有 ⇒ ⛔ 不能当标志）。
    ("imp", "数据导入", ("导入哪个域", "落库前一个字节都不写库")),
)


def _probe(page, key: str) -> dict:
    """进这一页 → 取「标志串在不在 / 死控件 / 那页自己的数据」三件。"""
    page.click(f'[data-k="{key}"]')
    page.wait_for_timeout(900)
    return page.evaluate("""(key) => {
        const box = document.querySelector('#view');
        const txt = (box.innerText || '');
        const acts = [...box.querySelectorAll('[data-act]')].map(el => ({
            a: el.dataset.act, tag: el.tagName.toLowerCase(),
        }));
        return {
            view: VIEW, len: (box.innerHTML || '').length, txt: txt,
            acts: acts,
            dead: acts.filter(x => typeof ACT[x.a] !== 'function').map(x => x.a),
            notInChg: acts.filter(x => ['input', 'select', 'textarea'].includes(x.tag)
                                    && !CHG.includes(x.a)).map(x => x.a),
            inputs: box.querySelectorAll('input,select').length,
            rows: box.querySelectorAll('tbody tr').length,
        };
    }""", key)


def check(page, errors: list[str]) -> None:
    """⑳ 真机走一遍：四页 **渲染 ＋ 无死控件 ＋ 内容是后端的**。"""
    from app.core.app_settings import SPECS

    stage = "开页"
    try:
        for key, name, marks in PAGES:
            stage = name
            got = _probe(page, key)
            miss = [m for m in marks if m not in got["txt"]]
            ok_render = got["view"] == key and got["len"] > 400 and not miss
            print(("  ✅ " if ok_render else "  ⛔ ")
                  + f"⑳ {name}（`{key}`）渲染出来了"
                  + (f"（{got['len']} B）" if ok_render else f"：view={got['view']} 缺 {miss}"))
            if not ok_render:
                errors.append(f"四个暂留件收口自检未通过：{name} 没渲染出来（缺 {miss}）")

            # ② 死控件 ＋ 表单元素漏登记 `CHG`（本仓最贵的一类"静默"）
            ok_acts = not got["dead"] and not got["notInChg"]
            print(("  ✅ " if ok_acts else "  ⛔ ")
                  + f"⑳ {name} 无死控件（{len(got['acts'])} 个 data-act"
                  + f"，表单元素 {got['inputs']} 个）"
                  + ("" if ok_acts else f"：ACT 里没有 {got['dead']}；未进 CHG {got['notInChg']}"))
            if not ok_acts:
                errors.append(
                    f"四个暂留件收口自检未通过：{name} 有死控件 / 表单动作没进 CHG"
                    f"（ACT 缺 {got['dead']}；CHG 缺 {got['notInChg']}）")

        # ③ 内容是后端的（⛔ 壳里另抄一份 = 两处副本必漂）
        stage = "与后端对账"
        got = page.evaluate("""async () => {
            const j = async u => await (await fetch(u)).json();
            const r = {spec: (await j('/api/m14/settings')).items.length,
                       m05: (await j('/api/imp/m05_flow/schema')).fields.length,
                       m06: (await j('/api/imp/m06_proc/schema')).fields.length,
                       m06d: (await j('/api/imp/m06_proc/options')).projects.length};
            return r;
        }""")
        oks = [
            (got["spec"] == len(SPECS), f"设置项条数与 `SPECS` 一致（{got['spec']} = {len(SPECS)}）"),
            # ⚠️ 2026-09-23（`B5b` 第三步 · 用户裁定 `B`）：`/api/m05/import/meta` 已随旧页删除
            #    ⇒ 列契约改从**通用面的域声明**读（判词不变：五列契约就是 A–E，只是出口换成域声明）。
            (got["m05"] == 5, f"付款导入的列契约是 A–E 五列（{got['m05']}）"),
            (got["m06"] >= 1, f"过程资料导入的材料列清单非空（{got['m06']} 列）"),
            (got["m06d"] >= 0, f"过程资料导入的项目候选可读（{got['m06d']} 个）"),
        ]
        for ok, what in oks:
            print(("  ✅ " if ok else "  ⛔ ") + f"⑳ {what}")
            if not ok:
                errors.append("四个暂留件收口自检未通过：" + what)
    except Exception as exc:                              # noqa: BLE001
        print(f"  ⛔ ⑳ 在「{stage}」这一步失败：{type(exc).__name__}: {str(exc)[:160]}")
        errors.append(f"四个暂留件收口自检异常（{stage}）：{type(exc).__name__}")


__all__ = ["check"]
