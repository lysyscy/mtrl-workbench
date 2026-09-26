"""`import_kit.spec` —— **域声明**（`TAIL-75` B1）。

⭐ 分工（设计 §六）：**通用层**管读表 / 表头定位 / 映射建议 / 记忆 / 预览 / 暂存；
**域**只声明「字段 ＋ 要求」并给两个钩子（`commit` / `rollback`）—— 落库口径仍是域内的事。

⛔ 本件**不含任何业务字段**：字段名词、必填、别名都来自各域。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.import_kit.mapping import Field, normalize

#: 域钩子签名：`(session, records, mapping, operator[, options]) -> report`
#:
#: ⭐ **`options` 可省**（第 5 个位置参数）：域若需要界面给的上下文（如 `m11` 要"这次导哪个项目/哪张表"
#:   才谈得上按合同价匹配）⇒ 写成 **5 参**，通用面会把 `commit` 请求体里的 `options` 原样递过来。
#:   4 参与 5 参**都合法**（`api._takes_options` 按签名判 —— ⛔ 不靠"调一下试试"捕 `TypeError`，
#:   那会把钩子内部真出的 `TypeError` 一起吃下去）。
CommitHook = Callable[..., dict]
RollbackHook = Callable[[Any, str, str], dict]
#: 域**预览**钩子签名：`(session, records, mapping) -> dict | None`。
#:
#: ⭐ **为什么要有它**（2026-09-23 · `TAIL-75` `B5b` 第三步接 `m05` 时逼出来的）：
#:   通用面的预览是**域无关**的（类型/必填/行级问题清单）；可有的域的**判据**要求
#:   "预览里必须列出**只有它自己算得出**的东西"—— 如 `m05` 的
#:   「**单据号本地查不到 ⇒ 未匹配清单**」（要读库）＋「未识别的付款方式取值」＋「金额必须 > 0」。
#:   ⇒ 给域一个**只读**补丁口子：⛔ 仍**不写库**（`preview_store` 仍是唯一载具）。
PreviewHook = Callable[..., dict]


@dataclass(frozen=True)
class DomainSpec:
    """一个导入域的**全部声明**（⛔ 只写"要什么"，不写"怎么落库"）。"""

    domain: str                                  # `m04` / `m11` / `imp_xxx`
    title: str                                   # 界面上那句话（如「付款计划 · 材机费」）
    fields: tuple[Field, ...]
    source_label: str = ""                       # 记忆用的来源标签（可空）
    max_rows: int | None = None                  # 读表截断（各域不同 ⇒ 由域给）
    preferred_sheet: str | None = None           # 已知优先工作表；None ⇒ 自动挑
    note: str = ""                               # 界面「本域要求」那段
    keep_note: str = ""                          # 「刻意不采」说明（原样保留的列）
    batch: bool = False                          # 有无批次回滚
    #: ⭐ **明确不采的列**：`((列名的任一写法, 为什么不采), …)`（写法按 `mapping.normalize` 比）。
    #:
    #: ⚠️ 为什么要这一条（`B5-0` 接 `m06` 实测逼出来的）：机械 6 列**认得出但按口径不导入**，
    #:   早先它们落进"未认出" ⇒ 界面上看着像**系统漏了**（用户会一列列去点）。两者含义完全不同：
    #:   **未认出 = 系统不认识**（该让人点）；**不采 = 系统认识、但按规矩不导**（该把理由说清）。
    ignored: tuple[tuple[str, str], ...] = ()
    #: ⭐ **逐列后果**：`((目标字段, 一句话), …)` 或 `((目标字段, 一句话, 去向), …)`。
    #:
    #: ⚠️ 为什么必须有它（用户 2026-09-26 拷问后定）：用户要决定"这列导不导、选哪个字段"，
    #:   就必须知道**导了会怎样** —— 而"哪几列会被覆盖、哪一列只是用来对号、哪几列是 i8 的、一个字都不碰"
    #:   **只有域知道**（壳看一眼数据猜不出）。⛔ 措辞一律**由域给**，壳不猜、不拼；
    #:   **域没声明 ⇒ 界面不标**（不替域编）。⚠️ 键是**目标字段名**（不是源列名）——
    #:   这样它随用户改下拉**实时跟着变**：同一列选不同字段，后果不同就得说不同的话。
    #:
    #: ⭐⭐ **第三项「去向」**（2026-09-26 用户裁定）：**只许三个词** ——
    #:   `写台账`（会盖掉台账里的值，**含"往发票子表加一张票"** —— 用户原话：
    #:   「写台账和进子表为一个意思，合并为写台账」）· `当钥匙`（拿它去找那张合同，合同上的原值不动）·
    #:   `不参与`（导入不用它）。⚠️ 屏上只留这三个短词（守则 §5.9 同屏做优先级），
    #:   **完整说明放第二项**（界面把它放进**悬停**）。
    impacts: tuple[tuple, ...] = ()
    #: ⭐ **这一批怎么入库**（页头一句话）：对号键是什么 · 覆盖谁 · 能不能反悔 —— **大白话**，域给。
    #: ⚠️ 四域的规则互不相同（`m04` 按"年月＋单据号"更新、`m11` 按"含税合同价"对号、`m06` 每次新批…）
    #:   ⇒ 这句话**必须由域说**，⛔ 通用层不写"套话"（套话=误导）。
    rule_note: str = ""
    #: ⭐ **「本系统要哪些列」那段的一句话提醒**（域给 · 大白话）：2026-09-26 用户裁定
    #:   「缺列提醒**必须默认露出来**」（⛔ 不能藏在折叠里 —— 藏了等于没提醒）。
    #: ⚠️ 通用层⛔ 不编这句（"缺哪列要紧"只有域知道），域不给 ⇒ 界面不显示。
    field_list_hint: str = ""
    extra: dict = field(default_factory=dict)    # 域自定义（⛔ 通用层不看）

    @property
    def required(self) -> tuple[str, ...]:
        return tuple(f.label for f in self.fields if f.required)

    def by_label(self, label: str) -> Field | None:
        return next((f for f in self.fields if f.label == label), None)

    def as_schema(self) -> dict:
        """给界面的**字段契约**（壳侧渲染向导用；⛔ 壳里不许再抄一份字段名）。"""
        return {
            "domain": self.domain, "title": self.title, "required": list(self.required),
            "note": self.note, "keep_note": self.keep_note, "batch": bool(self.batch),
            "rule_note": self.rule_note, "field_list_hint": self.field_list_hint,
            "ignored": [{"label": lb, "why": why} for lb, why in self.ignored],
            "impacts": [{"label": x[0], "what": x[1], "kind": (x[2] if len(x) > 2 else "")}
                        for x in self.impacts],
            "fields": [{"key": f.key, "label": f.label, "type": f.type,
                        "required": bool(f.required), "aliases": list(f.aliases)}
                       for f in self.fields],
        }

    def ignored_why(self, label: str) -> str:
        """该列表头是不是"明确不采"⇒ 回理由；不是 ⇒ `""`。"""
        key = normalize(label)
        for raw, why in self.ignored:
            if normalize(raw) == key:
                return why
        return ""

    def impact_kind_of(self, label: str) -> str:
        """该**目标字段**的「去向」（`写台账` / `当钥匙` / `不参与`）；没声明 ⇒ `""`（界面不标）。"""
        key = normalize(label)
        for x in self.impacts:
            if normalize(x[0]) == key:
                return x[2] if len(x) > 2 else ""
        return ""

    def impact_of(self, label: str) -> str:
        """该**目标字段**的「导入后会怎样」⇒ 域给的原文；没声明 ⇒ `""`（界面不标）。

        ⚠️ 按**下标**取，⛔ 不写 `for raw, what in …` —— 声明可以是 **2 元组或 3 元组**
        （第三项 = 去向），按 2 个解包会在遇到 3 元组时 `ValueError`（2026-09-26 当场踩到）。
        """
        key = normalize(label)
        for x in self.impacts:
            if normalize(x[0]) == key:
                return x[1]
        return ""


@dataclass
class Hooks:
    """域侧只提供这四件（**落库口径归域内**，通用层不碰）。"""

    commit: CommitHook
    rollback: RollbackHook | None = None
    #: ⭐ **域上下文**（如 `m06` 的"这批进哪个项目 / 截止核算月 / 已有批次"）。
    #:
    #: ⚠️ 为什么要有它（2026-09-23 · `B5c-2`）：早先这类"域自己的候选"只能靠域专属读端点
    #:   （`/api/m06/import/data`）⇒ **加一个域要在壳里再加一条**正是要防的事。现在通用面据此开
    #:   `GET /api/imp/{domain}/options`，壳**只认这一条**（⛔ 不再为每个域留专属读端点）。
    options: Callable[[Any], dict] | None = None
    #: ⭐ **域预览补丁**（可选）：`(session, records, mapping) -> dict | None`，可回
    #: `{"problems": […], "writable": int, "kpis": {名: 值}, "blocks": [{title, note, columns, rows}]}`。
    #:
    #: ⚠️ 为什么要有它（2026-09-23 · `B5b` 第三步接 `m05`）：通用面的预览是**域无关**的，
    #:   而 `m05` 的判据要求预览里列出「**未匹配清单**」（要读库）＋「未识别的付款方式取值」；
    #:   ⇒ 把"只有域自己算得出的那几块"交回域内补，⛔ 通用层不碰业务判定。
    #:   ⚠️ 它是**只读**的：`preview_store` 仍是预览的**唯一载具**（确认前零写库）。
    preview: PreviewHook | None = None


class Registry:
    """域注册表（⛔ 同号不许重复注册 —— 重号 = 两处口径，正是要防的事）。"""

    def __init__(self) -> None:
        self._items: dict[str, DomainSpec] = {}

    def add(self, spec: DomainSpec) -> DomainSpec:
        if spec.domain in self._items:
            raise ValueError(f"域号重复：{spec.domain}（⛔ 一处口径一个域号）")
        self._items[spec.domain] = spec
        return spec

    def get(self, domain: str) -> DomainSpec | None:
        return self._items.get(domain)

    def domains(self) -> list[str]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)


__all__ = ["CommitHook", "DomainSpec", "Hooks", "PreviewHook", "Registry", "RollbackHook"]
