# -*- coding: utf-8 -*-
"""给 `ACC-USR-MGMT-001` 加点 —— `§7.8`「i8 账号与密码**绑定到本系统账号、每人一份**」（2026-09-21）。

⭐ 为什么必须新建一条（`T7` 那类缺口）：
   `test_acc_usr_i8.py` 的断言**暂时挂在 `001-11`** 上，而 `001-11` 的判词是
   「**「当前登录用户」的供给**：留痕的改前人与录入人一律取当前登录用户，不得写死成某个名字」——
   那是**留痕的人名**，i8 凭据只是它的一个 consumer ⇒ 两件事，判词对不上。
   ⚠️ 本仓的老毛病正是「同一件事横跨三处，每处都以为别人测过了」⇒ 点**自己的判词**得说清这件事。

⚠️ **这是"加点"，不是"新增用例"** ⇒ 按纪律**只动 `验收基线.json` 一处**：
   `用例索引.md` / `MOD-15.md` / `05-任务分解.md` 那三处是**用例级**的，加点不改它们。
⚠️ 改 JSON 的三个细节（本仓实测过）：① 走**结构操作**；② **本文件结尾没有换行** ⇒
   写入时**不许**多写一个 `\\n`；③ ⭐⭐ **本文件是 CRLF**（2026-09-21 实测）——
   而 `json.dumps` 出的是 **LF** ⇒ 直接 `write_bytes(dumps(...))` 会把**整份文件的行尾**换掉
   （"只加了一条判据点"变成"整个文件都改了"，`shutil` 备份与任何 diff 都失去意义）。
   ⇒ **先量原文件的 EOL，再按它写回**（本脚本下面的 `eol` 就是这么来的）。
   ⚠️ 本仓既有那份 `_acc_add_prj_type.py` 的注释只写了前两条（当时那份文件应是 LF）——
   照抄它在这份 CRLF 文件上会**当场被往返自检拦住**（这道闸正是为此存在的）。

跑法（工程根）：`backend\\.venv\\Scripts\\python.exe tools\\_acc_add_i8bind.py`
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "audit"))  # ⭐ `TAIL-58` 分目录
from acc_report import resolve_baseline  # noqa: E402

CASE = "ACC-USR-MGMT-001"

NEW_POINTS = [
    {
        "id": "001-13",
        "kind": "outcome",
        "cover": "§7.8",
        "claim": (
            "**i8 的账号与密码绑定到本系统账号、每人一份**：凭据**按当前登录用户**取"
            "（唯一出口 `core/identity.current_i8_credentials`），⛔ 不共享 `.env` 那一个身份"
            "（拿错账号 = **顶了别人的号去抓数**）；① 绑了 ⇒ 用绑的；"
            "② 查无此人 / 未登录的路径 ⇒ 回落 `.env`（**过渡期口径**：定时抓取 / 命令行 / 测试进程都走这里）；"
            "③ ⭐ **账号绑了但密码为空 ⇒ 密码就是空，⛔ 不回落**"
            "（否则成了「甲的账号配乙的密码」那种**静默错配** —— i8 只会说「账号或密码错」，没人看得出是混搭）；"
            "④ 列表出参**只出账号名、不出密码**（要看密码走单独动作、且**指名要哪一个**，"
            "⛔ 不提供「列出全部密码」）"
        ),
    },
]


def main() -> int:
    path = resolve_baseline(None)
    raw = path.read_bytes()
    data = json.loads(raw.decode("utf-8"))

    # ⭐ 按原文件的 EOL 写回（见文件头第 ③ 条：本文件是 CRLF，⛔ 别用 `json.dumps` 的 LF 覆盖掉）
    eol = "\r\n" if b"\r\n" in raw else "\n"

    def dump(obj) -> bytes:
        return json.dumps(obj, ensure_ascii=False, indent=2).replace("\n", eol).encode("utf-8")

    if dump(data) != raw:
        print("⛔ 往返**不是**逐字节一致 —— 先别改（EOL 与结尾换行都要对上）")
        return 1

    case = data["cases"][CASE]
    have = {p["id"] for p in case["points"]}
    added = []
    for p in NEW_POINTS:
        if p["id"] in have:
            print(f"· {p['id']} 已在，跳过")
            continue
        case["points"].append(p)
        added.append(p["id"])

    data["asof"] = date.today().isoformat()          # ⚠️ 项目当前时点 = 2026-09-21

    bak = path.with_name(f"_backup-acc_i8bind-{date.today().strftime('%Y%m%d-%H%M')}.json")
    shutil.copy2(path, bak)
    path.write_bytes(dump(data))

    after = json.loads(path.read_bytes().decode("utf-8"))
    total = sum(len(c["points"]) for c in after["cases"].values())
    print(f"✅ {CASE}：{len(case['points'])} 点（新增 {added or '无'}）· asof={data['asof']}")
    print(f"   全库判据点合计 = {total}")
    print(f"   备份 = {bak.name}")
    print(f"   复核：条数 {len(after['cases'][CASE]['points'])} · 结尾无多余换行 = "
          f"{not path.read_bytes().endswith(b'\n')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
