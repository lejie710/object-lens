"""Configuration startup races and recovery with real local HTTP responses.

The existing controlled worker supplies predictions; these are not accuracy tests.
"""
from __future__ import annotations

import json
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from serve import AppHandler
from test_ui import result_labels, upload, wait_state


@pytest.fixture
def startup_server():
    """Hold only the first configuration response, before headers or mid-body."""
    normal_payload = json.dumps({"testMode": True}).encode("utf-8")
    control = SimpleNamespace(
        requests=0,
        worker_requests=0,
        first_worker_error=False,
        hold_mode="headers",
        first_payload=normal_payload,
        requested=threading.Event(),
        release=threading.Event(),
        sent=threading.Event(),
        requested_at=None,
    )
    request_lock = threading.Lock()

    class StartupHandler(AppHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/test-worker.js":
                with request_lock:
                    control.worker_requests += 1
                    fail_worker = control.first_worker_error and control.worker_requests == 1
                if fail_worker:
                    script = b"""
                        // Deliberately controlled startup failure; no model is loaded.
                        self.onmessage = ({data}) => {
                            if (data.type === 'load') self.postMessage({type: 'error',
                                stage: 'load', message: 'Controlled first-worker startup failure.'});
                        };
                    """
                    self.send_response(200)
                    self.send_header("Content-Type", "text/javascript")
                    self.send_header("Content-Length", str(len(script)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(script)
                    return
                return super().do_GET()
            if path != "/runtime-config.json":
                return super().do_GET()

            with request_lock:
                control.requests += 1
                first = control.requests == 1
            payload = control.first_payload if first else normal_payload
            mode = control.hold_mode if first else None
            try:
                if mode == "headers":
                    control.requested_at = time.monotonic()
                    control.requested.set()
                    if not control.release.wait(timeout=45):
                        self.send_error(504, "Controlled configuration was not released")
                        return

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                if mode == "body":
                    split = max(1, len(payload) // 2)
                    self.wfile.write(payload[:split])
                    self.wfile.flush()
                    control.requested_at = time.monotonic()
                    control.requested.set()
                    if not control.release.wait(timeout=45):
                        return
                    self.wfile.write(payload[split:])
                else:
                    self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                # The application's deadline deliberately aborts the held response.
                pass
            finally:
                if first:
                    control.sent.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(StartupHandler, test_mode=True))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    control.url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield control
    finally:
        control.release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def open_with_held_configuration(browser, startup_server):
    browser.get(startup_server.url)
    assert startup_server.requested.wait(timeout=5), "Configuration request did not reach its hold point"
    assert startup_server.worker_requests == 0, "Worker started before configuration was available"


def wait_for_worker_ready(browser):
    # This observes actual worker readiness even when an input error must stay visible.
    WebDriverWait(browser, 5, poll_frequency=0.05).until(
        lambda driver: not driver.find_element(By.ID, "model-loading").is_displayed(),
        message="The controlled worker did not finish startup after configuration was released",
    )


def assert_car_result(browser):
    wait_state(browser, "complete")
    assert browser.find_element(By.ID, "filename").text == "car.png"
    assert result_labels(browser) == ["car"]
    assert browser.find_element(By.ID, "test-mode-notice").is_displayed()
    assert not browser.find_element(By.ID, "error-message").is_displayed()


def hold_car_file_read(browser):
    browser.execute_script("""
        window.startupOriginalArrayBuffer = File.prototype.arrayBuffer;
        File.prototype.arrayBuffer = function(...args) {
            if (this.name !== 'car.png') {
                return window.startupOriginalArrayBuffer.apply(this, args);
            }
            const file = this;
            return new Promise((resolve, reject) => {
                window.startupReleaseRead = () =>
                    window.startupOriginalArrayBuffer.apply(file, args).then(resolve, reject);
            });
        };
    """)


def wait_for_held_file_read(browser):
    WebDriverWait(browser, 5, poll_frequency=0.05).until(
        lambda driver: driver.execute_script("return typeof window.startupReleaseRead === 'function'"),
        message="The selected file did not enter the controlled arrayBuffer hold",
    )


def release_file_read(browser):
    browser.execute_script("""
        File.prototype.arrayBuffer = window.startupOriginalArrayBuffer;
        const release = window.startupReleaseRead;
        delete window.startupReleaseRead;
        if (release) release();
    """)


def test_configuration_completion_preserves_an_existing_input_error(
    browser, startup_server, make_image, tmp_path,
):
    open_with_held_configuration(browser, startup_server)
    invalid = tmp_path / "unsupported.txt"
    invalid.write_bytes(b"Deliberately unsupported image input.")
    upload(browser, invalid)
    wait_state(browser, "error")
    message = browser.find_element(By.ID, "error-message").text
    assert message, "Invalid input did not provide an explanation"

    startup_server.release.set()
    wait_for_worker_ready(browser)
    assert browser.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "error"
    assert browser.find_element(By.ID, "error-message").is_displayed()
    assert browser.find_element(By.ID, "error-message").text == message
    assert browser.find_element(By.ID, "status").text == "Action needed"

    browser.find_element(By.ID, "clear-image").click()
    wait_state(browser, "ready")
    upload(browser, make_image("car.png"))
    assert_car_result(browser)


def test_worker_ready_preserves_in_progress_file_preparation(browser, startup_server, make_image):
    open_with_held_configuration(browser, startup_server)
    hold_car_file_read(browser)
    try:
        upload(browser, make_image("car.png"))
        wait_for_held_file_read(browser)
        assert browser.find_element(By.ID, "status").text == "Reading image…"
        startup_server.release.set()
        wait_for_worker_ready(browser)
        assert browser.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "loading"
        assert browser.find_element(By.ID, "status").text == "Reading image…"
        assert not browser.find_element(By.ID, "error-message").is_displayed()
    finally:
        release_file_read(browser)
    assert_car_result(browser)


def test_worker_retry_restores_status_while_file_preparation_is_pending(
    browser, startup_server, make_image,
):
    startup_server.first_worker_error = True
    open_with_held_configuration(browser, startup_server)
    hold_car_file_read(browser)
    try:
        upload(browser, make_image("car.png"))
        wait_for_held_file_read(browser)
        startup_server.release.set()
        wait_state(browser, "error")
        assert startup_server.worker_requests == 1
        assert browser.find_element(By.ID, "error-message").is_displayed()
        assert browser.find_element(By.ID, "retry-detection").is_displayed()

        browser.find_element(By.ID, "retry-detection").click()
        wait_for_worker_ready(browser)
        assert startup_server.worker_requests == 2, "Retry did not load a replacement controlled worker"
        assert startup_server.requests == 1, "A worker failure must not discard valid configuration"
        assert browser.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "loading"
        assert browser.find_element(By.ID, "status").text == "Reading image…"
        assert not browser.find_element(By.ID, "error-message").is_displayed()
    finally:
        release_file_read(browser)
    assert_car_result(browser)


@pytest.mark.parametrize("hold_mode", ["headers", "body"])
def test_stalled_configuration_times_out_and_retry_fetches_it_again(
    browser, startup_server, make_image, hold_mode,
):
    startup_server.hold_mode = hold_mode
    open_with_held_configuration(browser, startup_server)
    upload(browser, make_image("car.png"))
    WebDriverWait(browser, 5, poll_frequency=0.05).until(
        lambda driver: driver.find_element(By.ID, "filename").text == "car.png",
        message="A valid selected image was not prepared while configuration was pending",
    )
    assert browser.find_element(By.ID, "image-preview").is_displayed()
    assert startup_server.worker_requests == 0

    # Exercise the real 15-second configuration deadline without changing timers.
    wait_state(browser, "error", timeout=20)
    assert time.monotonic() - startup_server.requested_at >= 14, "Configuration failed before its deadline"
    assert "too long" in browser.find_element(By.ID, "error-message").text.lower()
    assert browser.find_element(By.ID, "retry-detection").is_displayed()
    assert browser.find_element(By.ID, "filename").text == "car.png"
    assert browser.find_element(By.ID, "image-preview").is_displayed()
    assert result_labels(browser) == []
    assert not browser.find_element(By.ID, "model-loading").is_displayed()

    startup_server.release.set()
    assert startup_server.sent.wait(timeout=5), "The retired configuration response was not released"
    browser.find_element(By.ID, "retry-detection").click()
    assert_car_result(browser)
    assert startup_server.requests == 2, "Retry must fetch configuration before choosing the worker"
    assert startup_server.worker_requests == 1


def test_invalid_configuration_can_be_refetched_without_losing_the_image(
    browser, startup_server, make_image,
):
    startup_server.first_payload = b"null"
    open_with_held_configuration(browser, startup_server)
    upload(browser, make_image("car.png"))
    WebDriverWait(browser, 5, poll_frequency=0.05).until(
        lambda driver: driver.find_element(By.ID, "filename").text == "car.png",
        message="The chosen image did not finish preparation before configuration was released",
    )
    startup_server.release.set()
    wait_state(browser, "error")
    assert browser.find_element(By.ID, "error-message").text.strip()
    assert browser.find_element(By.ID, "retry-detection").is_displayed()
    assert startup_server.worker_requests == 0, "Invalid configuration must not select a worker mode"
    browser.find_element(By.ID, "retry-detection").click()
    assert_car_result(browser)
    assert startup_server.requests == 2
    assert startup_server.worker_requests == 1
