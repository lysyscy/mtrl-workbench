# Notice association

## Sub-features

Edit a supplier, choose a contract, confirm association, and remove the association.

## How to get to it (user POV)

Open `/preview/notices?notice=<id>` for a procurement notice. Open **供应商与合同关联** for its row and choose **下一步：选择合同**.

## Driving it with Playwright/pytest

Run `apps/frontend/tests/test_notice_association.py::test_real_two_step_association_and_uncertain_hint`. Open `[data-contract-notice="<id>"]`, scope to the named dialog, and select a radio in `.contract-candidates`. Check API readback after **确认关联**. Use `backend/tests/test_notice_association.py` for matching and save rules.

## Gotchas

Use the disposable preview and a notice with matching supplier evidence. An uncertain result requires **重读核对** before another write.
