"""Read old printer settings without changing device or writing the live environment."""

from types import SimpleNamespace

import pytest

from app.core.errors import MustReportError
from app.mod03_notice import router, settings_store
from app.mod03_notice.schemas import PrinterSettingRequest


@pytest.mark.parametrize("old", ["driver", "raw"])
def test_legacy_channel_requires_explicit_switch(tmp_path, monkeypatch, old):
    path = tmp_path / ".env"
    before = f"PRINT_MODE={old}\nPRINTER_NAME=old device\nPRINTER_IPP_URL=ipp://old\nOTHER=retained\n"
    path.write_text(before, encoding="utf-8")
    settings = SimpleNamespace(print_mode=old, printer_ipp_url="ipp://old")
    monkeypatch.setattr(router, "get_settings", lambda: settings)
    monkeypatch.setenv("PRINT_MODE", old)
    settings_store.get_settings.cache_clear()
    monkeypatch.setattr(settings_store, "ENV_FILE", path)
    try:
        assert router.get_printer_setting().model_dump() == {"printer_ipp_url": "ipp://old", "print_mode": old, "printer_name": ""}
        for request in (None, "", "  ", "auto", old):
            with pytest.raises(MustReportError, match="改用 IPP，或导出 PDF"):
                router.set_printer_setting(PrinterSettingRequest(printer_ipp_url="ipp://new", print_mode=request))
            assert path.read_text(encoding="utf-8") == before

        updated = router.set_printer_setting(PrinterSettingRequest.model_validate(
            {"printer_ipp_url": "ipp://new", "print_mode": "ipp", "printer_name": "old client device"}
        ))
        assert updated.model_dump() == {"printer_ipp_url": "ipp://new", "print_mode": "ipp", "printer_name": ""}
        assert path.read_text(encoding="utf-8") == before.replace(f"PRINT_MODE={old}", "PRINT_MODE=ipp").replace("ipp://old", "ipp://new")
    finally:
        settings_store.get_settings.cache_clear()
