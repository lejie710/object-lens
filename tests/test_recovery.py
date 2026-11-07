"""Controlled deadline and invalid-result failures, not observed real-model defects."""
from __future__ import annotations

import threading
from functools import partial
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from helpers import assert_no_visible_image, open_ready_page, result_labels, upload, wait_state
from serve import AppHandler


MODEL_FILE = "onnx/model_quantized.onnx"


def model_progress(loaded):
    return f"self.postMessage({{type: 'progress', status: 'progress', file: '{MODEL_FILE}', loaded: {loaded}, total: 100}});"


MODEL_DONE = f"self.postMessage({{type: 'progress', status: 'done', file: '{MODEL_FILE}'}});"

# Each first worker is a deliberate component simulation; retry gets the ordinary controlled worker.
FIRST_WORKERS = {
    # No loading event at all: the transfer watchdog must fire.
    "load-timeout": "self.onmessage = () => {};",
    # Two loading events, then silence: a stalled transfer.
    "load-stall": f"""
        self.onmessage = ({{data}}) => {{
            if (data.type !== 'load') return;
            {model_progress(10)}
            setTimeout(() => {{ {model_progress(20)} }}, 300);
        }};
    """,
    # Slow but steady transfer lasting longer than several stall windows, then ready.
    "slow-progress": f"""
        self.onmessage = ({{data}}) => {{
            if (data.type === 'infer') {{
                self.postMessage({{type: 'result', id: data.id, predictions: [
                    {{label: 'car', score: 0.94, box: {{xmin: 0.2, ymin: 0.3, xmax: 0.7, ymax: 0.8}}}}]}});
                return;
            }}
            if (data.type !== 'load') return;
            let loaded = 0;
            const timer = setInterval(() => {{
                loaded += 5;
                self.postMessage({{type: 'progress', status: 'progress', file: '{MODEL_FILE}', loaded, total: 100}});
                if (loaded >= 100) {{
                    clearInterval(timer);
                    {MODEL_DONE}
                    self.postMessage({{type: 'ready'}});
                }}
            }}, 250);
        }};
    """,
    # Every model byte arrives, then the library's silent Cache Storage write never finishes.
    "transfer-then-silence": f"""
        self.onmessage = ({{data}}) => {{
            if (data.type !== 'load') return;
            {model_progress(50)}
            setTimeout(() => {{ {model_progress(100)} }}, 300);
        }};
    """,
    # The model file finishes, then runtime initialization never reports ready.
    "init-hang": f"""
        self.onmessage = ({{data}}) => {{
            if (data.type !== 'load') return;
            {model_progress(100)}
            {MODEL_DONE}
            setInterval(() => self.postMessage({{type: 'progress', status: 'done', file: 'config.json'}}), 300);
        }};
    """,
    "infer-crash": """
        self.onmessage = ({data}) => {
            if (data.type === 'load') self.postMessage({type: 'ready'});
            if (data.type === 'infer') throw new Error('Controlled worker crash.');
        };
    """,
}

# Accelerate only the production loading deadlines in an isolated page. This exercises
# their callbacks and recovery wiring, not elapsed production time.
ACCELERATED_LOAD_DEADLINES = """
    const originalSetTimeout = window.setTimeout.bind(window);
    window.recoveryLoadDeadlines = [];
    const accelerated = {45000: 1500, 120000: 2500};
    window.setTimeout = (callback, delay, ...args) => {
        if (delay in accelerated) {
            window.recoveryLoadDeadlines.push(delay);
            return originalSetTimeout(callback, accelerated[delay], ...args);
        }
        return originalSetTimeout(callback, delay, ...args);
    };
"""


def open_with_accelerated_loading(browser, url):
    browser.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": ACCELERATED_LOAD_DEADLINES})
    browser.get(url)


@pytest.fixture
def recovery_server():
    """Only the first worker is broken; retry receives the ordinary controlled worker."""
    control = SimpleNamespace(mode="load-timeout", requests=0)

    class RecoveryHandler(AppHandler):
        def do_GET(self):
            if urlsplit(self.path).path == "/test-worker.js":
                control.requests += 1
                if control.requests == 1:
                    script = FIRST_WORKERS[control.mode].encode()
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
    # Ordinary controlled loading tests retain the full production load deadlines.
    open_with_accelerated_loading(browser, recovery_server.url)
    upload(browser, make_image("car.png"))
    wait_state(browser, "error")
    message = browser.find_element(By.ID, "error-message").text.lower()
    assert "model" in message and "stopped loading" in message and "connection" in message
    assert "another image" not in message
    assert browser.execute_script("return window.recoveryLoadDeadlines") == [45000]
    assert browser.find_element(By.ID, "image-preview").is_displayed()
    assert_no_results(browser)
    clear_and_restart(browser, make_image)
    assert recovery_server.requests == 2


def test_stalled_model_transfer_times_out_after_its_last_progress(browser, recovery_server, make_image):
    recovery_server.mode = "load-stall"
    open_with_accelerated_loading(browser, recovery_server.url)
    wait_state(browser, "error")
    message = browser.find_element(By.ID, "error-message").text.lower()
    assert "stopped loading" in message and "connection" in message and "try again" in message
    # The initial deadline plus one extension per progress event; initialization never started.
    assert browser.execute_script("return window.recoveryLoadDeadlines") == [45000, 45000, 45000]
    assert not browser.find_element(By.ID, "model-loading").is_displayed()
    clear_and_restart(browser, make_image)
    assert recovery_server.requests == 2


def test_slow_steady_model_transfer_is_not_timed_out(browser, recovery_server, make_image):
    # About five seconds of steady progress spans more than three accelerated stall windows.
    recovery_server.mode = "slow-progress"
    open_with_accelerated_loading(browser, recovery_server.url)
    wait_state(browser, "ready", timeout=20)
    deadlines = browser.execute_script("return window.recoveryLoadDeadlines")
    # The initial window and 19 partial events; the final bytes start initialization once.
    assert deadlines.count(45000) == 20 and deadlines.count(120000) == 1 and deadlines[-1] == 120000
    assert not browser.find_element(By.ID, "error-notice").is_displayed()
    upload(browser, make_image("car.png"))
    wait_state(browser, "complete")
    assert result_labels(browser) == ["car"]
    assert recovery_server.requests == 1


def test_completed_transfer_starts_initialization_before_the_done_event(browser, recovery_server, make_image):
    # Transformers.js stores the model in Cache Storage after the last byte and before
    # 'done'. That local write must not be reported as a stalled connection.
    recovery_server.mode = "transfer-then-silence"
    open_with_accelerated_loading(browser, recovery_server.url)
    wait_state(browser, "error")
    message = browser.find_element(By.ID, "error-message").text.lower()
    assert "too long to start" in message and "connection" not in message
    assert browser.execute_script("return window.recoveryLoadDeadlines") == [45000, 45000, 120000]
    clear_and_restart(browser, make_image)
    assert recovery_server.requests == 2


def test_clear_during_a_hung_analysis_restarts_quietly(app, make_image):
    # The controlled worker never answers silent.png; Clear removes that image first.
    upload(app, make_image("silent.png"))
    WebDriverWait(app, 5).until(lambda driver: driver.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "processing")
    app.find_element(By.ID, "clear-image").click()
    wait_state(app, "ready")
    WebDriverWait(app, 10, poll_frequency=0.2).until(lambda driver: any(
        "restarting a detector" in entry["message"] for entry in driver.get_log("browser")))
    wait_state(app, "ready")
    assert not app.find_element(By.ID, "error-notice").is_displayed()
    assert "analysis" not in app.find_element(By.ID, "status").text.lower()
    assert_no_visible_image(app)
    upload(app, make_image("car.png"))
    wait_state(app, "complete")
    assert result_labels(app) == ["car"]


def test_model_initialization_has_its_own_deadline(browser, recovery_server, make_image):
    recovery_server.mode = "init-hang"
    open_with_accelerated_loading(browser, recovery_server.url)
    wait_state(browser, "error")
    message = browser.find_element(By.ID, "error-message").text.lower()
    assert "too long to start" in message and "try again" in message
    assert "connection" not in message
    # Later settings-file events must not extend the initialization deadline.
    assert browser.execute_script("return window.recoveryLoadDeadlines") == [45000, 45000, 120000]
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
    open_ready_page(browser, recovery_server.url)
    upload(browser, make_image("car.png"))
    wait_state(browser, "error")
    message = browser.find_element(By.ID, "error-message").text.lower()
    assert "stopped unexpectedly" in message and "try again" in message
    assert "could not start" not in message
    assert_no_results(browser)
    clear_and_restart(browser, make_image)
    assert recovery_server.requests == 2


@pytest.mark.parametrize("kind", [
    "not-array", "null-item", "empty-label", "blank-label", "missing-box", "missing-coordinate", "string-coordinate",
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
