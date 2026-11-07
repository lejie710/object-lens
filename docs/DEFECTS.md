# Defects and corrections

This document lists every confirmed defect in Object Lens, grouped by area. Each entry gives what failed, how it was detected, its impact, the cause in the system and the test that prevents it from returning. [VERIFICATION.md](VERIFICATION.md) holds the current results and source hashes.

Several defects have a deliberate fault in [`tools/check_review_sensitivity.py`](../tools/check_review_sensitivity.py) that restores the defective behavior in a disposable copy; the named test must then fail. [v1-0-2-sensitivity.json](evidence/v1-0-2-sensitivity.json) records those outcomes (a passing clean control, 16 faults with 28 intended failures, and one equivalent fault that passes as expected), and [branch-review-sensitivity.json](evidence/history/branch-review-sensitivity.json) records 11 of those faults against an earlier commit.

## How defects were found

The application, Python server, tests and setup, package and evidence helpers were read in full, including AI-assisted review. Findings were confirmed by reproduction: controlled local HTTP timing, a loopback probe that paced the model download, ordinary temporary directories, isolated mocks and disposable copies. The application source was not corrupted to create the defects listed here; deliberate faults are used only to show that a test can fail. Model and runtime binaries, distributed notices and preserved upstream files are checked against their recorded hashes. That check is not a manual audit of third-party code or an evaluation of model accuracy.

## Model loading

### Slow connections could never load the model

- **What failed:** with only the 43 MB model response paced at 2.5 Mbps on loopback, loading failed at 121 seconds with 37.4 of 43.1 MB (86%) received. Try again restarted the transfer from zero.
- **How it was detected:** a paced loopback probe of `a338f7c` (the same audit's 93-case suite run passed and did not detect it: [audit-17f2b9a-full-suite.xml](evidence/history/audit-17f2b9a-full-suite.xml)). The corrected package, under the same 2.5 Mbps transfer, received every byte and reached ready at 140.6 seconds ([slow-transfer-2-5-mbps.json](evidence/slow-transfer-2-5-mbps.json), which also holds the probe source; the probe against `b8ff7bc` is in [loading-followup-slow-transfer.json](evidence/history/loading-followup-slow-transfer.json)). Each condition ran once on loopback; this is not an Internet speed measurement.
- **Impact:** a steady connection below about 2.9 Mbps could not load the model at all, and retrying could not help.
- **Cause in the system:** the model-load deadline counted 120 seconds from worker start and ignored progress. The correction fails a transfer only after 45 seconds without a loading event, and each event restarts that window. Try again still restarts the transfer from zero; resumable download is a non-goal because it would require changing the underlying library. Runtime initialization after the model file arrives keeps its own fixed 120-second deadline that later settings-file events cannot extend. The messages distinguish a stalled transfer from slow initialization.
- **Test that prevents it:** `tests/test_recovery.py::test_slow_steady_model_transfer_is_not_timed_out` (fails under the `fixed-load-deadline` fault), `tests/test_recovery.py::test_stalled_model_transfer_times_out_after_its_last_progress` and `tests/test_recovery.py::test_model_initialization_has_its_own_deadline` (fails under the `initialization-extended-by-later-events` fault). The stalled-transfer and initialization tests then Clear and recover.

### A completed download could be reported as a stalled connection

- **What failed:** after the model's final bytes arrive, Transformers.js writes the 43 MB file to Cache Storage before it sends `done`. That silent write was timed by the 45-second connection-stall window.
- **How it was detected:** source review of the loading states against the library's event order.
- **Impact:** a slow local cache write could produce a "stopped loading, check your connection" message although the download had finished.
- **Cause in the system:** the stall window ended only on the library's `done` event. Once every byte of a known-size transfer has arrived, the 120-second initialization deadline applies instead.
- **Test that prevents it:** `tests/test_recovery.py::test_completed_transfer_starts_initialization_before_the_done_event` (fails under the `completed-transfer-left-under-stall-window` fault).

### Progress showed 100% for the whole download without Content-Length

- **What failed:** when a host omits Content-Length, Transformers.js 2.17.2 reports a total equal to the bytes received so far, so the page showed "100%" throughout the transfer. The existing test injected an event shape the library never sends.
- **How it was detected:** source review of the library's progress events and of the test fixture.
- **Impact:** the user saw a finished download while most of the model was still arriving.
- **Cause in the system:** the page trusted any reported total. A size is trusted only after an event shows fewer bytes than the total; otherwise the page shows megabytes received with an indeterminate bar.
- **Test that prevents it:** `tests/test_loading.py::test_missing_content_length_shape_stays_indeterminate`, which replays the real event shape.

## Stale results and Clear

### Timeout and Clear messages described the wrong stage

- **What failed:** the timeout callback always described image detection, including while the model was still loading. Clear then reported any stopped worker as a startup failure.
- **How it was detected:** source review, confirmed by a before/after comparison of three wording tests. Against a disposable copy of `8a35f38` the three tests fail (26.732 seconds); against the corrected source they pass (27.644 seconds) ([followup-recovery-comparison.json](evidence/history/followup-recovery-comparison.json); the same comparison against the current source is in [branch-review-recovery-comparison.json](evidence/history/branch-review-recovery-comparison.json)). The earlier source fails at the message checks before Clear, so its Clear behavior is a source finding that the failed run did not reach.
- **Impact:** the user was told the wrong thing failed, and after Clear a slow analysis read as a broken detector.
- **Cause in the system:** one message for every timeout, and Clear mapped any stopped worker to a startup failure. The timeout callback selects a message for the active loading or inference stage. Clear shows a generic unavailable and restart message without reclassifying the earlier cause; Retry or a valid new image recovers.
- **Test that prevents it:** `tests/test_recovery.py::test_model_load_timeout_clear_and_retry_describe_detector_availability`, `tests/test_recovery.py::test_inference_timeout_clear_and_retry_describe_detector_availability` and `tests/test_recovery.py::test_worker_crash_during_inference_is_not_described_as_startup_failure`. Each continues through Clear, Retry and a successful analysis. Worker crashes are simulated; no crash of the real model was observed.

### Clear during a hung analysis showed an error on an empty workspace

- **What failed:** after Clear, an analysis of the removed image that never answered still produced "Image analysis took too long" on an empty workspace.
- **How it was detected:** review of the application state handling.
- **Impact:** an error about an image the user had already removed.
- **Cause in the system:** the inference timeout handler did not check whether an image was still shown. When the image has been cleared, the detector restarts quietly. Replacing a hung image with a new one keeps the error-and-retry behavior.
- **Test that prevents it:** `tests/test_recovery.py::test_clear_during_a_hung_analysis_restarts_quietly` (fails under the `cleared-hang-reported-as-analysis-failure` fault).

## Malformed output and labels

### Blank labels were accepted without a test

- **What failed:** deleting the `!label.trim()` check from `renderResults` left all 44 recovery and UI tests passing ([audit-17f2b9a-blank-label-fault.xml](evidence/history/audit-17f2b9a-blank-label-fault.xml)).
- **How it was detected:** a deliberate fault in a disposable copy of `a338f7c`.
- **Impact:** a prediction with an empty or whitespace label could be shown as a result row with no name, and no test would notice.
- **Cause in the system:** the malformed-response cases had no empty or whitespace label. Both are included among them.
- **Test that prevents it:** `tests/test_recovery.py::test_malformed_result_is_rejected_without_partial_detections_and_recovers` with `[empty-label]` and `[blank-label]` (both fail under the `accepted-blank-labels` fault).

The same test rejects missing or non-finite coordinates, invalid scores, impossible boxes and a mixed batch, then recovers with a valid image. These are simulated failures of the model component, not defects observed inside the actual model. Finite out-of-range coordinates that still leave a usable rectangle are clamped by design (`tests/test_recovery.py::test_partially_outside_box_is_clamped_to_the_rendered_image`). The real model produces two spoon predictions for one photo, so `tests/test_filter.py::test_duplicate_labels_keep_distinct_identity_and_selection_through_filtering` checks selection, coordinates, colors and filtering by prediction identity rather than by label; no duplicate-selection defect was found.

## Startup and configuration

The first three defects below were present in `6306ba6`. The five startup regressions written for them fail against that source in 73.298 seconds of JUnit time ([review-startup-before.xml](evidence/history/review-startup-before.xml)) and pass after correction in 63.996 seconds ([review-startup-after.xml](evidence/history/review-startup-after.xml)). The fourth is a gap in those startup tests themselves.

### Configuration loading had no deadline

- **What failed:** a configuration response held before its headers or during its JSON body left the app loading beyond a 20-second wait.
- **How it was detected:** controlled local HTTP timing that holds the configuration response.
- **Impact:** the app could stay in Loading indefinitely, because the model watchdog had not started yet.
- **Cause in the system:** the configuration request had no application deadline. A 15-second deadline aborts it, and Retry fetches configuration again while keeping the chosen image.
- **Test that prevents it:** `tests/test_startup.py::test_stalled_configuration_times_out_and_retry_fetches_it_again` (`[headers]` and `[body]`).

### Background startup could erase an input error

- **What failed:** an invalid file's explanation disappeared when delayed configuration completed and started the worker.
- **How it was detected:** controlled local HTTP timing with an invalid file chosen while configuration was held.
- **Impact:** the user lost the reason their file was rejected.
- **Cause in the system:** worker creation cleared user-facing errors as a side effect. The error stays until a deliberate recovery action.
- **Test that prevents it:** `tests/test_startup.py::test_configuration_completion_preserves_an_existing_input_error` and `tests/test_loading.py::test_startup_progress_and_ready_do_not_replace_an_input_error`.

### Worker readiness could misreport an unfinished file read

- **What failed:** the app said "Ready to choose an image" while a held file read was still pending.
- **How it was detected:** controlled timing that holds the file read while the worker becomes ready.
- **Impact:** the status contradicted what the app was doing with the user's image.
- **Cause in the system:** readiness did not know about image preparation in progress. The current preparation revision is tracked separately, so Ready and Retry keep "Reading image" or "Loading sample" until preparation finishes.
- **Test that prevents it:** `tests/test_startup.py::test_worker_ready_preserves_in_progress_file_preparation` and `tests/test_startup.py::test_worker_retry_restores_status_while_file_preparation_is_pending`.

### Startup tests could not see a premature real worker

- **What failed:** startup tests counted only controlled-worker requests. Before configuration is valid, test mode is off, so a worker started too early would request the real worker and go unnoticed.
- **How it was detected:** review of test strength.
- **Impact:** a start-before-configuration defect could pass the suite.
- **Cause in the system:** the test server did not count `/worker.js`. It counts both workers, and the startup tests require no request for either before valid configuration.
- **Test that prevents it:** every test in `tests/test_startup.py` opens the page through a shared check that requires zero requests for either worker while configuration is held, for example `tests/test_startup.py::test_stalled_configuration_times_out_and_retry_fetches_it_again`; `tests/test_startup.py::test_invalid_configuration_can_be_refetched_without_losing_the_image` also requires none after invalid configuration.

## Test strength

### Real-model checks compared the page with itself

- **What failed:** the real-model tests compared visible text with the page's own `data-*` attributes.
- **How it was detected:** review of test strength.
- **Impact:** a fault that changed visible text and attributes together could pass.
- **Cause in the system:** the oracle came from the page under test. The selected row's visible label and score are compared with an earlier recorded output of the same pinned model ([model-observations.json](evidence/model-observations.json)), with a 0.01 score tolerance. That reference is a regression baseline, not ground truth.
- **Test that prevents it:** `tests/test_inference.py::test_real_model_detects_reviewed_object` (all three photo cases fail under the `consistently-scaled-scores` fault).

### Every score forced to 1.0 still passed

- **What failed:** the selected reference scores were all 0.998 to 0.999, so a fault forcing every score to 1.0 stayed within tolerance.
- **How it was detected:** review of test strength.
- **Impact:** a score defect that inflates confidence would not be caught by the real-model checks.
- **Cause in the system:** only the selected row was compared. Every visible row is compared with the recorded output, including the 0.67 and 0.93 coffee spoons.
- **Test that prevents it:** `tests/test_inference.py::test_real_model_detects_reviewed_object` (the `coffee.png-cup` case fails under the `scores-forced-to-one` fault).

### Blank visible text, displaced boxes and removed announcements could pass

- **What failed:** blank visible names or scores, real-model boxes drawn in the wrong place and removed live-region settings could pass the 72-case suite.
- **How it was detected:** external AI-assisted review of the 72-case suite, then deliberate faults in disposable copies ([followup-sensitivity.json](evidence/history/followup-sensitivity.json)). No broad mutation score is claimed.
- **Impact:** text the user reads, box placement and status announcements were not protected.
- **Cause in the system:** assertions read data attributes instead of visible text and did not measure rendered boxes. The tests check visible names and two-decimal scores, compare the selected box coordinates with the pinned-model reference, and measure the rendered box against the image rectangle. The announcement check establishes configuration, not screen-reader behavior.
- **Test that prevents it:** `tests/test_ui.py::test_predictions_and_boxes_match_the_current_image` (`blank-visible-labels`), `tests/test_ui.py::test_visible_scores_round_without_changing_the_underlying_values` (`blank-visible-scores`), `tests/test_inference.py::test_real_model_detects_reviewed_object` (`displaced-rendered-boxes`) and `tests/test_ui.py::test_status_and_error_announcement_configuration_follows_visible_states` (`removed-announcement-configuration`).

### The late-response check could pass before the late reply arrived

- **What failed:** the shared check for stale results held its invariant for a fixed 1.4 seconds, chosen to outlast the controlled worker's 900-millisecond reply delay. Nothing confirmed that the delayed reply had actually reached the page within that window.
- **How it was detected:** review of test strength.
- **Impact:** on a slow runner the late reply could arrive after the window closed, so a stale-result regression could pass without the stale reply ever being exercised.
- **Cause in the system:** a fixed wall-clock window. The browser fixture installs a small worker trace, and `tests/helpers.py::assert_for_late_response_window` asserts the invariant on every poll until the trace shows no outstanding inference request, which proves the late reply was delivered, then holds it a little longer while the page handles that reply. Checks whose late event is a held encoder callback or a held sample response, not a worker reply, keep a 1.4-second hold.
- **Test that prevents it:** the stale-result tests whose late event is a worker reply: `tests/test_ui.py::test_replacing_a_processing_image_discards_the_old_result`, `tests/test_ui.py::test_clearing_a_processing_image_prevents_late_repaint` and `tests/test_filter.py::test_new_image_and_clear_reset_filter_and_retire_old_cached_predictions`. The helper fails the test if the trace is missing or a reply is still outstanding after 10 seconds.

## Evidence claims

### Fault counts were overstated

- **What failed:** the documents at `b8ff7bc` described the sensitivity record as nine faults and 15 intended failures. The file holds eight faults and 14 failures ([loading-followup-sensitivity.json](evidence/history/loading-followup-sensitivity.json)).
- **How it was detected:** recounting from the evidence file.
- **Impact:** a published claim larger than its evidence.
- **Cause in the system:** the clean control was counted as a fault. Counts are quoted from the evidence files.
- **Test that prevents it:** no automated test; document counts are checked against the evidence by hand.

### Claims without retained evidence, and overstatements

- **What failed:** a 93-case reproduction and the "44 tests still passed" blank-label observation had no retained record, and four startup and package timings differed from the retained JUnit. Wording claimed more than the evidence: an "independent oracle" that is the same model's earlier output, "only the reference catches" scaled scores, and "2 to 3 source pixels" where one sample is 1.5.
- **How it was detected:** review of each claim against its evidence.
- **Impact:** a reader could not check the claims, or would trust them more than they deserve.
- **Cause in the system:** results quoted from memory or from raw artifacts that were not retained. Both runs are retained ([audit-17f2b9a-full-suite.xml](evidence/history/audit-17f2b9a-full-suite.xml), [audit-17f2b9a-blank-label-fault.xml](evidence/history/audit-17f2b9a-blank-label-fault.xml)), timings quote the JUnit records, and the wording states what the evidence shows.
- **Test that prevents it:** no automated test; wording is a review matter.

### Retained evidence exposed a local user path

- **What failed:** three retained JUnit files contained the Windows user path. The verification recorder wrote a fixed run label, and the sensitivity tool missed backslash-escaped paths.
- **How it was detected:** privacy review of the retained evidence and of the tools that write it.
- **Impact:** a personal path in files intended for publication, and a record whose label did not match its run.
- **Cause in the system:** the writers redacted only plain path spellings and used a hard-coded label. Selected copies use placeholders recorded in each redaction note, while raw-record hashes still refer to the originals. The recorder's label is neutral; the sensitivity tool writes LF and redacts plain, forward-slash and escaped spellings.
- **Test that prevents it:** no automated test; the redaction is in the evidence-writing tools.

## Packaging and provenance

### Package provenance failed outside a Git checkout

- **What failed:** the packaging privacy test failed when the project sat outside a Git checkout, because a deliberately incomplete `.git` marker made Git exit with code 128.
- **How it was detected:** running the browser-free package tests from an ordinary temporary directory. The original case fails in 1.688 seconds ([review-package-before.xml](evidence/history/review-package-before.xml)); after correction eight browser-free cases pass in 4.176 seconds ([review-package-after.xml](evidence/history/review-package-after.xml)).
- **Impact:** a package could not be built from a source copy, and a copy could inherit its parent folder's repository metadata.
- **Cause in the system:** Git metadata was treated as required. Missing or unusable metadata produces absent provenance; byte-integrity and public-file checks are unchanged.
- **Test that prevents it:** `tests/test_public_package.py::test_git_provenance_is_absent_for_a_non_repository_marker` (`[not-repository]` and `[missing-git]`) and `tests/test_public_package.py::test_git_provenance_never_uses_a_parent_repository`.

At that checkpoint, with the configuration, input-error, file-read, outside-checkout provenance and browser-cleanup corrections, the 72-case suite (68 controlled, 4 real-model) passed with zero failures, errors or skips in 531.363 seconds of JUnit time, run from a temporary directory outside any Git repository ([review-full-suite.xml](evidence/history/review-full-suite.xml), [source-review-verification.json](evidence/history/source-review-verification.json)). The current result is in [VERIFICATION.md](VERIFICATION.md).

### Package provenance failed for a repository with no commits

- **What failed:** a repository with no commits still made provenance fail.
- **How it was detected:** review of the Git fallbacks.
- **Impact:** a fresh repository could not build a package.
- **Cause in the system:** not every Git call fell back. All of them fall back to absent provenance.
- **Test that prevents it:** `tests/test_public_package.py::test_git_provenance_is_absent_for_a_repository_without_commits`.

### The package failed under a URL subpath

- **What failed:** the worker requested the model from `/assets/models/` and the runtime from `/assets/runtime/`, absolute paths from the host root. A package served under a subpath such as `/object-lens/` sent those requests outside its own directory.
- **How it was detected:** review of how the package resolves its URLs.
- **Impact:** a GitHub Pages project site, which serves the package under the repository name, could not load the model.
- **Cause in the system:** absolute URLs. The worker resolves both locations relative to its own URL (`new URL('./assets/...', import.meta.url)`), so the package works at a site root or under a subpath.
- **Test that prevents it:** `tests/test_public_package.py::test_packaged_site_runs_real_sample_filter_and_export_on_an_ordinary_static_server` serves the built package under `/object-lens/` from an ordinary static server, requires a 404 for application files at the host root, and runs the real sample, filter and export there.

### Embedded libraries lacked their licence texts

- **What failed:** the ONNX Runtime Web 1.14.0 code inside the bundled runtime contains five libraries whose licence texts were not in the package: long 4.0.0 (Apache-2.0), flatbuffers 1.12.0 (Apache-2.0), onnx-proto 4.0.4 (MIT), protobufjs 6.11.3 (BSD-3-Clause) and guid-typescript 1.0.9 (ISC).
- **How it was detected:** searching the bundle for each library's code.
- **Impact:** the package redistributed code without the licence notices those licences require.
- **Cause in the system:** the credits covered the top-level libraries but not libraries compiled into the runtime bundle. The five licences are in `dist/licenses`, recorded with hashes and their version source in [`credits-lock.json`](../credits-lock.json), linked from `dist/credits.html` and listed in [NOTICE.md](../NOTICE.md). guid-typescript ships no licence file, so its notice records the ISC declaration in its `package.json` with the standard ISC text.
- **Test that prevents it:** no automated test detects an undeclared embedded library; the bundle search is recorded in `credits-lock.json`, and the recorded licence files are checked against their hashes.

## Local server

### Served content types depended on the Windows registry

- **What failed:** `serve.py` took content types from Python's `mimetypes` table, which on Windows reads the registry of the machine serving the app.
- **How it was detected:** review of the local server.
- **Impact:** a machine whose registry maps `.js` or `.wasm` to another type would serve the module worker or runtime with a type the browser refuses, and the app could not start there.
- **Cause in the system:** the server relied on machine configuration. It uses a fixed map (`.js` as `text/javascript`, `.wasm` as `application/wasm` and the other served types).
- **Test that prevents it:** `tests/test_server.py::test_controlled_worker_requires_explicit_test_mode` requires `/worker.js` and `/app.js` to be served as `text/javascript`.

## Test harness

### Failure-evidence writing could skip browser cleanup

- **What failed:** when the evidence directory could not be created, `driver.quit()` was never called; the mocked call count was zero.
- **How it was detected:** injected directory denial in an isolated mock.
- **Impact:** a failing test could leave Chrome running.
- **Cause in the system:** cleanup sat after the evidence write. An outer `finally` always attempts cleanup once the browser exists; evidence-write failures stay secondary.
- **Test that prevents it:** `tests/test_harness_cleanup.py::test_browser_closes_when_failure_evidence_directory_cannot_be_created`, `tests/test_harness_cleanup.py::test_browser_closes_when_screenshot_and_fallback_evidence_both_fail` and `tests/test_harness_cleanup.py::test_browser_closes_when_timeout_setup_fails` ([review-harness-cleanup.xml](evidence/history/review-harness-cleanup.xml)). No real Chrome is launched for these cases.

### A runner network error stopped one test page from loading

- **What failed:** on the first hosted CI run, the setup of `tests/test_filter.py::test_new_image_and_clear_reset_filter_and_retire_old_cached_predictions` timed out after 10 s: the page loaded `app.js` but never requested its other files, so it stayed in the loading state. The other 97 controlled tests passed.
- **How it was detected:** the failure evidence that CI uploads (`artifacts/test-failures`) held one browser error: `png-export.js - Failed to load resource: net::ERR_NO_BUFFER_SPACE`, a Windows error meaning the runner briefly had no socket buffer space for a new connection.
- **Impact:** CI went red for a fault in the test machine, not in Object Lens, and the timeout message was empty, so the cause was only visible in the uploaded evidence.
- **Cause in the system:** the shared `app` fixture loaded the page once and waited with no diagnosis. A failed module request stops the page before any application code runs.
- **Test that prevents it:** `tests/conftest.py` `app` fixture. It reloads the page once only when the browser log shows `net::ERR_NO_BUFFER_SPACE`, records a warning naming the loaded files and the error, and otherwise fails at once with the page state, the loaded files and the browser errors. No automated test exercises this rule; it was checked with a fake browser driver covering a ready page, the runner error, another error and a page that stays broken after the reload.

### Shared helpers raised assertion errors with no message

- **What failed:** in the deliberate-fault run, the `core-late-sample-defences-removed` fault made both of its intended tests fail, but the runner reported that the outcome did not match, because one failure's message was a bare `AssertionError`.
- **How it was detected:** the sensitivity run for the link preview change ([link-preview-sensitivity-before-fix.json](evidence/history/link-preview-sensitivity-before-fix.json)). The `[clear]` case failed with a bare `AssertionError` and no other detail. The only assertions on that path without pytest's explanation are the three in `tests/helpers.py::assert_no_visible_image`, so one of its Clear checks failed (an image, a box or a result was still visible after Clear), the symptom the fault is meant to cause. Earlier runs had failed that case at the file name check instead (`'coffee.png' == 'No image selected'`), so the problem stayed hidden.
- **Impact:** none on users. The planted fault was caught; the runner could not recognise one of its two intended symptoms, so whether the run passed depended on which symptom appeared first. Every assertion failing inside a shared helper also gave no detail in ordinary runs.
- **Cause in the system:** pytest explains failed assertions only in test modules, `conftest.py` and modules registered for rewriting. When the assertions moved into `tests/helpers.py` (`0c7e890`), they lost their explanation, and the runner's expected reason `is_displayed` could no longer appear in the message. `tests/conftest.py` now registers `helpers` for rewriting before its first import.
- **Test that prevents it:** `tests/test_helpers.py::test_helper_assertion_failure_names_the_failed_check`. Run against the `tests/conftest.py` of `e24155b`, before the change, it failed with an empty message ([helpers-test-before-fix.xml](evidence/history/helpers-test-before-fix.xml)). The sensitivity run for the corrected source passed ([v1-0-2-sensitivity.json](evidence/v1-0-2-sensitivity.json)); in that run the `[clear]` case failed at the file name check, so the unit test, not that run, shows the helper's message is now recognised.

### Real-model references hold only on the recording machine

- **What failed:** a manual CI run of the real-model tests on a GitHub-hosted Windows runner failed `tests/test_inference.py::test_real_model_detects_reviewed_object[coffee.png-cup]` and `[chelsea.png-cat]`. The astronaut case and the static-package workflow passed.
- **How it was detected:** the failure evidence that CI uploads held each page as it was. Every label matched, but the coffee spoon scored 0.710 instead of the recorded 0.667, the other spoon 0.945 instead of 0.927, and the cat box's right edge was at 0.9325 instead of 0.9412. The browser console had no errors.
- **Impact:** none on users; the app showed the model's output correctly. The checks would fail on any machine whose model output differs this much, so they cannot run in CI.
- **Cause in the system:** the references in `docs/evidence/model-observations.json` are earlier outputs of the same pinned model on the owner's laptop, compared within 0.01 for scores and 0.005 for box edges. A different machine produces slightly different numbers from the same model and image. Widening the tolerances would let the deliberate fault that scales every score by 0.95 pass for the cup (0.998 becomes 0.948), so the tolerances stay.
- **Test that prevents it:** none. CI runs the 100 controlled tests only, and the real-model tests stay a local check on the recording machine. The real-model regression references are recorded outputs of the same pinned model on the owner's Windows laptop.

### Repository presentation errors

- **What failed:** the README sent readers first to an owner handoff note, and a second, byte-identical set of 12 screenshots was kept.
- **How it was detected:** review of how the repository reads to a newcomer.
- **Impact:** a confusing first read and two copies of the same captures.
- **Cause in the system:** link order and duplicated captures. The README leads with the project question and its evidence, and one current screenshot set is kept in [docs/screenshots/app](screenshots/app).
- **Test that prevents it:** no automated test; presentation is a review matter.

Defects in the tooling of the separate study companion, which is not published with this repository, are recorded with that companion.

## Layout

### Content overflowed a 320-pixel viewport

- **What failed:** at a 320-pixel viewport the vertical scrollbar left 305 pixels of usable width, but the body's minimum width was 320 pixels.
- **How it was detected:** rendered review at a 320-pixel viewport; [viewport-before-fix.xml](evidence/history/viewport-before-fix.xml) retains the failing assertion of the clientWidth check against the uncorrected layout.
- **Impact:** horizontal scrolling on the narrowest supported width.
- **Cause in the system:** a fixed 320-pixel body minimum, and a test that compared against `window.innerWidth`, which includes the scrollbar and hid the overflow. The check uses `documentElement.clientWidth`, and content fits the 305-pixel space.
- **Test that prevents it:** `tests/test_ui.py::test_narrow_layout_preserves_results_and_does_not_overflow` (`[320]` and `[390]`).

## Findings that did not hold

- A suggested contradiction about the Clear button behavior is not a contradiction.
- The CRLF output of the sensitivity tool has no visible consequence; the tool writes LF regardless.

No defect was found in the slow-connection correction itself.

## Limits

No blocking defect is known in the local workflow. That does not prove every input, browser, operating system or third-party dependency correct. Chrome on the recorded Windows environment is the verified target; other browsers and devices, general recognition accuracy and hosted behavior are not verified.

The optional transfer-rate checker has its own 120-second readiness wait, so very low requested rates fail in the helper independently of the app's stall window. The 10 Mbps model-only simulation is limited to that scenario.

Hosted behavior, including any GitHub Pages showcase, is outside the recorded verification; CI runs the controlled suite on GitHub Actions, and hosted results are not recorded in this repository.
