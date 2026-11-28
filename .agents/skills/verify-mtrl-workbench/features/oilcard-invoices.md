# Oil-card invoices

## Sub-features

Register a manual amount, reconcile a lost reply, and add the invoice number to the saved row.

## How to get to it (user POV)

Open **油卡管理** at `/preview/oilcard`, select **充值与发票**, and open **手动增行**.

## Driving it with Playwright/pytest

Run `apps/frontend/tests/test_oilcard_manual.py::test_manual_invoice_lost_reply_and_same_row_number`. Scope fields to the **手动增行** dialog and use **分配项目 1**, **分配账户 1**, and **登记已开金额**. Use `backend/tests/test_oilcard_invoices.py` and `backend/tests/test_oilcard_invoice_adjustments.py` for originals and amount rules.

## Gotchas

The disposable preview needs an active account and its project. After a lost reply, use **重读核对** and **已核对，保留输入继续** before editing the existing row.
