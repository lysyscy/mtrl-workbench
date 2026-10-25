"""壳真机自检第⑳段：设置渲染、搬迁参数入口和界面大小。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import app.models_registry  # noqa: E402, F401

PAGES = (("set", "系统设置", ("外观主题", "界面大小")),)


def _probe(page, key: str, marks: tuple[str, ...] = ()) -> dict:
    """进这一页 → 取「标志串在不在 / 死控件 / 那页自己的数据」三件。"""
    page.click(f'[data-k="{key}"]')
    # ⚠️ 2026-09-26：**死等改条件等待**（原 `wait_for_timeout(900)`）。
    #    ⚠️ 条件**必须带上这一页自己的标志串**（`marks`）—— 实测第一版只等"内容非空"会**跑早**：
    #        `set` 页 7096 B 时长度早就够了，而「与直觉相反」那一段还没渲染 ⇒ 报出
    #        "渲染出来了：缺 ['与直觉相反']"（**假红**，其实是没等够）；`imp` 页同理 ——
    #        域下拉的候选是**异步**取来的，早读到的 `value` 是空串。
    #    ⭐ 条件里放 `marks` 不算"拿判据自己证明自己"：**超时不算过**（这里吞掉超时），
    #       仍由下面那条正式断言判定并报原因 ⇒ 等待只负责"别跑早"，判词一字不动。
    try:
        page.wait_for_function(
            """a => VIEW === a.k && a.m.every(x =>
                   (document.querySelector('#view').innerText || '').includes(x))""",
            arg={"k": key, "m": list(marks)}, timeout=8000)
    except Exception:                                      # noqa: BLE001 —— 没等到就交给正式断言报
        pass
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
            /* ⛔ `#2`（2026-09-26）：`CHG` 名单已拆 ⇒ 这里**不再查"有没有登记"**
               —— `change` 委托看见 `data-act` 就跑，"漏登记"这回事不存在。 */
            inputs: box.querySelectorAll('input,select').length,
            rows: box.querySelectorAll('tbody tr').length,
        };
    }""", key)


def check(page, errors: list[str]) -> None:
    """设置页正常渲染、无死控件，并保留原参数和字号检查。"""
    from app.core.app_settings import SPECS

    try:
        for key, name, marks in PAGES:
            got = _probe(page, key, marks)
            missing = [mark for mark in marks if mark not in got["txt"]]
            if got["view"] != key or got["len"] <= 400 or missing:
                errors.append(f"设置自检未通过：{name} 没渲染出来（缺 {missing}）")
            if got["dead"]:
                errors.append(f"设置自检未通过：{name} 有死控件（ACT 缺 {got['dead']}）")
        count = page.evaluate("async () => (await (await fetch('/api/m14/settings')).json()).items.length")
        if count != len(SPECS):
            errors.append(f"设置自检未通过：设置项条数 {count} 与 SPECS {len(SPECS)} 不一致")
        print(f"⑳ 设置渲染与控件检查完成（设置项 {count}）")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"设置自检异常：{type(exc).__name__}: {str(exc)[:160]}")
    _check_moved(page, errors)
    _check_uiscale(page, errors)


def _check_uiscale(page, errors: list[str]) -> None:
    """⭐ `TAIL-129`（2026-09-27 · 用户裁定走**方案 B**）：**界面大小**这一档真的能改。

    ⚠️ 为什么必须真机：方案 B 的效果全在**CSS 变量 `--fscale` 被真的写进 `<html>`** 这一下 ——
       离线只能证"样式里都乘了它""壳里有那段代码"，证不到"点了它真的变"。
    判词四件（**都在同一屏上量**）：
      ① 点另一档 ⇒ `--fscale` 变了；② **页面没刷新**（`VIEW` 不变 —— 刷新会把用户扔回看板）；
      ③ **正文字号真的变了**（`getComputedStyle(body).fontSize`）—— 这才叫"能看清"；
      ④ **复原**（点回原来那一档）并断言回到原值 —— ⚠️ 自检⛔ **不许留残留**（它会写库：
         界面大小是**按用户**存的，跑完必须还原成跑之前那个值）。
    """
    n = 0
    try:
        page.click('[data-k="set"]')
        page.wait_for_selector('#view [data-act="uiScaleSet"]', timeout=8000)
        got0 = page.evaluate("""() => {
            const bs = [...document.querySelectorAll('#view [data-act="uiScaleSet"]')];
            const cur = bs.findIndex(b => b.classList.contains('pri'));   /* 当前那一档带 pri */
            return {n: bs.length, cur: cur, fs: getComputedStyle(document.body).fontSize,
                    sc: getComputedStyle(document.documentElement).getPropertyValue('--fscale').trim()};
        }""")
        n = int(got0["n"])
        if n >= 2 and got0["cur"] >= 0:
            other = 0 if got0["cur"] != 0 else n - 1        # 挑**另一档**（⛔ 不赌档位键字面量）
            page.evaluate("""(i) => document.querySelectorAll('#view [data-act="uiScaleSet"]')[i].click()""",
                          other)
            page.wait_for_function(
                "(v) => getComputedStyle(document.documentElement)"
                ".getPropertyValue('--fscale').trim() !== v", arg=got0["sc"], timeout=8000)
            got1 = page.evaluate("""() => ({
                view: VIEW, fs: getComputedStyle(document.body).fontSize,
                sc: getComputedStyle(document.documentElement).getPropertyValue('--fscale').trim(),
            })""")
            ok = (got1["sc"] != got0["sc"]) and (got1["fs"] != got0["fs"]) and got1["view"] == "set"
            print(("  ✅ " if ok else "  ⛔ ")
                  + f"⑳ 界面大小：{n} 档 · 点另一档 ⇒ `--fscale` {got0['sc']}→{got1['sc']} · "
                    f"正文字号 {got0['fs']}→{got1['fs']} · 页面没刷新（VIEW={got1['view']}）")
            if not ok:
                errors.append("四个暂留件收口自检未通过：改了界面大小档但**字体没变**"
                              f"（或页面被刷新了）—— 实测 {got0} ⇒ {got1}")
            page.evaluate("""(i) => document.querySelectorAll('#view [data-act="uiScaleSet"]')[i].click()""",
                          got0["cur"])                       # ⭐ 复原
            page.wait_for_function(
                "(v) => getComputedStyle(document.documentElement)"
                ".getPropertyValue('--fscale').trim() === v", arg=got0["sc"], timeout=8000)
            back = page.evaluate("() => getComputedStyle(document.documentElement)"
                                 ".getPropertyValue('--fscale').trim()")
            print(("  ✅ " if back == got0["sc"] else "  ⛔ ")
                  + f"⑳ 界面大小：自检已**复原**到跑之前那一档（`--fscale`={back}）")
            if back != got0["sc"]:
                errors.append(f"四个暂留件收口自检未通过：界面大小自检**没复原**（{got0['sc']} → {back}）"
                              " —— 自检不许留残留（这一项是按用户存的）")
        else:
            errors.append(f"四个暂留件收口自检未通过：设置页的「界面大小」档位没画出来"
                          f"（实测 {n} 个档位按钮 · 选中档 {got0['cur']}）")
            print(f"  ⛔ ⑳ 界面大小：档位没画出来（实测 {n} 个）")
    except Exception as exc:                              # noqa: BLE001
        errors.append(f"四个暂留件收口自检异常（界面大小）：{type(exc).__name__}: {str(exc)[:120]}")
        print(f"  ⛔ ⑳ 界面大小：{type(exc).__name__}: {str(exc)[:120]}")


def _check_moved(page, errors: list[str]) -> None:
    """⭐ `TAIL-127`（2026-09-27 · 用户裁定 **B**）：连接参数**搬家后的两个入口**是否真的能用。

    用户原话：「连接参数这个板块说实话可以删掉，因为**不可能有变动**；那系统设置就只剩下主题色了」
    ⇒ 三个参数各自搬回**它起作用的地方**（守则 §5.8「换地方，不是删掉」）：
      · `i8 服务地址`       → 「i8 接入层」（`m02`）卡头的「**i8 连接设置**」（`BIND.m02` 注入）
      · 两个**打印版式 ID** → 「付款通知书」（`m03`）的「**打印机设置**」弹窗（`print-export.js`）

    ⚠️ **为什么这一条必须真机**：`V.set` 那一页现在已经**没有输入框**了 ⇒
       光看源码**证不到"能力还在"**（符号还在、入口没画出来 = 用户找不到）。
       ⭐ 判词里带上「**与直觉相反**」是有意的：那句是**配错版式的唯一提示**，
         它必须**在版式那一格旁边**出现（原先它在系统设置页，搬家后就跟过去）。
    """
    ok1 = ok2 = False
    try:
        page.click('[data-k="m02"]')
        page.wait_for_selector('#view [data-act="i8SetOpen"]', timeout=8000)
        page.click('[data-act="i8SetOpen"]')
        page.wait_for_selector('#m02I8Url', timeout=8000)
        got = page.evaluate("""() => ({
            has: !!document.querySelector('#m02I8Url'),
            txt: document.body.innerText || '',
        })""")
        ok1 = bool(got["has"]) and ("i8" in got["txt"])
        print(("  ✅ " if ok1 else "  ⛔ ")
              + "⑳ i8 服务地址**搬到「i8 接入层」页**了：卡头按钮 ⇒ 弹窗里有那一格（`#m02I8Url`）")
        if not ok1:
            errors.append("四个暂留件收口自检未通过：`m02` 的「i8 连接设置」入口/弹窗没出来"
                          "（连接参数搬家的这一半丢了 ⇒ 用户再也改不了 i8 地址）")
        page.click('[data-act="closeModal"]')
    except Exception as exc:                              # noqa: BLE001
        errors.append(f"四个暂留件收口自检异常（m02 的 i8 连接设置入口）：{type(exc).__name__}: "
                      f"{str(exc)[:120]}")
        print(f"  ⛔ ⑳ m02 i8 连接设置入口：{type(exc).__name__}: {str(exc)[:120]}")

    try:
        page.click('[data-k="m03"]')
        page.wait_for_selector('#view [data-act="m03PrinterOpen"]', timeout=8000)
        page.click('[data-act="m03PrinterOpen"]')
        page.wait_for_selector('#m03PidMat', timeout=8000)
        d = page.evaluate("""() => ({
            a: !!document.querySelector('#m03PidMat'),
            b: !!document.querySelector('#m03PidMech'),
            t: document.body.innerText || '',
        })""")
        need = ("其他支出", "付款通知书", "与直觉相反")
        ok2 = bool(d["a"]) and bool(d["b"]) and all(x in d["t"] for x in need)
        print(("  ✅ " if ok2 else "  ⛔ ")
              + "⑳ 两个**打印版式 ID 搬到打印机弹窗**了：两格在（`#m03PidMat`/`#m03PidMech`）"
              + "＋ 反直觉提示原样在（「与直觉相反 / 其他支出 / 付款通知书」）")
        if not ok2:
            errors.append("四个暂留件收口自检未通过：打印机弹窗里没看到「打印版式」两格"
                          f"（或反直觉提示丢了）—— 实测 {d}")
        page.click('[data-act="closeModal"]')
    except Exception as exc:                              # noqa: BLE001
        errors.append(f"四个暂留件收口自检异常（打印机弹窗里的打印版式）：{type(exc).__name__}: "
                      f"{str(exc)[:120]}")
        print(f"  ⛔ ⑳ m03 打印版式两格：{type(exc).__name__}: {str(exc)[:120]}")
