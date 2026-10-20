"""2026-09-21 用户裁定（mod01 小微壳置底 · 交互统一像集采 · **m08 抓取导出分开** · 删 m02 接口清单）的判据。

⭐ 为什么钉源码形态：这四件的**本体就是交互形态**（弹窗 / 反馈 / 排序 / 入口存在性），
   "统一像集采台账"这类口径只有把**形态**钉住才不会回退。⛔ 全部读 `shell_source`（切片外不改判 U1）。
"""
from __future__ import annotations

from types import SimpleNamespace

from app.mod01_projects.domain import ordered
from tests.shell_src import SHELL, dl_kernel, parts_text

ROOT_BACKEND = __import__('pathlib').Path(__file__).resolve().parents[1]


def _shell_and_core() -> str:
    return "\n".join(t for _, t in parts_text())


def test_mod01_小微壳默认置底_归档仍在最底():
    """用户 2026-09-21：「小微壳改为默认置底」⇒ 顺序 = **归档最底 > 小微壳 > 普通项目**（各段内按 ord）。"""
    P = lambda **kw: SimpleNamespace(status=kw.get("status", "active"),
                                     project_type=kw.get("project_type", "normal"), ord=kw.get("ord", 0))
    rows = [P(ord=1), P(project_type="shell", ord=2), P(ord=3), P(status="archived", ord=0),
            P(status="archived", project_type="shell", ord=9)]
    got = [p.project_type + (":arch" if p.status == "archived" else "") for p in ordered(rows)]
    assert got == ["normal", "normal", "shell", "normal:arch", "shell:arch"], got


def test_抓取结果一律弹窗_不再是提示条():
    """⭐ 用户口径「统一像集采台账」：nt / wh / iv 三条抓取的结果**必须弹窗**（集采本就是弹窗）。"""
    src = _shell_and_core()
    # ⚠️ 2026-09-27（守则 §3.1 · `TAIL-117` 批次 2）：标题里的接口代号「（API-0x）」**已撤出可见文案**
    #    （用户看的是「抓取结果 · 付款通知书」，代号只在排障处留痕）⇒ 本判据的 token 同步去码。
    for token in ("抓取结果 · 付款通知书", "抓取结果 · 收发结存",
                  "抓取结果 · 库存单据明细", "抓取被拒 · 付款通知书",
                  "抓取没能完成 · 收发结存", "抓取没能完成 · 库存单据明细"):
        assert f"fetchResultModal(`{token}`" in src, f"缺结果弹窗：{token}"
    assert "function fetchResultModal" in src


def test_导出点击即有反馈_不再让人以为没点住():
    """`dlExport` 一进来就给「正在准备文件」的反馈（导出是重动作，几秒很正常）。"""
    assert "正在从服务器准备文件" in dl_kernel()


def test_m08导出_走最近一次抓取的缓存_不碰i8():
    """⭐ 用户裁定「**抓取导出分开**」（与 m07 同一套心智）：

    - 壳：`expPivot` 直接走 `dlExport`（⛔ 不再有二次确认 / `allow_kick` —— 导出不碰 i8）；
    - 后端：`export_inventory` 读**源文件缓存**（`source_cache.load`），现导包装 `_fetch_inventory_bytes` 已删；
    - 抓取侧：`run_fetch` 把源文件**按月存档**（`source_cache.save`）。
    """
    acts = (ROOT_BACKEND / "app" / "web" / "shell" / "actions.js").read_text(encoding="utf-8", errors="replace")
    assert "expPivotOk" not in acts, "确认流应已撤销（导出不碰 i8 ⇒ 不需要）"
    blk = acts[acts.find(" expPivot:async"):]
    blk = blk[:blk.find("',6400); },")]
    code = "\n".join(l.split("#", 1)[0] for l in blk.splitlines())   # ⛔ 去注释再断言（注释里会"说"这个词）
    assert "dlExport" in code and "allow_kick" not in code and "最近一次抓取" in code
    svc = (ROOT_BACKEND / "app" / "report_export" / "service.py").read_text(encoding="utf-8", errors="replace")
    assert 'source_cache.load("inv", ym)' in svc, "导出必须读源文件缓存"
    assert "_fetch_inventory_bytes" not in svc and "allow_kick" not in svc, "现导包装必须已删"
    fs = (ROOT_BACKEND / "app" / "mod08_inv" / "fetch_service.py").read_text(encoding="utf-8", errors="replace")
    assert "source_cache.save(SPEC_KEY" in fs, "抓取时必须存档源文件"


def test_源文件缓存_存取往返与未命中(monkeypatch, tmp_path):
    import app.mod02_i8.source_cache as SC
    monkeypatch.setattr(SC, "DIR", tmp_path)
    assert SC.load("inv", "2026-09") is None                  # 未命中 ⇒ None（调用方显式报"请先抓取"）
    SC.save("inv", "2026-09", b"PK\x03\x04fake")
    assert SC.load("inv", "2026-09") == b"PK\x03\x04fake"     # 命中
    SC.save("inv", "2026-09", b"PK\x03\x04new")               # 同月再抓 ⇒ 覆盖（幂等）
    assert SC.load("inv", "2026-09") == b"PK\x03\x04new"


def test_m02_接口清单已删_正式壳没有():
    """用户裁定：接口清单删除 —— 每个接口在系统里都有自己的位置（抓取在各页 · 同步在 m01）。"""
    assert "数据接口清单" not in SHELL, "正式壳里还留着接口清单"
