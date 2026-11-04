"""Prove specific browser assertions detect deliberately seeded faults in copies.

Uses prepared local model assets and the existing Selenium cache, one browser at
a time. Never edits the application checkout. This is bounded test-sensitivity
evidence, not a mutation score, real model failure, or model accuracy benchmark.
The faults named core-* break, once each, the five rules the project question
depends on; an equivalent-* fault is expected to change nothing observable.
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
RECOVERY = "tests/test_recovery.py::"
SLOW_LOAD = RECOVERY + "test_slow_steady_model_transfer_is_not_timed_out"
STALLED_LOAD = RECOVERY + "test_stalled_model_transfer_times_out_after_its_last_progress"
INITIALIZATION = RECOVERY + "test_model_initialization_has_its_own_deadline"
MALFORMED = RECOVERY + "test_malformed_result_is_rejected_without_partial_detections_and_recovers"
BLANK_LABELS = [MALFORMED + "[empty-label]", MALFORMED + "[blank-label]"]
COMPLETED_TRANSFER = RECOVERY + "test_completed_transfer_starts_initialization_before_the_done_event"
CLEARED_HANG = RECOVERY + "test_clear_during_a_hung_analysis_restarts_quietly"
# Core rules the project question depends on. Each is broken once on purpose below.
SIZE_BOUNDARY = ["tests/test_ui.py::test_file_size_boundary[10485760-complete]",
                 "tests/test_ui.py::test_file_size_boundary[10485761-error]"]
FILTER = "tests/test_filter.py"
STALE_RESULT = ["tests/test_ui.py::test_replacing_a_processing_image_discards_the_old_result[car.png]",
                "tests/test_ui.py::test_replacing_a_processing_image_discards_the_old_result[slow-car.png]",
                "tests/test_ui.py::test_clearing_a_processing_image_prevents_late_repaint"]
STALE_EXPORT = "tests/test_export.py::test_changed_result_cancels_a_png_still_being_encoded"
LATE_SAMPLE = "tests/test_sample.py::test_late_sample_response_cannot_override_a_later_user_action"
CLEAN_CONTROLS = [VISIBLE, ROUNDING, ANNOUNCEMENTS, GEOMETRY, SLOW_LOAD, STALLED_LOAD, INITIALIZATION, *BLANK_LABELS,
                  COMPLETED_TRANSFER, CLEARED_HANG, *SIZE_BOUNDARY, FILTER, *STALE_RESULT, STALE_EXPORT, LATE_SAMPLE]
CLEAN_CONTROL_CASES = 30
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
    {
        "name": "fixed-load-deadline", "path": "dist/app.js",
        "replacements": [("  if (modelReady || loadTimer === null || loadInitializing) return;", "  return;")],
        "tests": [SLOW_LOAD], "expected_failures": 1,
        "reason_fragment": "Observed state: 'error'",
        "purpose": "Restore a fixed transfer deadline that ignores loading progress, as before the stall watchdog.",
    },
    {
        "name": "initialization-extended-by-later-events", "path": "dist/app.js",
        "replacements": [("  if (modelReady || loadTimer === null || loadInitializing) return;",
                          "  if (modelReady || loadTimer === null) return;")],
        "tests": [INITIALIZATION], "expected_failures": 1,
        "reason_fragment": "Observed state: 'loading'",
        "purpose": "Let settings-file events keep extending the deadline after the model file has finished.",
    },
    {
        "name": "accepted-blank-labels", "path": "dist/app.js",
        "replacements": [("!label.trim() ||", "")],
        "tests": BLANK_LABELS, "expected_failures": 2,
        "reason_fragment": "Observed state: 'complete'",
        "purpose": "Remove the blank-label rejection while keeping every other prediction check.",
    },
    {
        "name": "consistently-scaled-scores", "path": "dist/app.js",
        "replacements": [("    return { id: index, label, score, box: bounds, color",
                          "    return { id: index, label, score: score * 0.95, box: bounds, color")],
        "tests": [GEOMETRY], "expected_failures": 3,
        "reason_fragment": "Visible score regression",
        "purpose": "Scale every score before rendering so visible text and data attributes still agree with each other.",
    },
    {
        "name": "scores-forced-to-one", "path": "dist/app.js",
        "replacements": [("    return { id: index, label, score, box: bounds, color",
                          "    return { id: index, label, score: 1, box: bounds, color")],
        "tests": [GEOMETRY + "::test_real_model_detects_reviewed_object[coffee.png-cup]"], "expected_failures": 1,
        "reason_fragment": "Visible score regression for spoon",
        "purpose": "Force every score to 1.0; the 0.99+ cup and dining-table references tolerate this, but both spoon rows (0.67 and 0.93) must fail.",
    },
    {
        "name": "completed-transfer-left-under-stall-window", "path": "dist/app.js",
        "replacements": [("  if (transferComplete || (data.status === 'done' && isModelEvent(data))) {",
                          "  if (data.status === 'done' && isModelEvent(data)) {")],
        "tests": [COMPLETED_TRANSFER], "expected_failures": 1,
        "reason_fragment": "too long to start",
        "purpose": "Keep the silent Cache Storage write under the 45-second connection-stall window.",
    },
    {
        "name": "cleared-hang-reported-as-analysis-failure", "path": "dist/app.js",
        "replacements": [("    if (!currentImage) {\n", "    if (false) {\n")],
        "tests": [CLEARED_HANG], "expected_failures": 1,
        "reason_fragment": "TimeoutException",
        "purpose": "Report the timeout of an already cleared image as an analysis failure on an empty workspace.",
    },
    {
        "name": "core-size-limit-made-exclusive", "path": "dist/app.js",
        "replacements": [("if (file.size > MAX_BYTES)", "if (file.size >= MAX_BYTES)")],
        "tests": SIZE_BOUNDARY, "expected_failures": 1,
        "reason_fragment": "This image exceeds 10 MiB",
        "failing_tests": ["test_file_size_boundary[10485760-complete]"],
        "purpose": "Core rule: a file of exactly 10 MiB is accepted. Reject it by making the size limit exclusive.",
    },
    {
        "name": "core-filter-minimum-made-exclusive", "path": "dist/app.js",
        "replacements": [("filter(({ score }) => score >= minimum)", "filter(({ score }) => score > minimum)")],
        "tests": [FILTER], "expected_failures": 3,
        "reason_fragment": ("['bottle'] == ['cup', 'bottle']", "data-label=\"cup\"", "[] == ['bottle']"),
        "failing_tests": ["test_exact_minimum_filters_underlying_scores_and_restores_without_inference",
                          "test_filter_preserves_result_identity_color_and_surviving_selection",
                          "test_hidden_predictions_can_be_restored_and_differ_from_no_model_predictions"],
        "purpose": "Core rule: the score filter keeps predictions whose score equals the minimum. Make the comparison exclusive.",
    },
    {
        "name": "core-stale-result-guard-removed", "path": "dist/app.js",
        "replacements": [("if (data.id === revision && currentImage?.id === revision) {", "if (true) {")],
        "tests": STALE_RESULT, "expected_failures": 2,
        "reason_fragment": ("'dog' not in", "Left contains one more item"),
        "failing_tests": ["test_replacing_a_processing_image_discards_the_old_result[slow-car.png]",
                          "test_clearing_a_processing_image_prevents_late_repaint"],
        "purpose": "Core rule: an old image's result cannot repaint a newer image or a cleared workspace. Accept every result.",
    },
    {
        "name": "core-stale-export-guard-removed", "path": "dist/app.js",
        "replacements": [("    // Clear, image replacement and filter changes all retire an older export.\n"
                          "    if (token !== exportRevision || snapshot.id !== revision) return;\n", "")],
        "tests": [STALE_EXPORT], "expected_failures": 3,
        "reason_fragment": ".crdownload",
        "purpose": "Core rule: an outdated export cannot download. Remove the check made after PNG encoding finishes.",
    },
    {
        "name": "core-late-sample-defences-removed", "path": "dist/app.js",
        "replacements": [("  finishSampleLoad(request);\n  request.controller.abort();\n}",
                          "  finishSampleLoad(request);\n}"),
                         ("    if (id !== revision || sampleRequest !== request) return;\n    finishSampleLoad(request);",
                          "    finishSampleLoad(request);"),
                         ("{ type: blob.type || 'image/png' }), id);", "{ type: blob.type || 'image/png' }));")],
        "tests": [LATE_SAMPLE], "expected_failures": 2,
        "reason_fragment": ("is_displayed", "'coffee.png' == 'car.png'"),
        "purpose": ("Core rule: a late sample cannot replace a newer image or undo Clear. The rule has three "
                    "independent defences (cancelling the fetch, the check after the download, and the reserved "
                    "image revision), so removing one alone is an equivalent fault; remove all three."),
    },
    {
        "name": "equivalent-late-sample-check-only-removed", "path": "dist/app.js",
        "replacements": [("    if (id !== revision || sampleRequest !== request) return;\n    finishSampleLoad(request);",
                          "    finishSampleLoad(request);")],
        "tests": [LATE_SAMPLE], "expected_failures": 0,
        "reason_fragment": "",
        "purpose": ("Equivalent fault, recorded so the result is not mistaken for a gap: removing only the check after "
                    "the sample download changes nothing observable, because cancelling the fetch and the reserved "
                    "image revision still stop the late sample. Both cases are expected to pass."),
    },
)


def matches_reason(fragments, reason):
    """A fault's failures must show its intended assertion; tests with different messages list each one."""
    fragments = (fragments,) if isinstance(fragments, str) else fragments
    return any(fragment in reason for fragment in fragments)


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
        for spelling in (str(path), path.as_posix(), str(path).replace("\\", "\\\\")):
            text = text.replace(spelling, replacement)
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
    (output / f"{name}.log").write_text(portable(completed.stdout + completed.stderr, destination),
                                        encoding="utf-8", newline="\n")
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
                                      mutation["tests"] if mutation else CLEAN_CONTROLS, output)
                if mutation:
                    result["mutation"] = {"path": mutation["path"], "purpose": mutation["purpose"],
                                          "replacements": details, "original_sha256": original_sha256,
                                          "mutated_sha256": sha256(target)}
                    failures = [case for case in result["cases"] if case["outcome"] == "failed"]
                    result["expected_outcome_verified"] = (
                        result["exit_code"] == (1 if mutation["expected_failures"] else 0)
                        and len(failures) == mutation["expected_failures"]
                        and result["counts"]["error"] == result["counts"]["skipped"] == 0
                        and all(matches_reason(mutation["reason_fragment"], case["reason"]) for case in failures)
                        and ("failing_tests" not in mutation or sorted(
                            case["id"].split("::")[-1] for case in failures) == sorted(mutation["failing_tests"]))
                    )
                else:
                    result["expected_outcome_verified"] = result["exit_code"] == 0 and result["counts"] == {
                        "passed": CLEAN_CONTROL_CASES, "failed": 0, "error": 0, "skipped": 0}
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
        (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    if not report["all_expected_outcomes_verified"]:
        raise SystemExit("Sensitivity verification incomplete; inspect summary.json")


if __name__ == "__main__":
    main()
