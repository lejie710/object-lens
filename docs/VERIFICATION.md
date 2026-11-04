# Verification and release assessment

**Question.** When someone tries a browser object detector on their own photos, switching images quickly, on a slow connection, or when the model returns something broken, can the page show results that belong to a different photo, misplace boxes, or get stuck with no way to recover? ([DESIGN.md](DESIGN.md#the-question))

**Measure.** A controlled test for each of those failures; every core rule the question depends on caught when it is broken on purpose; and a before/after measurement of model loading at 2.5 Mbps.

**Result.**

| Measure | Result | Evidence |
| --- | --- | --- |
| Recorded full suite | **102 passed, 0 failures/errors/skips** (98 controlled, 4 real-model), 774.316 s of JUnit suite time on Windows 11, Chrome 156.0.8078.80, Python 3.12.10, pytest 9.0.3 and Selenium 4.40.0 | [release-verification.json](evidence/release-verification.json), [release-full-suite.xml](evidence/release-full-suite.xml) |
| Core rules broken on purpose | A 30-case clean control passes; each of 16 deliberate faults fails its intended tests (28 intended failures); 1 equivalent fault passes as expected. Every core rule has at least one test that fails when the rule is broken | [release-sensitivity.json](evidence/release-sensitivity.json), [Core rules broken on purpose](#core-rules-broken-on-purpose) |
| Model loading at 2.5 Mbps | A fixed 120-second deadline (`17f2b9a`) failed at 121 s with 37.4 of 43.1 MB (86%) received; stall-based loading received every byte and reached ready at 140.6 s | [branch-review-slow-transfer.json](evidence/branch-review-slow-transfer.json) |
| Fresh clone following the README | Pending: run against this commit and recorded in the next commit | [fresh-clone-run.json](evidence/fresh-clone-run.json) |

The release record identifies the tested files by their source hashes. The slow-transfer probe ran against a package whose loading, inference, filter, sample and export code is identical to the release source; the two differ only in `dist/credits.html`. Acceptance examples mapped to named tests are in [DESIGN.md](DESIGN.md#acceptance-examples); the ranked risks and the test mix are in [DESIGN.md](DESIGN.md#risks-and-test-mix). Every confirmed defect, with the test that prevents it, is in [Defects and corrections](SOURCE_REVIEW.md). Each evidence file is described in the [evidence index](evidence/README.md).

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

On the 2.5 Mbps loopback probe, only the ONNX model response was paced. The fixed-deadline source failed at 121.0 s with 37,486,592 of 43,102,531 bytes received, and Try again restarted the transfer from zero (2.4 MB received eight seconds later). The stall-based package received all 43,102,531 bytes and reached ready at 140.6 s ([branch-review-slow-transfer.json](evidence/branch-review-slow-transfer.json), which includes the probe source). Each condition ran once. A separate package (`3ac9422`) paced only the model response at 10 Mbps on loopback: 43,102,531 bytes arrived in 34.493 seconds and readiness occurred at 36.776 seconds ([public-prep-verification.json](evidence/public-prep-verification.json)). Neither observation is Internet performance.

## Stale results, exports and samples

| Behaviour | What is checked | What the evidence does not establish |
| --- | --- | --- |
| Results match the current image | The list shows exactly the returned labels with their two-decimal scores, each box carries its returned label, and the laptop box is placed at the returned coordinates within 2 CSS pixels; replacing an image replaces every result; selecting a row highlights only its box (`tests/test_ui.py::test_predictions_and_boxes_match_the_current_image`, `tests/test_ui.py::test_replacing_image_replaces_all_results`, `tests/test_ui.py::test_selecting_a_result_highlights_its_box`) | Recognition accuracy |
| An old result cannot repaint | Replacing an image that is still being analysed, with a fast or slow replacement, never shows the old result; Clear during analysis keeps the workspace empty (`tests/test_ui.py::test_replacing_a_processing_image_discards_the_old_result`, `tests/test_ui.py::test_clearing_a_processing_image_prevents_late_repaint`) | Timing on other browsers |
| Cached predictions are retired | A new image or Clear resets the filter and retires cached predictions; an invalid replacement discards the filter cache (`tests/test_filter.py::test_new_image_and_clear_reset_filter_and_retire_old_cached_predictions`, `tests/test_filter.py::test_invalid_replacement_discards_filter_cache_and_valid_image_recovers`) | |
| An outdated export cannot download | Clear, a replacement or a filter change while the PNG is still being encoded cancels the download (`tests/test_export.py::test_changed_result_cancels_a_png_still_being_encoded`, 3 cases) | |
| A late sample cannot override the user | A held sample response released after Clear or an upload leaves the workspace empty or showing the upload, with no second sample request (`tests/test_sample.py::test_late_sample_response_cannot_override_a_later_user_action`, 2 cases) | |
| Clear during a hung analysis | If Clear removed the image before its analysis timed out, the detector restarts quietly instead of showing an analysis failure on an empty workspace (`tests/test_recovery.py::test_clear_during_a_hung_analysis_restarts_quietly`) | That a real model hang occurred |

## Malformed model output and recovery

| Behaviour | What is checked | What the evidence does not establish |
| --- | --- | --- |
| Malformed responses rejected as a whole | 16 kinds of invalid output (not an array, null item, empty or blank label, missing box or coordinate, string or non-finite coordinate, missing, string, non-finite, negative or excess score, reversed, zero-area or fully outside box) show an invalid-result message with Try again, no partial predictions, and the next valid image recovers (`tests/test_recovery.py::test_malformed_result_is_rejected_without_partial_detections_and_recovers`) | Exhaustive validation of every possible object shape or dependency fault |
| Clamping | A box partly outside the image is clamped to the rendered image edge (`tests/test_recovery.py::test_partially_outside_box_is_clamped_to_the_rendered_image`) | |
| Retry after an invalid result | Try again re-analyses the same image (`tests/test_recovery.py::test_retry_after_a_transient_invalid_result_reanalyzes_the_same_image`) | |
| Truthful timeout and Clear feedback | Model-loading and inference deadlines have distinct explanations; Clear leaves a stopped detector unavailable; Retry restores operation; a worker crash during inference is not described as a startup failure (`tests/test_recovery.py::test_model_load_timeout_clear_and_retry_describe_detector_availability`, `tests/test_recovery.py::test_inference_timeout_clear_and_retry_describe_detector_availability`, `tests/test_recovery.py::test_worker_crash_during_inference_is_not_described_as_startup_failure`) | That a real model outage occurred |
| Silent worker | A worker that never answers times out and Try again analyses the latest image (`tests/test_ui.py::test_nonresponding_worker_times_out_and_retries_the_latest_image`) | No real-model hang was observed |
| Empty and failed results | No predictions is shown as an empty result, not an error; a processing or worker-start failure is visible and recoverable (`tests/test_ui.py::test_empty_predictions_are_not_an_error`, `tests/test_ui.py::test_processing_failure_is_visible_and_next_image_recovers`, `tests/test_ui.py::test_worker_start_failure_can_be_retried`) | |

[branch-review-recovery-comparison.json](evidence/branch-review-recovery-comparison.json) runs three controlled wording checks against `app.js` from `74d108f` and from `764fb9d`, whose `app.js` is identical to the release source. All three fail against `74d108f` (26.952 s) and pass against `764fb9d` (26.040 s). The old checks fail before Clear, so they do not independently reproduce the old Clear message. The passing checks continue through Clear, truthful detector unavailability, Retry and a successful new image. The substituted runtime crash is a component simulation; no production trigger is claimed.

The malformed responses are deliberate test-worker outputs, not faults observed from the real pretrained model. Two records show the gap the blank-label check closes: [audit-17f2b9a-full-suite.xml](evidence/audit-17f2b9a-full-suite.xml), a 93-case run of `17f2b9a` in a disposable copy, and [audit-17f2b9a-blank-label-fault.xml](evidence/audit-17f2b9a-blank-label-fault.xml), where 44 recovery and UI tests still passed with the blank-label check deleted.

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

Several export tests assert that the download folder stays empty when no export should happen. [extension-first-full-suite.xml](evidence/extension-first-full-suite.xml) has 47 passes and one failed download-folder assertion: the extra file was `downloads.htm.crdownload` with a CRX container header, not an application PNG, and its producing request was not captured. The assertion is kept, and external hostname resolution is disabled only inside isolated test browsers.

## Layout, keyboard and announcements

| Behaviour | What is checked | What the evidence does not establish |
| --- | --- | --- |
| Keyboard | Clear, Try sample and the minimum-score control are reachable and usable with the keyboard (`tests/test_ui.py::test_clear_is_reachable_and_usable_with_keyboard`, `tests/test_sample.py::test_try_sample_is_keyboard_reachable_and_activates_with_enter`, `tests/test_filter.py::test_minimum_score_has_accessible_label_and_keyboard_controls`) | |
| Useful feedback and announcements | Important input errors contain the format, limit and recovery information; status and error elements keep their intended roles and live settings (`tests/test_ui.py::test_status_and_error_announcement_configuration_follows_visible_states`) | Actual screen-reader speech, accessibility certification or every assistive technology |
| Narrow screens | At 320 and 390 CSS pixels the page does not scroll sideways and results stay usable (`tests/test_ui.py::test_narrow_layout_preserves_results_and_does_not_overflow`) | Every device |

A 320-pixel viewport defect was observed rather than injected. The vertical scrollbar left 305 pixels of usable width, but the body's minimum was 320 pixels. Comparing against `window.innerWidth` hid the overflow; the check compares against `documentElement.clientWidth`. [viewport-before-fix.xml](evidence/viewport-before-fix.xml) retains the real failing assertion, and the corrected capture measured 305-pixel content inside the 305-pixel space ([extension-verification.json](evidence/extension-verification.json)).

## Real-model regression checks

`tests/test_inference.py::test_real_model_detects_reviewed_object` runs the actual pinned model on three public photos (astronaut, coffee through Try sample, and cat). Every visible row, including the 0.67 coffee spoon, must match the recorded output of the same pinned model within 0.01, and the selected box's coordinates must stay within 0.005 of the image extent per edge, plus 2 CSS pixels for layout. The expected values come from the recorded file [model-observations.json](evidence/model-observations.json), not from the page's own attributes. This detects a position regression, a score change or a rendering displacement. It cannot establish whether the reference boxes are objectively correct; the reference is an earlier output, not ground truth.

The five-photo observations in [model-observations.json](evidence/model-observations.json) are: astronaut produced person; coffee produced spoon, dining table, cup and another spoon; chelsea produced cat; camera included person with incorrect or duplicate other predictions; rocket produced no predictions. These convenience samples are not an annotated dataset. Expected-label notes came from upstream descriptions and a separate AI-assisted visual inspection made before inference; they are partial expectations, not full human annotations.

## Static package

The public package is checked by 10 browser-free tests in `tests/test_public_package.py`: the ZIP exactly matches the manifest and excludes private material; a missing or changed runtime asset, a changed licence, test mode or an unapproved manifest path stops the build; and Git provenance is optional outside a checkout, in a repository with no commits, and never taken from a parent repository. `tests/test_public_package.py::test_packaged_site_runs_real_sample_filter_and_export_on_an_ordinary_static_server` runs the real model, filter and export through an ordinary static server. `tests/test_server.py::test_controlled_worker_requires_explicit_test_mode` checks that a normal server never serves controlled test predictions.

The rebuilt package is identified in [release-package.json](evidence/release-package.json). It is a local package; no deployment or public URL is verified. Browser captures, viewport measurements and the labelled controlled timeout and Clear captures are recorded with their hashes in [release-rendered-review.json](evidence/release-rendered-review.json); the 12 captures are byte-identical to the images kept in `docs/screenshots/review-followup`. Real coffee inference and export captures are distinguished from the deliberately controlled timeout and Clear states. Browser console and request observations describe the captured sessions, not all operating-system activity.

## Core rules broken on purpose

[`tools/check_review_sensitivity.py`](../tools/check_review_sensitivity.py) copies the application into disposable folders and plants one deliberate fault in each copy; the checkout is never changed. In [release-sensitivity.json](evidence/release-sensitivity.json) a 30-case clean control passes, then each of 16 deliberate faults fails its intended tests, 28 intended failures in total.

Five faults each break one core rule the question depends on:

| Core rule | Deliberate change | Test that failed |
| --- | --- | --- |
| A file of exactly 10 MiB is accepted | `file.size > MAX_BYTES` becomes `>=` | `tests/test_ui.py::test_file_size_boundary[10485760-complete]` (the 10 MiB + 1 byte case still passes) |
| The filter keeps a score equal to the minimum | `score >= minimum` becomes `>` | 3 of 7 in `tests/test_filter.py`: `test_exact_minimum_filters_underlying_scores_and_restores_without_inference`, `test_filter_preserves_result_identity_color_and_surviving_selection`, `test_hidden_predictions_can_be_restored_and_differ_from_no_model_predictions` |
| An old image's result cannot repaint a newer image or a cleared workspace | the guard `data.id === revision && currentImage?.id === revision` becomes `true` | `tests/test_ui.py::test_replacing_a_processing_image_discards_the_old_result[slow-car.png]`, `tests/test_ui.py::test_clearing_a_processing_image_prevents_late_repaint` |
| An outdated export cannot download | the check after PNG encoding (`if (token !== exportRevision \|\| snapshot.id !== revision) return;`) removed | all 3 cases of `tests/test_export.py::test_changed_result_cancels_a_png_still_being_encoded` |
| A late sample cannot replace a newer image or undo Clear | all three defences removed: the fetch abort in `cancelSampleLoad`, the check after the download, and the reserved revision passed to `selectFile` | both cases of `tests/test_sample.py::test_late_sample_response_cannot_override_a_later_user_action` |

**Equivalent fault.** Removing only the check after the sample download changes nothing observable, because the fetch abort and the reserved revision still stop the late sample. It is recorded with its 2 cases expected to pass, and they do. This is why the late-sample fault removes all three defences.

The other 11 faults produce 17 of the intended failures. Four target visible output: blank visible names, blank visible scores, displaced rendered boxes and removed announcement settings. Seven target loading and validation: a fixed load deadline that ignores progress, settings events extending initialization, accepted blank labels, every score scaled by 0.95, every score forced to 1.0, a completed transfer left under the stall window, and a cleared hang reported as an analysis failure. Within the real-model checks, only the recorded-reference comparison catches the two score faults, because the page's own attributes change with them; controlled UI tests compare against independently specified fixture values and are a separate oracle. The README lists each of these faults with its failing module and count.

Conclusion: every core rule the question depends on has at least one test that fails when the rule is broken. The clean application is preserved. These results show that the selected checks detect the selected faults; they are not a mutation score, a test-completeness proof or naturally observed production incidents. Only locally retained runs are claimed as evidence.

## Fresh-clone run

Pending: run against this commit and recorded in the next commit.

The run clones the repository into a new, empty folder and follows the README exactly: the first-setup steps, the smallest usage example and the test command. The operating system and runtime versions it ran on are recorded in [fresh-clone-run.json](evidence/fresh-clone-run.json).

## Reproduce the evidence

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
```

`check_review_sensitivity.py`, `check_recovery_comparison.py` and `capture_review.py` refuse an output location that already holds results, and `record_verification.py` refuses a prefix whose evidence files already exist, so choose new names for a repeat run. The verification record lists the exact invocation used, including its temporary directory outside any Git checkout. These helpers reproduce the sensitivity, capture and evidence-export runs; some older records have no tracked helper. JUnit evidence copies remove hostnames; the record notes the redaction and the hashes of the raw and selected files. Test processes run headlessly with local assets and a cached driver. They do not change system security settings.

## Earlier recorded runs

Each record covers the source it names. Counts overlap and are never added to the current result. Run dates are kept inside the evidence files. "Files committed as" means the record's own source hashes match the files of that commit; "not recorded" means the record does not identify its source.

| Source commit | Recorded result | Evidence |
| --- | --- | --- |
| `764fb9d` (run from `f1a19a9` with uncommitted changes; files committed as `764fb9d`) | 102 passed, 0 failures/errors/skips; 780.398 s JUnit; 98 controlled and 4 real-model. Sensitivity: 13-case control passed, 11 faults, 17 intended failures. 2.5 Mbps probe: ready at 140.6 s | [branch-review-verification.json](evidence/branch-review-verification.json), [branch-review-full-suite.xml](evidence/branch-review-full-suite.xml), [branch-review-sensitivity.json](evidence/branch-review-sensitivity.json), [branch-review-slow-transfer.json](evidence/branch-review-slow-transfer.json), [branch-review-recovery-comparison.json](evidence/branch-review-recovery-comparison.json), [branch-review-rendered-review.json](evidence/branch-review-rendered-review.json), [branch-review-package.json](evidence/branch-review-package.json) |
| `f1a19a9` (run from `17f2b9a` with uncommitted changes; files committed as `f1a19a9`) | 98 passed, 0 failures/errors/skips; 783.414 s JUnit; 94 controlled and 4 real-model. Sensitivity: 11-case control passed, 8 faults, 14 intended failures. 2.5 Mbps probe: ready at 139.6 s | [loading-followup-verification.json](evidence/loading-followup-verification.json), [loading-followup-full-suite.xml](evidence/loading-followup-full-suite.xml), [loading-followup-sensitivity.json](evidence/loading-followup-sensitivity.json), [loading-followup-slow-transfer.json](evidence/loading-followup-slow-transfer.json), [loading-followup-recovery-comparison.json](evidence/loading-followup-recovery-comparison.json), [loading-followup-rendered-review.json](evidence/loading-followup-rendered-review.json), [loading-followup-package.json](evidence/loading-followup-package.json) |
| `17f2b9a`, disposable copy (named by the file; the XML records no source hash) | 93 passed, 0 failures/errors/skips; 725.685 s JUnit. With the blank-label check deleted, 44 recovery and UI tests still passed | [audit-17f2b9a-full-suite.xml](evidence/audit-17f2b9a-full-suite.xml), [audit-17f2b9a-blank-label-fault.xml](evidence/audit-17f2b9a-blank-label-fault.xml) |
| `17f2b9a` (run from `74d108f` with uncommitted changes; files committed as `17f2b9a`) | 93 passed, 0 failures/errors/skips; 648.509 s JUnit; 89 controlled and 4 real-model. Sensitivity: 6-case control passed, 4 faults, 7 intended failures | [followup-verification.json](evidence/followup-verification.json), [followup-full-suite.xml](evidence/followup-full-suite.xml), [followup-sensitivity.json](evidence/followup-sensitivity.json), [followup-recovery-comparison.json](evidence/followup-recovery-comparison.json), [followup-rendered-review.json](evidence/followup-rendered-review.json), [followup-package.json](evidence/followup-package.json) |
| `74d108f` (reviewed from `9a60886`; files committed as `74d108f`) | 72 passed, 0 failures/errors/skips; 531.363 s JUnit (531.53 s runner); 68 controlled and 4 real-model | [source-review-verification.json](evidence/source-review-verification.json), [review-full-suite.xml](evidence/review-full-suite.xml) |
| `3ac9422` (files committed as `3ac9422`) | 59 passed; 441.33 s runner; focused startup and package run 11 passed in 52.46 s runner. 10 Mbps probe: ready at 36.776 s | [public-prep-verification.json](evidence/public-prep-verification.json), [public-prep-full-suite.xml](evidence/public-prep-full-suite.xml), [public-prep-focused-suite.xml](evidence/public-prep-focused-suite.xml), [public-prep-review.json](evidence/public-prep-review.json) |
| `781d9b7` (run from `d8a0c27` with uncommitted changes; files committed as `781d9b7`) | 48 passed; 418.62 s runner; 45 controlled and 3 real-model | [extension-verification.json](evidence/extension-verification.json), [extension-full-suite.xml](evidence/extension-full-suite.xml) |
| Not recorded (record committed in `781d9b7`) | PNG export suite: 8 controlled cases passed; 88.818 s JUnit | [export-png-suite.xml](evidence/export-png-suite.xml) |
| Not recorded (record committed in `d8a0c27`) | Sample suite: 7 controlled and 3 real-model cases passed; 137.27 s runner | [sample-image-record.json](evidence/sample-image-record.json), [sample-image-suite.xml](evidence/sample-image-suite.xml) |
| Not recorded (record committed in `782fcff`) | Score-filter suite: 29 controlled cases passed; 199.37 s runner | [score-filter-record.json](evidence/score-filter-record.json), [score-filter-suite.xml](evidence/score-filter-suite.xml) |
| Not recorded (record committed in `615f5c0`) | Final run: 26 passed; 214.967 s JUnit. Earlier run before the final test diagnostics: 26 passed; 204.954 s JUnit | [final-full-suite.xml](evidence/final-full-suite.xml), [initial-full-suite.xml](evidence/initial-full-suite.xml) |
| Not recorded (its `source_tree_id` matches no commit) | Independently prepared copy on the same laptop, not a clone: 26 passed; 205.13 s runner | [fresh-setup-summary.json](evidence/fresh-setup-summary.json), [fresh-setup-suite.xml](evidence/fresh-setup-suite.xml) |
| `615f5c0` application files except `dist/style.css` (the record's `post_run_change` notes a different empty-state text colour; runtime logic and model are unchanged) | Repeated real-model use: 320 cycles, 320 clears and 32 rapid replacements in 3615.927 s; no observed failure | [stability-summary.json](evidence/stability-summary.json) |

## Release assessment and limits

The recorded suite and the targeted fault and recovery evidence support the local exploration workflow: **102 passed, 0 failures/errors/skips (98 controlled, 4 real-model)**. Stall-based loading completed a paced 2.5 Mbps model transfer that a fixed-deadline source could not complete. The static ZIP is a local package. No public deployment or verified public URL exists.

Only the recorded Windows and Chrome environment was checked. No other browser, iOS or Safari, mobile device, hosted CI, deployed URL, general accuracy benchmark, GPU or NPU execution, or production-scale behaviour was qualified. The one-hour session ran on the base version and does not requalify the current source, establish a flake rate or certify freedom from memory leaks. Timing varies with workstation load. Announcement configuration checks are not screen-reader testing.

Known risks that are not tested ([DESIGN.md](DESIGN.md#risks-and-test-mix)):

- **Repeated 45-second stalls.** Try again restarts the model download from the beginning, so a connection that repeatedly stalls for 45 seconds cannot load the detector. Resumable download is a non-goal.
- **Other browsers and mobile.** Only Windows with Chrome is in scope.
- **Large real phone photos with EXIF rotation.** Only synthetic images and small public photos are tested.

After Clear in the unavailable state the Clear button stays enabled on an empty workspace; pressing it again is harmless.

Raw outputs and retained recovery-comparison copies remain under ignored working directories. The sensitivity runner removes its own temporary source copies after each run while preserving logs and results. The maintained application is the repository's root `dist` directory.
