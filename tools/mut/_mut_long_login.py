"""守长期会话、签名与旧票拒绝和主动退出：只在隔离后端副本造红，不访问数据库。"""
from __future__ import annotations

from pathlib import Path as _WorkspacePath
import sys as _workspace_sys
_workspace_sys.path.insert(0, str(_WorkspacePath(__file__).resolve().parents[2] / 'tools/audit'))
from workspace_paths import output as _run_output, output_dir as _run_dir, finish_run as _finish_run

import json
import subprocess
import sys
from pathlib import Path

from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
TEST = "tests/test_session_long_login.py"
MUTATIONS = [
    ("restore-server-expiry", "app/core/session.py",
     "        int(exp_s)  # 保留原时间字段的整数校验，不再用它判断过期。",
     "        exp = int(exp_s)\n        if (now or _dt.datetime.now()).timestamp() > exp:\n            return None",
     "test_signed_account_remains_valid_after_long_time"),
    ("restore-12h-cookie", "app/mod15_user/api.py", "max_age=SESS.COOKIE_MAX_AGE_SECONDS,",
     "max_age=12 * 3600,", "test_login_sets_persistent_cookie_and_logout_removes_identity"),
    ("forget-logout-cookie", "app/mod15_user/api.py",
     '    out.delete_cookie(SESS.COOKIE_NAME, path="/")', "    pass",
     "test_login_sets_persistent_cookie_and_logout_removes_identity"),
    ("skip-signature", "app/core/session.py", 'if not hmac.compare_digest(_sign(".".join(parts[:-1])), sig):',
     'if False:', "test_tampering_each_signed_field_is_rejected_by_read_and_write_gate"),
    ("accept-unknown-version", "app/core/session.py", 'if len(parts) != 4 or parts[0] != "v2":',
     'if len(parts) != 4:', "test_correct_signature_cannot_bypass_format_and_account_checks"),
    ("accept-legacy-ticket", "app/core/session.py",
     'if len(parts) != 4 or parts[0] != "v2":\n        return None\n    _, acc_b64, exp_s, sig = parts',
     'if len(parts) == 3:\n        acc_b64, exp_s, sig = parts\n    elif len(parts) == 4 and parts[0] == "v2":\n        _, acc_b64, exp_s, sig = parts\n    else:\n        return None',
     "test_correct_signature_cannot_bypass_format_and_account_checks"),
    ("skip-time-field-validation", "app/core/session.py",
     "        int(exp_s)  # 保留原时间字段的整数校验，不再用它判断过期。", "        pass",
     "test_correct_signature_cannot_bypass_format_and_account_checks"),
    ("write-gate-only-cookie", "app/main.py",
     "if SESS.read(request.cookies.get(SESS.COOKIE_NAME)):",
     "if request.cookies.get(SESS.COOKIE_NAME):",
     "test_tampering_each_signed_field_is_rejected_by_read_and_write_gate"),
    ("accept-empty-account", "app/core/session.py",
     "return AccountIdentity(identity) if identity.strip() else None", "return AccountIdentity(identity)",
     "test_correct_signature_cannot_bypass_format_and_account_checks"),
]


def run(base, env, selection=""):
    command = [sys.executable, "-B", "-X", "utf8", "-m", "pytest", "-q",
               "-p", "no:cacheprovider", "--tb=line", TEST]
    if selection:
        command += ["-k", selection]
    result = subprocess.run(command, cwd=base, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace", timeout=60)
    return result.returncode, result.stdout + result.stderr


def main():
    before = {ROOT / "backend" / item[1]: (ROOT / "backend" / item[1]).read_bytes()
              for item in MUTATIONS}
    receipt = []
    with isolated_backend("tmp-long-login-") as (base, env):
        env.update(SESSION_SECRET="isolated-long-login-key", DATABASE_URL="", TEST_DATABASE_URL="",
                   I8_USER="", I8_PASSWORD="", PYTHONDONTWRITEBYTECODE="1")
        code, output = run(base, env)
        if code:
            raise AssertionError("正常输入失败：\n" + output)
        print("正常输入通过；不访问数据库")
        for label, relative, old, new, selection in MUTATIONS:
            path = base / relative
            original = path.read_bytes()
            newline = "\r\n" if b"\r\n" in original else "\n"
            old_bytes, new_bytes = [s.replace("\n", newline).encode() for s in (old, new)]
            assert original.count(old_bytes) == 1, f"{label}: 变异锚不唯一或不存在"
            try:
                path.write_bytes(original.replace(old_bytes, new_bytes))
                code, output = run(base, env, selection)
                assert code == 1 and "FAILED " in output and "AssertionError" in output, output
                assert "ERROR tests/" not in output, output
                receipt.append({"mutation": label, "exit_code": code, "output": output})
                print(f"{label}: 行为断言造红", flush=True)
            finally:
                path.write_bytes(original)
        code, output = run(base, env)
        assert code == 0, output
        print(f"复原输入通过；{len(receipt)}/{len(MUTATIONS)}隔离靶命中")
    assert all(path.read_bytes() == content for path, content in before.items())
    out = ROOT / str(_run_output('tail308-mutation-results.json'))
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"mutations": receipt, "restored_exit_code": code,
                              "formal_source_unchanged": True}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("正式源码字节未变；独立回执：" + str(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(_finish_run(main()))
