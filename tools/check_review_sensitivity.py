"""Prove specific browser assertions detect deliberately seeded faults in copies.

Uses prepared local model assets and the existing Selenium cache, one browser at
a time. Never edits the application checkout. This is bounded test-sensitivity
evidence, not a mutation score, real model failure, or model accuracy benchmark.
Run with .venv/Scripts/python.exe tools/check_review_sensitivity.py.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VISIBLE = "tests/test_ui.py::test_predictions_and_boxes_match_the_current_image"
ROUNDING = "tests/test_ui.py::test_visible_scores_round_without_changing_the_underlying_values"
ANNOUNCEMENTS = "tests/test_ui.py::test_status_and_error_announcement_configuration_follows_visible_states"
GEOMETRY = "tests/test_inference.py"
MUTATIONS = (
    {
        "name": "blank-visible-labels", "path": "dist/app.js",
        "replacements": [("name.textContent = label;", "name.textContent = '';"),
                         ("tag.textContent = label;", "tag.textContent = '';" )],
        "tests": [VISIBLE], "expected_failures": 1, "reason_fragment": "laptop",
        "purpose": "Blank user-visible names and box labels while preserving data attributes.",
    },
    {
        "name": "blank-visible-scores", "path": "dist/app.js",
        "replacements": [("modelScore.textContent = score.toFixed(2);", "modelScore.textContent = '';" )],
        "tests": [VISIBLE, ROUNDING], "expected_failures": 2,
        "reason_fragment": "Visible model score does not match",
        "purpose": "Blank user-visible formatted scores while preserving numeric metadata.",
    },
    {
        "name": "displaced-rendered-boxes", "path": "dist/app.js",
        "replacements": [("left: `${box.xmin * 100}%`, top: `${box.ymin * 100}%`,",
                          "left: '50%', top: '50%',")],
        "tests": [GEOMETRY], "expected_failures": 3,
        "reason_fragment": "Rendered box regression",
        "purpose": "Move every rendered rectangle to the image center; preserve model coordinates and labels.",
    },
    {
        "name": "removed-announcement-configuration", "path": "dist/index.html",
        "replacements": [('role="status" aria-live="polite" aria-atomic="true"', ""),
                         ('role="alert"', "")],
        "tests": [ANNOUNCEMENTS], "expected_failures": 1,
        "reason_fragment": "Missing status role",
        "purpose": "Remove status/live-region/alert declarations while retaining visible page content.",
    },
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    paths = [ROOT / "serve.py", ROOT / "pytest.ini", Path(__file__).resolve(),
             ROOT / "docs/evidence/model-observations.json", ROOT / "asset-lock.json",
             ROOT / "requirements-lock.txt", ROOT / "requirements.txt"]
    paths += [path for path in (ROOT / "dist").iterdir() if path.is_file()]
    paths += sorted((ROOT / "tests").rglob("*.py"))
    paths += sorted((ROOT / "tests/fixtures").glob("*.js"))
    return {path.relative_to(ROOT).as_posix(): sha256(path) for path in sorted(set(paths))}


def copy_project(destination):
    # Model/sample bytes are immutable inputs. Only these may be hardlinked;
    # editable code, HTML, and tests are always independent copies.
    def copy_dist_file(source, target):
        relative = Path(source).relative_to(ROOT / "dist")
        if relative.parts[0] in {"assets", "samples"}:
            try:
                os.link(source, target)
                return target
            except OSError:
                pass
        return shutil.copy2(source, target)

    shutil.copytree(ROOT / "dist", destination / "dist", copy_function=copy_dist_file)
    shutil.copytree(ROOT / "tests", destination / "tests", ignore=shutil.ignore_patterns("__pycache__"))
    for filename in ("serve.py", "pytest.ini"):
        shutil.copy2(ROOT / filename, destination / filename)
    (destination / "docs/evidence").mkdir(parents=True)
    shutil.copy2(ROOT / "docs/evidence/model-observations.json", destination / "docs/evidence/model-observations.json")


def portable(text, copy_root):
    for path, replacement in ((copy_root, "<disposable-copy>"), (ROOT, "<repository>"),
                              (Path.home(), "<user-home>")):
        text = text.replace(str(path), replacement).replace(path.as_posix(), replacement)
    return text


def execute_case(name, destination, test_ids, output):
    xml_path = output / f"{name}.xml"
    command = [sys.executable, "-m", "pytest", *test_ids, "-q", "--tb=short",
               f"--basetemp={destination / '.pytest-temp'}", f"--junitxml={xml_path}"]
    environment = dict(os.environ)
    environment["SE_CACHE_PATH"] = str(ROOT / ".local/selenium")
    environment["SE_AVOID_STATS"] = "true"
    environment["SE_OFFLINE"] = "true"
    environment.pop("PYTEST_ADDOPTS", None)
    environment.pop("PYTEST_PLUGINS", None)
    started = time.monotonic()
    # Browser actions already have deadlines. Do not kill pytest in isolation:
    # its fixtures must get the chance to close their owned Chrome processes.
    completed = subprocess.run(command, cwd=destination, env=environment, capture_output=True,
                               text=True, encoding="utf-8", errors="replace")
    elapsed = round(time.monotonic() - started, 3)
    (output / f"{name}.log").write_text(portable(completed.stdout + completed.stderr, destination), encoding="utf-8")
    if not xml_path.is_file():
        raise RuntimeError(f"{name}: pytest produced no XML; inspect {name}.log")
    tree = ET.parse(xml_path)
    for suite in tree.iter("testsuite"):
        suite.attrib.pop("hostname", None)
    for element in tree.iter():
        element.attrib.update({key: portable(value, destination) for key, value in element.attrib.items()})
        if element.text:
            element.text = portable(element.text, destination)
    tree.write(xml_path, encoding="utf-8", xml_declaration=True)
    cases = []
    for case in tree.iter("testcase"):
        failure, error, skipped = case.find("failure"), case.find("error"), case.find("skipped")
        outcome = "failed" if failure is not None else "error" if error is not None else "skipped" if skipped is not None else "passed"
        problem = failure if failure is not None else error
        cases.append({"id": case.get("classname", "").replace(".", "/") + ".py::" + case.get("name", ""),
                      "outcome": outcome,
                      "reason": problem.get("message", "") if problem is not None else None})
    return {"name": name, "command": ["<venv-python>",
            *(portable(argument, destination) for argument in command[1:])],
            "elapsed_seconds": elapsed, "exit_code": completed.returncode,
            "counts": {key: sum(case["outcome"] == key for case in cases) for key in ("passed", "failed", "error", "skipped")},
            "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/review-sensitivity")
    arguments = parser.parse_args()
    output = arguments.output.resolve()
    if output.exists() and any(output.iterdir()):
        parser.error("Use a fresh output directory to preserve earlier sensitivity evidence")
    output.mkdir(parents=True, exist_ok=True)
    before = source_hashes()
    report = {"evidence_type": "deliberately seeded fault sensitivity in disposable copies",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "source_sha256": before, "python_version": sys.version.split()[0], "runs": [],
              "limits": ["Only the explicitly listed faults were seeded; no overall mutation score is measured.",
                         "Malformed/blank/displaced outputs are simulations, not observed real-model defects.",
                         "Reference boxes are earlier pinned-model outputs, not localization ground truth.",
                         "Announcement tests inspect DOM content/configuration, not actual assistive technology."]}
    try:
        for mutation in (None, *MUTATIONS):
            name = mutation["name"] if mutation else "clean-baseline"
            prefix = f"object-lens-{name}-"
            with tempfile.TemporaryDirectory(prefix=prefix) as temporary:
                destination = Path(temporary).resolve()
                if (destination.parent != Path(tempfile.gettempdir()).resolve()
                        or not destination.name.startswith(prefix)):
                    raise RuntimeError("Disposable directory is outside the owned temporary location")
                copy_project(destination)
                details = []
                if mutation:
                    target = destination / mutation["path"]
                    original = target.read_text(encoding="utf-8")
                    mutated = original
                    for old, new in mutation["replacements"]:
                        count = mutated.count(old)
                        expected_count = 3 if old.startswith('role="status"') else 1
                        if count != expected_count:
                            raise RuntimeError(f"{name}: expected {expected_count} occurrences of {old!r}; found {count}")
                        mutated = mutated.replace(old, new)
                        details.append({"before": old, "after": new, "occurrences": count})
                    original_sha256 = sha256(target)
                    target.write_text(mutated, encoding="utf-8", newline="\n")
                result = execute_case(name, destination,
                                      mutation["tests"] if mutation else [VISIBLE, ROUNDING, ANNOUNCEMENTS, GEOMETRY], output)
                if mutation:
                    result["mutation"] = {"path": mutation["path"], "purpose": mutation["purpose"],
                                          "replacements": details, "original_sha256": original_sha256,
                                          "mutated_sha256": sha256(target)}
                    failures = [case for case in result["cases"] if case["outcome"] == "failed"]
                    result["expected_outcome_verified"] = (
                        result["exit_code"] == 1 and len(failures) == mutation["expected_failures"]
                        and result["counts"]["error"] == result["counts"]["skipped"] == 0
                        and all(mutation["reason_fragment"] in case["reason"] for case in failures)
                    )
                else:
                    result["expected_outcome_verified"] = result["exit_code"] == 0 and result["counts"] == {
                        "passed": 6, "failed": 0, "error": 0, "skipped": 0}
                report["runs"].append(result)
                print(f"{name}: {result['counts']} expected={result['expected_outcome_verified']}", flush=True)
                if not result["expected_outcome_verified"]:
                    raise RuntimeError(f"{name}: observed result did not match the intended assertion outcome")
    finally:
        report["checkout_source_unchanged"] = before == source_hashes()
        report["all_expected_outcomes_verified"] = (
            len(report["runs"]) == len(MUTATIONS) + 1
            and all(run["expected_outcome_verified"] for run in report["runs"])
            and report["checkout_source_unchanged"])
        (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if not report["all_expected_outcomes_verified"]:
        raise SystemExit("Sensitivity verification incomplete; inspect summary.json")


if __name__ == "__main__":
    main()
