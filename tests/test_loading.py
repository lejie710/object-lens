"""Model-startup feedback with explicit controlled events, not download-speed evidence."""
from __future__ import annotations

import json
import queue
import threading
from collections import defaultdict
from functools import partial
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from serve import AppHandler
from test_ui import upload, wait_state


@pytest.fixture
def loading_server():
    """Control each worker's startup events without loading the actual AI model."""
    control = SimpleNamespace(requests=0, messages=defaultdict(queue.Queue))

    class LoadingHandler(AppHandler):
        def do_GET(self):
            path = urlsplit(self.path).path
            if path == "/test-worker.js":
                control.requests += 1
                script = """
                    const instance = INSTANCE;
                    self.onmessage = async ({data}) => {
                        if (data.type === 'infer') {
                            self.postMessage({type: 'result', id: data.id, predictions: []});
                            return;
                        }
                        if (data.type !== 'load') return;
                        while (true) {
                            const response = await fetch('./loading-events/' + instance);
                            const event = await response.json();
                            if (event.type === 'idle') continue;
                            self.postMessage(event);
                            if (event.type === 'ready' || event.type === 'error') return;
                        }
                    };
                """.replace("INSTANCE", str(control.requests))
                return self.send_content(script.encode("utf-8"), "text/javascript")
            if path.startswith("/loading-events/"):
                instance = int(path.rsplit("/", 1)[1])
                try:
                    event = control.messages[instance].get(timeout=0.25)
                except queue.Empty:
                    event = {"type": "idle"}
                return self.send_content(json.dumps(event).encode("utf-8"), "application/json")
            return super().do_GET()

        def send_content(self, content, content_type):
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                # Retired workers intentionally abandon any outstanding event request.
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(LoadingHandler, test_mode=True))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    control.url = f"http://127.0.0.1:{server.server_port}"
    try:
        yield control
    finally:
        for messages in list(control.messages.values()):
            messages.put({"type": "ready"})
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def model_event(status="progress", loaded=None, total=None):
    return {"type": "progress", "status": status, "file": "onnx/model_quantized.onnx",
            "loaded": loaded, "total": total}


def wait_progress(browser, value):
    def matches(driver):
        actual = driver.find_element(By.ID, "model-loading-progress").get_dom_attribute("value")
        return actual is None if value is None else actual is not None and float(actual) == pytest.approx(value)

    WebDriverWait(browser, 5, poll_frequency=0.05).until(matches)


def wait_phase(browser, phase):
    WebDriverWait(browser, 5, poll_frequency=0.05).until(
        lambda driver: driver.find_element(By.ID, "model-loading").get_attribute("data-phase") == phase
    )


def test_model_bytes_complete_before_runtime_is_ready(browser, loading_server):
    loading_server.messages[1].put(model_event(loaded=10_000_000, total=40_000_000))
    browser.get(loading_server.url)
    wait_phase(browser, "downloading")
    wait_progress(browser, 25)
    notice = browser.find_element(By.ID, "model-loading")
    assert notice.is_displayed()
    assert "43 MB" in notice.text
    assert "browser runtime" in notice.text
    assert "25%" in browser.find_element(By.ID, "model-loading-detail").text
    assert "model_quantized.onnx" not in notice.text

    loading_server.messages[1].put(model_event(loaded=40_000_000, total=40_000_000))
    wait_progress(browser, 100)
    assert notice.is_displayed()
    assert browser.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "loading"
    loading_server.messages[1].put(model_event(status="done"))
    wait_phase(browser, "initializing")
    wait_progress(browser, None)
    assert "runtime" in browser.find_element(By.ID, "model-loading-detail").text
    assert browser.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "loading"

    loading_server.messages[1].put({"type": "ready"})
    wait_state(browser, "ready")
    assert not notice.is_displayed()


def test_model_progress_is_clamped_and_unknown_length_is_indeterminate(browser, loading_server):
    loading_server.messages[1].put(model_event(loaded=10_000_000, total=40_000_000))
    browser.get(loading_server.url)
    wait_phase(browser, "downloading")
    wait_progress(browser, 25)
    loading_server.messages[1].put(model_event(loaded=60_000_000, total=40_000_000))
    wait_progress(browser, 100)
    assert "40.0 of 40.0 MB" in browser.find_element(By.ID, "model-loading-detail").text

    loading_server.messages[1].put(model_event(loaded=20_000_000))
    wait_progress(browser, None)
    assert "not available" in browser.find_element(By.ID, "model-loading-detail").text
    loading_server.messages[1].put(model_event(loaded=-1, total=40_000_000))
    wait_progress(browser, 0)
    loading_server.messages[1].put(model_event(loaded="invalid", total=40_000_000))
    wait_progress(browser, None)
    loading_server.messages[1].put({"type": "ready"})
    wait_state(browser, "ready")


def test_missing_content_length_shape_stays_indeterminate(browser, loading_server):
    # Transformers.js 2.17.2 sets total to the bytes received so far when a host omits
    # Content-Length, so every event has total == loaded. That is not a known size.
    loading_server.messages[1].put(model_event(loaded=5_000_000, total=5_000_000))
    browser.get(loading_server.url)
    wait_phase(browser, "downloading")
    wait_progress(browser, None)
    detail = browser.find_element(By.ID, "model-loading-detail")
    assert "5.0 MB received" in detail.text and "not available" in detail.text and "100%" not in detail.text
    loading_server.messages[1].put(model_event(loaded=15_000_000, total=15_000_000))
    WebDriverWait(browser, 5).until(lambda driver: "15.0 MB received" in detail.text)
    assert browser.find_element(By.ID, "model-loading-progress").get_dom_attribute("value") is None
    loading_server.messages[1].put(model_event(status="done"))
    wait_phase(browser, "initializing")
    loading_server.messages[1].put({"type": "ready"})
    wait_state(browser, "ready")


def test_startup_progress_and_ready_do_not_replace_an_input_error(browser, loading_server, tmp_path):
    loading_server.messages[1].put(model_event(loaded=10_000_000, total=40_000_000))
    browser.get(loading_server.url)
    wait_progress(browser, 25)
    invalid = tmp_path / "notes.txt"
    invalid.write_bytes(b"Not an image.")
    upload(browser, invalid)
    wait_state(browser, "error")
    message = browser.find_element(By.ID, "error-message").text

    loading_server.messages[1].put(model_event(loaded=30_000_000, total=40_000_000))
    wait_progress(browser, 75)
    assert browser.find_element(By.ID, "error-message").text == message
    assert browser.find_element(By.ID, "status").text == "Action needed"
    loading_server.messages[1].put({"type": "ready"})
    WebDriverWait(browser, 5, poll_frequency=0.05).until(
        lambda driver: not driver.find_element(By.ID, "model-loading").is_displayed()
    )
    assert browser.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "error"
    assert browser.find_element(By.ID, "error-message").text == message


def test_loading_failure_hides_notice_and_retry_ignores_the_old_worker(browser, loading_server):
    browser.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": """
        window.loadingTestWorkers = [];
        const OriginalWorker = window.Worker;
        window.Worker = class extends OriginalWorker {
            constructor(...args) {
                super(...args);
                window.loadingTestWorkers.push(this);
            }
        };
    """})
    loading_server.messages[1].put(model_event(loaded=30_000_000, total=40_000_000))
    browser.get(loading_server.url)
    wait_progress(browser, 75)
    loading_server.messages[1].put({"type": "error", "stage": "load", "message": "Controlled startup failure."})
    wait_state(browser, "error")
    assert not browser.find_element(By.ID, "model-loading").is_displayed()
    browser.find_element(By.ID, "retry-detection").click()
    wait_phase(browser, "preparing")
    wait_progress(browser, None)
    assert browser.find_element(By.ID, "model-loading").is_displayed()

    # Invoke the retired instance's original handler after its replacement exists.
    browser.execute_script("""
        const retired = window.loadingTestWorkers[0];
        retired.onmessage({data: {type: 'progress', status: 'progress',
            file: 'onnx/model_quantized.onnx', loaded: 99, total: 100}});
        retired.onmessage({data: {type: 'ready'}});
    """)
    assert browser.find_element(By.ID, "model-loading").get_attribute("data-phase") == "preparing"
    assert browser.find_element(By.ID, "model-loading-progress").get_dom_attribute("value") is None
    assert browser.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "loading"
    loading_server.messages[2].put({"type": "ready"})
    wait_state(browser, "ready")
    assert not browser.find_element(By.ID, "model-loading").is_displayed()
