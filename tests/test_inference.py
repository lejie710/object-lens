"""Real model checks on a small fixed image set; not a general accuracy benchmark."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

from test_ui import assert_visible_result_text

ROOT = Path(__file__).resolve().parents[1]
# These are earlier outputs of the same pinned model, not independent annotations.
REFERENCE_PATH = ROOT / "docs" / "evidence" / "model-observations.json"
NORMALIZED_TOLERANCE = 0.005
LAYOUT_TOLERANCE_PX = 2


def selected_reference(filename, label):
    observations = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    sample = next(item for item in observations["app"] if item["image"] == filename)
    return max((item for item in sample["predictions"] if item["label"] == label),
               key=lambda item: item["score"])


def assert_reference_geometry(box, image_rect, reference):
    """Separate model-coordinate regression from actual CSS placement and sizing."""
    bounds = reference["box"]
    for coordinate, expected in bounds.items():
        actual = float(box.get_attribute(f"data-{coordinate}"))
        assert actual == pytest.approx(expected, abs=NORMALIZED_TOLERANCE), (
            f"Pinned-model coordinate regression for {coordinate}: {actual} vs {expected}"
        )
    expected_rect = {
        "x": image_rect["x"] + image_rect["width"] * bounds["xmin"],
        "y": image_rect["y"] + image_rect["height"] * bounds["ymin"],
        "width": image_rect["width"] * (bounds["xmax"] - bounds["xmin"]),
        "height": image_rect["height"] * (bounds["ymax"] - bounds["ymin"]),
    }
    actual_rect = box.rect
    for dimension, expected in expected_rect.items():
        extent = image_rect["width" if dimension in {"x", "width"} else "height"]
        # Each edge may drift by 0.5% of its image extent (~2-3 source pixels in
        # these samples). Width/height depend on two edges. Add 2 CSS pixels for
        # subpixel layout rounding and borders, independently of model variation.
        edge_count = 2 if dimension in {"width", "height"} else 1
        tolerance = LAYOUT_TOLERANCE_PX + edge_count * extent * NORMALIZED_TOLERANCE
        assert actual_rect[dimension] == pytest.approx(expected, abs=tolerance), (
            f"Rendered box regression for {dimension}: {actual_rect[dimension]} vs {expected}"
        )
    return expected_rect


@pytest.mark.inference
@pytest.mark.parametrize("filename,expected_label", [
    ("astronaut.png", "person"),
    ("coffee.png", "cup"),
    ("chelsea.png", "cat"),
])
def test_real_model_detects_reviewed_object(browser, real_url, filename, expected_label):
    sample = ROOT / "dist" / "samples" / filename
    assert sample.is_file(), f"Prepare the documented sample image first: {sample}"
    browser.get(real_url)
    WebDriverWait(browser, 120).until(
        lambda driver: driver.find_element(By.TAG_NAME, "html").get_attribute("data-state") in {"ready", "error"}
    )
    assert browser.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "ready", browser.find_element(By.ID, "error-message").text
    if filename == "coffee.png":
        browser.find_element(By.ID, "try-sample").click()
        input_action = "Try sample button; ordinary local sample fetch"
    else:
        browser.find_element(By.ID, "file-input").send_keys(str(sample))
        input_action = "Choose image file input"
    WebDriverWait(browser, 120).until(
        lambda driver: driver.find_element(By.TAG_NAME, "html").get_attribute("data-state") in {"complete", "empty", "error"}
    )

    rows = browser.find_elements(By.CSS_SELECTOR, ".result-row")
    observed = [{"label": row.get_attribute("data-label"), "score": row.get_attribute("data-score"),
                 "displayed_text": row.text} for row in rows]
    boxes = [{"label": box.get_attribute("data-label"),
              "coordinates": {name: box.get_attribute(f"data-{name}") for name in ("xmin", "ymin", "xmax", "ymax")},
              "displayed_rectangle": box.rect}
             for box in browser.find_elements(By.CSS_SELECTOR, ".detection-box")]
    reference = selected_reference(filename, expected_label)
    image_rect = browser.find_element(By.ID, "image-preview").rect
    target = ROOT / "artifacts" / "inference"
    target.mkdir(parents=True, exist_ok=True)
    report = {"evidence_type": "real model inference", "input": filename,
              "input_action": input_action,
              "reviewed_expected_label": expected_label,
              "state": browser.find_element(By.TAG_NAME, "html").get_attribute("data-state"),
              "observed_predictions": observed, "boxes": boxes,
              "image_rectangle": image_rect,
              "regression_reference": {"source": "docs/evidence/model-observations.json",
                                       "prediction": reference},
              "tolerances": {"normalized_per_edge": NORMALIZED_TOLERANCE,
                             "additional_layout_css_pixels": LAYOUT_TOLERANCE_PX,
                             "note": "Rendered positions allow one edge tolerance; sizes allow two."},
              "browser_version": browser.capabilities.get("browserVersion"),
              "note": "Visible labels/scores and selected-box regression against prior pinned-model outputs; not localization accuracy, complete annotation, or a general accuracy estimate."}
    (target / f"{sample.stem}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    browser.save_screenshot(str(target / f"{sample.stem}.png"))
    assert report["state"] == "complete", browser.find_element(By.ID, "error-message").text
    assert expected_label in [item["label"] for item in observed]
    assert len(rows) == len(boxes)
    assert_visible_result_text(browser, [(item["label"], f"{float(item['score']):.2f}") for item in observed])
    # Selecting the highest-score matching row avoids depending on prediction order.
    matching_rows = [row for row in rows if row.get_attribute("data-label") == expected_label]
    selected_row = max(matching_rows, key=lambda row: float(row.get_attribute("data-score")))
    # The page's own metadata is not an independent oracle: compare the visible text of
    # the selected row with the earlier recorded output of the same pinned model.
    assert selected_row.find_element(By.CSS_SELECTOR, ".object-name").text == reference["label"]
    visible_score = float(selected_row.find_element(By.CSS_SELECTOR, ".object-score").text)
    assert visible_score == pytest.approx(reference["score"], abs=0.01), (
        f"Visible score regression: {visible_score} vs reference {reference['score']}"
    )
    selected_row.click()
    prediction_id = selected_row.get_attribute("data-prediction-id")
    selected_box = browser.find_element(By.CSS_SELECTOR, f'.detection-box[data-prediction-id="{prediction_id}"]')
    assert "is-selected" in selected_box.get_attribute("class").split()
    assert_reference_geometry(selected_box, image_rect, reference)
    assert "Controlled test mode" not in browser.find_element(By.TAG_NAME, "body").text
