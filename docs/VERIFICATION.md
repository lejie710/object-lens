# Verification and release assessment

**Question.** When someone tries a browser object detector on their own photos, switching images quickly, on a slow connection, or when the model returns something broken, can the page show results that belong to a different photo, misplace boxes, or get stuck with no way to recover? ([DESIGN.md](DESIGN.md#the-question))

**Measure.** A controlled test for each of those failures; every core rule the question depends on caught when it is broken on purpose; and a before/after measurement of model loading at 2.5 Mbps.

**Result.**

| Measure | Result | Evidence |
| --- | --- | --- |
| Recorded full suite | **102 passed, 0 failures/errors/skips** (98 controlled, 4 real-model), 784.165 s of JUnit suite time on Windows 11, Chrome 156.0.8078.80, Python 3.12.10, pytest 9.0.3 and Selenium 4.40.0 | [v1-0-1-verification.json](evidence/v1-0-1-verification.json), [v1-0-1-full-suite.xml](evidence/v1-0-1-full-suite.xml) |
| Core rules broken on purpose | A 30-case clean control passes; each of 16 deliberate faults fails its intended tests (28 intended failures); 1 equivalent fault passes as expected. Every core rule has at least one test that fails when the rule is broken | [v1-0-1-sensitivity.json](evidence/v1-0-1-sensitivity.json), [Core rules broken on purpose](#core-rules-broken-on-purpose) |
| Model loading at 2.5 Mbps | A fixed 120-second deadline (`a338f7c`) failed at 121 s with 37.4 of 43.1 MB (86%) received; stall-based loading received every byte and reached ready at 140.6 s | [slow-transfer-2-5-mbps.json](evidence/slow-transfer-2-5-mbps.json) |
| Fresh clone following the README | Passed on the public repository at commit `673f8b3`, cloned from GitHub: every README setup step exited 0, the usage example showed 4 predictions at 0.50 and 3 at 0.80 and saved a 600 x 400 PNG, and the full suite reported 102 passed in 781.58 s (Windows 11, Python 3.12.10, Chrome 156.0.8078.80) | [fresh-clone-github.json](evidence/fresh-clone-github.json) |
| Live showcase | Opened in a fresh headless Chrome profile: ready in 11.2 s including the 43 MB model, Try sample in 10 s with the same 4 predictions, the 0.80 filter hid the 0.67 spoon, Save result gave a 600 x 400 PNG; test mode off, test worker and documents not published (404) | [showcase-check.json](evidence/showcase-check.json) |
| Dependency audit | pip-audit on `requirements-lock.txt`: 30 packages checked, 0 known vulnerabilities (local run). The result is for the day of the run; the database of known vulnerabilities changes. The browser runtime and model are pinned by hash in `asset-lock.json` and are not covered by this audit | [security/pip-audit.json](evidence/security/pip-audit.json) |
| Hosted CI | `.github/workflows/ci.yml` runs the 98 controlled tests and the dependency audit on GitHub Actions (`windows-latest`) for pushes to main, pull requests and manual runs. The 4 real-model tests run locally only, because a hosted runner gives slightly different model outputs than the recorded references ([DEFECTS.md](DEFECTS.md#real-model-references-hold-only-on-the-recording-machine)). Hosted results are shown on GitHub and are not recorded in this repository | [ci.yml](../.github/workflows/ci.yml) |

The current record identifies the tested files by their source hashes. The slow-transfer probe ran against a package (`8c154b7`) whose `app.js` loading deadlines, inference, filter, sample and export code are identical to the current source. The current source differs in `dist/credits.html`, the added licence files, and `dist/worker.js`, which now resolves the model and runtime URLs relative to the worker; that changes where the assets are requested from, not how long loading may take. Acceptance examples mapped to named tests are in [DESIGN.md](DESIGN.md#acceptance-examples); the ranked risks and the test mix are in [DESIGN.md](DESIGN.md#risks-and-test-mix). Every confirmed defect, with the test that prevents it, is in [Defects and corrections](DEFECTS.md). Each evidence file is described in the [evidence index](evidence/README.md).

## Model loading on slow or stalled connections

Production deadlines are 15 seconds for configuration, a 45-second model-transfer stall window that each loading event restarts, 120 seconds for runtime initialization once every model byte has arrived, and 90 seconds for inference. Normal controlled loading keeps the production deadlines. Dedicated loading tests accelerate only the 45000 ms stall timer to 1500 ms and the 120000 ms initialization timer to 2500 ms; controlled inference uses four seconds. Those durations exercise failure paths and are not measured model performance.

| Behaviour | What is checked | What the evidence does not establish |
| --- | --- | --- |
| Slow but steady transfer | A transfer that keeps reporting progress for longer than several stall windows is not timed out (`tests/test_recovery.py::test_slow_steady_model_transfer_is_not_timed_out`) | Real Internet performance |
| Stalled transfer | A transfer that stops reporting progress fails 45 seconds after its last event, with a message asking the user to check the connection (`tests/test_recovery.py::test_stalled_model_transfer_times_out_after_its_last_progress`) | Behaviour of every network failure mode |
| Transfer completion starts initialization | When every model byte has arrived, the 120-second initialization deadline replaces the stall window, so the library's silent Cache Storage write is not reported as a stalled connection; later settings events cannot extend it (`tests/test_recovery.py::test_completed_transfer_starts_initialization_before_the_done_event`, `tests/test_recovery.py::test_model_initialization_has_its_own_deadline`) | Cache Storage timing on every device |
| Honest progress without a known size | Transformers.js 2.17.2 reports total = bytes received when a host omits Content-Length; the page shows received megabytes and an indeterminate bar instead of a false 100%, replaying that real event shape (`tests/test_loading.py::test_missing_content_length_shape_stays_indeterminate`) | Every hosting provider's headers |
| Startup never overwrites the user's work | Startup progress, readiness and worker retry preserve an input error or an image still being prepared, and a retired worker cannot change the loading notice; startup tests count real-worker as well as controlled-worker requests (`tests/test_startup.py::test_configuration_completion_preserves_an_existing_input_error`, `tests/test_startup.py::test_worker_ready_preserves_in_progress_file_preparation`, `tests/test_startup.py::test_worker_retry_restores_status_while_file_preparation_is_pending`, `tests/test_loading.py::test_startup_progress_and_ready_do_not_replace_an_input_error`, `tests/test_loading.py::test_loading_failure_hides_notice_and_retry_ignores_the_old_worker`) | |
| Configuration deadline and Retry | A configuration response held at the headers or the body times out after 15 seconds, and Retry fetches it again without losing the selected image (`tests/test_startup.py::test_stalled_configuration_times_out_and_retry_fetches_it_again`, `tests/test_startup.py::test_invalid_configuration_can_be_refetched_without_losing_the_image`) | Every possible server response |

On the 2.5 Mbps loopback probe, only the ONNX model response was paced. The fixed-deadline source failed at 121.0 s with 37,486,592 of 43,102,531 bytes received, and Try again restarted the transfer from zero (2.4 MB received eight seconds later). The stall-based package received all 43,102,531 bytes and reached ready at 140.6 s ([slow-transfer-2-5-mbps.json](evidence/slow-transfer-2-5-mbps.json), which includes the probe source). Each condition ran once. A separate package (`e4781ab`) paced only the model response at 10 Mbps on loopback: 43,102,531 bytes arrived in 34.493 seconds and readiness occurred at 36.776 seconds ([public-prep-verification.json](evidence/history/public-prep-verification.json)). Neither observation is Internet performance.

## Stale results, exports and samples

| Behaviour | What is checked | What the evidence does not establish |
| --- | --- | --- |
| Results match the current image | The list shows exactly the returned labels with their two-decimal scores, each box carries its returned label, and the laptop box is placed at the returned coordinates within 2 CSS pixels; replacing an image replaces every result; selecting a row highlights only its box (`tests/test_ui.py::test_predictions_and_boxes_match_the_current_image`, `tests/test_ui.py::test_replacing_image_replaces_all_results`, `tests/test_ui.py::test_selecting_a_result_highlights_its_box`) | Recognition accuracy |
| An old result cannot repaint | Replacing an image that is still being analysed, with a fast or slow replacement, never shows the old result; Clear during analysis keeps the workspace empty (`tests/test_ui.py::test_replacing_a_processing_image_discards_the_old_result`, `tests/test_ui.py::test_clearing_a_processing_image_prevents_late_repaint`) | Timing on other browsers |
| Cached predictions are retired | A new image or Clear resets the filter and retires cached predictions; an invalid replacement discards the filter cache (`tests/test_filter.py::test_new_image_and_clear_reset_filter_and_retire_old_cached_predictions`, `tests/test_filter.py::test_invalid_replacement_discards_filter_cache_and_valid_image_recovers`) | |
| An outdated export cannot download | Clear, a replacement or a filter change while the PNG is still being encoded cancels the download (`tests/test_export.py::test_changed_result_cancels_a_png_still_being_encoded`, 3 cases) | |
| A late sample cannot override the user | A held sample response released after Clear or an upload leaves the workspace empty or showing the upload, with no second sample request (`tests/test_sample.py::test_late_sample_response_cannot_override_a_later_user_action`, 2 cases) | |
| Clear during a hung analysis | If Clear removed the image before its analysis timed out, the detector restarts quietly instead of showing an analysis failure on an empty workspace (`tests/test_recovery.py::test_clear_during_a_hung_analysis_restarts_quietly`) | That a real model hang occurred |

A stale-result test is only meaningful if the late reply actually arrives while the invariant is being checked. The browser fixture wraps the page's `Worker` so each outgoing analysis request is recorded until its result or error message arrives (a terminated worker can never reply, so its requests are dropped). `tests/helpers.py::assert_for_late_response_window` asserts the invariant on every poll until no analysis reply is outstanding, fails if any reply is still outstanding after 10 seconds or if the trace is missing, and then holds the invariant a little longer so the page has handled the last reply. Tests whose late event is not a worker reply (a held PNG encoder callback or a held sample response) hold the invariant for 1.4 seconds. Tests that exercise a real 15-second deadline wait up to 30 seconds.

## Malformed model output and recovery

| Behaviour | What is checked | What the evidence does not establish |
| --- | --- | --- |
| Malformed responses rejected as a whole | 16 kinds of invalid output (not an array, null item, empty or blank label, missing box or coordinate, string or non-finite coordinate, missing, string, non-finite, negative or excess score, reversed, zero-area or fully outside box) show an invalid-result message with Try again, no partial predictions, and the next valid image recovers (`tests/test_recovery.py::test_malformed_result_is_rejected_without_partial_detections_and_recovers`) | Exhaustive validation of every possible object shape or dependency fault |
| Clamping | A box partly outside the image is clamped to the rendered image edge (`tests/test_recovery.py::test_partially_outside_box_is_clamped_to_the_rendered_image`) | |
| Retry after an invalid result | Try again re-analyses the same image (`tests/test_recovery.py::test_retry_after_a_transient_invalid_result_reanalyzes_the_same_image`) | |
| Truthful timeout and Clear feedback | Model-loading and inference deadlines have distinct explanations; Clear leaves a stopped detector unavailable; Retry restores operation; a worker crash during inference is not described as a startup failure (`tests/test_recovery.py::test_model_load_timeout_clear_and_retry_describe_detector_availability`, `tests/test_recovery.py::test_inference_timeout_clear_and_retry_describe_detector_availability`, `tests/test_recovery.py::test_worker_crash_during_inference_is_not_described_as_startup_failure`) | That a real model outage occurred |
| Silent worker | A worker that never answers times out and Try again analyses the latest image (`tests/test_ui.py::test_nonresponding_worker_times_out_and_retries_the_latest_image`) | No real-model hang was observed |
| Empty and failed results | No predictions is shown as an empty result, not an error; a processing or worker-start failure is visible and recoverable (`tests/test_ui.py::test_empty_predictions_are_not_an_error`, `tests/test_ui.py::test_processing_failure_is_visible_and_next_image_recovers`, `tests/test_ui.py::test_worker_start_failure_can_be_retried`) | |

[branch-review-recovery-comparison.json](evidence/history/branch-review-recovery-comparison.json) runs three controlled wording checks against `app.js` from `8a35f38` and from `8c154b7`, whose `app.js` is identical to the current source. All three fail against `8a35f38` (26.952 s) and pass against `8c154b7` (26.040 s). The old checks fail before Clear, so they do not independently reproduce the old Clear message. The passing checks continue through Clear, truthful detector unavailability, Retry and a successful new image. The substituted runtime crash is a component simulation; no production trigger is claimed.

The malformed responses are deliberate test-worker outputs, not faults observed from the real pretrained model. Two records show the gap the blank-label check closes: [audit-17f2b9a-full-suite.xml](evidence/history/audit-17f2b9a-full-suite.xml), a 93-case run of `a338f7c` in a disposable copy, and [audit-17f2b9a-blank-label-fault.xml](evidence/history/audit-17f2b9a-blank-label-fault.xml), where 44 recovery and UI tests still passed with the blank-label check deleted.

## Input limits

| Behaviour | What is checked | What the evidence does not establish |
| --- | --- | --- |
| File size | Exactly 10 MiB (10,485,760 bytes) is analysed; one byte more is rejected with a message naming the limit (`tests/test_ui.py::test_file_size_boundary`) | |
| Decoded size | 4000 × 4000 pixels is analysed; 4001 × 4000 is rejected with a message about 16 megapixels (`tests/test_ui.py::test_decoded_pixel_boundary`) | Behaviour on large real phone photos |
| Invalid content | Unsupported or unreadable files and a truncated PNG body are rejected, and the next valid image recovers (`tests/test_ui.py::test_invalid_input_is_rejected_and_valid_input_recovers`, `tests/test_ui.py::test_truncated_png_body_is_rejected_and_recovers`) | Every malformed image format |
| JPEG and EXIF | A real JPEG is accepted; an EXIF-rotated JPEG is displayed upright with aligned boxes (`tests/test_ui.py::test_real_jpeg_input_is_accepted`, `tests/test_ui.py::test_jpeg_exif_orientation_preserves_display_and_box_alignment`) | Large real phone photos with EXIF rotation; only small synthetic and public images are tested |
| File names | A Unicode file name works and selecting the same file again re-analyses it (`tests/test_ui.py::test_unicode_filename_and_reselecting_same_file`) | |

## Score filter and export

| Behaviour | What is checked | What the evidence does not establish |
| --- | --- | --- |
| Score filter | A score equal to the minimum is kept; comparisons use the underlying score while visible scores are rounded to two decimals; hidden predictions keep identity, colour and selection and return without another inference request; "no predictions meet this minimum" is distinct from "no objects detected" (all 7 tests in `tests/test_filter.py`, and `tests/test_ui.py::test_visible_scores_round_without_changing_the_underlying_values`) | |
| PNG export | The downloaded PNG bytes have the original dimensions, contain only the visible boxes and leave the photo unchanged outside them; JPEG orientation is preserved; Save requires current visible predictions; an encoder failure or 15-second encoder timeout keeps the result and allows a new attempt (`tests/test_export.py::test_downloaded_png_contains_only_filtered_boxes_at_original_dimensions`, `tests/test_export.py::test_export_preserves_jpeg_orientation_and_oriented_dimensions`, `tests/test_export.py::test_save_requires_current_visible_predictions`, `tests/test_export.py::test_png_encoding_failure_preserves_results_and_can_be_retried`, `tests/test_export.py::test_nonresponding_png_encoder_times_out_and_a_new_export_recovers`) | |
| Try sample | The real local sample photo goes through the normal app path and resets the previous filter; a missing, unreadable or unresponsive sample (15-second deadline) can be retried (`tests/test_sample.py::test_try_sample_fetches_the_real_photo_and_resets_the_previous_filter`, `tests/test_sample.py::test_sample_fetch_or_decode_failure_can_be_retried`, `tests/test_sample.py::test_nonresponding_sample_fetch_times_out_and_a_new_attempt_recovers`) | |

Several export tests assert that the download folder stays empty when no export should happen. [extension-first-full-suite.xml](evidence/history/extension-first-full-suite.xml) has 47 passes and one failed download-folder assertion: the extra file was `downloads.htm.crdownload` with a CRX container header, not an application PNG, and its producing request was not captured. The assertion is kept, and external hostname resolution is disabled only inside isolated test browsers.

## Layout, keyboard and announcements

| Behaviour | What is checked | What the evidence does not establish |
| --- | --- | --- |
| Keyboard | Clear, Try sample and the minimum-score control are reachable and usable with the keyboard (`tests/test_ui.py::test_clear_is_reachable_and_usable_with_keyboard`, `tests/test_sample.py::test_try_sample_is_keyboard_reachable_and_activates_with_enter`, `tests/test_filter.py::test_minimum_score_has_accessible_label_and_keyboard_controls`) | |
| Useful feedback and announcements | Important input errors contain the format, limit and recovery information; status and error elements keep their intended roles and live settings (`tests/test_ui.py::test_status_and_error_announcement_configuration_follows_visible_states`) | Actual screen-reader speech, accessibility certification or every assistive technology |
| Narrow screens | At 320 and 390 CSS pixels the page does not scroll sideways and results stay usable (`tests/test_ui.py::test_narrow_layout_preserves_results_and_does_not_overflow`) | Every device |

A 320-pixel viewport defect was observed rather than injected. The vertical scrollbar left 305 pixels of usable width, but the body's minimum was 320 pixels. Comparing against `window.innerWidth` hid the overflow; the check compares against `documentElement.clientWidth`. [viewport-before-fix.xml](evidence/history/viewport-before-fix.xml) retains the real failing assertion, and the corrected capture measured 305-pixel content inside the 305-pixel space ([extension-verification.json](evidence/history/extension-verification.json)).

## Real-model regression checks

`tests/test_inference.py::test_real_model_detects_reviewed_object` runs the actual pinned model on three public photos (astronaut, coffee through Try sample, and cat). Every visible row, including the 0.67 coffee spoon, must match the recorded output of the same pinned model within 0.01, and the selected box's coordinates must stay within 0.005 of the image extent per edge, plus 2 CSS pixels for layout. The expected values come from the recorded file [model-observations.json](evidence/model-observations.json), not from the page's own attributes. This detects a position regression, a score change or a rendering displacement. It cannot establish whether the reference boxes are objectively correct; the reference is an earlier output, not ground truth.

The five-photo observations in [model-observations.json](evidence/model-observations.json) are: astronaut produced person; coffee produced spoon, dining table, cup and another spoon; chelsea produced cat; camera included person with incorrect or duplicate other predictions; rocket produced no predictions. These convenience samples are not an annotated dataset. Expected-label notes came from upstream descriptions and a separate AI-assisted visual inspection made before inference; they are partial expectations, not full human annotations.

## Static package

The public package is checked by 10 browser-free tests in `tests/test_public_package.py`: the ZIP exactly matches the manifest and excludes private material; a missing or changed runtime asset, a changed licence, test mode or an unapproved manifest path stops the build; and Git provenance is optional outside a checkout, in a repository with no commits, and never taken from a parent repository. `tests/test_public_package.py::test_packaged_site_runs_real_sample_filter_and_export_on_an_ordinary_static_server` serves the package under the `/object-lens/` URL subpath from Python's standard static server and runs the real model, filter and export there. The worker resolves the model and runtime URLs relative to its own location, so the same package works at a site root or under a subpath such as a GitHub Pages project site; only the loopback subpath is tested, not a hosted URL. `tests/test_server.py::test_controlled_worker_requires_explicit_test_mode` checks that a normal server never serves controlled test predictions and that JavaScript is served as `text/javascript`; `serve.py` uses a fixed MIME map, so the content type does not depend on the Windows registry.

The package carries a licence for every library found in the shipped browser bundle. Besides the Transformers.js, ONNX Runtime Web, Jinja and model licences, the ONNX Runtime Web 1.14.0 bundle embeds five libraries whose licences are included: long 4.0.0 (Apache-2.0), flatbuffers 1.12.0 (Apache-2.0), onnx-proto 4.0.4 (MIT), protobufjs 6.11.3 (BSD-3-Clause) and guid-typescript 1.0.9 (ISC, declared in its `package.json`; the package ships no licence file, so the notice records the declaration and the standard ISC text). Each licence file is recorded with its size, hash and source in `credits-lock.json`, linked from `dist/credits.html` and listed in `NOTICE.md`; the package build stops if a recorded licence is missing or changed. The libraries were identified by searching the bundle for each library's code, and their versions come from ONNX Runtime 1.14.0's `package-lock.json`.

The rebuilt package (28 files, all entries verified against the manifest) is identified in [v1-0-package.json](evidence/v1-0-package.json). `.github/workflows/pages.yml` builds the same allowlisted package and deploys it to GitHub Pages when started by hand. The deployed showcase was opened and checked once ([showcase-check.json](evidence/showcase-check.json)). Browser captures, viewport measurements and the labelled controlled timeout and Clear captures are recorded with their hashes in [v1-0-rendered-review.json](evidence/v1-0-rendered-review.json); the 12 captures are expected to be byte-identical to the images kept in `docs/screenshots/app`. Real coffee inference and export captures are distinguished from the deliberately controlled timeout and Clear states. Browser console and request observations describe the captured sessions, not all operating-system activity.

## Core rules broken on purpose

[`tools/check_review_sensitivity.py`](../tools/check_review_sensitivity.py) copies the application into disposable folders and plants one deliberate fault in each copy; the checkout is never changed. In [v1-0-1-sensitivity.json](evidence/v1-0-1-sensitivity.json) a 30-case clean control passes, then each of 16 deliberate faults fails its intended tests, 28 intended failures in total.

Five faults each break one core rule the question depends on:

| Core rule | Deliberate change | Test that failed |
| --- | --- | --- |
| A file of exactly 10 MiB is accepted | `file.size > MAX_BYTES` becomes `>=` | `tests/test_ui.py::test_file_size_boundary[10485760-complete]` (the 10 MiB + 1 byte case still passes) |
| The filter keeps a score equal to the minimum | `score >= minimum` becomes `>` | 3 of 7 in `tests/test_filter.py`: `test_exact_minimum_filters_underlying_scores_and_restores_without_inference`, `test_filter_preserves_result_identity_color_and_surviving_selection`, `test_hidden_predictions_can_be_restored_and_differ_from_no_model_predictions` |
| An old image's result cannot repaint a newer image or a cleared workspace | the guard `data.id === revision && currentImage?.id === revision` becomes `true` | `tests/test_ui.py::test_replacing_a_processing_image_discards_the_old_result[slow-car.png]`, `tests/test_ui.py::test_clearing_a_processing_image_prevents_late_repaint` |
| An outdated export cannot download | the check after PNG encoding (`if (token !== exportRevision \|\| snapshot.id !== revision) return;`) removed | all 3 cases of `tests/test_export.py::test_changed_result_cancels_a_png_still_being_encoded` |
| A late sample cannot replace a newer image or undo Clear | all three defences removed: the fetch abort in `cancelSampleLoad`, the check after the download, and the reserved revision passed to `selectFile` | both cases of `tests/test_sample.py::test_late_sample_response_cannot_override_a_later_user_action` |

**Equivalent fault.** Removing only the check after the sample download changes nothing observable, because the fetch abort and the reserved revision still stop the late sample. It is recorded with its 2 cases expected to pass, and they do. This is why the late-sample fault removes all three defences.

**A replacement case that cannot prove the stale-result rule.** With the stale-result guard removed, `tests/test_ui.py::test_replacing_a_processing_image_discards_the_old_result[car.png]` sometimes fails and sometimes passes: the old result is shown for only about 40 ms before the faster new result replaces it, so whether a check sees it is a matter of timing. That case is therefore not counted for this fault. The `[slow-car.png]` case and the Clear case keep the old result on screen and fail every time.

The other 11 faults produce 17 of the intended failures. Four target visible output: blank visible names, blank visible scores, displaced rendered boxes and removed announcement settings. Seven target loading and validation: a fixed load deadline that ignores progress, settings events extending initialization, accepted blank labels, every score scaled by 0.95, every score forced to 1.0, a completed transfer left under the stall window, and a cleared hang reported as an analysis failure. Within the real-model checks, only the recorded-reference comparison catches the two score faults, because the page's own attributes change with them; controlled UI tests compare against independently specified fixture values and are a separate oracle. Each of these faults, with its failing module and count:

| Fault planted | Caught by | Failures |
| --- | --- | ---: |
| Visible labels blanked | `test_ui.py` | 1 |
| Visible scores blanked, numeric metadata kept | `test_ui.py` | 2 |
| Rendered boxes moved out of position | `test_inference.py` | 3 |
| Status, live-region and alert settings removed | `test_ui.py` | 1 |
| Fixed load deadline that ignores progress | `test_recovery.py` | 1 |
| Later settings-file events keep extending initialization | `test_recovery.py` | 1 |
| Blank-label rejection removed | `test_recovery.py` | 2 |
| Every score scaled by 0.95 | `test_inference.py` | 3 |
| Every score forced to 1.0 | `test_inference.py` | 1 |
| Completed download still timed by the stall window | `test_recovery.py` | 1 |
| A cleared hang reported as an analysis failure | `test_recovery.py` | 1 |

Conclusion: every core rule the question depends on has at least one test that fails when the rule is broken. The clean application is preserved. These results show that the selected checks detect the selected faults; they are not a mutation score, a test-completeness proof or naturally observed production incidents. Only locally retained runs are claimed as evidence.

## Fresh-clone run

Passed on the public repository at commit `673f8b3`, cloned from GitHub: every README setup step exited 0, the usage example showed 4 predictions at 0.50 and 3 at 0.80 and saved a 600 x 400 PNG, and the full suite reported 102 passed in 781.58 s (Windows 11, Python 3.12.10, Chrome 156.0.8078.80). An earlier run from the development repository is in [history/fresh-clone-run.json](evidence/history/fresh-clone-run.json).

The run clones the repository into a new, empty folder and follows the README exactly: the first-setup steps, the smallest usage example and the test command. The operating system and runtime versions it ran on are recorded in [fresh-clone-github.json](evidence/fresh-clone-github.json).

## Reproduce the evidence

![How browser tests produce evidence: pytest starts an isolated local server and headless Chrome, Selenium drives the app through either the controlled test worker or the real model worker, pytest asserts the expected behaviour, and failures keep a screenshot, page HTML, console and test context](diagrams/testing-workflow.png)

How a browser test runs: each test uses either the controlled test worker (UI rules and recovery) or the real model worker (real path and selected labels), and pytest decides pass or fail.

From the prepared repository environment:

```powershell
.\.venv\Scripts\python.exe tools/prepare_assets.py --verify-only
.\.venv\Scripts\python.exe tools/download_samples.py --verify
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe tools/check_review_sensitivity.py --output artifacts/sensitivity
.\.venv\Scripts\python.exe tools/check_recovery_comparison.py --output artifacts/recovery-comparison
.\.venv\Scripts\python.exe tools/capture_review.py --screenshots artifacts/captures --report artifacts/captures.json
.\.venv\Scripts\python.exe tools/record_verification.py --retain-prefix <new-prefix>
.\.venv\Scripts\python.exe tools/build_public_demo.py
.\.venv\Scripts\python.exe -m pip install pip-audit==2.10.1
.\.venv\Scripts\python.exe tools/security_scan.py
```

`security_scan.py` needs an internet connection and rewrites `docs/evidence/security/pip-audit.json`.

`check_review_sensitivity.py`, `check_recovery_comparison.py` and `capture_review.py` refuse an output location that already holds results, and `record_verification.py` refuses a prefix whose evidence files already exist, so choose new names for a repeat run. The verification record lists the exact invocation used, including its temporary directory outside any Git checkout. These helpers reproduce the sensitivity, capture and evidence-export runs; some older records have no tracked helper. JUnit evidence copies remove hostnames; the record notes the redaction and the hashes of the raw and selected files. Test processes run headlessly with local assets and a cached driver. They do not change system security settings.

## Earlier recorded runs

Each record covers the source it names. Counts overlap and are never added to the current result. Run dates are kept inside the evidence files, and paths written inside older records describe where files were when they were recorded. "Files committed as" means the record's own source hashes match the files of that commit; "not recorded" means the record does not identify its source.

| Source commit | Recorded result | Evidence |
| --- | --- | --- |
| `0c7e890` (run from `bda90df` with uncommitted changes; files committed as `0c7e890`) | 102 passed, 0 failures/errors/skips; 702.164 s JUnit; 98 controlled and 4 real-model. Sensitivity: 30-case control passed, 16 faults, 28 intended failures, 1 equivalent fault passed as expected. The test page fixture then loaded once with no diagnosis | [v1-0-verification.json](evidence/history/v1-0-verification.json), [v1-0-full-suite.xml](evidence/history/v1-0-full-suite.xml), [v1-0-sensitivity.json](evidence/history/v1-0-sensitivity.json) |
| `ccd3d5b` (run from `0601bbc` with uncommitted changes; files committed as `ccd3d5b`) | 102 passed, 0 failures/errors/skips; 774.316 s JUnit; 98 controlled and 4 real-model (Windows 11, Chrome 156.0.8078.80, Python 3.12.10). Sensitivity: 30-case control passed, 16 faults, 28 intended failures, 1 equivalent fault passed as expected. Package: 23 files, before the five embedded-library licences were added | [release-verification.json](evidence/history/release-verification.json), [release-full-suite.xml](evidence/history/release-full-suite.xml), [release-sensitivity.json](evidence/history/release-sensitivity.json), [release-rendered-review.json](evidence/history/release-rendered-review.json), [release-package.json](evidence/history/release-package.json) |
| `8c154b7` (run from `b8ff7bc` with uncommitted changes; files committed as `8c154b7`) | 102 passed, 0 failures/errors/skips; 780.398 s JUnit; 98 controlled and 4 real-model. Sensitivity: 13-case control passed, 11 faults, 17 intended failures. 2.5 Mbps probe: ready at 140.6 s | [branch-review-verification.json](evidence/history/branch-review-verification.json), [branch-review-full-suite.xml](evidence/history/branch-review-full-suite.xml), [branch-review-sensitivity.json](evidence/history/branch-review-sensitivity.json), [slow-transfer-2-5-mbps.json](evidence/slow-transfer-2-5-mbps.json), [branch-review-recovery-comparison.json](evidence/history/branch-review-recovery-comparison.json), [branch-review-rendered-review.json](evidence/history/branch-review-rendered-review.json), [branch-review-package.json](evidence/history/branch-review-package.json) |
| `b8ff7bc` (run from `a338f7c` with uncommitted changes; files committed as `b8ff7bc`) | 98 passed, 0 failures/errors/skips; 783.414 s JUnit; 94 controlled and 4 real-model. Sensitivity: 11-case control passed, 8 faults, 14 intended failures. 2.5 Mbps probe: ready at 139.6 s | [loading-followup-verification.json](evidence/history/loading-followup-verification.json), [loading-followup-full-suite.xml](evidence/history/loading-followup-full-suite.xml), [loading-followup-sensitivity.json](evidence/history/loading-followup-sensitivity.json), [loading-followup-slow-transfer.json](evidence/history/loading-followup-slow-transfer.json), [loading-followup-recovery-comparison.json](evidence/history/loading-followup-recovery-comparison.json), [loading-followup-rendered-review.json](evidence/history/loading-followup-rendered-review.json), [loading-followup-package.json](evidence/history/loading-followup-package.json) |
| `a338f7c`, disposable copy (named by the file; the XML records no source hash) | 93 passed, 0 failures/errors/skips; 725.685 s JUnit. With the blank-label check deleted, 44 recovery and UI tests still passed | [audit-17f2b9a-full-suite.xml](evidence/history/audit-17f2b9a-full-suite.xml), [audit-17f2b9a-blank-label-fault.xml](evidence/history/audit-17f2b9a-blank-label-fault.xml) |
| `a338f7c` (run from `8a35f38` with uncommitted changes; files committed as `a338f7c`) | 93 passed, 0 failures/errors/skips; 648.509 s JUnit; 89 controlled and 4 real-model. Sensitivity: 6-case control passed, 4 faults, 7 intended failures | [followup-verification.json](evidence/history/followup-verification.json), [followup-full-suite.xml](evidence/history/followup-full-suite.xml), [followup-sensitivity.json](evidence/history/followup-sensitivity.json), [followup-recovery-comparison.json](evidence/history/followup-recovery-comparison.json), [followup-rendered-review.json](evidence/history/followup-rendered-review.json), [followup-package.json](evidence/history/followup-package.json) |
| `8a35f38` (reviewed from `6306ba6`; files committed as `8a35f38`) | 72 passed, 0 failures/errors/skips; 531.363 s JUnit (531.53 s runner); 68 controlled and 4 real-model | [source-review-verification.json](evidence/history/source-review-verification.json), [review-full-suite.xml](evidence/history/review-full-suite.xml) |
| `e4781ab` (files committed as `e4781ab`) | 59 passed; 441.33 s runner; focused startup and package run 11 passed in 52.46 s runner. 10 Mbps probe: ready at 36.776 s | [public-prep-verification.json](evidence/history/public-prep-verification.json), [public-prep-full-suite.xml](evidence/history/public-prep-full-suite.xml), [public-prep-focused-suite.xml](evidence/history/public-prep-focused-suite.xml), [public-prep-review.json](evidence/history/public-prep-review.json) |
| `724d04d` (run from `3afc8a9` with uncommitted changes; files committed as `724d04d`) | 48 passed; 418.62 s runner; 45 controlled and 3 real-model | [extension-verification.json](evidence/history/extension-verification.json), [extension-full-suite.xml](evidence/history/extension-full-suite.xml) |
| Not recorded (record committed in `724d04d`) | PNG export suite: 8 controlled cases passed; 88.818 s JUnit | [export-png-suite.xml](evidence/history/export-png-suite.xml) |
| Not recorded (record committed in `3afc8a9`) | Sample suite: 7 controlled and 3 real-model cases passed; 137.27 s runner | [sample-image-record.json](evidence/history/sample-image-record.json), [sample-image-suite.xml](evidence/history/sample-image-suite.xml) |
| Not recorded (record committed in `8e5b977`) | Score-filter suite: 29 controlled cases passed; 199.37 s runner | [score-filter-record.json](evidence/history/score-filter-record.json), [score-filter-suite.xml](evidence/history/score-filter-suite.xml) |
| Not recorded (record committed in `0f60bae`) | Final run: 26 passed; 214.967 s JUnit. Earlier run before the final test diagnostics: 26 passed; 204.954 s JUnit | [final-full-suite.xml](evidence/history/final-full-suite.xml), [initial-full-suite.xml](evidence/history/initial-full-suite.xml) |
| Not recorded (its `source_tree_id` matches no commit) | Independently prepared copy on the same laptop, not a clone: 26 passed; 205.13 s runner | [fresh-setup-summary.json](evidence/history/fresh-setup-summary.json), [fresh-setup-suite.xml](evidence/history/fresh-setup-suite.xml) |
| `0f60bae` application files except `dist/style.css` (the record's `post_run_change` notes a different empty-state text colour; runtime logic and model are unchanged) | Repeated real-model use: 320 cycles, 320 clears and 32 rapid replacements in 3615.927 s; no observed failure | [stability-summary.json](evidence/history/stability-summary.json) |

## Release assessment and limits

The recorded suite and the targeted fault and recovery evidence support the local exploration workflow: **102 passed, 0 failures/errors/skips (98 controlled, 4 real-model)**. Stall-based loading completed a paced 2.5 Mbps model transfer that a fixed-deadline source could not complete. The static ZIP is a local package. The manual Pages workflow (`.github/workflows/pages.yml`) builds the same allowlisted package and deploys it to GitHub Pages; no deployment or public URL is verified in this repository.

Only the recorded Windows and Chrome environment was checked. No other browser, iOS or Safari, mobile device, deployed URL, general accuracy benchmark, GPU or NPU execution, or production-scale behaviour was qualified. The one-hour session ran on the base version and does not requalify the current source, establish a flake rate or certify freedom from memory leaks. Timing varies with workstation load. CI runs the controlled suite and the dependency audit on GitHub Actions; hosted results are shown on GitHub and are not recorded here. The dependency audit covers the locked Python packages on the day of the run, not the browser runtime or model. Announcement configuration checks are not screen-reader testing.

Known risks that are not tested ([DESIGN.md](DESIGN.md#risks-and-test-mix)):

- **Repeated 45-second stalls.** Try again restarts the model download from the beginning, so a connection that repeatedly stalls for 45 seconds cannot load the detector. Resumable download is a non-goal.
- **Other browsers and mobile.** Only Windows with Chrome is in scope.
- **Large real phone photos with EXIF rotation.** Only synthetic images and small public photos are tested.

After Clear in the unavailable state the Clear button stays enabled on an empty workspace; pressing it again is harmless.

Raw outputs and retained recovery-comparison copies remain under ignored working directories. The sensitivity runner removes its own temporary source copies after each run while preserving logs and results. The maintained application is the repository's root `dist` directory.
