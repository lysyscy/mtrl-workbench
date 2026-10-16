"""真机验证 · 链路 C「补词 → 去重追加」真的落库（写 → 回读 → **复原**）。

用法：先起服务，再 `python tools/probe/_e2e_own_assign.py`。
⚠️ 不替用户做业务判断：只用**单据名里确实出现的一个片段**当临时词，
   验证完**把关键词复原成原值**（`set_keywords` 不留痕 ⇒ 可逆）。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
import app.models_registry  # noqa: E402, F401

import httpx  # noqa: E402

from app.core.db import session_scope  # noqa: E402
from app.mod01_projects.models import Project  # noqa: E402
from app.mod01_projects.repository import set_keywords  # noqa: E402

BASE = "http://127.0.0.1:8000"
fails: list[str] = []


def check(ok: bool, what: str, extra: str = "") -> None:
    print(("  ✅ " if ok else "  ⛔ ") + what + (f" —— {extra}" if extra else ""))
    if not ok:
        fails.append(what)


def keywords_of(project_id: int) -> list[str]:
    """读取一个项目的关键词原值。"""
    with session_scope() as s:
        row = s.get(Project, project_id)
        if row is None:
            raise RuntimeError(f"项目档案 {project_id} 不存在")
        return list(row.match_keywords or [])


def restore_keywords_if_owned(project_id: int, *, baseline: list[str], expected: list[str]) -> bool:
    """只恢复仍保持本次追加结果的关键词；并发改动时停止，不覆盖。"""
    from sqlalchemy import select

    with session_scope() as s:
        row = s.execute(
            select(Project).where(Project.id == project_id).with_for_update()
        ).scalars().first()
        if row is None:
            raise RuntimeError(f"项目档案 {project_id} 不存在，无法恢复")
        current = list(row.match_keywords or [])
        if current == baseline:
            return False
        if current != expected:
            raise RuntimeError(f"项目 {project_id} 的关键词已被其他值改动，停止恢复以免覆盖")
        set_keywords(s, row, baseline)
    if keywords_of(project_id) != baseline:
        raise RuntimeError(f"项目 {project_id} 的关键词恢复后仍未回到基线")
    return True


def main() -> int:
    c = httpx.Client(base_url=BASE, timeout=30.0)
    items = c.get("/api/m03/notices/unresolved").json().get("items", [])
    check(len(items) > 0, "清单端点返回了未命中条目", f"{len(items)} 条")
    hit = next((x for x in items if x.get("candidates")), None)
    if hit is None:
        print("  （没有带候选小微的条目 —— 跳过写验证）")
        return 0

    doc, small = hit["doc_name"], hit["candidates"][0]
    sid = small["id"]
    print(f"  （用：单据名「{doc}」· 小微 id={sid}「{small['disp']}」）")

    with session_scope() as s:
        before = list(s.get(Project, sid).match_keywords or [])
    print(f"  补词前 · 小微 {sid} 的关键词 = {before}")
    canonical = []
    for word in before:
        word = (word or "").strip()
        if word and word not in canonical:
            canonical.append(word)
    if before != canonical:
        check(False, "目标关键词含空白或重复，停止写入以免规范化改变原值")
        return 1

    # ① 词**不在单据名里** ⇒ 必须被拒，且**不落库**
    bad_response = c.post("/api/m03/notices/ownership-assign",
                          json={"doc_name": doc, "keyword": "__绝不在单据名里的词__", "small_id": sid})
    check(bad_response.status_code == 200, "非法词请求正常返回业务拒绝")
    bad = bad_response.json()
    check(bad.get("ok") is False, "词不在单据名里 ⇒ 被拒", str(bad.get("message"))[:60])
    with session_scope() as s:
        check(list(s.get(Project, sid).match_keywords or []) == before, "被拒之后**档案没被动过**")

    # ② 单据名里**确实存在**的片段 ⇒ 成功追加
    kw = doc[:2]
    expected = list(before)
    if kw not in expected:
        expected.append(kw)
    if keywords_of(sid) != before:
        check(False, "写入前关键词仍保持基线")
        return 1
    try:
        resp = c.post("/api/m03/notices/ownership-assign",
                      json={"doc_name": doc, "keyword": kw, "small_id": sid})
        ok = resp.json()
        check(resp.status_code == 200, "补词请求正常返回")
        check(ok.get("ok") is True, "补上单据名里存在的词 ⇒ 成功", str(ok.get("message"))[:60])
        after = keywords_of(sid)
        check(kw in after, "关键词**已落库**", f"{after}")

        # ③ 同一词再补一次 ⇒ 去重（只留一份）
        repeated = c.post("/api/m03/notices/ownership-assign",
                          json={"doc_name": doc, "keyword": kw, "small_id": sid})
        check(repeated.status_code == 200 and repeated.json().get("ok") is True,
              "重复补词请求成功")
        dup = keywords_of(sid)
        check(dup.count(kw) == 1, "重复补同一个词 ⇒ **去重**", f"{dup}")
    finally:
        try:
            restored = restore_keywords_if_owned(sid, baseline=before, expected=expected)
            check(restored or expected == before, "已**复原**（不留验证痕迹）")
        except Exception as exc:  # noqa: BLE001
            check(False, "已**复原**（不留验证痕迹）", str(exc))

    print("\n结论：" + ("✅ 全通（补词链路真的落库、且可逆）" if not fails else f"⛔ {len(fails)} 项未过"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
