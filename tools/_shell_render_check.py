"""前端壳**渲染链路自检**：在页面内注入样本行（**只活在浏览器内存里、不落库**），
核验 `m03` 在"有数据"时的结构 —— 表头 / 合计行 / 勾选禁用 / 剔除分档。

⚠️ 它**不是**验收判据（判据在 `backend/tests/test_*.py`）—— 它守的是
   "前端壳接上数据后，原型那套结构还在不在"，属工程自检。
"""

from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"

# 样本：1 正常 + 1 已付清 + 1 剔除 + 1 手动行
# ⚠️ 必须走 **`adaptNotice`**（模拟 API 载荷）—— 手写原型格式会绕过适配层，
#    测出来的东西与真实链路不同（实测：手写数字 id ⇒ 勾选静默失效，误判成壳有 bug）。
SEED = """() => {
  const mk = o => adaptNotice(Object.assign({
    notice_id:0, doc_date:'2026-09-05', bill_no:'', project_display:'甲项目',
    project_name:'甲项目', bill_name:'', biz_type:'付材料采购款', payee:'某供应商',
    input_by:'科室用户', category:'辅材', category_label:'辅材', approve_status:'已审批',
    amount_approved:'0', pay_amount:'0', amount_paid:'0', stat_settle:'0', stat_paid:'0',
    is_excluded:false, exclude_source:'none', is_revoked:false, is_manual:false,
    edited_fields:[], jc_supplier:'', has_effective_flow:false, has_link:false,
    ownership_id:1,
  }, o));
  NO = [
    mk({ notice_id:1, bill_no:'FKTZ-A', amount_approved:'10000', pay_amount:'10000',
         stat_settle:'10000', stat_paid:'0' }),
    mk({ notice_id:2, bill_no:'FKTZ-B', amount_approved:'5000', pay_amount:'0',
         stat_settle:'5000', stat_paid:'5000', amount_paid:'5000' }),
    mk({ notice_id:3, bill_no:'FKTZ-C', amount_approved:'3000', pay_amount:'3000',
         stat_settle:'3000', stat_paid:'0', is_excluded:true, exclude_source:'manual' }),
    mk({ notice_id:4, bill_no:'手工-001', amount_approved:'2000', pay_amount:'2000',
         stat_settle:'0', stat_paid:'2000', is_manual:true }),
  ];
  render();
}"""


def main() -> int:
    errs: list[str] = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(BASE + "/app", wait_until="networkidle", timeout=45000)
        pg.click('[data-k="m03"]')
        pg.wait_for_timeout(400)
        pg.evaluate(SEED)
        pg.wait_for_timeout(400)

        d = pg.evaluate("""() => {
          const rows=[...document.querySelectorAll('#view tbody tr')];
          const dataRows=rows.filter(r=>!r.classList.contains('sum')&&!r.classList.contains('sumrow'));
          const sum=document.querySelector('#view tr.sumrow');
          const cbs=[...document.querySelectorAll('#view tbody input.chk')];
          return {
            dataRows: dataRows.length,
            sumText: sum ? sum.innerText.replace(/\\s+/g,' ').trim().slice(0,90) : '(无合计行)',
            sumCols: sum ? sum.children.length : 0,
            disabled: cbs.filter(c=>c.disabled).length,
            enabled: cbs.filter(c=>!c.disabled).length,
            picked: document.querySelectorAll('#view tbody tr.pick').length,
            selbar: (document.querySelector('#view .selbar')||{}).innerText||'',
            detail: rows.map(r=>({cls:r.className||'(无)',
                                  code:(r.children[2]||{}).textContent||'',
                                  chk:!!r.querySelector('input.chk')})),
            pickSetSize: pickSet.size,
          };
        }""")
        print("数据行数 =", d["dataRows"], "（样本 4：正常 / 已付清 / 剔除 / 手动）")
        print("勾选框 = 可用", d["enabled"], "· 禁用", d["disabled"], "（剔除行应被禁用）")
        print("合计行 =", d["sumText"], f"· 列数 {d['sumCols']}")
        print("汇总条 =", d["selbar"].replace("\n", " ")[:90])
        print("逐行明细（class | 单据号 | 有勾选框）:")
        for r in d["detail"]:
            print(f"   {r['cls']:<28} {r['code']:<12} {r['chk']}")

        # 勾选联动：点第一行 → 汇总条金额应实时变
        pg.click('#view tbody tr:first-child input.chk')
        pg.wait_for_timeout(300)
        after = pg.evaluate("document.querySelector('#view .selbar').innerText.replace(/\\n/g,' ')")
        print("勾选 1 行后汇总条 =", after[:90])

        # 写链路：勾选 → 「批量剔除」应真的 POST 到后端（样本 id 不在库里 ⇒ 后端的回执是 no-op，正常）
        with pg.expect_response(lambda r: "/api/m03/actions/exclude" in r.url) as got:
            pg.evaluate("async () => { pickSet.add('1'); await ACT.batchEx(); }")
        resp = got.value
        print(f"⑤ 写接口 → HTTP {resp.status} · {resp.text()[:130]}")
        b.close()

    if errs:
        print("\n❌ page errors:")
        for e in errs[:10]:
            print("  ", e)
        return 1
    print("\n（无 page error）✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
