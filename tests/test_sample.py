"""Sample-image loading and recovery; model responses remain controlled."""
from __future__ import annotations

import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from helpers import (
    assert_for_late_response_window,
    assert_no_visible_image,
    result_labels,
    set_minimum,
    upload,
    wait_state,
)
from serve import AppHandler


@pytest.fixture
def sample_server():
    """Serve real sample bytes, with explicit one-shot failure/hold controls."""
    control = SimpleNamespace(
        requests=0,
        next_response="normal",
        hold_next=False,
        requested=threading.Event(),
        release=threading.Event(),
        sent=threading.Event(),
    )

    class ControlledSampleHandler(AppHandler):
        def do_GET(self):
            if urlsplit(self.path).path != "/samples/coffee.png":
                return super().do_GET()
            control.requests += 1
            held = control.hold_next
            control.hold_next = False
            response = control.next_response
            control.next_response = "normal"
            control.requested.set()
            if held and not control.release.wait(timeout=25):
                self.send_error(504, "Controlled sample response was not released")
                return
            try:
                if response != "normal":
                    content = b"Deliberately unavailable or unreadable sample image."
                    self.send_response(404 if response == "missing" else 200)
                    self.send_header("Content-Type", "image/png")
                    self.send_header("Content-Length", str(len(content)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(content)
                else:
                    super().do_GET()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                # Clear/replacement may abort the request; this is the tested path.
                pass
            finally:
                if held:
                    control.sent.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(ControlledSampleHandler, test_mode=True))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    control.url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield control
    finally:
        control.release.set()
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


def open_sample_app(browser, sample_server):
    browser.get(sample_server.url)
    wait_state(browser, "ready")


def test_try_sample_fetches_the_real_photo_and_resets_the_previous_filter(browser, sample_server, make_image):
    open_sample_app(browser, sample_server)
    upload(browser, make_image("score-boundary.png"))
    wait_state(browser, "complete")
    set_minimum(browser, 0.80)
    browser.find_element(By.ID, "try-sample").click()
    wait_state(browser, "complete")
    assert sample_server.requests == 1
    assert browser.find_element(By.ID, "filename").text == "coffee.png"
    assert browser.find_element(By.ID, "image-dimensions").text == "600 × 400"
    assert result_labels(browser) == ["laptop", "cup"]  # Explicit controlled-worker output.
    assert float(browser.find_element(By.ID, "minimum-score").get_attribute("value")) == 0.50
    assert browser.find_element(By.ID, "try-sample").is_enabled()


@pytest.mark.parametrize("response", ["missing", "unreadable"])
def test_sample_fetch_or_decode_failure_can_be_retried(browser, sample_server, response):
    open_sample_app(browser, sample_server)
    sample_server.next_response = response
    browser.find_element(By.ID, "try-sample").click()
    wait_state(browser, "error")
    assert browser.find_element(By.ID, "error-message").is_displayed()
    assert browser.find_element(By.ID, "error-message").text.strip()
    assert_no_visible_image(browser)
    assert browser.find_element(By.ID, "try-sample").is_enabled()
    browser.find_element(By.ID, "try-sample").click()
    wait_state(browser, "complete")
    assert sample_server.requests == 2
    assert browser.find_element(By.ID, "filename").text == "coffee.png"
    assert result_labels(browser) == ["laptop", "cup"]
    assert not browser.find_element(By.ID, "error-message").is_displayed()


@pytest.mark.parametrize("action", ["clear", "upload"])
def test_late_sample_response_cannot_override_a_later_user_action(browser, sample_server, make_image, action):
    open_sample_app(browser, sample_server)
    sample_server.hold_next = True
    button = browser.find_element(By.ID, "try-sample")
    button.click()
    assert sample_server.requested.wait(timeout=5), "No sample request reached the local server"
    assert not button.is_enabled()
    assert "Loading sample" in button.text
    if action == "clear":
        browser.find_element(By.ID, "clear-image").click()
        wait_state(browser, "ready")
    else:
        upload(browser, make_image("car.png"))
        wait_state(browser, "complete")
    sample_server.release.set()
    assert sample_server.sent.wait(timeout=5), "The deliberately held response was not released"

    def latest_action_still_wins(driver):
        assert driver.find_element(By.ID, "try-sample").is_enabled()
        assert sample_server.requests == 1
        if action == "clear":
            assert_no_visible_image(driver)
            assert driver.find_element(By.ID, "filename").text == "No image selected"
        else:
            assert driver.find_element(By.ID, "filename").text == "car.png"
            assert result_labels(driver) == ["car"]

    # The late event here is the released sample fetch, not a worker reply: keep the full window.
    assert_for_late_response_window(browser, latest_action_still_wins, hold=1.4)


def test_try_sample_is_keyboard_reachable_and_activates_with_enter(browser, sample_server):
    open_sample_app(browser, sample_server)
    button = browser.find_element(By.ID, "try-sample")
    assert "sample" in button.accessible_name.lower()
    for _ in range(20):
        active = browser.switch_to.active_element
        if active.get_attribute("id") == "try-sample":
            break
        active.send_keys(Keys.TAB)
    else:
        pytest.fail("Try sample was not reachable in the keyboard tab order")
    browser.switch_to.active_element.send_keys(Keys.ENTER)
    wait_state(browser, "complete")
    assert sample_server.requests == 1
    assert browser.find_element(By.ID, "filename").text == "coffee.png"


def test_nonresponding_sample_fetch_times_out_and_a_new_attempt_recovers(browser, sample_server):
    # Keep the HTTP response pending beyond the real 15-second fetch deadline.
    # No application timer is replaced or shortened for this check.
    open_sample_app(browser, sample_server)
    sample_server.hold_next = True
    started = time.monotonic()
    browser.find_element(By.ID, "try-sample").click()
    assert sample_server.requested.wait(timeout=5), "No sample request reached the local server"
    wait_state(browser, "error", timeout=30)
    assert time.monotonic() - started >= 14, "Sample failed before the intended timeout window"
    message = browser.find_element(By.ID, "error-message").text.lower()
    assert "sample" in message and "too long" in message
    assert_no_visible_image(browser)
    assert browser.find_element(By.ID, "try-sample").is_enabled()
    sample_server.release.set()
    assert sample_server.sent.wait(timeout=5), "The deliberately held response was not released"
    browser.find_element(By.ID, "try-sample").click()
    wait_state(browser, "complete")
    assert sample_server.requests == 2
    assert browser.find_element(By.ID, "filename").text == "coffee.png"
    assert result_labels(browser) == ["laptop", "cup"]
    assert not browser.find_element(By.ID, "error-message").is_displayed()
