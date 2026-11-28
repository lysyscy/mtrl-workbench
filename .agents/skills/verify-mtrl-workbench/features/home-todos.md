# Home todos

## Sub-features

Read ownership, unlinked contract, and revoked-with-activity counts. Open each scoped notice list.

## How to get to it (user POV)

Open the home page at `/preview`. Choose **去指定归属**, **去关联合同**, or **去处理** in its own tile.

## Driving it with Playwright/pytest

Run `apps/frontend/tests/test_home.py::test_real_todo_counts_and_scope_links`. Find each `.home-tile` by its label. Compare `.home-tile-count` and the destination `todo` query with the notice API. Backend membership cases live in `backend/tests/test_acc_home_todo.py`.

## Gotchas

Use counts from the preview's current data. AG Grid's accessible row count includes the header and a total row for nonempty results.
