"""Actual PNG download checks with controlled predictions and encoding failures."""
from __future__ import annotations

import base64
import struct
import time

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from test_filter import set_minimum
from test_ui import (
    assert_for_late_response_window,
    assert_no_visible_image,
    make_browser_jpeg,
    result_labels,
    upload,
    wait_state,
)


@pytest.fixture
def downloads(browser, tmp_path):
    folder = tmp_path / "downloads"
    folder.mkdir()
    browser.execute_cdp_cmd("Browser.setDownloadBehavior", {
        "behavior": "allow", "downloadPath": str(folder), "eventsEnabled": True,
    })
    return folder


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


def read_png_pixels(browser, path, coordinates):
    """Decode the saved file independently of the app's preview/export state."""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    result = browser.execute_async_script("""
        const [encoded, coordinates, done] = arguments;
        const image = new Image();
        image.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = image.naturalWidth;
            canvas.height = image.naturalHeight;
            const context = canvas.getContext('2d');
            context.drawImage(image, 0, 0);
            done({pixels: coordinates.map(([x, y]) =>
                Array.from(context.getImageData(x, y, 1, 1).data))});
        };
        image.onerror = () => done({error: 'Downloaded PNG did not decode'});
        image.src = 'data:image/png;base64,' + encoded;
    """, encoded, coordinates)
    assert "error" not in result, result.get("error")
    return result["pixels"]


def test_save_requires_current_visible_predictions(app, make_image):
    save = app.find_element(By.ID, "save-result")
    assert not save.is_enabled()
    upload(app, make_image("score-boundary.png"))
    wait_state(app, "complete")
    assert save.is_enabled()
    set_minimum(app, 1.00)
    assert not save.is_enabled()
    set_minimum(app, 0.95)
    assert save.is_enabled()
    upload(app, make_image("empty.png"))
    wait_state(app, "empty")
    assert not save.is_enabled()
    app.find_element(By.ID, "clear-image").click()
    assert not save.is_enabled()


def test_downloaded_png_contains_only_filtered_boxes_at_original_dimensions(app, downloads, make_image):
    app.execute_script("""
        window.exportTestInferenceRequests = 0;
        const original = Worker.prototype.postMessage;
        Worker.prototype.postMessage = function(message, ...rest) {
            if (message?.type === 'infer') window.exportTestInferenceRequests += 1;
            return original.call(this, message, ...rest);
        };
    """)
    source_colour = [102, 143, 179, 255]
    upload(app, make_image("score-boundary.png", width=640, height=480))
    wait_state(app, "complete")
    set_minimum(app, 0.80)
    app.find_element(By.ID, "save-result").click()
    path, dimensions = wait_for_png(app, downloads)
    assert dimensions == (640, 480)
    # Known fixture boxes: cup bottom at y=336; excluded spoon bottom at y=384.
    # Inspect a small neighbourhood to tolerate legitimate stroke placement.
    coordinates = [(230, y) for y in range(334, 339)]
    coordinates += [(80, y) for y in range(382, 387)]
    coordinates += [(620, 460)]
    pixels = read_png_pixels(app, path, coordinates)
    assert any(pixel != source_colour for pixel in pixels[:5]), "Retained cup box is absent"
    assert all(pixel == source_colour for pixel in pixels[5:10]), "Filtered spoon box leaked into export"
    assert pixels[10] == source_colour, "Photo background changed outside annotations"
    assert app.execute_script("return window.exportTestInferenceRequests") == 1
    assert result_labels(app) == ["cup", "bottle"]
    assert app.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "complete"


def test_export_preserves_jpeg_orientation_and_oriented_dimensions(app, downloads, tmp_path):
    jpeg = make_browser_jpeg(app)
    tiff = (b"II" + struct.pack("<HIH", 42, 8, 1)
            + struct.pack("<HHI", 0x0112, 3, 1) + struct.pack("<H", 6) + b"\x00\x00"
            + struct.pack("<I", 0))
    exif = b"Exif\x00\x00" + tiff
    segment = b"\xff\xe1" + struct.pack(">H", len(exif) + 2) + exif
    path = tmp_path / "oriented.jpg"
    path.write_bytes(jpeg[:2] + segment + jpeg[2:])
    upload(app, path)
    wait_state(app, "complete")
    app.find_element(By.ID, "save-result").click()
    exported, dimensions = wait_for_png(app, downloads)
    assert dimensions == (240, 320)
    top, bottom = read_png_pixels(app, exported, [(120, 20), (120, 300)])
    # A clockwise quarter-turn puts the stored left blue half above the yellow half.
    assert top[:3] == pytest.approx([40, 91, 180], abs=5)
    assert bottom[:3] == pytest.approx([230, 190, 60], abs=5)
    assert top[3] == bottom[3] == 255


def test_png_encoding_failure_preserves_results_and_can_be_retried(app, downloads, make_image):
    upload(app, make_image("score-boundary.png"))
    wait_state(app, "complete")
    set_minimum(app, 0.80)
    app.execute_script("""
        window.exportTestOriginalToBlob = HTMLCanvasElement.prototype.toBlob;
        HTMLCanvasElement.prototype.toBlob = function(callback) { callback(null); };
    """)
    app.find_element(By.ID, "save-result").click()
    WebDriverWait(app, 5).until(
        lambda driver: driver.find_element(By.ID, "export-message").is_displayed()
        and driver.find_element(By.ID, "export-message").text.strip()
        and driver.find_element(By.ID, "save-result").is_enabled()
    )
    assert app.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "complete"
    assert result_labels(app) == ["cup", "bottle"]
    assert app.find_element(By.ID, "image-preview").is_displayed()
    assert not app.find_element(By.ID, "error-message").is_displayed()
    assert list(downloads.iterdir()) == []
    app.execute_script("HTMLCanvasElement.prototype.toBlob = window.exportTestOriginalToBlob;")
    app.find_element(By.ID, "save-result").click()
    _, dimensions = wait_for_png(app, downloads)
    assert dimensions == (640, 480)


def test_nonresponding_png_encoder_times_out_and_a_new_export_recovers(app, downloads, make_image):
    upload(app, make_image("score-boundary.png"))
    wait_state(app, "complete")
    # Deliberately withhold the encoder callback; exercise the real 15-second deadline.
    app.execute_script("""
        window.exportTestOriginalToBlob = HTMLCanvasElement.prototype.toBlob;
        HTMLCanvasElement.prototype.toBlob = function() {};
    """)
    started = time.monotonic()
    app.find_element(By.ID, "save-result").click()
    WebDriverWait(app, 20).until(
        lambda driver: driver.find_element(By.ID, "export-message").is_displayed()
        and "too long" in driver.find_element(By.ID, "export-message").text.lower()
        and driver.find_element(By.ID, "save-result").is_enabled()
    )
    assert time.monotonic() - started >= 14, "Export failed before the intended timeout window"
    assert app.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "complete"
    assert result_labels(app) == ["spoon", "cup", "bottle"]
    assert not app.find_element(By.ID, "error-message").is_displayed()
    assert list(downloads.iterdir()) == []
    app.execute_script("HTMLCanvasElement.prototype.toBlob = window.exportTestOriginalToBlob;")
    app.find_element(By.ID, "save-result").click()
    _, dimensions = wait_for_png(app, downloads)
    assert dimensions == (640, 480)


@pytest.mark.parametrize("action", ["clear", "replacement", "filter"])
def test_changed_result_cancels_a_png_still_being_encoded(app, downloads, make_image, action):
    upload(app, make_image("score-boundary.png"))
    wait_state(app, "complete")
    app.execute_script("""
        const original = HTMLCanvasElement.prototype.toBlob;
        window.exportTestOriginalToBlob = original;
        HTMLCanvasElement.prototype.toBlob = function(callback, ...args) {
            original.call(this, (blob) => {
                window.exportTestHeldBlob = blob;
                window.exportTestHeldCallback = callback;
            }, ...args);
        };
    """)
    app.find_element(By.ID, "save-result").click()
    WebDriverWait(app, 5).until(
        lambda driver: driver.execute_script("return typeof window.exportTestHeldCallback === 'function'")
    )
    assert not app.find_element(By.ID, "save-result").is_enabled()
    if action == "clear":
        app.find_element(By.ID, "clear-image").click()
    elif action == "replacement":
        upload(app, make_image("car.png"))
        wait_state(app, "complete")
    else:
        set_minimum(app, 0.96)
    app.execute_script("""
        HTMLCanvasElement.prototype.toBlob = window.exportTestOriginalToBlob;
        const callback = window.exportTestHeldCallback;
        delete window.exportTestHeldCallback;
        callback(window.exportTestHeldBlob);
    """)

    def old_export_stays_cancelled(driver):
        assert list(downloads.iterdir()) == []
        if action == "clear":
            assert_no_visible_image(driver)
        elif action == "replacement":
            assert driver.find_element(By.ID, "filename").text == "car.png"
            assert result_labels(driver) == ["car"]
        else:
            assert result_labels(driver) == []
            assert "minimum score" in driver.find_element(By.ID, "results-empty").text

    assert_for_late_response_window(app, old_export_stays_cancelled)
    # Cancellation must not strand the save action for the next eligible result.
    if action == "clear":
        upload(app, make_image("car.png"))
        wait_state(app, "complete")
    elif action == "filter":
        set_minimum(app, 0.95)
    assert app.find_element(By.ID, "save-result").is_enabled()
    app.find_element(By.ID, "save-result").click()
    _, dimensions = wait_for_png(app, downloads)
    assert dimensions == (640, 480)
