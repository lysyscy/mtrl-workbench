"""模板本体（**运行期交付物**）的**唯一路径出口** ＋ 完整性闸门。

依据 = 工程侧实测结论 `ops/模板法导出-实测结论.md` §五：
- 模板本体**随系统走**（已入库 `backend/app/resources/templates/`，**与代码同行、进 git**）；
- 该文档里**仍待做的一条实现侧硬性**：「模板缺失 ⇒ **必须显式报错**（不许静默产出空文件）」；
- 同一节登记的 **SHA256** 就是「防回退 / 损坏判据」（交付面那两份被 WPS 同步回退过两次）
  ⇒ 本模块把它落成代码里的闸门：**每次导出前核对**，不一致就**显式拒做**并说清怎么办。

⛔ 路径只在本模块写一次（`mod07`/`mod08` 两条导出链路共用）—— 各写一份必然走形。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.errors import MustReportError

#: 模板目录（`app/resources/templates/`）
TEMPLATE_DIR: Path = Path(__file__).resolve().parents[1] / "resources" / "templates"

#: 收发结存表模板（`API-02` 的成品基底）
SETL_TEMPLATE: Path = TEMPLATE_DIR / "模板_收发结存表.xlsx"
#: 库存单据明细表模板（`API-03` 的成品基底）
KCDJ_TEMPLATE: Path = TEMPLATE_DIR / "模板_库存单据明细表.xlsx"

#: 登记的 SHA256（**唯一登记处** = 实测结论文档 §五 那张表；改模板必须同时改这里）
EXPECTED_SHA256: dict[str, str] = {
    "模板_收发结存表.xlsx":
        "eab1c626dce769ac979408564cbffa52a8ca3bc42d80c76c40e0335f8c46d323",
    "模板_库存单据明细表.xlsx":
        "6803d01b1b0793f02543b281e737f9de42c9b955b7f45da0d55547e15b5e6bd2",
}

_OPS_DOC = "ops/模板法导出-实测结论.md §五"
_RETRY = ("请从交付面 `PRD素材包-20260911/data/templates/` 重新复制这一份进 "
          "`backend/app/resources/templates/`（该目录进 git），并核对 SHA256（见 %s）。" % _OPS_DOC)


def sha256_of(path: Path) -> str:
    """文件的 SHA256（分块读，避免整文件进内存）。"""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def require_template(path: Path) -> Path:
    """模板**可用性闸门** —— 缺失 / 损坏（SHA256 不符）⇒ **显式报错**（⛔ 不静默产出空文件）。

    ⚠️ 为什么连"损坏"也要拦：模板是 `zipfile` 的**基底**，被云同步回退/截断后
       `zipfile` 可能照旧打开、产出**看起来正常但内容陈旧**的文件（实测结论 §四 已列为"必复做"触发条件）。
    """
    p = Path(path)
    if not p.exists():
        raise MustReportError(f"模板缺失：`{p}` —— 导出无法进行（模板是成品文件的**基底**）。{_RETRY}")
    want = EXPECTED_SHA256.get(p.name)
    if want:
        got = sha256_of(p)
        if got != want:
            raise MustReportError(
                f"模板内容与登记不符（可能被回退 / 损坏）：`{p.name}`\n"
                f"　实际 SHA256 = {got}\n　登记 SHA256 = {want}\n{_RETRY}"
            )
    return p


__all__ = ["TEMPLATE_DIR", "SETL_TEMPLATE", "KCDJ_TEMPLATE", "EXPECTED_SHA256",
           "sha256_of", "require_template"]
