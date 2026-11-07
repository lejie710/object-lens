"""Shared test helpers checked without a browser: assertion messages and the page-load guard."""
from __future__ import annotations

import json

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


class _State:
    def __init__(self, value):
        self.value = value

    def get_attribute(self, name):
        return self.value


def _failed_request(index, url, error):
    """The two Chrome network-log events for a request that failed in transport.

    Real Chrome reports a worker script whose connection failed as canceled
    net::ERR_ABORTED (docs/evidence/history/worker-load-probe.json).
    """
    sent = {"method": "Network.requestWillBeSent", "params": {"requestId": str(index), "request": {"url": url}}}
    failed = {"method": "Network.loadingFailed",
              "params": {"requestId": str(index), "errorText": error, "canceled": True}}
    return [{"message": json.dumps({"message": event})} for event in (sent, failed)]


class _LoadingBrowser:
    """Each load shows its own page state, console and network log; nothing real is opened.

    Like Chrome, reading a log returns its entries once and then drains it.
    """

    def __init__(self, *loads):
        self.loads = [(*load, [])[:3] for load in loads]
        self.opened = []
        self.read = set()

    def get(self, url):
        self.opened.append(url)

    def _opened(self):
        self.get("http://app")
        return self

    def _current(self):
        return self.loads[len(self.opened) - 1]

    def find_element(self, by, value):
        return _State(self._current()[0])

    def get_log(self, kind):
        key = (len(self.opened), kind)
        if key in self.read:
            return []
        self.read.add(key)
        return self._current()[1] if kind == "browser" else self._current()[2]

    def execute_script(self, script):
        return ["index.html", "app.js"]


RUNNER_ERROR = [{"level": "SEVERE", "message": "png-export.js - Failed to load resource: net::ERR_NO_BUFFER_SPACE"}]
OTHER_ERROR = [{"level": "SEVERE", "message": "app.js - Uncaught SyntaxError"}]
# The app's only console line when its worker script cannot be loaded, whatever the cause.
WORKER_LOAD_ERROR = [{"level": "SEVERE", "message": 'app.js 665:14 "Object Lens worker:" undefined'}]
DROPPED_WORKER = _failed_request(1, "http://app/test-worker.js", "net::ERR_ABORTED")


def test_ready_page_is_not_reloaded():
    browser = _LoadingBrowser(("ready", []))
    assert helpers.open_ready_page(browser, "http://app", timeout=0.1) is browser
    assert browser.opened == ["http://app"]


def test_runner_network_error_earns_one_reload():
    browser = _LoadingBrowser(("error", RUNNER_ERROR), ("ready", []))
    with pytest.warns(UserWarning, match="Reloaded the page once"):
        helpers.open_ready_page(browser, "http://app", timeout=0.1)
    assert browser.opened == ["http://app", "http://app"]


def test_worker_script_transport_failure_earns_one_reload():
    browser = _LoadingBrowser(("error", WORKER_LOAD_ERROR, DROPPED_WORKER), ("ready", []))
    with pytest.warns(UserWarning, match=r"test-worker\.js.*net::ERR_ABORTED"):
        helpers.open_ready_page(browser, "http://app", timeout=0.1)
    assert browser.opened == ["http://app", "http://app"]


def test_runner_network_error_in_the_network_log_earns_one_reload():
    network = _failed_request(1, "http://app/png-export.js", helpers.RUNNER_NETWORK_ERROR)
    browser = _LoadingBrowser(("error", [], network), ("ready", []))
    with pytest.warns(UserWarning, match=r"png-export\.js.*ERR_NO_BUFFER_SPACE"):
        helpers.open_ready_page(browser, "http://app", timeout=0.1)
    assert browser.opened == ["http://app", "http://app"]


@pytest.mark.parametrize("console, network", [
    (OTHER_ERROR, []),
    # A worker script answered with an HTTP error is not a transport failure.
    (WORKER_LOAD_ERROR, []),
    # A transport failure of a file other than a worker script needs the runner's error code.
    (OTHER_ERROR, _failed_request(1, "http://app/app.js", "net::ERR_ABORTED")),
], ids=["script-error", "worker-http-error", "other-file-aborted"])
def test_any_other_load_failure_fails_at_once_and_reports_it(console, network):
    browser = _LoadingBrowser(("error", console, network), ("ready", []))
    with pytest.raises(pytest.fail.Exception, match="within 0.1 s") as failure:
        helpers.open_ready_page(browser, "http://app", timeout=0.1)
    assert console[0]["message"] in str(failure.value)
    assert browser.opened == ["http://app"]


def test_a_page_still_broken_after_the_reload_fails():
    browser = _LoadingBrowser(("error", RUNNER_ERROR), ("error", RUNNER_ERROR))
    with pytest.warns(UserWarning), pytest.raises(pytest.fail.Exception, match="after one reload"):
        helpers.open_ready_page(browser, "http://app", timeout=0.1)
    assert browser.opened == ["http://app", "http://app"]


def test_failure_evidence_keeps_the_logs_the_guard_read():
    browser = _LoadingBrowser(("error", WORKER_LOAD_ERROR, DROPPED_WORKER), ("error", WORKER_LOAD_ERROR, DROPPED_WORKER))
    with pytest.warns(UserWarning), pytest.raises(pytest.fail.Exception):
        helpers.open_ready_page(browser, "http://app", timeout=0.1)
    # Chrome has drained both logs; the evidence must still hold both loads' entries.
    logs = helpers.kept_logs(browser)
    assert [entry["message"] for entry in logs["console"]] == [WORKER_LOAD_ERROR[0]["message"]] * 2
    assert [failure["file"] for failure in logs["network"]] == ["test-worker.js"] * 2


def test_a_request_that_fails_after_an_earlier_read_is_still_named():
    sent, failed = _failed_request(1, "http://app/test-worker.js?v=1", "net::ERR_ABORTED")
    browser = _LoadingBrowser(("loading", [], [sent]))
    browser.get("http://app")
    assert helpers.network_failures(browser) == []  # Only the request has been logged so far.
    browser.loads[0] = ("error", [], [failed])
    browser.read.clear()
    assert helpers.network_failures(browser) == [
        {"file": "test-worker.js", "error": "net::ERR_ABORTED", "canceled": True}]


def _lone_failure(error):
    """A failed request whose start was never logged, so its address is unknown."""
    event = {"method": "Network.loadingFailed", "params": {"requestId": "7", "errorText": error, "canceled": True}}
    return [{"message": json.dumps({"message": event})}]


@pytest.mark.parametrize("error, reloads", [("net::ERR_ABORTED", False), (helpers.RUNNER_NETWORK_ERROR, True)])
def test_an_unnamed_failed_request_is_reported_and_only_the_runner_error_reloads(error, reloads):
    assert helpers.network_failures(_LoadingBrowser(("error", [], _lone_failure(error)))._opened()) == [
        {"file": "<request 7>", "error": error, "canceled": True}]
    browser = _LoadingBrowser(("error", OTHER_ERROR, _lone_failure(error)), ("ready", []))
    if reloads:
        with pytest.warns(UserWarning, match="Reloaded the page once"):
            helpers.open_ready_page(browser, "http://app", timeout=0.1)
        assert browser.opened == ["http://app", "http://app"]
    else:
        with pytest.raises(pytest.fail.Exception, match="<request 7>"):
            helpers.open_ready_page(browser, "http://app", timeout=0.1)
        assert browser.opened == ["http://app"]
