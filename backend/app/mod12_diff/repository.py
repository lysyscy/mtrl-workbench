"""`MOD-12` 差异登记的**读写**（薄层：判定在 `domain`，本层只管库）。

⚠️ 三个出口各司其职（判据点 `001-01` / `001-02` / `001-06`）：
   · `list_records` —— **这是本页数据的唯一来源**；⛔ 本模块**没有**其它写入函数
     （"不由库存单据 / 过程资料自动生成行"这条口径，就靠**没有那条路**来保证）；
   · `create_record` —— 由 `domain.validate` 过了才进来，**编号取 `max(seq)+1`**；
   · `delete_record` —— **只删该行**（`001-06`：其余行一行不动）。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mod12_diff.domain import code_of, next_seq, to_record
from app.mod12_diff.models import DiffRecord


def list_records(session: Session) -> list[DiffRecord]:
    """全部差异行（**全量，不筛**）—— 本页数据的唯一出口。

    ⚠️ **筛选交给壳**（与 `/api/m03/notice-list` / `m07` / `m08` 同款：全量返回、前端筛）。
       ⚠️ 2026-09-20 刚踩过的那个坑（`ACC-PAY-LIST-001/001-10`）就是"取数层替壳砍了一刀" ⇒
       本模块从第一天起就**不含任何筛选参数**，⛔ 日后也别加。

    ⚠️ 排序 = `seq` 升序（**登记顺序**）：编号是人肉眼对账用的锚点，
       按 `seq` 排才与编号同序；⛔ 别按 `id` 倒序（那样 `DF01` 会跑到最后一行）。
    """
    return list(session.execute(select(DiffRecord).order_by(DiffRecord.seq)).scalars().all())


def all_seqs(session: Session) -> list[int]:
    """已用序号 —— 仅供 `domain.next_seq` 算下一个编号（"不撞号"的输入）。"""
    return list(session.execute(select(DiffRecord.seq)).scalars().all())


def get_record(session: Session, record_id: int) -> DiffRecord | None:
    """按 **`id`**（不是 `code`）定位一行 —— §9.8.2-5「写操作按 id 定位」的落点。"""
    return session.get(DiffRecord, int(record_id))


def create_record(session: Session, data, *, operator: str = "") -> DiffRecord:
    """登记一条（`data` = `domain.DiffInput`）—— 编号 `max(seq)+1`，**删行不回退**。"""
    seq = next_seq(all_seqs(session))
    row = DiffRecord(seq=seq, code=code_of(seq), created_by=operator or "", **to_record(data))
    session.add(row)
    session.flush()
    return row


def delete_record(session: Session, row: DiffRecord) -> None:
    """删除**该行**（判据点 `001-06`：其余行一行不动）。

    ⚠️ 与"配置类数据硬删不留痕"（§9.4）口径一致：本页是**手工清单**，
       删除 = **不再跟踪该笔**（⛔ 不是"把差异改掉了"—— 真正的修正动作在库存单据，§5.8.3）。
    ⚠️ 序号**不回退**（见 `domain.next_seq`）⇒ 删完再登记，编号继续往前走、不撞已删的号。
    """
    session.delete(row)
    session.flush()


def set_status(session: Session, row: DiffRecord, status: str) -> None:
    """改状态（`待核对 → 已核对 / 差异保留`，§8.3）—— 取值合法性由 `domain.validate` 之外
    的调用方先过一遍（本层只落库）。"""
    if row.status != status:
        row.status = status
        session.flush()


__all__ = [
    "all_seqs", "create_record", "delete_record", "get_record", "list_records", "set_status",
]
