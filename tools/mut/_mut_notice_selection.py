"""守通知书搜索保留、隐藏核对、付款行序和失效清理：只在隔离壳副本造红，不连服务或数据库。"""
from pathlib import Path
import json
import subprocess
import sys
from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
TEST = "tests/test_tail309_notice_selection.py"
MUTATIONS = [
    ("search-prunes-selection", "actions.js", 'fNt.q=t.value; render();',
     'fNt.q=t.value; prunePick(); render();', "搜索改词清空"),
    ("bypass-hidden-direct-action", "actions.js", 'if(!c||!ntBatchVisible()) return;',
     'if(!c) return;', "直接批量动作"),
    ("lose-payment-row-order", "actions.js",
     "   if(rows.length!==payBatchIds.length||rows.some((n,i)=>n.id!==payBatchIds[i])){\n     ACT.batchPay(); return toast('勾选记录已变化，请重新核对本次付款后再确认',5200); }\n",
     "", "付款弹窗后删除"),
    ("lose-stale-id-reconciliation", "proj.js",
     'const reconcilePick=()=>{ const valid=new Set(NO.filter(ntSelectable).map(n=>n.id));\n  [...pickSet].forEach(i=>{ if(!valid.has(i)) pickSet.delete(i); }); };',
     'const reconcilePick=()=>{};', "批量出口清理"),
]

def run(base, env, selection=""):
    command = [sys.executable, "-B", "-X", "utf8", "-m", "pytest", "-o", "addopts=-p tests.acc_plugin",
               "-q", "-p", "no:cacheprovider", "--tb=short", TEST]
    if selection:
        command += ["-k", selection]
    result = subprocess.run(command, cwd=base, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout + result.stderr

def main():
    before = {ROOT / "backend/app/web/shell" / item[1]: (ROOT / "backend/app/web/shell" / item[1]).read_bytes()
              for item in MUTATIONS}
    receipt = []
    with isolated_backend("tmp-notice-selection-") as (base, env):
        import shutil
        shutil.copytree(ROOT / "tools", base.parent / "tools", ignore=shutil.ignore_patterns("__pycache__"))
        env.update(SESSION_SECRET="isolated-notice-selection-key", DATABASE_URL="", TEST_DATABASE_URL="",
                   I8_USER="", I8_PASSWORD="", PYTHONDONTWRITEBYTECODE="1",
                   PLAYWRIGHT_BROWSERS_PATH="C:/ProgramData/ms-playwright")
        code, output = run(base, env)
        assert code == 0, output
        print(output.strip().splitlines()[-1], flush=True)
        for label, relative, old, new, selection in MUTATIONS:
            path = base / "app/web/shell" / relative
            original = path.read_bytes()
            newline = "\r\n" if b"\r\n" in original else "\n"
            old_b, new_b = [text.replace("\n", newline).encode() for text in (old, new)]
            assert original.count(old_b) == 1, label
            extra_path = base / "app/web/shell/proj.js"
            extra_original = extra_path.read_bytes()
            try:
                path.write_bytes(original.replace(old_b, new_b))
                if label == "search-prunes-selection":
                    old_scope = b'ntHit({...fNt,q:\'\'})'
                    assert extra_original.count(old_scope) == 1
                    extra_path.write_bytes(extra_original.replace(old_scope, b'ntHit(fNt)'))
                code, output = run(base, env, selection)
                assert code == 1 and "FAILED " in output and "AssertionError" in output and "ERROR tests/" not in output, output
                receipt.append({"mutation": label, "returncode": code, "output": output})
                print(label + ": 明确断言造红", flush=True)
            finally:
                path.write_bytes(original)
                if label == "search-prunes-selection":
                    extra_path.write_bytes(extra_original)
        code, output = run(base, env)
        assert code == 0, output
        print(output.strip().splitlines()[-1], flush=True)
    assert all(path.read_bytes() == data for path, data in before.items())
    out = ROOT / "artifacts/tail309-integration/mutations.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"mutations": receipt, "restored_returncode": code,
                  "formal_source_unchanged": True}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("4/4通过；正式壳字节未变；回执", out)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
