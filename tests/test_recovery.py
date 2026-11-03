"""Controlled deadline and invalid-result failures, not observed real-model defects."""
from __future__ import annotations

import threading
from functools import partial
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from selenium.webdriver.common.by import By

from serve import AppHandler
from test_ui import assert_no_visible_image, result_labels, upload, wait_state


@pytest.fixture
def recovery_server():
    """Only the first worker is broken; retry receives the ordinary controlled worker."""
    control = SimpleNamespace(mode="load-timeout", requests=0)

    class RecoveryHandler(AppHandler):
        def do_GET(self):
            if urlsplit(self.path).path == "/test-worker.js":
                control.requests += 1
                if control.requests == 1:
                    script = (b"self.onmessage = () => {};" if control.mode == "load-timeout" else b"""
                        self.onmessage = ({data}) => {
                            if (data.type === 'load') self.postMessage({type: 'ready'});
                            if (data.type === 'infer') throw new Error('Controlled worker crash.');
                        };
                    """)
                    self.send_response(200)
                    self.send_header("Content-Type", "text/javascript")
                    self.send_header("Content-Length", str(len(script)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(script)
                    return
            super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(RecoveryHandler, test_mode=True))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    control.url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield control
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def assert_no_results(browser):
    assert result_labels(browser) == []
    assert browser.find_elements(By.CSS_SELECTOR, ".detection-box") == []
    assert browser.find_element(By.ID, "result-count").text == "0"
    assert not browser.find_element(By.ID, "minimum-score").is_enabled()
    assert not browser.find_element(By.ID, "save-result").is_enabled()
    assert browser.find_element(By.ID, "image-stage").get_attribute("aria-busy") == "false"


def clear_and_restart(browser, make_image):
    browser.find_element(By.ID, "clear-image").click()
    wait_state(browser, "error")
    assert_no_visible_image(browser)
    assert_no_results(browser)
    message = browser.find_element(By.ID, "error-message").text.lower()
    assert "unavailable" in message and "try again" in message and "restart" in message
    assert "could not start" not in message
    assert browser.find_element(By.ID, "status").text == "Action needed"
    assert not browser.find_element(By.ID, "model-loading").is_displayed()
    assert browser.find_element(By.ID, "retry-detection").is_displayed()

    browser.find_element(By.ID, "retry-detection").click()
    wait_state(browser, "ready")
    assert "ready" in browser.find_element(By.ID, "status").text.lower()
    assert not browser.find_element(By.ID, "error-notice").is_displayed()
    upload(browser, make_image("car.png"))
    wait_state(browser, "complete")
    assert result_labels(browser) == ["car"]
    assert browser.find_element(By.CSS_SELECTOR, ".object-name").text == "car"


def test_model_load_timeout_clear_and_retry_describe_detector_availability(
    browser, recovery_server, make_image,
):
    # Accelerate only the production 120-second load deadline in this isolated page.
    # This exercises its callback and recovery wiring, not elapsed production time.
    # Ordinary controlled loading tests retain the full production load deadline.
    browser.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
        const originalSetTimeout = window.setTimeout.bind(window);
        window.recoveryLoadDeadlines = [];
        window.setTimeout = (callback, delay, ...args) => {
            if (delay === 120000) {
                window.recoveryLoadDeadlines.push(delay);
                return originalSetTimeout(callback, 2500, ...args);
            }
            return originalSetTimeout(callback, delay, ...args);
        };
    """})
    browser.get(recovery_server.url)
    upload(browser, make_image("car.png"))
    wait_state(browser, "error")
    message = browser.find_element(By.ID, "error-message").text.lower()
    assert "model" in message and "too long" in message and "load" in message
    assert "another image" not in message
    assert browser.execute_script("return window.recoveryLoadDeadlines") == [120000]
    assert browser.find_element(By.ID, "image-preview").is_displayed()
    assert_no_results(browser)
    clear_and_restart(browser, make_image)
    assert recovery_server.requests == 2


def test_inference_timeout_clear_and_retry_describe_detector_availability(app, make_image):
    upload(app, make_image("silent.png"))
    wait_state(app, "error")
    message = app.find_element(By.ID, "error-message").text.lower()
    assert "image" in message and "too long" in message and "analysis" in message
    assert "load" not in message and "could not start" not in message
    assert_no_results(app)
    clear_and_restart(app, make_image)


def test_worker_crash_during_inference_is_not_described_as_startup_failure(
    browser, recovery_server, make_image,
):
    recovery_server.mode = "infer-crash"
    browser.get(recovery_server.url)
    wait_state(browser, "ready")
    upload(browser, make_image("car.png"))
    wait_state(browser, "error")
    message = browser.find_element(By.ID, "error-message").text.lower()
    assert "stopped unexpectedly" in message and "try again" in message
    assert "could not start" not in message
    assert_no_results(browser)
    clear_and_restart(browser, make_image)
    assert recovery_server.requests == 2


@pytest.mark.parametrize("kind", [
    "not-array", "null-item", "missing-box", "missing-coordinate", "string-coordinate",
    "nonfinite-coordinate", "missing-score", "string-score", "nonfinite-score",
    "negative-score", "excess-score", "reversed-box", "zero-area-box", "outside-box",
])
def test_malformed_result_is_rejected_without_partial_detections_and_recovers(app, make_image, kind):
    upload(app, make_image(f"invalid-result-{kind}.png"))
    wait_state(app, "error")
    message = app.find_element(By.ID, "error-message").text.lower()
    assert "invalid result" in message and "try again" in message
    assert app.find_element(By.ID, "retry-detection").is_displayed()
    assert app.find_element(By.ID, "image-preview").is_displayed()
    assert_no_results(app)

    upload(app, make_image("car.png"))
    wait_state(app, "complete")
    assert result_labels(app) == ["car"]
    assert app.find_element(By.CSS_SELECTOR, ".object-name").text == "car"
    assert not app.find_element(By.ID, "error-notice").is_displayed()


def test_retry_after_a_transient_invalid_result_reanalyzes_the_same_image(app, make_image):
    upload(app, make_image("invalid-once.png"))
    wait_state(app, "error")
    assert_no_results(app)
    app.find_element(By.ID, "retry-detection").click()
    wait_state(app, "complete")
    assert app.find_element(By.ID, "filename").text == "invalid-once.png"
    assert result_labels(app) == ["laptop", "cup"]
    assert not app.find_element(By.ID, "error-notice").is_displayed()


def test_partially_outside_box_is_clamped_to_the_rendered_image(app, make_image):
    upload(app, make_image("clamped-box.png"))
    wait_state(app, "complete")
    assert result_labels(app) == ["laptop"]
    assert not app.find_element(By.ID, "error-notice").is_displayed()
    box = app.find_element(By.CSS_SELECTOR, ".detection-box")
    for key, expected in {"xmin": 0, "ymin": 0, "xmax": 1, "ymax": 0.85}.items():
        assert float(box.get_attribute(f"data-{key}")) == expected
    image = app.find_element(By.ID, "image-preview").rect
    rectangle = box.rect
    assert rectangle["x"] == pytest.approx(image["x"], abs=2)
    assert rectangle["y"] == pytest.approx(image["y"], abs=2)
    assert rectangle["width"] == pytest.approx(image["width"], abs=2)
    assert rectangle["height"] == pytest.approx(image["height"] * 0.85, abs=2)
