"""Run the integrated local suite and retain source-bound, hostname-free evidence.

Uses installed dependencies, cached ChromeDriver and prepared local assets only.
Each execution gets a new raw-results directory and a pytest temporary directory
outside Git. Historical evidence is never rewritten. No publication is performed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_REAL_CASES = {
    "tests/test_inference.py::test_real_model_detects_reviewed_object[astronaut.png-person]",
    "tests/test_inference.py::test_real_model_detects_reviewed_object[coffee.png-cup]",
    "tests/test_inference.py::test_real_model_detects_reviewed_object[chelsea.png-cat]",
    "tests/test_public_package.py::test_packaged_site_runs_real_sample_filter_and_export_on_an_ordinary_static_server",
}


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_hashes():
    paths = [ROOT / name for name in (
        "serve.py", "pytest.ini", "requirements.txt", "requirements-lock.txt",
        "asset-lock.json", "credits-lock.json",
        "docs/evidence/model-observations.json",
    )]
    paths += [path for path in (ROOT / "dist").iterdir() if path.is_file()]
    for folder in ("tests", "tools"):
        paths += [path for path in (ROOT / folder).rglob("*")
                  if path.is_file() and path.suffix in {".py", ".js"}]
    return {path.relative_to(ROOT).as_posix(): sha256(path) for path in sorted(paths)}


def write_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")


def pytest_runtest_teardown(item):
    """When loaded as a pytest plugin, retain actual browser/driver versions."""
    destination = os.environ.get("OBJECT_LENS_VERIFICATION_ENVIRONMENT")
    driver = item.funcargs.get("browser")
    capabilities = getattr(driver, "capabilities", None)
    if not destination or not isinstance(capabilities, dict):
        return
    path = Path(destination)
    value = {
        "browser": capabilities.get("browserName"),
        "browser_version": capabilities.get("browserVersion"),
        "driver_version": capabilities.get("chrome", {}).get("chromedriverVersion", "").split(" ")[0],
        "browser_platform": capabilities.get("platformName"),
    }
    records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    if value not in records:
        records.append(value)
        write_json(path, records)


def pytest_collection_finish(session):
    destination = os.environ.get("OBJECT_LENS_VERIFICATION_ENVIRONMENT")
    if destination:
        write_json(Path(destination).with_suffix(".tests.json"), {
            "inference_node_ids": [item.nodeid for item in session.items
                                   if item.get_closest_marker("inference") is not None],
            "collected": len(session.items),
        })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retain-prefix", help="New docs/evidence prefix, for example verification")
    args = parser.parse_args()
    if args.retain_prefix and (not args.retain_prefix.replace("-", "").isalnum()):
        parser.error("Use only letters, digits and hyphens for the evidence prefix")
    targets = []
    if args.retain_prefix:
        targets = [ROOT / "docs" / "evidence" / f"{args.retain_prefix}-{suffix}"
                   for suffix in ("full-suite.xml", "verification.json")]
        if any(path.exists() for path in targets):
            parser.error("Evidence already exists; choose a fresh prefix to preserve it")
    output_parent = ROOT / "artifacts" / "verification"
    output_parent.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="suite-", dir=output_parent))
    temporary_parent = Path(tempfile.mkdtemp(prefix="object-lens-pytest-"))
    before = source_hashes()
    environment = dict(os.environ, SE_CACHE_PATH=str(ROOT / ".local" / "selenium"),
                       SE_AVOID_STATS="true", SE_OFFLINE="true",
                       OBJECT_LENS_VERIFICATION_ENVIRONMENT=str(output / "browsers.json"))
    # An inherited selection such as -m "not inference" must not turn this full
    # verification command into a green partial run with old model observations.
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    command = [sys.executable, "-m", "pytest", "-p", "tools.record_verification",
               f"--junitxml={output / 'full-suite.xml'}", f"--basetemp={temporary_parent / 'cases'}"]
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    start = time.perf_counter()
    # Write the full log while streaming normal pytest progress to the caller.
    with (output / "pytest.log").open("w", encoding="utf-8", newline="\n") as log:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for line in process.stdout:
            log.write(line)
            log.flush()
            print(line, end="", flush=True)
        returncode = process.wait()
    elapsed = round(time.perf_counter() - start, 3)
    raw_xml = output / "full-suite.xml"
    tree = ET.parse(raw_xml)
    suites = list(tree.getroot().iter("testsuite"))
    counts = {key: sum(int(suite.get(key, 0)) for suite in suites)
              for key in ("tests", "failures", "errors", "skipped")}
    counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    collection = json.loads((output / "browsers.tests.json").read_text(encoding="utf-8"))
    real_count = len(collection["inference_node_ids"])
    passed_nodes = {case.get("classname", "").replace(".", "/") + ".py::" + case.get("name", "")
                    for case in tree.getroot().iter("testcase")
                    if all(case.find(outcome) is None for outcome in ("failure", "error", "skipped"))}
    required_real_cases_passed = REQUIRED_REAL_CASES <= passed_nodes
    after = source_hashes()
    observations = []
    # These three reports are written by the real-sample tests in this execution.
    # Keep a run-specific raw copy before a later pytest invocation overwrites them.
    if returncode == 0 and required_real_cases_passed:
        inference_output = output / "inference"
        inference_output.mkdir()
        for name in ("astronaut", "coffee", "chelsea"):
            record = ROOT / "artifacts" / "inference" / f"{name}.json"
            observations.append(json.loads(record.read_text(encoding="utf-8")))
            for suffix in (".json", ".png"):
                shutil.copyfile(record.with_suffix(suffix), inference_output / f"{name}{suffix}")
    report = {
        "started_at_utc": started,
        "evidence_type": "Integrated local pytest run of the application and tests identified by source_sha256",
        "base_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_identity": "Base commit plus source_sha256 identifies the tested uncommitted changes; documentation is recorded separately.",
        "source_sha256": before, "sources_unchanged_during_run": before == after,
        "result": {**counts, "real_model_cases": real_count,
                   "other_cases": counts["tests"] - real_count,
                   "pytest_seconds": round(sum(float(s.get("time", 0)) for s in suites), 3),
                   "wall_seconds": elapsed, "exit_code": returncode},
        "environment": {"python": platform.python_version(), "os": platform.platform(),
                        "pytest": importlib.metadata.version("pytest"),
                        "selenium": importlib.metadata.version("selenium"),
                        "browsers": json.loads((output / "browsers.json").read_text(encoding="utf-8"))
                        if (output / "browsers.json").exists() else []},
        "collection": collection,
        "required_real_cases_passed": required_real_cases_passed,
        "real_sample_observations": observations,
        "command": ".venv\\Scripts\\python.exe tools/record_verification.py"
                   + (f" --retain-prefix {args.retain_prefix}" if args.retain_prefix else ""),
        "pytest_arguments": ["-m", "pytest", "-p", "tools.record_verification",
                             "--junitxml=<new-raw-directory>/full-suite.xml",
                             "--basetemp=<new-owned-temporary-directory>/cases"],
        "repeat_note": "Choose a fresh retain prefix; existing evidence paths are never overwritten.",
        "execution": {"headless": True, "browser_concurrency": 1, "selenium_offline": True,
                      "pytest_temporary_directory_outside_git": True,
                      "inherited_pytest_addopts_ignored": True,
                      "inherited_pytest_plugins_ignored": True,
                      "raw_directory": output.relative_to(ROOT).as_posix()},
        "raw_xml_sha256": sha256(raw_xml),
        "retained_xml_transformation": "Remove hostname attributes only; serialize XML as UTF-8 with LF. Counts and test outcomes are unchanged.",
        "limits": ["One local Windows/Chrome environment; no remote CI or deployment validation.",
                   "Three selected-label and box-regression samples plus one real-model static-package smoke case are not an accuracy benchmark.",
                   "Non-model cases include controlled browser checks, server/package checks and harness cleanup checks.",
                   "One integrated execution is not a measured flake rate."]
    }
    report["passed"] = (returncode == 0 and before == after and required_real_cases_passed
                        and counts["tests"] == collection["collected"]
                        and not any(counts[k] for k in ("failures", "errors", "skipped")))
    if args.retain_prefix and report["passed"]:
        for element in tree.iter():
            element.attrib.pop("hostname", None)
        targets[0].write_bytes(ET.tostring(tree.getroot(), encoding="utf-8", xml_declaration=True) + b"\n")
        report["retained_xml"] = targets[0].relative_to(ROOT).as_posix()
        report["retained_xml_sha256"] = sha256(targets[0])
        write_json(targets[1], report)
    write_json(output / "verification.json", report)
    print(json.dumps({"passed": report["passed"], "result": report["result"], "raw_directory": str(output)}, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
