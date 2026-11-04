"""Score-filter behavior with deliberate model responses, not AI accuracy evidence."""
from __future__ import annotations

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

from test_ui import (
    assert_for_late_response_window,
    assert_no_visible_image,
    result_labels,
    upload,
    wait_for_inference,
    wait_state,
)


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


def assert_visible_predictions(browser, labels, total):
    assert result_labels(browser) == labels
    boxes = browser.find_elements(By.CSS_SELECTOR, ".detection-box")
    assert [box.get_attribute("data-label") for box in boxes] == labels
    assert browser.find_element(By.ID, "result-count").text == str(len(labels))
    assert browser.find_element(By.ID, "filter-summary").text == (
        f"Showing {len(labels)} of {total} predictions."
    )


def selected_label(browser):
    selected_rows = browser.find_elements(By.CSS_SELECTOR, '.result-row[aria-pressed="true"]')
    selected_boxes = browser.find_elements(By.CSS_SELECTOR, ".detection-box.is-selected")
    assert len(selected_rows) == len(selected_boxes) == 1
    label = selected_rows[0].get_attribute("data-label")
    assert selected_boxes[0].get_attribute("data-label") == label
    return label


def result_identity(browser, label):
    row = browser.find_element(By.CSS_SELECTOR, f'.result-row[data-label="{label}"]')
    box = browser.find_element(By.CSS_SELECTOR, f'.detection-box[data-label="{label}"]')
    return browser.execute_script("""
        return {
            rowId: arguments[0].dataset.predictionId,
            boxId: arguments[1].dataset.predictionId,
            rowColor: getComputedStyle(arguments[0]).getPropertyValue('--object-color').trim(),
            boxColor: getComputedStyle(arguments[1]).getPropertyValue('--object-color').trim()
        };
    """, row, box)


def test_exact_minimum_filters_underlying_scores_and_restores_without_inference(app, make_image):
    # Count messages at the browser/worker boundary, without calling application functions.
    app.execute_script("""
        window.filterTestInferenceRequests = 0;
        const original = Worker.prototype.postMessage;
        Worker.prototype.postMessage = function(message, ...rest) {
            if (message?.type === 'infer') window.filterTestInferenceRequests += 1;
            return original.call(this, message, ...rest);
        };
    """)
    upload(app, make_image("score-boundary.png"))
    wait_state(app, "complete")
    assert_visible_predictions(app, ["spoon", "cup", "bottle"], total=3)

    set_minimum(app, 0.80)
    # 0.7999 is excluded, exactly 0.80 is retained, and 0.95 is retained.
    assert_visible_predictions(app, ["cup", "bottle"], total=3)
    set_minimum(app, 0.50)
    assert_visible_predictions(app, ["spoon", "cup", "bottle"], total=3)
    assert app.execute_script("return window.filterTestInferenceRequests") == 1


def test_filter_preserves_result_identity_color_and_surviving_selection(app, make_image):
    upload(app, make_image("score-boundary.png"))
    wait_state(app, "complete")
    original_bottle = result_identity(app, "bottle")
    assert original_bottle["rowId"] is not None
    assert original_bottle["rowId"] == original_bottle["boxId"]
    assert original_bottle["rowColor"] == original_bottle["boxColor"]
    app.find_element(By.CSS_SELECTOR, '.result-row[data-label="bottle"]').click()

    set_minimum(app, 0.80)
    assert selected_label(app) == "bottle"
    assert result_identity(app, "bottle") == original_bottle

    app.find_element(By.CSS_SELECTOR, '.result-row[data-label="cup"]').click()
    set_minimum(app, 0.81)
    assert selected_label(app) == "bottle"
    assert result_identity(app, "bottle") == original_bottle
    set_minimum(app, 0.50)
    assert selected_label(app) == "bottle"
    assert result_identity(app, "bottle") == original_bottle


def test_duplicate_labels_keep_distinct_identity_and_selection_through_filtering(app, make_image):
    upload(app, make_image("duplicate-spoons.png"))
    wait_state(app, "complete")

    def snapshot():
        return app.execute_script("""
            const rows = [...document.querySelectorAll('.result-row')];
            const boxes = [...document.querySelectorAll('.detection-box')];
            const color = (element) =>
                getComputedStyle(element).getPropertyValue('--object-color').trim();
            return {
                rows: rows.map((row) => ({id: row.dataset.predictionId,
                    label: row.dataset.label, score: Number(row.dataset.score), color: color(row)})),
                boxes: boxes.map((box) => ({id: box.dataset.predictionId, color: color(box),
                    bounds: ['xmin', 'ymin', 'xmax', 'ymax'].map((key) => Number(box.dataset[key]))})),
                selectedRows: rows.filter((row) => row.getAttribute('aria-pressed') === 'true')
                    .map((row) => row.dataset.predictionId),
                selectedBoxes: boxes.filter((box) => box.classList.contains('is-selected'))
                    .map((box) => box.dataset.predictionId)
            };
        """)

    original = snapshot()
    assert [row["label"] for row in original["rows"]] == ["spoon", "spoon"]
    assert [row["score"] for row in original["rows"]] == pytest.approx([0.7, 0.95])
    identities = [row["id"] for row in original["rows"]]
    assert all(identity for identity in identities) and len(set(identities)) == 2
    assert [box["id"] for box in original["boxes"]] == identities
    assert original["boxes"][0]["bounds"] == pytest.approx([0.1, 0.2, 0.25, 0.8])
    assert original["boxes"][1]["bounds"] == pytest.approx([0.65, 0.15, 0.8, 0.9])
    colors = [row["color"] for row in original["rows"]]
    assert all(colors) and len(set(colors)) == 2
    assert [box["color"] for box in original["boxes"]] == colors

    selected_id = identities[1]
    app.find_element(By.CSS_SELECTOR, f'.result-row[data-prediction-id="{selected_id}"]').click()
    selected = snapshot()
    assert selected["selectedRows"] == selected["selectedBoxes"] == [selected_id]

    set_minimum(app, 0.80)
    filtered = snapshot()
    assert filtered["rows"] == [original["rows"][1]]
    assert filtered["boxes"] == [original["boxes"][1]]
    assert filtered["selectedRows"] == filtered["selectedBoxes"] == [selected_id]

    set_minimum(app, 0.50)
    restored = snapshot()
    assert restored["rows"] == original["rows"]
    assert restored["boxes"] == original["boxes"]
    assert restored["selectedRows"] == restored["selectedBoxes"] == [selected_id]


def test_hidden_predictions_can_be_restored_and_differ_from_no_model_predictions(app, make_image):
    upload(app, make_image("score-boundary.png"))
    wait_state(app, "complete")
    set_minimum(app, 0.96)
    assert_visible_predictions(app, [], total=3)
    assert app.find_element(By.ID, "results-empty").text == "No predictions meet this minimum score."
    assert app.find_element(By.ID, "image-preview").is_displayed()
    assert not app.find_element(By.ID, "error-message").is_displayed()
    assert app.find_element(By.ID, "minimum-score").is_enabled()

    set_minimum(app, 0.95)
    assert_visible_predictions(app, ["bottle"], total=3)
    upload(app, make_image("empty.png"))
    wait_state(app, "empty")
    assert result_labels(app) == []
    assert app.find_element(By.ID, "results-empty").text == "No supported objects were detected in this image."
    assert not app.find_element(By.ID, "error-message").is_displayed()


def test_new_image_and_clear_reset_filter_and_retire_old_cached_predictions(app, make_image):
    assert not app.find_element(By.ID, "minimum-score").is_enabled()
    upload(app, make_image("score-boundary.png"))
    wait_state(app, "complete")
    set_minimum(app, 0.80)
    upload(app, make_image("slow-car.png"))
    wait_for_inference(app, "slow-car.png")
    assert float(app.find_element(By.ID, "minimum-score").get_attribute("value")) == 0.50
    assert app.find_element(By.ID, "minimum-score-value").text == "0.50"
    assert not app.find_element(By.ID, "minimum-score").is_enabled()
    assert result_labels(app) == []
    app.find_element(By.ID, "clear-image").click()

    def empty_filter_remains_disabled(driver):
        assert_no_visible_image(driver)
        assert not driver.find_element(By.ID, "minimum-score").is_enabled()
        assert float(driver.find_element(By.ID, "minimum-score").get_attribute("value")) == 0.50

    assert_for_late_response_window(app, empty_filter_remains_disabled)
    upload(app, make_image("car.png"))
    wait_state(app, "complete")
    assert_visible_predictions(app, ["car"], total=1)


def test_invalid_replacement_discards_filter_cache_and_valid_image_recovers(app, make_image, tmp_path):
    upload(app, make_image("score-boundary.png"))
    wait_state(app, "complete")
    set_minimum(app, 0.80)
    invalid = tmp_path / "invalid.png"
    invalid.write_bytes(b"Deliberately invalid image bytes.")
    upload(app, invalid)
    wait_state(app, "error")
    assert result_labels(app) == []
    assert not app.find_element(By.ID, "minimum-score").is_enabled()
    assert float(app.find_element(By.ID, "minimum-score").get_attribute("value")) == 0.50
    upload(app, make_image("car.png"))
    wait_state(app, "complete")
    assert_visible_predictions(app, ["car"], total=1)


def test_minimum_score_has_accessible_label_and_keyboard_controls(app, make_image):
    upload(app, make_image("score-boundary.png"))
    wait_state(app, "complete")
    slider = app.find_element(By.ID, "minimum-score")
    assert slider.get_attribute("type") == "range"
    assert float(slider.get_attribute("min")) == 0.50
    assert float(slider.get_attribute("max")) == 1.00
    assert float(slider.get_attribute("step")) == 0.01
    assert "minimum" in slider.accessible_name.lower()
    for _ in range(25):
        active = app.switch_to.active_element
        if active.get_attribute("id") == "minimum-score":
            break
        active.send_keys(Keys.TAB)
    else:
        pytest.fail("Minimum score was not reachable in the keyboard tab order")
    focus = app.execute_script("""
        const slider = document.getElementById('minimum-score');
        const style = getComputedStyle(slider);
        return {visible: slider.matches(':focus-visible'), outline: style.outlineStyle,
                width: parseFloat(style.outlineWidth)};
    """)
    assert focus["visible"] and focus["outline"] != "none" and focus["width"] > 0
    app.switch_to.active_element.send_keys(Keys.HOME, Keys.ARROW_RIGHT)
    assert float(slider.get_attribute("value")) == pytest.approx(0.51)
    assert app.find_element(By.ID, "minimum-score-value").text == "0.51"
    assert_visible_predictions(app, ["spoon", "cup", "bottle"], total=3)
