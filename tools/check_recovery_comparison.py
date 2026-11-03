"""Compare three recovery checks against old and current app.js in disposable copies.

Uses installed pytest/Selenium and the repository's cached browser driver offline.
Only app.js differs between copies. No model is loaded and no tracked file is changed.
Each output directory is new so prior comparison evidence is preserved.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CASES = [
    "test_model_load_timeout_clear_and_retry_describe_detector_availability",
    "test_inference_timeout_clear_and_retry_describe_detector_availability",
    "test_worker_crash_during_inference_is_not_described_as_startup_failure",
]
EXPECTED_FAILURE_CONTENT = [
    "detection took too long. try again or choose another image.",
    "detection took too long. try again or choose another image.",
    "object detection could not start. try again or reload the page.",
]


def digest(content):
    return hashlib.sha256(content).hexdigest()


def input_hashes():
    inputs = [ROOT / "serve.py", ROOT / "pytest.ini", Path(__file__).resolve()]
    inputs.extend(path for path in (ROOT / "tests").rglob("*")
                  if path.is_file() and path.suffix in {".py", ".js"})
    inputs.extend(path for path in (ROOT / "dist").iterdir() if path.is_file())
    return {path.relative_to(ROOT).as_posix(): digest(path.read_bytes()) for path in sorted(inputs)}


def portable(text, output):
    for path, replacement in [(output, "<disposable-copy>"), (ROOT, "<repository>"),
                              (Path.home(), "<user-home>")]:
        for spelling in (str(path), path.as_posix(), str(path).replace("\\", "\\\\")):
            text = text.replace(spelling, replacement)
    return text


def run_copy(destination, app_bytes, environment):
    destination.mkdir()
    shutil.copytree(ROOT / "tests", destination / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    (destination / "dist").mkdir()
    for name in ("serve.py", "pytest.ini"):
        shutil.copyfile(ROOT / name, destination / name)
    for source in (ROOT / "dist").iterdir():
        if source.is_file():
            shutil.copyfile(source, destination / "dist" / source.name)
    (destination / "dist" / "app.js").write_bytes(app_bytes)
    junit = destination.parent / f"{destination.name}.xml"
    command = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q",
               f"--basetemp={destination / 'pytest-temp'}",
               *[f"tests/test_recovery.py::{case}" for case in CASES], f"--junitxml={junit}"]
    result = subprocess.run(command, cwd=destination, env=environment,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    (destination.parent / f"{destination.name}.log").write_text(
        result.stdout + result.stderr, encoding="utf-8", newline="\n",
    )
    if not junit.is_file():
        raise RuntimeError(f"{destination.name} did not produce JUnit; inspect its log")
    root = ET.parse(junit).getroot()
    cases = []
    for case in root.iter("testcase"):
        failure = case.find("failure")
        error = case.find("error")
        cases.append({"name": case.attrib["name"],
                      "outcome": "failure" if failure is not None else "error" if error is not None else "pass",
                      "details": failure.text if failure is not None else error.text if error is not None else ""})
    return {"returnCode": result.returncode, "cases": cases, "junit": junit.name,
            "durationSeconds": sum(float(suite.attrib.get("time", "0")) for suite in root.iter("testsuite")),
            "appSha256": digest(app_bytes)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", default="74d108f70c0bea8ca09b2d5bdd3bb974023d523f")
    parser.add_argument("--output", type=Path, required=True, help="New directory for immutable comparison outputs")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    baseline_ref = subprocess.check_output(
        ["git", "rev-parse", "--verify", args.baseline_ref + "^{commit}"], cwd=ROOT, text=True,
    ).strip()
    baseline = subprocess.check_output(["git", "show", f"{baseline_ref}:dist/app.js"], cwd=ROOT)
    current = (ROOT / "dist" / "app.js").read_bytes()
    initial_hashes = input_hashes()
    environment = {**os.environ, "SE_OFFLINE": "true", "SE_AVOID_STATS": "true",
                   "SE_CACHE_PATH": str(ROOT / ".local" / "selenium"), "PYTHONIOENCODING": "utf-8"}
    before = run_copy(output / "baseline", baseline, environment)
    after = run_copy(output / "current", current, environment)
    expected_before = (before["returnCode"] == 1 and len(before["cases"]) == len(CASES)
                       and all(case["name"] == name and case["outcome"] == "failure"
                               and expected in (case["details"] or "")
                               for case, name, expected in zip(before["cases"], CASES, EXPECTED_FAILURE_CONTENT)))
    expected_after = (after["returnCode"] == 0 and len(after["cases"]) == len(CASES)
                      and all(case["outcome"] == "pass" for case in after["cases"]))
    final_hashes = input_hashes()
    checkout_app_unchanged = current == (ROOT / "dist" / "app.js").read_bytes()
    source_tests_unchanged = initial_hashes == final_hashes
    for run in (before, after):
        for case in run["cases"]:
            case["details"] = portable(case["details"] or "", output)
    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evidenceType": "Controlled before/after recovery regression checks; no real-model fault",
        "baselineRef": baseline_ref,
        "loadDeadline": "Only the isolated test page's 120000ms callback is accelerated to 2500ms",
        "baselineLimit": "The baseline fails at pre-Clear timeout/crash wording assertions. "
                         "These failures do not independently reproduce its Clear wording; "
                         "current passing checks continue through Clear and successful recovery.",
        "sourceHashes": initial_hashes,
        "checkout_app_unchanged": checkout_app_unchanged,
        "source_tests_unchanged": source_tests_unchanged,
        "before": before, "after": after,
        "expectedThreeBaselineFailures": expected_before,
        "expectedThreeCurrentPasses": expected_after,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(output), "expectedThreeBaselineFailures": expected_before,
                      "expectedThreeCurrentPasses": expected_after}, indent=2))
    return 0 if expected_before and expected_after and checkout_app_unchanged and source_tests_unchanged else 1


if __name__ == "__main__":
    raise SystemExit(main())
