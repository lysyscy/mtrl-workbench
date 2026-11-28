# Projects

## Sub-features

Search project archives, edit the display name, and recover a lost save reply.

## How to get to it (user POV)

Open **项目档案** at `/preview/projects`. Use the **项目搜索** field to locate the warehouse.

## Driving it with Playwright/pytest

Run `apps/frontend/tests/test_project_history.py::test_project_confirmed_save_refreshes_actual_history_head`. Scope the input with `.project-table .ag-row[row-id="<id>"] input[aria-label^="展示名："]`. Press Enter and check the PUT, readback, and **撤销** state. Use `backend/tests/test_core_projects.py` for project data rules.

## Gotchas

The test inserts a synthetic project through the API and requires the `disposable` fixture. Use the row ID when names repeat.
