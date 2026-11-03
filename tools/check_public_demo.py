"""Review a prepared static package with SIMULATED model transfer on loopback.

This is local QA using the real model, not an Internet benchmark or hosted test.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import struct
import tempfile
import threading
import time
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
MODEL = "/assets/models/Xenova/detr-resnet-50/onnx/model_quantized.onnx"


def snapshot(driver):
    return driver.execute_script("""
        const panel = document.getElementById('model-loading');
        return {state: document.documentElement.dataset.state, visible: !panel.hidden,
          phase: panel.dataset.phase, progress: document.getElementById('model-loading-progress').getAttribute('value'),
          detail: document.getElementById('model-loading-detail').textContent,
          stage: document.getElementById('model-loading-stage').textContent};
    """)


def capture(driver, path):
    size = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})["cssContentSize"]
    png = driver.execute_cdp_cmd("Page.captureScreenshot", {
        "format": "png", "captureBeyondViewport": True,
        "clip": {"x": 0, "y": 0, "width": size["width"], "height": size["height"], "scale": 1},
    })
    path.write_bytes(base64.b64decode(png["data"]))


def viewport(driver, width, controls=False):
    driver.execute_cdp_cmd("Emulation.setDeviceMetricsOverride", {
        "width": width, "height": 1000, "deviceScaleFactor": 1, "mobile": False,
    })
    return driver.execute_script("""
        return {width: innerWidth, usable: document.documentElement.clientWidth,
          content: document.documentElement.scrollWidth,
          controls: arguments[0] ? ['choose-image','try-sample','clear-image','save-result','minimum-score'].map(id => {
            const box = document.getElementById(id).getBoundingClientRect();
            return {id, left: box.left, right: box.right, width: box.width};
          }) : []};
    """, controls)


def check(site, output, mbps):
    output.mkdir(parents=True, exist_ok=True)
    out = Path(tempfile.mkdtemp(prefix="run-", dir=output))
    downloads = out / "downloads"
    downloads.mkdir()
    stop = threading.Event()
    transfers = []
    report = {"evidence_type": "Local static-package QA with real model inference",
              "simulation": "Only the ONNX response body is paced on loopback; other assets are unpaced.",
              "limits": "Not an Internet speed benchmark, hosted deployment check or general accuracy measurement.",
              "site_directory": str(site), "target_model_mbps": mbps, "model_transfers": transfers,
              "loading_observations": [], "app_viewports": [], "credits_viewports": [], "passed": False}

    class PacedModelHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if urlsplit(self.path).path != MODEL:
                return super().do_GET()
            model = site / MODEL.lstrip("/")
            record = {"path": MODEL, "bytes": 0, "expected_bytes": model.stat().st_size, "complete": False}
            transfers.append(record)
            started = time.perf_counter()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/octet-stream")
                self.send_header("Content-Length", str(record["expected_bytes"]))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                with model.open("rb") as stream:
                    while block := stream.read(65536):
                        due = started + (record["bytes"] + len(block)) / (mbps * 1_000_000 / 8)
                        if stop.wait(max(0, due - time.perf_counter())):
                            break
                        self.wfile.write(block)
                        record["bytes"] += len(block)
                record["complete"] = record["bytes"] == record["expected_bytes"]
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                record["aborted"] = True
            finally:
                elapsed = time.perf_counter() - started
                record.update(elapsed_seconds=round(elapsed, 3), observed_mbps=round(record["bytes"] * 8 / elapsed / 1_000_000, 3))

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(PacedModelHandler, directory=str(site)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    driver = None
    try:
        os.environ.update(SE_CACHE_PATH=str(ROOT / ".local" / "selenium"), SE_AVOID_STATS="true", SE_OFFLINE="true")
        options = webdriver.ChromeOptions()
        for flag in ["--headless=new", "--window-size=1440,1000", "--no-first-run", "--no-default-browser-check",
                     "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost, EXCLUDE 127.0.0.1",
                     f"--user-data-dir={out / 'chrome-profile'}"]:
            options.add_argument(flag)
        options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        driver.execute_cdp_cmd("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": str(downloads)})
        report["browser_version"] = driver.capabilities.get("browserVersion")
        started = time.perf_counter()
        driver.get(url)

        def observe_ready(browser):
            observed = snapshot(browser)
            prior = report["loading_observations"][-1] if report["loading_observations"] else None
            if not prior or any(prior[key] != value for key, value in observed.items()):
                report["loading_observations"].append({**observed, "elapsed_seconds": round(time.perf_counter() - started, 3)})
            value = float(observed["progress"]) if observed["progress"] is not None else None
            if value is not None and 20 <= value < 100 and "loading_capture" not in report:
                driver.save_screenshot(str(out / "model-loading.png"))
                report["loading_capture"] = observed
            assert observed["state"] != "error", browser.find_element(By.ID, "error-message").text
            return observed["state"] == "ready"

        WebDriverWait(driver, 120, poll_frequency=0.2).until(observe_ready)
        report["cold_ready_seconds"] = round(time.perf_counter() - started, 3)
        assert "loading_capture" in report and not snapshot(driver)["visible"]
        assert transfers and all(record["complete"] for record in transfers)
        driver.find_element(By.ID, "try-sample").click()
        WebDriverWait(driver, 120).until(lambda d: d.find_element(By.TAG_NAME, "html").get_attribute("data-state") in {"complete", "empty", "error"})
        assert driver.find_element(By.TAG_NAME, "html").get_attribute("data-state") == "complete"
        predictions = lambda: [{"label": row.get_attribute("data-label"), "score": float(row.get_attribute("data-score"))}
                               for row in driver.find_elements(By.CSS_SELECTOR, ".result-row")]
        report["predictions"] = predictions()
        assert "cup" in [item["label"] for item in report["predictions"]]
        driver.execute_script("const e=document.getElementById('minimum-score');e.value='0.80';e.dispatchEvent(new Event('input',{bubbles:true}));")
        report["filtered_predictions"] = predictions()
        assert report["filtered_predictions"] == [item for item in report["predictions"] if item["score"] >= 0.8]
        driver.find_element(By.ID, "save-result").click()
        files = WebDriverWait(driver, 15).until(lambda d: list(downloads.glob("*.png")) if not list(downloads.glob("*.crdownload")) else [])
        payload = files[0].read_bytes()
        assert payload[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", payload[16:24]) == (600, 400)
        report["export"] = files[0].relative_to(out).as_posix()
        for width in [320, 390, 768, 1440]:
            metrics = viewport(driver, width, True)
            report["app_viewports"].append(metrics)
            capture(driver, out / f"app-{width}.png")
            assert metrics["content"] <= metrics["usable"] + 1, metrics
            assert all(c["left"] >= -1 and c["right"] <= metrics["usable"] + 1 and c["width"] > 0 for c in metrics["controls"]), metrics
        driver.get(url + "/credits.html")
        links = {element.get_attribute("href") for element in driver.find_elements(By.CSS_SELECTOR, "a[href]")}
        report["local_credit_links"] = []
        for link in sorted(links):
            if urlsplit(link).netloc == urlsplit(url).netloc and not urlsplit(link).fragment:
                with urlopen(Request(link, method="HEAD"), timeout=10) as response:
                    report["local_credit_links"].append({"url_path": urlsplit(link).path, "method": "HEAD", "status": response.status})
                    assert response.status == 200
        for width in [1440, 320]:
            metrics = viewport(driver, width)
            report["credits_viewports"].append(metrics)
            driver.execute_script("scrollTo(0, 0)")
            capture(driver, out / f"credits-{width}.png")
            assert metrics["content"] <= metrics["usable"] + 1, metrics
        report["credits_keyboard_focus"] = []
        for _ in range(len(driver.find_elements(By.CSS_SELECTOR, "a[href]")) + 2):
            driver.switch_to.active_element.send_keys(Keys.TAB)
            focus = driver.execute_script("const e=document.activeElement,s=getComputedStyle(e);return {tag:e.tagName,text:e.textContent.trim(),visible:e.matches(':focus-visible'),outline:s.outlineStyle,width:parseFloat(s.outlineWidth)};")
            if focus["tag"] == "A":
                report["credits_keyboard_focus"].append(focus)
                assert focus["visible"] and focus["outline"] != "none" and focus["width"] > 0, focus
        assert report["credits_keyboard_focus"]
        report["console"] = driver.get_log("browser")
        report["passed"] = True
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        stop.set()
        try:
            if driver is not None:
                driver.quit()
        finally:
            try:
                server.shutdown()
            finally:
                server.server_close()
                thread.join(timeout=5)
                (out / "observations.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                print(json.dumps({"review_directory": str(out), "report": str(out / "observations.json"), "passed": report["passed"]}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "public-release" / "review")
    parser.add_argument("--model-mbps", type=float, default=10)
    args = parser.parse_args()
    if not args.site.is_absolute() or not args.site.is_dir() or not (args.site / MODEL.lstrip("/")).is_file():
        parser.error("--site must be an absolute existing package directory containing the model")
    if not math.isfinite(args.model_mbps) or args.model_mbps <= 0:
        parser.error("--model-mbps must be a finite positive number")
    check(args.site.resolve(), args.output.resolve(), args.model_mbps)
