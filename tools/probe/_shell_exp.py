"""壳真机自检 · **第 ⑬ 段：`m07` 导出（材料报表）**（`TAIL-04` · 2026-09-21 外移）。

**为什么单独立一个文件**：`tools/probe/_shell_smoke.py` 有 **400 行即黄**（`doc_audit` 的 `T5`）；⚠️ 连 `>600` 也只是**黄** —— `[用户·2026-09-21]` 把"红·禁合入"**降级**，只须在 `docs/reference/thresholds.md` 登记"为什么不拆"
⇒ 与 `_shell_pend.py` / `_shell_arch.py` 同款，由主自检**调一段**（`check(page, errors)`）。

**它验的链条**（⭐ 可观测证据 = **从页面上下文真拉一次 zip**，⛔ 不是"看页面上有没有按钮"）：
  ① **默认月**：材料报表默认 = **上月** —— 而"上月有没有数据"是**数据状态**、不是代码保证
     ⇒ 断言**必须两态**：有数据 ⇒ 真 zip（`PK` 开头 ＋ 内容非空）；没数据 ⇒ **中文原因**＋`ok=False`。
     ⚠️ 2026-09-18 实测踩过这个坑：只写"没数据 ⇒ 回中文原因"那一态，默认月**真有了数据**时**误报红**。
  ② **有数据的月份**（近 4 个月里挑一个）⇒ 真拿到 `application/zip`、内容以 `PK` 开头、
     且**文件名由后端带出**（`x-export-filename` 响应头）并**含那个月份**。
"""

from __future__ import annotations


def check(page, errors: list[str]) -> None:
    """⑬ 真机走一遍：**默认月两态 ＋ 有数据的月真 zip**。"""

    # ⚠️ 默认月那一条**必须是两态断言**（2026-09-18 实测踩到 · 假红）：
    #    材料报表的默认月 = **上月**，而"上月到底有没有数据"是**数据状态**、不是代码保证
    #    ⇒ 若只写"没数据 ⇒ 回中文原因"那一态，则默认月**真有了数据**时这条会**误报红**
    #    （实测：2026-08 有 8 个仓、198 KB 的真 zip ⇒ `d.json` 为空 ⇒ 旧断言直接判红 ✗）。
    def _def_month_ok(x: dict) -> bool:
        if x.get("json"):                      # 没数据 ⇒ 必须是**中文原因**（⛔ 不是崩）
            return bool(x.get("ok") is False and (x.get("message") or "").strip())
        return (x.get("ct") == "application/zip"   # 有数据 ⇒ 必须是**真 zip**
                and x.get("magic") == "PK" and x.get("size", 0) > 0)

    # ---- m07 导出（`TAIL-04`）：⭐ 可观测证据 = **从页面上下文真拉一次 zip**。
    #      ⚠️ 两件事分开验（都是真事实）：
    #        ① **默认月没数据**时（材料报表默认 = 上月，而真机数据可能落在别的月）
    #           ⇒ 必须回**中文原因**、⛔ 不能崩、不能产出空文件；
    #        ② 换到**有数据的月份** ⇒ 必须真拿到 zip，且文件名含**那个月份**。
    exp = page.evaluate("""async () => {
        const label = p => { const [y, m] = p.split('-'); return Number(y) + '年' + Number(m) + '月'; };
        const grab = async p => {
            const r = await fetch('/api/m07/settlement/export?period=' + encodeURIComponent(p));
            const ct = r.headers.get('content-type') || '';
            if (ct.includes('application/json')) {
                const d = await r.json();
                return { period: p, json: true, ct: ct, ok: d.ok, message: (d.message || '').slice(0, 90) };
            }
            const b = await r.blob();
            const u8 = new Uint8Array(await b.slice(0, 2).arrayBuffer());
            return { period: p, ct: ct, label: label(p),
                     fn: decodeURIComponent(r.headers.get('x-export-filename') || ''),
                     size: b.size, magic: String.fromCharCode(u8[0], u8[1]),
                     warehouses: pjSort(whRows(p)).length };
        };
        const def = await grab(fWhYm);                 /* ① 默认月（可能就是没数据的那个月） */
        const cands = [];
        for (let i = 0; i <= 3; i++) {
            const d = new Date(); d.setDate(1); d.setMonth(d.getMonth() - i);
            cands.push(d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0'));
        }
        let hit = null;
        for (const p of cands) {
            const r = await grab(p);
            if (!r.json) { hit = r; break; }
        }
        return { def: def, hit: hit, tried: cands };
    }""")
    print("⑬ 导出（TAIL-04）= 默认月：", exp.get("def"))
    print("                 有数据的月：", exp.get("hit"))
    d, h = exp.get("def") or {}, exp.get("hit") or {}
    oks11 = [
        (
            _def_month_ok(d),
            "① 默认月（{}）**要么**回中文原因（那个月没数据）、**要么**给真 zip（有数据）"
            "—— 唯独不许是崩 / 空壳 ⇒ 实测：{}".format(
                d.get("period"),
                (f"真 zip {d.get('size')} B · {d.get('warehouses')} 仓")
                if not d.get("json")
                else f"中文原因「{(d.get('message') or '')[:36]}」",
            ),
        ),
        (bool(h), f"② 近 4 个月里至少有一个月导得出（试过 {exp.get('tried')}）"),
        (bool(h) and h.get("ct") == "application/zip",
         f"② content-type = application/zip（{h.get('ct')}）"),
        (bool(h) and h.get("magic") == "PK",
         "② 内容以 `PK` 开头 ⇒ **真的是 zip**（不是空壳 / 错误页）"),
        (bool(h) and h.get("label") in (h.get("fn") or ""),
         f"⭐ 文件名由后端带出、且含**该月份**：{h.get('fn')}"),
        (bool(h) and h.get("size", 0) > 20000,
         f"② 大小 {h.get('size')} B（应含 {h.get('warehouses')} 个分仓库表 ＋ 总表）"),
    ]
    for ok, what in oks11:
        print(("  ✅ " if ok else "  ⛔ ") + what)
        if not ok:
            errors.append("TAIL-04 导出自检未通过：" + what)
