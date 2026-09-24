#!/usr/bin/env python
"""AI 建议层**基准探针**（`TAIL-75` · 决策 `D24`）—— 换模型 / 调问法后重跑它就有对照。

用法：
    backend\\.venv\\Scripts\\python.exe tools\\probe\\_ai_map_bench.py [模型名]

⭐ 问法形态（**五轮实测才定下来，⛔ 别改回去**）：一次只问**一列**、只给 **3~4 个候选**、
要求输出 `{"pick": "候选里的一个"}`、`think:false` ＋ `temperature:0` ＋ `num_predict≤48`。
（前四轮为什么不行：模板被抄 · 序号错位 · 镜像列名 · schema 约束那次漏 `think:false` —— 见 `D24`。）

⚠️ 需要本机有 Ollama 服务（`http://127.0.0.1:11434`）且模型已拉好；⛔ 本探针**不碰业务代码**。
"""
from __future__ import annotations

import json
import random
import sys
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "qwen3:1.7b"
IGN = "忽略（原样保留）"
#: 候选池（取自真文件里的字段名）
LABELS = ["租分公司设备", "内租设备", "付款方式", "本月预付款金额", "剩余付款金额", "供应商", "贸易公司"]
#: (列名, 样本值, 真值) —— 素材按真文件形态造
CASES = [
    ("分公司设备费", ["1,100.00", "1,100.00"], "租分公司设备"),
    ("内租机械计费", ["11,593.00", "12,189.00"], "内租设备"),
    ("详细付款方式", ["电汇", "承兑"], "付款方式"),
    ("本月应付金额", ["400,000", "28,922"], "本月预付款金额"),
    ("剩余未付款", ["12,000", "0"], "剩余付款金额"),
    ("Supplier Name", ["洛阳桐玺", "赫尔威"], "供应商"),
    ("审批状态", ["已审批", "已审批"], IGN),        # ⭐ 该忽略的：测"会不会乱认"
    ("打印次数", ["1", "0"], IGN),
]


def post(body: dict) -> dict:
    req = urllib.request.Request(API, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return {"error": f"HTTP {exc.code}", "_body": exc.read().decode("utf-8", "replace")[:200]}


def ask_one(model: str, col: str, samples: list[str], cands: list[str]) -> tuple[str, float, int]:
    prompt = (
        "把 Excel 的某一列对到系统字段。**只能从候选里选一个，原样照抄**；"
        f"都不合适就选「{IGN}」。⛔ 不许创造字段名。\n\n"
        f"这一列：\n- 列名：{col}\n- 前几个值：{' / '.join(samples)}\n\n"
        "候选（选一个）：\n" + "\n".join(f"- {c}" for c in cands) + "\n\n"
        f'只输出 JSON：{{"pick": "候选里的某一个"}}'
    )
    t0 = time.time()
    out = post({"model": model, "stream": False, "think": False, "format": "json",
                "messages": [{"role": "user", "content": prompt}],
                "options": {"temperature": 0, "num_predict": 48, "top_k": 1}})
    dt = time.time() - t0
    if "error" in out:
        return f"⛔{out['error']}", dt, 0
    content = (out.get("message") or {}).get("content", "")
    try:
        pick = str(json.loads(content).get("pick", "")).strip()
    except ValueError:
        pick = content.strip()[:20]
    return pick, dt, int(out.get("eval_count") or 0)


def main() -> int:
    model = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MODEL
    print(f"模型 {model} · 服务 {API}\n")
    rnd = random.Random(20260922)
    print(f"{'列名':<16} {'真值':<12} {'AI 答案':<12} {'秒':>5s} {'出token':>7s}  判定")
    ok, total = 0, 0.0
    for col, samples, truth in CASES:
        cands = [truth] + rnd.sample([c for c in LABELS if c != truth], 3) + [IGN]
        rnd.shuffle(cands)
        pick, dt, ntok = ask_one(model, col, samples, cands)
        good = pick == truth
        ok += good
        total += dt
        print(f"{col:<16} {truth:<12} {pick:<12} {dt:5.1f} {ntok:7d}  {'✅' if good else '❌'}")
    print(f"\n合计 {ok}/{len(CASES)} · 总耗时 {total:.1f} 秒 · 平均 {total / len(CASES):.1f} 秒/列")
    print("⚠️ 这只是建议层的准确率：结论一律进「需你确认」档，⛔ 不自动落库（见 `D24`）。")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
