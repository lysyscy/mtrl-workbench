# Feature verification map

| Feature | React route | Browser pytest |
|---|---|---|
| [Projects](projects.md) | `/projects` | `test_project_history.py` |
| [Home todos](home-todos.md) | `/` | `test_home.py` |
| [Notice association](notice-association.md) | `/notices?notice=<id>` | `test_notice_association.py` |
| [Inventory adjustment](inventory-adjustment.md) | `/inventory` | `test_inventory.py` |
| [Oil-card invoices](oilcard-invoices.md) | `/oilcard` | `test_oilcard_manual.py` |

The registered preview serves these routes under `/preview`. From the repo root, use `backend/.venv/Scripts/python.exe -B -X utf8 -m pytest -c backend/pytest.ini -p no:cacheprovider --basetemp <unique-temp-dir> apps/frontend/tests/<file>::<node>`. The fixtures attach to the current worktree's verified preview. Follow [the skill](../SKILL.md) for isolation, evidence, and cleanup.
