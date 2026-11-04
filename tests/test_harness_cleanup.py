"""Failure-injection checks for browser cleanup; no Chrome process is launched."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import conftest


def browser_fixture(monkeypatch):
    driver = Mock()
    root = Path("controlled-harness-evidence")
    monkeypatch.setattr(conftest.webdriver, "Chrome", lambda **_kwargs: driver)
    monkeypatch.setattr(conftest, "ROOT", root)
    monkeypatch.setenv("SE_CACHE_PATH", str(root / "selenium"))
    monkeypatch.setenv("SE_AVOID_STATS", "true")
    node = SimpleNamespace(
        nodeid="cleanup-check", keywords={}, rep_setup=None,
        rep_call=SimpleNamespace(failed=True),
    )
    # Exercise the actual fixture body, including its setup and teardown paths.
    return driver, conftest.browser.__wrapped__(SimpleNamespace(node=node))


def test_browser_closes_when_failure_evidence_directory_cannot_be_created(monkeypatch, caplog):
    driver, fixture = browser_fixture(monkeypatch)
    assert next(fixture) is driver
    monkeypatch.setattr(Path, "mkdir", Mock(side_effect=PermissionError("Evidence directory denied")))
    monkeypatch.setattr(Path, "write_text", Mock(side_effect=FileNotFoundError("No evidence directory")))

    with pytest.raises(StopIteration):
        next(fixture)

    driver.quit.assert_called_once_with()
    assert "Could not capture failure evidence" in caplog.text
    assert "Evidence directory denied" in caplog.text


def test_browser_closes_when_screenshot_and_fallback_evidence_both_fail(monkeypatch, caplog):
    driver, fixture = browser_fixture(monkeypatch)
    assert next(fixture) is driver
    driver.save_screenshot.side_effect = RuntimeError("Screenshot unavailable")
    monkeypatch.setattr(Path, "mkdir", Mock())
    monkeypatch.setattr(Path, "write_text", Mock(side_effect=OSError("Evidence write failed")))

    with pytest.raises(StopIteration):
        next(fixture)

    driver.quit.assert_called_once_with()
    assert "Screenshot unavailable" in caplog.text
    assert "Could not write capture-error.txt" in caplog.text
    assert "Evidence write failed" in caplog.text


def test_browser_closes_when_timeout_setup_fails(monkeypatch):
    driver, fixture = browser_fixture(monkeypatch)
    driver.set_page_load_timeout.side_effect = RuntimeError("Timeout setup failed")

    with pytest.raises(RuntimeError, match="Timeout setup failed"):
        next(fixture)

    driver.quit.assert_called_once_with()
