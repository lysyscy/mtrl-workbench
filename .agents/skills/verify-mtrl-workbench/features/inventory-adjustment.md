# Inventory adjustment

## Sub-features

Find an inventory row, check recomputed amounts, save an adjustment, and revoke it.

## How to get to it (user POV)

Open **库存单据与调整单** at `/preview/inventory`. Choose the inventory period and filter to the material before selecting **办理调整** on its row.

## Driving it with Playwright/pytest

Run `apps/frontend/tests/test_inventory.py::test_actual_inventory_adjustment_save_readback_and_revoke`. Find the row in `.inventory-grid`, fill **调整后数量** and **调整备注**, then check **保存调整单**, API values, and **确认撤销调整单**. Use `backend/tests/test_inventory_adjustment_values.py` for field and amount rules.

## Gotchas

The test needs an unadjusted row with positive quantity in the disposable preview. Select **全部** if the default inventory period hides it.
