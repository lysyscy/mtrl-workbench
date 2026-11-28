---
name: verify-mtrl-workbench
description: Verify mtrl-workbench through its registered local preview and isolated pytest entry points. Use for project, home todo, notice association, inventory adjustment, and oil-card invoice checks.
---

# Verify mtrl-workbench

Run from the repository root with its existing backend virtual environment. Select the path in the [feature map](features/README.md).

## Doctor

Run these read-only checks from the repository root.

~~~powershell
backend/.venv/Scripts/python.exe -B -X utf8 tools/dev/frontend_preview.py --list
backend/.venv/Scripts/python.exe -B -X utf8 tools/audit/doc_ops.py check --config tools/audit/doc-ops.config.json
backend/.venv/Scripts/python.exe -B -X utf8 tools/audit/directory_audit.py --staged
~~~

Before a browser test, confirm the registered owner, current worktree, loopback port, actual `/visual-version`, source commit, and disposable schema. Follow the database identity checks in the [verification reference](../../../docs/guides/development-and-verification.md). Use an authorized **non-production** source. Keep the production database and service out of the run. If an approved non-production source or a dedicated test database is unavailable, stop at Doctor.

## Launch

Use [frontend_preview.py](../../../tools/dev/frontend_preview.py) and the [preview guide](../../../docs/guides/frontend-preview.md). A new browser test instance uses a registered run, an unused loopback port (8065, 8066, or 8067), and explicit `--source-env <non-production-source.env> --copy-source --disposable`. The file must declare the approved source and a distinct dedicated `TEST_DATABASE_URL`. The entry verifies effective identities before connecting. Keep existing preview registrations in place. Use local writes only in the run's own disposable schema. External i8 and printer calls require separate authorization.

For database-backed pytest, use [backend_verify.py](../../../tools/dev/backend_verify.py) with the same isolation policy and `--test <path-relative-to-backend>`. It owns the temporary `backend_verify_` schema and pytest temp directory.

## Evidence

Run the feature's Playwright pytest node against its registered instance. The `preview_screenshot` fixture calls [frontend_capture.py](../../../tools/dev/frontend_capture.py) and records the image, identity, and metadata. Use [frontend_layout.py](../../../tools/dev/frontend_layout.py) for layout measurements. Pass `--preview-run` with the verified owner run and `--route` with the affected route. Report the action, response, or persisted result you observed.

## Cleanup

Use `frontend_preview.py --stop --port <owned-port>` after checking the run's registration. The entry stops the owned process and removes its disposable schema. Use [artifact_lifecycle.py](../../../tools/artifact_lifecycle.py) to register, lease, and close the run or retain evidence under the [artifact lifecycle rules](../../../docs/guides/artifact-lifecycle.md). Confirm the owned preview exited and record any retained evidence and its release condition.
