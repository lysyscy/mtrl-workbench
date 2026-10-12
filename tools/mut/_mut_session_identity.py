"""守会话账号身份、旧标签消歧与姓名留痕：在隔离后端副本逐靶造红，不改正式源码。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from _isolated import isolated_backend

ROOT = Path(__file__).resolve().parents[2]
TEST = "tests/test_session_identity.py"
MUTATIONS = [
    ("login-label", "app/mod15_user/api.py", "account_identity = row.account",
     "account_identity = row.name or row.account", "test_login_keeps_worker_identity_and_rejects_admin_actions"),
    ("new-account-as-label", "app/mod15_user/repository.py", "if isinstance(who, AccountIdentity):",
     "if False:", "test_login_keeps_worker_identity_and_rejects_admin_actions"),
    ("accept-legacy-ticket", "app/core/session.py",
     'if len(parts) != 4 or parts[0] != "v2":\n        return None\n    _, acc_b64, exp_s, sig = parts',
     'if len(parts) == 3:\n        acc_b64, exp_s, sig = parts\n    elif len(parts) == 4 and parts[0] == "v2":\n        _, acc_b64, exp_s, sig = parts\n    else:\n        return None',
     "test_legacy_session_requires_new_login"),
    ("lose-middleware-account-type", "app/main.py", "SESS.set_current_name(who)",
     "SESS.set_current_name(str(who))", "test_login_keeps_worker_identity_and_rejects_admin_actions"),
    ("write-gate-only-cookie", "app/main.py",
     "if SESS.read(request.cookies.get(SESS.COOKIE_NAME)):",
     "if request.cookies.get(SESS.COOKIE_NAME):",
     "test_ambiguous_legacy_session_cannot_write_or_select_a_user"),
    ("audit-account-instead-of-name", "app/core/identity.py",
     'name = (row.name or row.account or "").strip()', 'name = (row.account or "").strip()',
     "test_login_uses_own_preferences_i8_and_display_name"),
    ("lose-i8-account-type", "app/core/identity.py",
     "row = _BINDING_LOOKUP(s, who)\n        if row is not None:",
     "row = _BINDING_LOOKUP(s, str(who))\n        if row is not None:",
     "test_login_uses_own_preferences_i8_and_display_name"),
]


def run(base, env, selection=""):
    """只把明确的断言失败算靶命中，收集/环境错误不能冒充造红。"""
    command = [sys.executable, "-X", "utf8", "-m", "pytest", "-q", "-p", "no:cacheprovider",
               "--tb=line", TEST]
    if selection:
        command.extend(["-k", selection])
    result = subprocess.run(command, cwd=base, env=env, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    return result.returncode, result.stdout + result.stderr


def main():
    paths = {ROOT / "backend" / item[1] for item in MUTATIONS}
    before = {path: path.read_bytes() for path in paths}
    with isolated_backend("tmp-session-identity-") as (base, env):
        env.update(SESSION_SECRET="isolated-session-identity-key", I8_USER="fake-env-i8",
                   I8_PASSWORD="fake-env-i8-password", PYTHONDONTWRITEBYTECODE="1")
        code, output = run(base, env)
        if code:
            print("正常输入失败；不能执行或声称反向通过")
            print(output)
            return 1
        print("正常输入通过")
        for label, relative, old, new, selection in MUTATIONS:
            path = base / relative
            original = path.read_bytes()
            newline = "\r\n" if b"\r\n" in original else "\n"
            old_bytes, new_bytes = (part.replace("\n", newline).encode() for part in (old, new))
            if original.count(old_bytes) != 1:
                raise AssertionError(f"{label}: 变异锚不唯一或不存在")
            try:
                path.write_bytes(original.replace(old_bytes, new_bytes))
                code, output = run(base, env, selection)
                assertion_failed = "AssertionError" in output or "E   assert " in output
                if code != 1 or "FAILED " not in output or not assertion_failed or "ERROR tests/" in output:
                    print(output)
                    raise AssertionError(f"{label}: 未产生明确行为断言失败")
                print(f"{label}: 行为断言造红")
            finally:
                path.write_bytes(original)
        code, output = run(base, env)
        if code:
            print(output)
            raise AssertionError("隔离复原输入没有通过")
        print(f"复原输入通过；{len(MUTATIONS)}/{len(MUTATIONS)}隔离靶命中")
    assert all(path.read_bytes() == content for path, content in before.items()), "正式源码字节被改变"
    print("正式源码字节未变；未刷新完整权威结果")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
