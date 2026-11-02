"""Collect real-model screenshots, timing observations and a local baseline comparison.

This is a bounded evidence collection script, not a benchmark or test runner.
The application's assertions remain in the pytest suite. No visible browser is used.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from serve import make_server

PHOTOS = {"astronaut.png": ["person"], "coffee.png": ["cup"], "chelsea.png": ["cat"],
          "camera.png": ["person"], "rocket.jpg": []}
OUTPUT = ROOT / "artifacts" / "evaluation"


def browser():
    os.environ["SE_CACHE_PATH"] = str(ROOT / ".local" / "selenium")
    os.environ["SE_AVOID_STATS"] = "true"
    os.environ["SE_OFFLINE"] = "true"
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1440,1000")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    # Only numeric loopback URLs are used. External hostname resolution is disabled
    # in this isolated browser session, without changing system settings.
    options.add_argument("--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1")
    options.set_capability("goog:loggingPrefs", {"browser": "ALL", "performance": "ALL"})
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)
    return driver


def state(driver):
    return driver.find_element(By.TAG_NAME, "html").get_attribute("data-state")


def read_predictions(driver):
    rows = driver.find_elements(By.CSS_SELECTOR, ".result-row")
    boxes = driver.find_elements(By.CSS_SELECTOR, ".detection-box")
    assert len(rows) == len(boxes)
    return [{"label": row.get_attribute("data-label"), "score": float(row.get_attribute("data-score")),
             "box": {name: float(box.get_attribute("data-" + name)) for name in ("xmin", "ymin", "xmax", "ymax")}}
            for row, box in zip(rows, boxes)]


def resource_urls(driver):
    urls = set()
    for entry in driver.get_log("performance"):
        message = json.loads(entry["message"])["message"]
        if message["method"] == "Network.requestWillBeSent":
            url = message["params"]["request"]["url"]
            if url.startswith(("http://", "https://")):
                urls.add(url)
    return sorted(urls)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    server = make_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    report = {"evidence_type": "actual CPU/WASM inference on public sample photos",
              "limitations": ["Small convenience sample, not a general accuracy benchmark.",
                              "Expected labels use upstream image descriptions and independent AI-assisted visual review before inference; they are not exhaustive human annotations.",
                              "Times measure observed UI completion, including decoding/rendering and browser polling.",
                              "Workstation load is not controlled; values are not performance guarantees.",
                              "Baseline uses the common pinned runtime; it is not the stock upstream release."],
              "model": json.loads((ROOT / "asset-lock.json").read_text(encoding="utf-8"))["model_revision"],
              "app": [], "baseline": [], "network": []}
    try:
        driver = browser()
        try:
            report["browser_version"] = driver.capabilities["browserVersion"]
            start = time.perf_counter()
            driver.get(base)
            WebDriverWait(driver, 120).until(lambda d: state(d) in {"ready", "error"})
            assert state(driver) == "ready", driver.find_element(By.ID, "error-message").text
            report["initial_app_ready_seconds"] = round(time.perf_counter() - start, 3)
            driver.save_screenshot(str(OUTPUT / "empty-desktop.png"))
            for filename, expected in PHOTOS.items():
                start = time.perf_counter()
                driver.find_element(By.ID, "file-input").send_keys(str(ROOT / "dist" / "samples" / filename))
                WebDriverWait(driver, 120).until(lambda d: state(d) in {"complete", "empty", "error"})
                elapsed = round(time.perf_counter() - start, 3)
                assert state(driver) in {"complete", "empty"}, driver.find_element(By.ID, "error-message").text
                predictions = read_predictions(driver)
                labels = [item["label"] for item in predictions]
                record = {"image": filename, "expected_visible_labels": expected,
                          "expected_labels_present": all(label in labels for label in expected) if expected else None,
                          "ui_completion_seconds": elapsed, "predictions": predictions}
                report["app"].append(record)
                driver.save_screenshot(str(OUTPUT / f"{Path(filename).stem}-desktop.png"))
                print(f"{filename}: {labels}; observed UI completion {elapsed}s", flush=True)
                if filename == "coffee.png":
                    driver.find_element(By.CSS_SELECTOR, '.result-row[data-label="cup"]').click()
                    driver.save_screenshot(str(OUTPUT / "coffee-selected-cup.png"))
                    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
                        "width": 390, "height": 844, "deviceScaleFactor": 1, "mobile": False,
                    })
                    driver.save_screenshot(str(OUTPUT / "coffee-narrow.png"))
                    driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
            report["network"].extend(resource_urls(driver))
            report["app_console"] = driver.get_log("browser")
        finally:
            driver.quit()

        driver = browser()
        try:
            start = time.perf_counter()
            driver.get(base + "/baseline/")
            WebDriverWait(driver, 120).until(lambda d: d.find_element(By.ID, "status").text == "Ready")
            report["initial_baseline_ready_seconds"] = round(time.perf_counter() - start, 3)
            for filename in list(PHOTOS)[:3]:
                start = time.perf_counter()
                driver.find_element(By.ID, "file-upload").send_keys(str(ROOT / "dist" / "samples" / filename))
                WebDriverWait(driver, 120).until(lambda d: d.find_element(By.ID, "status").text == ""
                                               and d.find_elements(By.CSS_SELECTOR, ".bounding-box"))
                elapsed = round(time.perf_counter() - start, 3)
                predictions = driver.execute_script("""
                    return [...document.querySelectorAll('.bounding-box')].map(box => {
                        const x = parseFloat(box.style.left) / 100;
                        const y = parseFloat(box.style.top) / 100;
                        const clamp = value => Math.max(0, Math.min(1, value));
                        return {label: box.textContent, box: {
                            xmin: clamp(x), ymin: clamp(y),
                            xmax: clamp(x + parseFloat(box.style.width) / 100),
                            ymax: clamp(y + parseFloat(box.style.height) / 100)}};
                    });
                """)
                current = next(item for item in report["app"] if item["image"] == filename)["predictions"]
                matching = len(current) == len(predictions) and all(
                    left["label"] == right["label"] and all(abs(left["box"][key] - right["box"][key]) < 0.00001
                    for key in ("xmin", "ymin", "xmax", "ymax")) for left, right in zip(current, predictions)
                )
                report["baseline"].append({"image": filename, "ui_completion_seconds": elapsed,
                                           "predictions": predictions, "matches_app_labels_and_boxes": matching})
                driver.save_screenshot(str(OUTPUT / f"{Path(filename).stem}-baseline.png"))
                print(f"Baseline {filename}: matches application predictions = {matching}", flush=True)
            report["network"].extend(resource_urls(driver))
            report["baseline_console"] = driver.get_log("browser")
        finally:
            driver.quit()
        report["network"] = sorted(set(report["network"]))
        report["external_http_requests"] = [url for url in report["network"] if urlsplit(url).hostname != "127.0.0.1"]
        assert not report["external_http_requests"], report["external_http_requests"]
        assert all(item["matches_app_labels_and_boxes"] for item in report["baseline"])
    finally:
        (OUTPUT / "observations.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    print(f"Evidence saved in {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
