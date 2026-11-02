"""Application behavior with controlled predictions, NOT AI accuracy tests."""
from __future__ import annotations

import base64
import struct
import time

import pytest
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
    return [row.get_attribute("data-label") for row in browser.find_elements(By.CSS_SELECTOR, ".result-row")]


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


def assert_for_late_response_window(browser, assertion):
    """Check an invariant past the controlled worker's known 900 ms response delay."""
    end = time.monotonic() + 1.4

    def invariant_still_holds(driver):
        assertion(driver)
        return time.monotonic() >= end

    WebDriverWait(browser, 2.5, poll_frequency=0.1).until(invariant_still_holds)


def test_predictions_and_boxes_match_the_current_image(app, make_image):
    upload(app, make_image())
    wait_state(app, "complete")
    assert result_labels(app) == ["laptop", "cup"]
    boxes = app.find_elements(By.CSS_SELECTOR, ".detection-box")
    assert [box.get_attribute("data-label") for box in boxes] == ["laptop", "cup"]
    assert "2" in app.find_element(By.ID, "result-count").text
    assert app.find_element(By.ID, "filename").text == "normal.png"
    # Independently specified fixture coordinates should scale with the displayed image.
    image = app.find_element(By.ID, "image-preview").rect
    laptop = boxes[0].rect
    assert laptop["x"] == pytest.approx(image["x"] + image["width"] * 0.1, abs=2)
    assert laptop["y"] == pytest.approx(image["y"] + image["height"] * 0.2, abs=2)
    assert laptop["width"] == pytest.approx(image["width"] * 0.6, abs=2)
    assert laptop["height"] == pytest.approx(image["height"] * 0.65, abs=2)


def test_selecting_a_result_highlights_its_box(app, make_image):
    upload(app, make_image())
    wait_state(app, "complete")
    app.find_element(By.CSS_SELECTOR, '.result-row[data-label="cup"]').click()
    selected = app.find_elements(By.CSS_SELECTOR, ".detection-box.is-selected")
    assert len(selected) == 1
    assert selected[0].get_attribute("data-label") == "cup"


def test_replacing_image_replaces_all_results(app, make_image):
    upload(app, make_image())
    wait_state(app, "complete")
    upload(app, make_image("car.png", width=320, height=640))
    wait_state(app, "complete")
    assert result_labels(app) == ["car"]
    assert app.find_element(By.ID, "filename").text == "car.png"
    assert [box.get_attribute("data-label") for box in app.find_elements(By.CSS_SELECTOR, ".detection-box")] == ["car"]


@pytest.mark.parametrize("replacement", ["car.png", "slow-car.png"])
def test_replacing_a_processing_image_discards_the_old_result(app, make_image, replacement):
    upload(app, make_image("slow-dog.png"))
    wait_for_inference(app, "slow-dog.png")
    upload(app, make_image(replacement))
    WebDriverWait(app, 10).until(lambda driver: driver.find_element(By.ID, "filename").text == replacement)

    def current_result_without_old_label(driver):
        # Check during the transition as well as after it: an old result must not flash.
        assert "dog" not in result_labels(driver)
        assert driver.find_elements(By.CSS_SELECTOR, '.detection-box[data-label="dog"]') == []
        return result_labels(driver) == ["car"]

    WebDriverWait(app, 10, poll_frequency=0.05).until(current_result_without_old_label)

    def only_current_result(driver):
        assert result_labels(driver) == ["car"]
        assert driver.find_element(By.ID, "filename").text == replacement

    assert_for_late_response_window(app, only_current_result)


def test_clearing_a_processing_image_prevents_late_repaint(app, make_image):
    upload(app, make_image("slow-dog.png"))
    wait_for_inference(app, "slow-dog.png")
    app.find_element(By.ID, "clear-image").click()
    assert_for_late_response_window(app, assert_no_visible_image)


def test_nonresponding_worker_times_out_and_retries_the_latest_image(app, make_image):
    # The controlled worker intentionally never answers silent.png; no real model hangs.
    upload(app, make_image("silent.png"))
    wait_for_inference(app, "silent.png")
    app.find_element(By.ID, "clear-image").click()
    upload(app, make_image("car.png"))
    WebDriverWait(app, 5).until(lambda driver: driver.find_element(By.ID, "filename").text == "car.png")
    wait_state(app, "error", timeout=8)
    assert app.find_element(By.ID, "filename").text == "car.png"
    assert app.find_element(By.ID, "image-preview").is_displayed()
    assert result_labels(app) == []
    assert "Try again" in app.find_element(By.ID, "error-message").text
    assert app.find_element(By.ID, "retry-detection").is_displayed()
    app.find_element(By.ID, "retry-detection").click()
    wait_state(app, "complete")
    assert app.find_element(By.ID, "filename").text == "car.png"
    assert result_labels(app) == ["car"]


def test_empty_predictions_are_not_an_error(app, make_image):
    upload(app, make_image("empty.png"))
    wait_state(app, "empty")
    assert app.find_element(By.ID, "image-preview").is_displayed()
    assert result_labels(app) == []
    assert not app.find_element(By.ID, "error-message").is_displayed()
    assert app.find_element(By.ID, "status").text.strip()


def test_processing_failure_is_visible_and_next_image_recovers(app, make_image):
    upload(app, make_image("fail.png"))
    wait_state(app, "error")
    assert app.find_element(By.ID, "error-message").is_displayed()
    assert app.find_element(By.ID, "error-message").text.strip()
    assert result_labels(app) == []
    upload(app, make_image("car.png"))
    wait_state(app, "complete")
    assert result_labels(app) == ["car"]
    assert not app.find_element(By.ID, "error-message").is_displayed()


def test_worker_start_failure_can_be_retried(browser, recoverable_worker_url, make_image):
    # The dedicated test server returns 503 for the first controlled-worker request.
    # This is a simulated loading problem, not evidence of a real model outage.
    browser.get(recoverable_worker_url)
    wait_state(browser, "error")
    assert browser.find_element(By.ID, "error-message").is_displayed()
    assert browser.find_element(By.ID, "retry-detection").is_displayed()
    browser.find_element(By.ID, "retry-detection").click()
    wait_state(browser, "ready")
    upload(browser, make_image("car.png"))
    wait_state(browser, "complete")
    assert result_labels(browser) == ["car"]


@pytest.mark.parametrize("filename,contents", [
    ("damaged.png", b"This is not a readable PNG."),
    ("notes.txt", b"This file is intentionally not an image."),
])
def test_invalid_input_is_rejected_and_valid_input_recovers(app, make_image, tmp_path, filename, contents):
    invalid = tmp_path / filename
    invalid.write_bytes(contents)
    upload(app, invalid)
    wait_state(app, "error")
    assert app.find_element(By.ID, "error-message").is_displayed()
    assert result_labels(app) == []
    upload(app, make_image("car.png"))
    wait_state(app, "complete")
    assert result_labels(app) == ["car"]


def test_truncated_png_body_is_rejected_and_recovers(app, make_image, tmp_path):
    # Signature and dimensions are valid. Missing image data must fail actual decoding.
    valid = make_image("source.png")
    damaged = tmp_path / "truncated-body.png"
    damaged.write_bytes(valid.read_bytes()[:24])
    upload(app, damaged)
    wait_state(app, "error")
    assert "could not be read" in app.find_element(By.ID, "error-message").text
    assert result_labels(app) == []
    assert not app.find_element(By.ID, "image-preview").is_displayed()
    upload(app, make_image("car.png"))
    wait_state(app, "complete")
    assert result_labels(app) == ["car"]


@pytest.mark.parametrize("size,expected_state", [(10 * 1024 * 1024, "complete"), (10 * 1024 * 1024 + 1, "error")])
def test_file_size_boundary(app, make_image, size, expected_state):
    upload(app, make_image("size-boundary.png", total_bytes=size))
    wait_state(app, expected_state, timeout=20)
    if expected_state == "error":
        assert app.find_element(By.ID, "error-message").is_displayed()
        assert result_labels(app) == []
    else:
        assert result_labels(app) == ["laptop", "cup"]


@pytest.mark.parametrize("width,expected_state", [(4000, "complete"), (4001, "error")])
def test_decoded_pixel_boundary(app, make_image, width, expected_state):
    upload(app, make_image("pixel-boundary.png", width=width, height=4000))
    wait_state(app, expected_state, timeout=20)
    if expected_state == "error":
        assert app.find_element(By.ID, "error-message").is_displayed()
        assert result_labels(app) == []
    else:
        assert result_labels(app) == ["laptop", "cup"]


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


def test_real_jpeg_input_is_accepted(app, tmp_path):
    jpeg = tmp_path / "normal.jpg"
    jpeg.write_bytes(make_browser_jpeg(app))
    upload(app, jpeg)
    wait_state(app, "complete")
    assert result_labels(app) == ["laptop", "cup"]


def test_jpeg_exif_orientation_preserves_display_and_box_alignment(app, tmp_path):
    jpeg = make_browser_jpeg(app)
    # EXIF IFD0 Orientation = 6 means rotate the stored 320x240 pixels 90 degrees clockwise.
    tiff = (b"II" + struct.pack("<HIH", 42, 8, 1)
            + struct.pack("<HHI", 0x0112, 3, 1) + struct.pack("<H", 6) + b"\x00\x00"
            + struct.pack("<I", 0))
    exif = b"Exif\x00\x00" + tiff
    segment = b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
    oriented = tmp_path / "oriented.jpg"
    oriented.write_bytes(jpeg[:2] + segment + jpeg[2:])
    upload(app, oriented)
    wait_state(app, "complete")
    dimensions = app.execute_script("""
        const image = document.getElementById('image-preview');
        return [image.naturalWidth, image.naturalHeight];
    """)
    assert dimensions == [240, 320]
    assert app.find_element(By.ID, "image-dimensions").text == "240 × 320"
    image = app.find_element(By.ID, "image-preview").rect
    assert image["width"] / image["height"] == pytest.approx(240 / 320, abs=0.01)
    laptop = app.find_element(By.CSS_SELECTOR, '.detection-box[data-label="laptop"]').rect
    assert laptop["x"] == pytest.approx(image["x"] + image["width"] * 0.1, abs=2)
    assert laptop["y"] == pytest.approx(image["y"] + image["height"] * 0.2, abs=2)
    assert laptop["width"] == pytest.approx(image["width"] * 0.6, abs=2)
    assert laptop["height"] == pytest.approx(image["height"] * 0.65, abs=2)


def test_unicode_filename_and_reselecting_same_file(app, make_image):
    path = make_image("desk photo 測試.png")
    upload(app, path)
    wait_state(app, "complete")
    assert app.find_element(By.ID, "filename").text == path.name
    app.find_element(By.ID, "clear-image").click()
    assert_no_visible_image(app)
    upload(app, path)
    wait_state(app, "complete")
    assert app.find_element(By.ID, "filename").text == path.name
    assert result_labels(app) == ["laptop", "cup"]


def test_clear_is_reachable_and_usable_with_keyboard(app, make_image):
    upload(app, make_image())
    wait_state(app, "complete")
    for _ in range(20):
        active = app.switch_to.active_element
        if active.get_attribute("id") == "clear-image":
            break
        active.send_keys(Keys.TAB)
    else:
        pytest.fail("Clear was not reachable in the keyboard tab order")
    app.switch_to.active_element.send_keys(Keys.ENTER)
    assert_no_visible_image(app)


def test_narrow_layout_preserves_results_and_does_not_overflow(app, make_image):
    app.set_window_size(390, 844)
    # Chrome can impose a larger minimum outer-window width. Set the CSS viewport explicitly.
    app.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": False,
    })
    upload(app, make_image())
    wait_state(app, "complete")
    metrics = app.execute_script("""
        return {content: document.documentElement.scrollWidth, viewport: window.innerWidth};
    """)
    assert metrics["viewport"] == 390
    assert metrics["content"] <= metrics["viewport"] + 1
    assert app.find_element(By.ID, "results-list").is_displayed()
    app.find_element(By.CSS_SELECTOR, '.result-row[data-label="cup"]').click()
    assert app.find_element(By.CSS_SELECTOR, '.detection-box[data-label="cup"]').get_attribute("class").find("is-selected") >= 0
    for control_id in ("choose-image", "clear-image"):
        rect = app.find_element(By.ID, control_id).rect
        assert rect["width"] > 0
        assert rect["x"] >= 0
        assert rect["x"] + rect["width"] <= metrics["viewport"] + 1
