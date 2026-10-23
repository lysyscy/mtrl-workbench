"""Read-only checks for active run and finite evidence retention."""
from pathlib import Path
import json
import time
REPO_ROOT=Path(__file__).resolve().parents[2]
SCRATCH_TTL_DAYS=14
YELLOW='yellow'

def _hit(code: str, rel: str, what: str, why: str, fix: str, line: int = 1) -> dict:
    """本件四条黄档共用的命中形状 —— ⛔ 别在别处手拼同样的 dict（`/code-review` 2026-10-05 指出）。

    ⚠️ `line` **只有"能点到具体那一行"的判据才传**（`T26` 点声明行）；其余默认 1 —— 它们的
       "命中处"是**整件**（白名单外的 md / 超期临时件 / 仓库根多出来的条目），点行号没有意义。
    """
    return {"code": code, "side": "仓", "rel": rel, "line": line,
            "what": what, "why": why, "fix": fix, "level": YELLOW, "text": ""}

def check_scratch_ttl() -> list[dict]:
    """`T14`：scratch 超期 ＋ 散件落点（tools 根 / logs）。"""
    hits: list[dict] = []
    scratch = REPO_ROOT / ".artifacts" / "active"
    now = time.time()
    if scratch.is_dir():
        for f in sorted(scratch.rglob("*")):
            if not f.is_file() or f.name == ".gitkeep":
                continue
            days = (now - f.stat().st_mtime) / 86400
            if days > SCRATCH_TTL_DAYS:
                hits.append(_hit(
                    "T14", f.relative_to(REPO_ROOT).as_posix(),
                    f"开发运行仍未退出 active：{days:.0f} 天（调查线 {SCRATCH_TTL_DAYS} 天）",
                    "临时区变垃圾场（审计 P2 的复发形态）—— 过期件会让下个 Agent 以为是当前线索",
                    "按README归入当前任务、docs或历史；先核活动和恢复用途再清理"))
    import json
    from datetime import date, timedelta
    archive = REPO_ROOT / '.artifacts/archive'
    for effort in sorted(archive.iterdir()) if archive.is_dir() else []:
        if not effort.is_dir():
            continue
        try:
            policy = json.loads((effort/'retention.json').read_text(encoding='utf-8'))
            expires = date.fromisoformat(policy['expires_on'])
            if not policy.get('reason') or not date.today() <= expires <= date.today() + timedelta(days=30):
                raise ValueError('缺少理由或期限越界')
        except (OSError, ValueError, KeyError, TypeError):
            hits.append(_hit('T14', effort.relative_to(REPO_ROOT).as_posix(),
                             '本机证据缺少有效的有限保留期',
                             '归档不能成为无限保存临时现场的入口',
                             '核实际用途，删除无价值证据或迁入长期样本/数据；不自动续期'))
    for legacy in ('artifacts', 'logs', '.scratch/local'):
        path = REPO_ROOT/legacy
        if path.is_dir() and any(path.iterdir()):
            hits.append(_hit('T14', legacy, '旧混合目录仍有内容',
                             '现行消费者应使用固定类型目录', '核在途任务和真实消费者后完成具名迁移；不可批量删除'))
    tools = REPO_ROOT / "tools"
    if tools.is_dir():
        for f in sorted(tools.glob("*.py")):
            hits.append(_hit(
                "T14", f"tools/{f.name}",
                "`tools/` 根出现了散件脚本",
                "工具根只放 `*_expected.txt` 登记表与 README（审计 P6）—— 根上散件没人知道它属于哪一类",
                "归位：尺子→`audit/` · 变异→`mut/` · 探针→`probe/` · 一次性→`oneoff/`"))
    logs = REPO_ROOT / "var/log"
    if logs.is_dir():
        for f in sorted(logs.iterdir()):
            if f.is_file() and f.suffix not in (".log", "") and f.name != ".gitkeep":
                hits.append(_hit(
                    "T14", f"var/log/{f.name}",
                    "`logs/` 里出现了非日志文件",
                    "logs 只放服务日志（审计 P13：探测便签混入过一次）",
                    "开发输出归本轮.artifacts/active/<effort>/<run>/<kind>"))
    return hits

if __name__ == '__main__':
    hits=check_scratch_ttl()
    print(json.dumps(hits,ensure_ascii=False,indent=2))
    raise SystemExit(1 if hits else 0)
