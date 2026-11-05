"""Capture the real model's result on each public sample photo in headless Chrome.

Used for the walkthrough. Each photo is chosen through the normal file input and
analysed by the real pinned model; nothing is simulated. The report records what
the page showed. It is not an accuracy measurement: the photos are a small,
partially annotated convenience set (see docs/IMAGE_SOURCES.md).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.capture_review import application
from tools.check_public_demo import capture
from tools.collect_evidence import state
from tools.record_verification import sha256, source_hashes, write_json

SAMPLES = ("astronaut.png", "chelsea.png", "camera.png", "rocket.jpg")


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
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "evidence_type": "real model inference on the public sample photos, for the walkthrough",
              "source_sha256": source_hashes(), "captures": [], "passed": False,
              "limits": "One run per photo in local Chrome on Windows at a 1440 x 1000 window. "
                        "Model output, not ground truth; not an accuracy measurement."}
    try:
        with application() as driver:
            report["browser_version"] = driver.capabilities["browserVersion"]
            for name in SAMPLES:
                driver.find_element(By.ID, "file-input").send_keys(str(ROOT / "dist" / "samples" / name))
                WebDriverWait(driver, 120).until(lambda d: state(d) in {"complete", "empty", "error"})
                assert state(driver) in {"complete", "empty"}, driver.find_element(By.ID, "error-message").text
                assert driver.find_element(By.ID, "filename").text == name
                rows = driver.find_elements(By.CSS_SELECTOR, ".result-row")
                target = out / f"sample-{Path(name).stem}.png"
                capture(driver, target)
                report["captures"].append({
                    "file": target.name, "sha256": sha256(target), "input": f"dist/samples/{name}",
                    "state": state(driver), "status": driver.find_element(By.ID, "status").text,
                    "results_message": driver.find_element(By.ID, "results-empty").text if not rows else "",
                    "predictions": [{"label": r.get_attribute("data-label"),
                                     "displayed_score": r.find_element(By.CSS_SELECTOR, ".object-score").text}
                                    for r in rows]})
                driver.find_element(By.ID, "clear-image").click()
                WebDriverWait(driver, 30).until(lambda d: state(d) == "ready")
        report["sources_unchanged_during_capture"] = report["source_sha256"] == source_hashes()
        assert report["sources_unchanged_during_capture"], "Application or test sources changed during capture"
        report["passed"] = True
    finally:
        write_json(args.report, report)
    print(json.dumps({"passed": report["passed"], "screenshots": str(out), "report": str(args.report)}, indent=2))


if __name__ == "__main__":
    main()
