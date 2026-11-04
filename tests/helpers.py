"""Browser helpers shared by more than one test module.

Helpers used by a single module stay in that module.
"""
from __future__ import annotations

import base64
import struct
import time

import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


def upload(browser, path):
    browser.find_element(By.ID, "file-input").send_keys(str(path))


def wait_state(browser, expected, timeout=10):
    try:
        WebDriverWait(browser, timeout).until(
            lambda driver: driver.find_element(By.TAG_NAME, "html").get_attribute("data-state") == expected
        )
        return
    except TimeoutException:
        pass
    # Keep the full wait, then explain its failure using the final visible UI.
    html = browser.find_elements(By.TAG_NAME, "html")
    errors = browser.find_elements(By.ID, "error-message")
    filenames = browser.find_elements(By.ID, "filename")
    observed = html[0].get_attribute("data-state") if html else "<no page>"
    error = errors[0].text.strip() if errors else ""
    filename = filenames[0].text.strip() if filenames else "<not displayed>"
    pytest.fail(
        f"Timed out waiting for UI state {expected!r} (timeout={timeout}s).\n"
        f"Observed state: {observed!r}\n"
        f"Displayed filename: {filename!r}\n"
        f"UI error: {error or '<none displayed>'}",
        pytrace=False,
    )


def result_labels(browser):
    # Read what a person can see, rather than the application's internal metadata.
    return [name.text for name in browser.find_elements(By.CSS_SELECTOR, ".result-row .object-name")]


def assert_visible_result_text(browser, expected):
    """Check independently supplied names and formatted scores in both visible views."""
    rows = browser.find_elements(By.CSS_SELECTOR, ".result-row")
    boxes = browser.find_elements(By.CSS_SELECTOR, ".detection-box")
    assert len(rows) == len(boxes) == len(expected)
    for row, box, (label, score_text) in zip(rows, boxes, expected):
        name = row.find_element(By.CSS_SELECTOR, ".object-name")
        score = row.find_element(By.CSS_SELECTOR, ".object-score")
        tag = box.find_element(By.CSS_SELECTOR, ".box-label")
        assert name.is_displayed() and name.text == label, "Visible detection name does not match"
        assert score.is_displayed() and score.text == score_text, "Visible model score does not match"
        assert tag.is_displayed() and tag.text == label, "Visible box label does not match"
        assert row.get_attribute("data-label") == box.get_attribute("data-label") == label
        accessible_name = row.get_attribute("aria-label")
        assert label in accessible_name and score_text in accessible_name


def wait_for_inference(browser, filename):
    """Wait past file reading/decoding so the worker has actually received this image."""
    WebDriverWait(browser, 10).until(
        lambda driver: driver.find_element(By.ID, "filename").text == filename
        and driver.find_element(By.ID, "status").text.startswith("Analyzing image")
        and driver.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "processing"
    )


def assert_no_visible_image(browser):
    assert not browser.find_element(By.ID, "image-preview").is_displayed()
    assert browser.find_elements(By.CSS_SELECTOR, ".detection-box") == []
    assert result_labels(browser) == []


# Installed on every page by the conftest `browser` fixture. Each worker created by
# the page records the ids of its outgoing 'infer' messages; an id is removed when a
# 'result' or 'error' message carrying that id arrives, and terminate() drops all of
# that worker's outstanding ids (a terminated worker can never reply).
WORKER_TRACE_SCRIPT = """
(() => {
    const NativeWorker = window.Worker;
    if (typeof NativeWorker !== 'function' || window.__olWorkerTrace) return;
    const records = new WeakMap();
    const workers = [];
    window.__olWorkerTrace = {
        workers,
        pendingIds() {
            return workers.flatMap((record) => [...record.pending]);
        },
    };
    window.Worker = class TracedWorker extends NativeWorker {
        constructor(...args) {
            super(...args);
            const record = {pending: new Set(), answered: [], terminated: false};
            records.set(this, record);
            workers.push(record);
            // Registered before the page assigns onmessage, so it observes every reply.
            this.addEventListener('message', ({data}) => {
                if (data && (data.type === 'result' || data.type === 'error')
                        && record.pending.delete(data.id)) {
                    record.answered.push(data.id);
                }
            });
        }
        postMessage(message, ...rest) {
            const record = records.get(this);
            const tracked = record && !record.terminated && message && message.type === 'infer';
            if (tracked) record.pending.add(message.id);
            try {
                return super.postMessage(message, ...rest);
            } catch (error) {
                if (tracked) record.pending.delete(message.id);
                throw error;
            }
        }
        terminate() {
            const record = records.get(this);
            if (record) {
                record.terminated = true;
                record.pending.clear();
            }
            return super.terminate();
        }
    };
})();
"""


def assert_for_late_response_window(browser, assertion, hold=0.3):
    """Hold an invariant until every outstanding worker inference reply has arrived.

    The invariant is asserted on each poll while waiting (up to 10 s) for the page's
    worker trace to report no outstanding 'infer' request, and then for a further
    `hold` seconds so the application has handled the last reply. A caller whose
    late event is not a worker reply (a held fetch or encoder callback) passes a
    longer `hold`.
    """
    def pending_ids(driver):
        pending = driver.execute_script(
            "const trace = window.__olWorkerTrace; return trace ? trace.pendingIds() : null;"
        )
        if pending is None:
            pytest.fail("The worker trace (window.__olWorkerTrace) is missing from this page; "
                        "late replies cannot be proven to have arrived.", pytrace=False)
        return pending

    def replies_delivered(driver):
        assertion(driver)
        return not pending_ids(driver)

    try:
        WebDriverWait(browser, 10, poll_frequency=0.05).until(replies_delivered)
    except TimeoutException:
        pytest.fail(f"Worker inference replies still outstanding after 10 s: {pending_ids(browser)!r}",
                    pytrace=False)

    end = time.monotonic() + hold

    def invariant_still_holds(driver):
        assertion(driver)
        return time.monotonic() >= end

    WebDriverWait(browser, hold + 5, poll_frequency=0.05).until(invariant_still_holds)


def make_browser_jpeg(browser):
    # Generate an ordinary JPEG with the browser's standard encoder, not application code.
    encoded = browser.execute_script("""
        const canvas = document.createElement('canvas');
        canvas.width = 320; canvas.height = 240;
        const context = canvas.getContext('2d');
        context.fillStyle = '#285bb4'; context.fillRect(0, 0, 160, 240);
        context.fillStyle = '#e6be3c'; context.fillRect(160, 0, 160, 240);
        return canvas.toDataURL('image/jpeg', 0.9).split(',')[1];
    """)
    return base64.b64decode(encoded)


def set_minimum(browser, value):
    """Exercise the public range input; keyboard operation has its own check."""
    slider = browser.find_element(By.ID, "minimum-score")
    assert slider.is_enabled()
    browser.execute_script("""
        arguments[0].value = arguments[1];
        arguments[0].dispatchEvent(new Event('input', {bubbles: true}));
    """, slider, str(value))
    WebDriverWait(browser, 5).until(
        lambda driver: driver.find_element(By.ID, "minimum-score-value").text == f"{value:.2f}"
    )


def wait_for_png(browser, downloads):
    def completed_download(_):
        files = list(downloads.glob("*.png"))
        if len(files) == 1 and not list(downloads.glob("*.crdownload")):
            return files[0] if files[0].stat().st_size >= 24 else False
        return False

    path = WebDriverWait(browser, 10).until(completed_download)
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    assert data[12:16] == b"IHDR"
    return path, struct.unpack(">II", data[16:24])
