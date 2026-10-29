"""模板本体（**运行期交付物**）的**唯一路径出口** ＋ 完整性闸门。

依据 = 工程侧实测结论 `docs/reference/template-export.md` §五：
- 模板本体**随系统走**（已入库 `backend/app/resources/templates/`，**与代码同行、进 git**）；
- 该文档里**仍待做的一条实现侧硬性**：「模板缺失 ⇒ **必须显式报错**（不许静默产出空文件）」；
- 同一节登记的 **SHA256** 就是「防回退 / 损坏判据」（交付面那两份被 WPS 同步回退过两次）
  ⇒ 本模块把它落成代码里的闸门：**每次导出前核对**，不一致就**显式拒做**并说清怎么办。

⛔ 路径只在本模块写一次（`mod07`/`mod08` 两条导出链路共用）—— 各写一份必然走形。

⭐ **本模块管全部运行模板**：路径②（模板法 · `zip` 字节替换）= 收发结存 · 库存单据明细表；
路径①（模板填充 · `openpyxl` 读） = 逐月欠款台账 · 过程资料 · 焊材气体 · 开会大表 · 集采打印版 ——
**两类都要「缺失 / 损坏 ⇒ 显式拒做」**（它们都是产物生成的基底本体，不是"形态样例"）。
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from app.core.errors import MustReportError
from app.core.logging import get_logger

logger = get_logger()

#: 模板目录（`app/resources/templates/`）
TEMPLATE_DIR: Path = Path(__file__).resolve().parents[1] / "resources" / "templates"
MECHANICAL_TEMPLATE: Path = TEMPLATE_DIR / "模板-机械费四页.xlsx"

#: 收发结存表模板（`API-02` 的成品基底）
SETL_TEMPLATE: Path = TEMPLATE_DIR / "模板_收发结存表.xlsx"
#: 库存单据明细表模板（`API-03` 的成品基底）
KCDJ_TEMPLATE: Path = TEMPLATE_DIR / "模板_库存单据明细表.xlsx"

#: 路径①（模板填充）模板；登记与映射回交付面模板清单。
#: 来源 = 2026-09-18已入库的原始模板（那份 `模板清单.md` §二 是它们的**唯一登记处**）；
#: ⚠️ 它们与上面两份同理：**要被 `openpyxl` 读**，所以是**运行时依赖**（必须随代码走、进 git）。
#: 明细（每个模板含哪些 sheet / `DATA_START` 在哪 / 列映射）**一律回 `docs/requirements/report-templates.md`**，
#: ⛔ 本文件不复述（复述必漂）。
LEDGER_TEMPLATE: Path = TEMPLATE_DIR / "模板-逐月欠款台账.xlsx"      # sheet: 辅材 / 机械 / 特殊费用月报表
PROC_TEMPLATE: Path = TEMPLATE_DIR / "模板-过程资料.xlsx"            # sheet: 汇总表
WELD_TEMPLATE: Path = TEMPLATE_DIR / "模板-焊材气体.xlsx"            # sheet: 焊材 / 气
BIG_TEMPLATE: Path = TEMPLATE_DIR / "模板-开会大表.xlsx"             # sheet: Sheet1

#: 路径① 的集采打印模板与登记清单（供完整性检查使用）。
JC_PRINT_TEMPLATE: Path = TEMPLATE_DIR / "模板-集采打印台账.xlsx"

PATH1_TEMPLATES: tuple[Path, ...] = (LEDGER_TEMPLATE, PROC_TEMPLATE, WELD_TEMPLATE, BIG_TEMPLATE, JC_PRINT_TEMPLATE, MECHANICAL_TEMPLATE)

#: 登记的 SHA256（**唯一登记处** = `docs/reference/template-export.md` §五 那张表；改模板必须同时改这里）
EXPECTED_SHA256: dict[str, str] = {
    "模板-机械费四页.xlsx": "1f8c6638a1235d573edd6f4021b40a38cad0f9824c7d2a91ea30976e64316f88",
    "模板-集采打印台账.xlsx": "a9654f0530479929cdb5bd687d8f1fa2fa61ed0979a79af969bd56e0a03f8e6d",
    "模板_收发结存表.xlsx":
        "eab1c626dce769ac979408564cbffa52a8ca3bc42d80c76c40e0335f8c46d323",
    "模板_库存单据明细表.xlsx":
        "6803d01b1b0793f02543b281e737f9de42c9b955b7f45da0d55547e15b5e6bd2",
    # --- 路径①（2026-09-18 从旧demo入库，当前只读取运行资源目录）---
    "模板-逐月欠款台账.xlsx":
        "6b8568d48a7e5e254dd258c5f3c7b91b6ba0ebd18d77e6b546a24e7e9bc14d74",
    "模板-过程资料.xlsx":
        "74cc3db92a5c4926a2e29ed1be60c4fe1a5625c9e1a0025dc80037186a087eb4",
    "模板-焊材气体.xlsx":
        "9a049140ce738792865a2101afa40cde543ca1c8d241697628f0a6068a549d55",
    "模板-开会大表.xlsx":
        "5d4620f523898e3c6f62fd1f1a72c88854374c6565f41e7a16c094be27e3dd90",
}

#: ⚠️ `_RETRY` 是**给用户看的**（模板缺失 / 损坏 ⇒ 导出被拦时上屏）⇒ ⛔ 不许写工程侧路径 / 内部文件名。
#:   2026-10-01（`TAIL-211`）：原先写着「见 docs/reference/template-export.md §五」＋ 交付面与仓内两条路径
#:   —— 那是**写给维护者**的（守则 §3.1）；维护口径改走 `ops/` 那份文档，⛔ 别写回这里。
_RETRY = "请让维护人重新部署导出模板（模板是成品文件的**基底**，缺失或损坏时无法导出）。"


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
        logger.warning("模板缺失：%s", p)
        raise MustReportError(f"模板缺失 —— 导出无法进行（模板是成品文件的**基底**）。{_RETRY}")
    want = EXPECTED_SHA256.get(p.name)
    if want:
        got = sha256_of(p)
        if got != want:
            logger.warning("模板内容与登记不符：%s 实际 %s / 登记 %s", p.name, got, want)
            raise MustReportError(f"模板内容与登记不符（可能被回退 / 损坏）—— 导出无法进行。{_RETRY}")
    return p


__all__ = ["TEMPLATE_DIR", "SETL_TEMPLATE", "KCDJ_TEMPLATE", "LEDGER_TEMPLATE", "PROC_TEMPLATE",
           "WELD_TEMPLATE", "BIG_TEMPLATE", "JC_PRINT_TEMPLATE", "MECHANICAL_TEMPLATE", "PATH1_TEMPLATES", "EXPECTED_SHA256",
           "sha256_of", "require_template"]
