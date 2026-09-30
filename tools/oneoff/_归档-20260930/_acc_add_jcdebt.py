"""一次性件（`TAIL-100` · 2026-09-25）：给 `ACC-FLOW-DEBT-001` 补 **`001-07`**「注入方真的存在」。

**为什么**：`001-03` 只钉了**域内核**（「集采值由 `jc_debt` 参数给」）—— 而"**谁给**"没人管。
实测后果：`build_debt(s)` 在生产**两个调用点**都不传 `jc_debt` ⇒ 看板 / 欠款页的「集采欠款」
**恒 ¥0.00**（真值 7444 万级，页面完全看不出来）。⇒ 这不是"实现 bug"一条，是**判据缺一格**。

⚠️ 改 `.json` 一律**结构操作**（`json.loads` → 改 dict → `json.dumps`），**先 round-trip 验证序列化参数**。
⭐ 已实测该文件的参数 = `indent=1` · `ensure_ascii=False` · **CRLF** · **末尾一个 CRLF**。

用法：
  `backend/.venv/Scripts/python.exe tools/oneoff/_acc_add_jcdebt.py`          # 只报不写
  `backend/.venv/Scripts/python.exe tools/oneoff/_acc_add_jcdebt.py --apply`  # 真写
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = Path(r"D:\工作\AI\PRD编写夹 - Workbuddy专用\PRD\验收\验收基线.json")
BACKUPS = ROOT / ".workbuddy" / "backups"
CASE = "ACC-FLOW-DEBT-001"
NEW = {
    "id": "001-07",
    "kind": "outcome",
    "claim": ("⭐ 「集采欠款由外部注入」这件事，**注入方真的存在**：装配层（`build_debt_live`）在不给 "
              "`jc_debt` 时必须**现取**集采台账里「纳入台账」合同的 Σ欠款，且看板端点与手改统计金额的回执"
              "**都走它** ⇒ ⛔ 不得让「集采」那一格恒 ¥0.00"),
    "cover": "§4.5.1 · §6.4.4",
}


def dumps(data: dict) -> str:
    return json.dumps(data, indent=1, ensure_ascii=False).replace("\n", "\r\n") + "\r\n"


def main() -> int:
    apply = "--apply" in sys.argv
    raw = BASE.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    assert dumps(data).encode("utf-8") == raw, "round-trip 不一致 ⇒ ⛔ 序列化参数变了，先复核"

    pts = data["cases"][CASE]["points"]
    ids = [p["id"] for p in pts]
    assert "001-07" not in ids, "001-07 已经在册（幂等）"
    assert ids == [f"001-{i:02d}" for i in range(1, len(ids) + 1)], f"编号不是顺延的：{ids}"

    total_before = sum(len(c.get("points") or []) for c in data["cases"].values())
    pts.append(NEW)
    data["asof"] = date.today().isoformat()
    total_after = sum(len(c.get("points") or []) for c in data["cases"].values())

    print("=" * 78)
    print(("  写入" if apply else "  DRY-RUN（只报不写）") + f" ·  {CASE} 补 {NEW['id']}")
    print("=" * 78)
    print(f"  {CASE} 点位：{len(ids)} ⇒ {len(pts)}")
    print(f"  全库判据点合计：{total_before} ⇒ {total_after}")
    print(f"  asof ⇒ {data['asof']}")
    if not apply:
        print("\n  （加 --apply 才真写；改前自动备份到 .workbuddy/backups/。）")
        return 0

    BACKUPS.mkdir(parents=True, exist_ok=True)
    bak = BACKUPS / f"face-{datetime.now():%Y%m%d-%H%M%S}-验收基线.json"
    shutil.copy2(BASE, bak)
    BASE.write_bytes(dumps(data).encode("utf-8"))
    after = json.loads(BASE.read_bytes().decode("utf-8"))
    print(f"\n  ✅ 已写盘（备份 {bak.name}）· 复核：{CASE} = {len(after['cases'][CASE]['points'])} 点 · "
          f"全库 = {sum(len(c.get('points') or []) for c in after['cases'].values())}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
