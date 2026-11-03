"""Real model checks on a small fixed image set; not a general accuracy benchmark."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]


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
    target = ROOT / "artifacts" / "inference"
    target.mkdir(parents=True, exist_ok=True)
    report = {"evidence_type": "real model inference", "input": filename,
              "input_action": input_action,
              "reviewed_expected_label": expected_label,
              "state": browser.find_element(By.TAG_NAME, "html").get_attribute("data-state"),
              "observed_predictions": observed, "boxes": boxes,
              "browser_version": browser.capabilities.get("browserVersion"),
              "note": "Selected-label check on one public image; not a complete annotation or general accuracy estimate."}
    (target / f"{sample.stem}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    browser.save_screenshot(str(target / f"{sample.stem}.png"))
    assert report["state"] == "complete", browser.find_element(By.ID, "error-message").text
    assert expected_label in [item["label"] for item in observed]
    assert len(rows) == len(boxes)
    assert "Controlled test mode" not in browser.find_element(By.TAG_NAME, "body").text
