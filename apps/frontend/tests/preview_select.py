"""Select only the open antd popup, including virtualized option lists."""
import re

from playwright.sync_api import TimeoutError


def reset_virtual_scroll(dropdown):
    # antd virtualizes long option lists: opening scrolled to the selected row
    # can leave earlier options unrendered, so reset whatever actually scrolls.
    dropdown.first.evaluate("""el => {
        const scroller = [...el.querySelectorAll('*')].find(
            n => n.clientHeight > 0 && n.scrollHeight > n.clientHeight + 1);
        if (scroller) scroller.scrollTop = 0;
    }""")


def open_popup(page, label):
    page.get_by_label(label, exact=True).click()
    # Only the open popup: closed antd dropdowns stay mounted in the DOM.
    dropdown = page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)')
    reset_virtual_scroll(dropdown)
    return dropdown.locator('.ant-select-item-option-content')


def pick_popup_option(page, text):
    dropdown = page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)')
    reset_virtual_scroll(dropdown)
    pattern = re.compile(f'^{re.escape(text)}$') if isinstance(text, str) else text
    options = dropdown.locator('.ant-select-item-option-content').filter(has_text=pattern)
    for attempt in range(2):
        try:
            options.click(timeout=6000)
            return
        except TimeoutError:
            if attempt or not dropdown.count():
                raise
            reset_virtual_scroll(dropdown)


def pick_option(page, label, text):
    open_popup(page, label)
    try:
        pick_popup_option(page, text)
    except TimeoutError:
        # Candidate refetches can close the popup while its options are changing.
        if page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden)').count():
            raise
        open_popup(page, label)
        pick_popup_option(page, text)
