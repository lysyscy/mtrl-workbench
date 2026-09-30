"""真机验证 · 链路 C「补词 → 去重追加」真的落库（写 → 回读 → **复原**）。

用法：先起服务，再 `python tools/_e2e_own_assign.py`。
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

    # ① 词**不在单据名里** ⇒ 必须被拒，且**不落库**
    bad = c.post("/api/m03/notices/ownership-assign",
                 json={"doc_name": doc, "keyword": "__绝不在单据名里的词__", "small_id": sid}).json()
    check(bad.get("ok") is False, "词不在单据名里 ⇒ 被拒", str(bad.get("message"))[:60])
    with session_scope() as s:
        check(list(s.get(Project, sid).match_keywords or []) == before, "被拒之后**档案没被动过**")

    # ② 单据名里**确实存在**的片段 ⇒ 成功追加
    kw = doc[:2]
    ok = c.post("/api/m03/notices/ownership-assign",
                json={"doc_name": doc, "keyword": kw, "small_id": sid}).json()
    check(ok.get("ok") is True, "补上单据名里存在的词 ⇒ 成功", str(ok.get("message"))[:60])
    with session_scope() as s:
        after = list(s.get(Project, sid).match_keywords or [])
    check(kw in after, "关键词**已落库**", f"{after}")

    # ③ 同一词再补一次 ⇒ 去重（只留一份）
    c.post("/api/m03/notices/ownership-assign",
           json={"doc_name": doc, "keyword": kw, "small_id": sid})
    with session_scope() as s:
        dup = list(s.get(Project, sid).match_keywords or [])
    check(dup.count(kw) == 1, "重复补同一个词 ⇒ **去重**", f"{dup}")

    # ④ 复原
    with session_scope() as s:
        set_keywords(s, s.get(Project, sid), before)
    with session_scope() as s:
        check(list(s.get(Project, sid).match_keywords or []) == before, "已**复原**（不留验证痕迹）")

    print("\n结论：" + ("✅ 全通（补词链路真的落库、且可逆）" if not fails else f"⛔ {len(fails)} 项未过"))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
