"""Shared assertion helpers must say what failed, without a browser."""
from __future__ import annotations

import pytest

import helpers


class _DisplayedElement:
    def is_displayed(self):
        return True


class _BrowserShowingAnImage:
    def find_element(self, by, value):
        return _DisplayedElement()


def test_helper_assertion_failure_names_the_failed_check():
    # pytest only explains assertions in modules it rewrites. A helper failure must
    # name its check: the deliberate-fault runner matches that text, and a bare
    # AssertionError hides which invariant broke.
    with pytest.raises(AssertionError) as failure:
        helpers.assert_no_visible_image(_BrowserShowingAnImage())
    assert "is_displayed" in str(failure.value)
