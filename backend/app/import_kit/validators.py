"""`import_kit.validators` —— 行级问题清单（**永不静默猜**的落点）。"""

from __future__ import annotations

from collections.abc import Iterable


class Problems:
    """收集「行 / 列 / 原值 / 原因」—— 预览界面上**显式列出**，绝不悄悄改值。"""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, row_no: int, column: str, raw, reason: str) -> None:
        self.items.append(
            {"row": row_no, "column": column, "raw": "" if raw is None else str(raw), "reason": reason}
        )

    def extend(self, others: Iterable[dict]) -> None:
        self.items.extend(others)

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    def as_list(self) -> list[dict]:
        return list(self.items)


__all__ = ["Problems"]
