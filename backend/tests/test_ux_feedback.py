"""2026-09-21 用户裁定（mod01 小微壳置底 · 交互统一像集采 · **m08 抓取导出分开** · 删 m02 接口清单）的判据。

⭐ 为什么钉源码形态：这四件的**本体就是交互形态**（弹窗 / 反馈 / 排序 / 入口存在性），
   "统一像集采台账"这类口径只有把**形态**钉住才不会回退。⛔ 全部读 `shell_source`（切片外不改判 U1）。
"""
from __future__ import annotations

from types import SimpleNamespace

from app.mod01_projects.domain import ordered

ROOT_BACKEND = __import__('pathlib').Path(__file__).resolve().parents[1]




def test_mod01_小微壳默认置底_归档仍在最底():
    """用户 2026-09-21：「小微壳改为默认置底」⇒ 顺序 = **归档最底 > 小微壳 > 普通项目**（各段内按 ord）。"""
    P = lambda **kw: SimpleNamespace(status=kw.get("status", "active"),
                                     project_type=kw.get("project_type", "normal"), ord=kw.get("ord", 0))
    rows = [P(ord=1), P(project_type="shell", ord=2), P(ord=3), P(status="archived", ord=0),
            P(status="archived", project_type="shell", ord=9)]
    got = [p.project_type + (":arch" if p.status == "archived" else "") for p in ordered(rows)]
    assert got == ["normal", "normal", "shell", "normal:arch", "shell:arch"], got








def test_源文件缓存_存取往返与未命中(monkeypatch, tmp_path):
    import app.mod02_i8.source_cache as SC
    monkeypatch.setattr(SC, "DIR", tmp_path)
    assert SC.load("inv", "2026-09") is None                  # 未命中 ⇒ None（调用方显式报"请先抓取"）
    SC.save("inv", "2026-09", b"PK\x03\x04fake")
    assert SC.load("inv", "2026-09") == b"PK\x03\x04fake"     # 命中
    SC.save("inv", "2026-09", b"PK\x03\x04new")               # 同月再抓 ⇒ 覆盖（幂等）
    assert SC.load("inv", "2026-09") == b"PK\x03\x04new"
