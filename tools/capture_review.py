"""Capture the current app and controlled timeout feedback in headless Chrome.

Real-model captures and deliberately simulated failure captures are identified
separately. No Internet assets are downloaded, no desktop UI is controlled, and
every run uses its own loopback servers and browser sessions.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from serve import make_server
from tools.check_public_demo import capture, viewport
from tools.collect_evidence import browser, resource_urls, state
from tools.record_verification import sha256, source_hashes, write_json


@contextmanager
def application(test_mode=False):
    server = make_server(port=0, test_mode=test_mode)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    driver = None
    try:
        driver = browser()
        driver.get(f"http://127.0.0.1:{server.server_port}")
        WebDriverWait(driver, 120).until(lambda d: state(d) in {"ready", "error"})
        assert state(driver) == "ready", driver.find_element(By.ID, "error-message").text
        yield driver
    finally:
        try:
            if driver is not None:
                driver.quit()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def wait(driver, expected):
    WebDriverWait(driver, 120).until(lambda d: state(d) in {expected, "error"})
    assert state(driver) == expected, driver.find_element(By.ID, "error-message").text


def set_minimum(driver, value):
    driver.execute_script("""
        const input = document.getElementById('minimum-score');
        input.value = arguments[0]; input.dispatchEvent(new Event('input', {bubbles: true}));
    """, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    out = args.screenshots.resolve()
    if out.exists() and any(out.iterdir()) or args.report.exists():
        parser.error("Use fresh screenshot/report paths to preserve previous captures")
    out.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    work_parent = ROOT / "artifacts" / "review-followup"
    work_parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="captures-", dir=work_parent))
    downloads = work / "downloads"
    downloads.mkdir()
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "source_sha256": source_hashes(), "captures": [], "viewports": [], "passed": False,
              "limits": "Rendered content and configuration on local Chrome/Windows; no actual screen-reader, accuracy or deployment claim."}

    def snapshot(driver, filename, evidence_type, description):
        target = out / filename
        capture(driver, target)
        report["captures"].append({"file": filename, "sha256": sha256(target),
                                   "evidence_type": evidence_type, "description": description,
                                   "state": state(driver),
                                   "status": driver.find_element(By.ID, "status").text,
                                   "error": driver.find_element(By.ID, "error-message").text})

    try:
        with application() as driver:
            report["browser_version"] = driver.capabilities["browserVersion"]
            report["driver_version"] = driver.capabilities["chrome"]["chromedriverVersion"].split(" ")[0]
            driver.execute_cdp_cmd("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(downloads)})
            snapshot(driver, "empty.png", "real application", "Ready workspace after real model startup.")
            start = time.perf_counter()
            driver.find_element(By.ID, "try-sample").click()
            wait(driver, "complete")
            report["sample_ui_seconds"] = round(time.perf_counter() - start, 3)
            rows = driver.find_elements(By.CSS_SELECTOR, ".result-row")
            report["predictions"] = [{"label": r.find_element(By.CSS_SELECTOR, ".object-name").text,
                                      "displayed_score": r.find_element(By.CSS_SELECTOR, ".object-score").text,
                                      "score": float(r.get_attribute("data-score"))} for r in rows]
            assert "cup" in [item["label"] for item in report["predictions"]]
            driver.find_element(By.CSS_SELECTOR, '.result-row[data-label="cup"]').click()
            snapshot(driver, "desktop.png", "real model inference", "Coffee sample at 0.50 with the cup selected; all predictions remain visible.")
            set_minimum(driver, "0.80")
            snapshot(driver, "filtered.png", "real model inference", "The 0.80 display filter keeps existing predictions without rerunning the model.")
            driver.find_element(By.ID, "save-result").click()
            files = WebDriverWait(driver, 20).until(lambda d: list(downloads.glob("*.png"))
                if not list(downloads.glob("*.crdownload")) else [])
            shutil.copyfile(files[0], out / "export.png")
            report["captures"].append({"file": "export.png", "sha256": sha256(out / "export.png"),
                                       "evidence_type": "real annotated PNG export",
                                       "description": "Downloaded original-resolution coffee PNG at minimum score 0.80.",
                                       "download_name": files[0].name})
            assert "PNG" in driver.find_element(By.ID, "export-message").text
            set_minimum(driver, "1.00")
            assert state(driver) == "filtered-empty"
            snapshot(driver, "filtered-empty.png", "real model inference", "At 1.00 the display filter hides all predictions and disables export.")
            set_minimum(driver, "0.80")
            for width in (320, 390, 768, 1440):
                metrics = viewport(driver, width, True)
                assert metrics["content"] <= metrics["usable"] + 1, metrics
                assert all(c["left"] >= -1 and c["right"] <= metrics["usable"] + 1 and c["width"] > 0
                           for c in metrics["controls"]), metrics
                report["viewports"].append(metrics)
                snapshot(driver, f"width-{width}.png", "real model inference",
                         f"Full page at {width} CSS pixels; viewport emulation is not a mobile-device test.")
            driver.execute_cdp_cmd("Emulation.clearDeviceMetricsOverride", {})
            invalid = work / "unsupported.txt"
            invalid.write_text("Deliberately unsupported image input.\n", encoding="utf-8")
            driver.find_element(By.ID, "file-input").send_keys(str(invalid))
            wait(driver, "error")
            message = driver.find_element(By.ID, "error-message").text.lower()
            assert all(word in message for word in ("jpeg", "png", "choose"))
            snapshot(driver, "error.png", "real application with deliberately invalid input",
                     "Unsupported file feedback explains accepted formats and the next action.")
            driver.find_element(By.ID, "clear-image").click()
            wait(driver, "ready")
            report["real_console"] = driver.get_log("browser")
            report["external_http_requests"] = [u for u in resource_urls(driver) if urlsplit(u).hostname != "127.0.0.1"]
            assert not report["external_http_requests"]
        with application(test_mode=True) as driver:
            silent = work / "silent.png"
            shutil.copyfile(ROOT / "dist" / "samples" / "coffee.png", silent)
            driver.find_element(By.ID, "file-input").send_keys(str(silent))
            wait(driver, "error")
            message = driver.find_element(By.ID, "error-message").text.lower()
            assert "too long" in message and "image" in message
            snapshot(driver, "timeout.png", "controlled worker failure",
                     "Simulated nonresponding inference triggers the controlled four-second deadline.")
            driver.find_element(By.ID, "clear-image").click()
            assert state(driver) == "error"
            assert "unavailable" in driver.find_element(By.ID, "error-message").text.lower()
            snapshot(driver, "timeout-cleared.png", "controlled worker failure",
                     "Clear removes the image but truthfully keeps the stopped detector unavailable with retry.")
            driver.find_element(By.ID, "retry-detection").click()
            wait(driver, "ready")
            report["controlled_retry_recovered"] = True
        report["sources_unchanged_during_capture"] = report["source_sha256"] == source_hashes()
        assert report["sources_unchanged_during_capture"], "Application or test sources changed during capture"
        report["passed"] = True
    finally:
        write_json(args.report, report)
    print(json.dumps({"passed": report["passed"], "screenshots": str(out), "report": str(args.report)}, indent=2))


if __name__ == "__main__":
    main()
