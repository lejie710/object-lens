# Object Lens

[![tests](https://github.com/lejie710/object-lens/actions/workflows/ci.yml/badge.svg)](https://github.com/lejie710/object-lens/actions/workflows/ci.yml)

A browser object detector built to be tested: stale results, slow model downloads, malformed model output and recovery.

**Showcase:** [lejie710.github.io/object-lens](https://lejie710.github.io/object-lens/) | **Status:** complete (version 1.0), not under active development

**The question.** When someone tries a browser object detector on their own photos, switching images quickly, on a slow connection, or when the model returns something broken, can the page show results that belong to a different photo, misplace boxes, or get stuck with no way to recover?

Object Lens is a small browser app that runs a pretrained DETR object detector on your photo, entirely on your own machine. Its Python, pytest and Selenium suite answers the question with three kinds of evidence: a controlled test for each failure, every core rule caught when it is broken on purpose, and a before/after measurement on a slow connection.

## The answer, with evidence

| Evidence | Result |
| --- | --- |
| Model download throttled to 2.5 Mbps on loopback | Before: loading failed at 121 s with 37.4 of 43.1 MB (86%) received, and Try again restarted from zero. After: the package received every byte and reached ready at 140.6 s ([slow-transfer-2-5-mbps.json](docs/evidence/slow-transfer-2-5-mbps.json)) |
| Recorded full suite | 102 passed, with 0 failures, errors or skips: 98 controlled cases and 4 real-model cases ([summary](docs/evidence/v1-0-verification.json), [JUnit XML](docs/evidence/v1-0-full-suite.xml)) |
| Core rules broken on purpose | Every core rule the question depends on has at least one test that fails when the rule is broken ([v1-0-sensitivity.json](docs/evidence/v1-0-sensitivity.json)) |

The question, its measure, the acceptance examples, the ranked risks and the design decisions are in [DESIGN.md](docs/DESIGN.md#the-question).

## Limits

What Object Lens deliberately does not do, and why ([non-goals and rabbit holes](docs/DESIGN.md#non-goals-and-rabbit-holes)):

- **Model training or accuracy evaluation.** The tests check how the app handles model output, not whether the model is accurate. Nothing here measures accuracy, precision or recall.
- **Accounts, upload records or image history.** The app handles one image at a time and photos never leave the browser, so nothing needs storing.
- **A hosted inference API or cloud deployment.** The model runs locally in the user's browser. The showcase is the same static package served as plain files; no server runs the model.
- **Other browsers and mobile.** Only Windows and Chrome were verified, which keeps the scope small enough to test thoroughly.
- **Resumable model download.** Try again restarts the download from zero. Resuming would require changing the underlying library.

Known risks that are not tested:

- **Repeated 45 s stalls.** Try again restarts from zero, so a connection that keeps stalling for 45 s cannot load the detector (non-goal 5).
- **Other browsers and mobile** (non-goal 4).
- **Large real phone photos with EXIF rotation.** Only synthetic images and small public photos are tested.

Other limits of the evidence:

- CI runs the 98 controlled tests on GitHub Actions (`windows-latest`), and the 4 real-model tests only on a manual run. Results of hosted runs are not recorded in this repository. The recorded results all come from one local Windows and Chrome environment.
- The real-model checks compare against earlier output from the same pinned model. They show regression, not accuracy.
- The announcement tests inspect how the page is configured. Nobody has tested it with an actual screen reader, and there is no accessibility certification.
- A single full run does not measure a flake rate.

The full release assessment is in [VERIFICATION.md](docs/VERIFICATION.md).

| Real detection on the sample photo | Score filter applied | Controlled analysis timeout |
| --- | --- | --- |
| [![Detections on the public coffee sample photo](docs/screenshots/app/desktop.png)](docs/screenshots/app/desktop.png) | [![Predictions hidden by the minimum score filter](docs/screenshots/app/filtered.png)](docs/screenshots/app/filtered.png) | [![Image analysis timeout raised by a controlled test worker](docs/screenshots/app/timeout.png)](docs/screenshots/app/timeout.png) |

The first two screenshots show the real model running on the public coffee sample. The third shows an image-analysis timeout that a test triggers on purpose with a controlled worker. It is not a model result. The screenshot after Clear shows the workspace emptied, with a prompt to restart the detector with Try again ([timeout-cleared.png](docs/screenshots/app/timeout-cleared.png)).

## What the app does

You choose a photo or click **Try sample**. The app shows the predicted labels and boxes, and you can select one to highlight it. A minimum model score slider (0.50 to 1.00) hides or restores predictions. **Save result** downloads the photo with its visible boxes at the original dimensions. Filtering and saving reuse the existing result, so the model does not run again.

The model runs in a web worker using Transformers.js 2.17.2 and ONNX Runtime Web on the CPU (WASM). A small Python server only serves the files. Object Lens adapts Hugging Face's object-detection example and uses a pretrained model as it is. It does not train a model.

## How it is tested

**Recorded full run: 102 passed, with 0 failures, errors or skips.** That is 98 controlled cases and 4 real-model cases, taking 702.164 s of JUnit suite time. The run used Windows 11, Chrome 156.0.8078.80, Python 3.12.10, pytest 9.0.3 and Selenium 4.40.0. Records: [summary](docs/evidence/v1-0-verification.json) and [JUnit XML](docs/evidence/v1-0-full-suite.xml).

CI runs the 98 controlled tests on every push to `main` and every pull request ([ci.yml](.github/workflows/ci.yml)); the 4 real-model tests run there only when the workflow is started by hand. Every run also audits the locked Python dependencies with pip-audit. Results of hosted runs are not recorded in this repository. A local audit of `requirements-lock.txt` found 0 known vulnerabilities in 30 packages ([pip-audit.json](docs/evidence/security/pip-audit.json)).

The tests use two kinds of check, and each answers a different question:

- **Controlled tests (98)** do not run the real model. 84 are browser tests that swap the model for a scripted test worker, which returns exact predictions, empty results, malformed responses, hangs and stalls on demand; 13 are browser-free checks of the package and the test harness, and 1 checks that the normal server cannot serve the test worker ([test mix](docs/DESIGN.md#risks-and-test-mix)). The browser tests check app state, race conditions and recovery against fixture values that were defined separately from the app.
- **Real-model tests (4, marked `inference`)** run the actual pinned model. Three of them use three public photos and compare each visible row's label and score, and the position of the target object's box, with earlier recorded output from the same model. That catches regressions. It does not prove the predictions are correct. The fourth runs the sample, filter and export workflow through the static package.

| Test module | Cases | What it protects |
| --- | ---: | --- |
| `test_recovery.py` | 26 | Deadlines, telling a stalled model download from a slow but steady one, rejecting a malformed result as a whole, and recovery through Clear and Try again |
| `test_ui.py` | 25 | Boxes and list match the current image, stale results cannot repaint after the image is replaced or cleared, file size and pixel limits, focus, announcement settings, narrow layout |
| `test_public_package.py` | 11 | The static package contains only allowlisted files and runs on an ordinary static server (1 case uses the real model) |
| `test_export.py` | 8 | The downloaded PNG has the original dimensions and only the visible predictions, and a pending export cannot download after Clear |
| `test_filter.py` | 7 | The score filter keeps boxes, list and counts in agreement and restores hidden predictions without rerunning the model |
| `test_sample.py` | 7 | Try sample uses the real app path, and missing or slow sample data can be recovered from |
| `test_startup.py` | 6 | Startup races and held configuration responses, using real local HTTP |
| `test_loading.py` | 5 | Startup feedback for configuration, download, unknown progress and readiness |
| `test_inference.py` | 3 | Real model on three photos: visible labels and scores, and box position compared with earlier recorded output |
| `test_harness_cleanup.py` | 3 | The test harness still closes the browser when timeout setup fails or when it cannot save failure evidence |
| `test_server.py` | 1 | The normal server cannot serve controlled test predictions |

Each [acceptance example](docs/DESIGN.md#acceptance-examples) in DESIGN.md names the tests that check it, and the [ranked risk table](docs/DESIGN.md#risks-and-test-mix) gives the covering test for each risk, or the reason it is not tested. [VERIFICATION.md](docs/VERIFICATION.md) holds the evidence for each behaviour.

### Do the tests catch real faults?

[`tools/check_review_sensitivity.py`](tools/check_review_sensitivity.py) copies the app into throwaway folders and plants one deliberate fault in each copy. It never changes the checkout itself. A **30-case clean control** passes first. Each of the **16 faults** then makes its intended tests fail, giving **28 intended failures** in total. Record: [v1-0-sensitivity.json](docs/evidence/v1-0-sensitivity.json).

Five of the faults each break one of the core rules the question depends on:

| Core rule | Deliberate change | Test that failed |
| --- | --- | --- |
| A file of exactly 10 MiB is accepted | `file.size > MAX_BYTES` becomes `>=` | `tests/test_ui.py::test_file_size_boundary[10485760-complete]` (the 10 MiB + 1 byte case still passes) |
| The filter keeps a score equal to the minimum | `score >= minimum` becomes `>` | 3 of 7 in `tests/test_filter.py`: `test_exact_minimum_filters_underlying_scores_and_restores_without_inference`, `test_filter_preserves_result_identity_color_and_surviving_selection`, `test_hidden_predictions_can_be_restored_and_differ_from_no_model_predictions` |
| An old image's result cannot repaint a newer image or a cleared workspace | The guard `data.id === revision && currentImage?.id === revision` becomes `true` | `tests/test_ui.py::test_replacing_a_processing_image_discards_the_old_result[slow-car.png]`, `tests/test_ui.py::test_clearing_a_processing_image_prevents_late_repaint` |
| An outdated export cannot download | The check after PNG encoding is removed | All 3 cases of `tests/test_export.py::test_changed_result_cancels_a_png_still_being_encoded` |
| A late sample cannot replace a newer image or undo Clear | All three defences are removed: the fetch abort, the check after the download, and the reserved revision | Both cases of `tests/test_sample.py::test_late_sample_response_cannot_override_a_later_user_action` |

One more fault is recorded as an equivalent fault. Removing only the check after the sample download changes nothing observable, because the fetch abort and the reserved revision still stop the late sample, so its 2 cases are expected to pass and do. That is why the late-sample fault removes all three defences.

The other 11 faults account for 17 of the intended failures:

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

The two score faults also change the page's own data attributes, so among the real-model checks only the comparison with the recorded output catches them. This shows that the selected checks detect the selected faults. It is not a mutation score.

### One defect, end to end: the model could not load on a slow connection

| Part | Detail |
| --- | --- |
| What failed | With only the 43.1 MB model download throttled to 2.5 Mbps on loopback, the app showed "The detection model took too long to load" after 121 s, with 37.4 of 43.1 MB received (86%). |
| How it was detected | An independent review ran a paced loopback probe at 2.5 Mbps against the package ([slow-transfer-2-5-mbps.json](docs/evidence/slow-transfer-2-5-mbps.json)). |
| Impact | Try again restarted the download from zero, so at this speed retrying could never succeed and the detector could not be used. |
| Cause in the system | Model loading had one fixed 120 s deadline, counted from worker start. It ignored download progress, so a slow but steady download was treated the same as a dead one. |
| Test that prevents it | `tests/test_recovery.py::test_slow_steady_model_transfer_is_not_timed_out` and `tests/test_recovery.py::test_stalled_model_transfer_times_out_after_its_last_progress` check that the download fails only after 45 s with no loading event, and that each event restarts that window. `tests/test_recovery.py::test_model_initialization_has_its_own_deadline` and `tests/test_recovery.py::test_completed_transfer_starts_initialization_before_the_done_event` check that start-up after the last byte has its own fixed 120 s deadline, which later events cannot extend. Three of the planted faults above guard this behaviour. |

The error messages say which stage stalled. Under the same 2.5 Mbps probe, the package received every byte and reached ready at 140.6 s. Each condition was run once, on loopback. That is not a measurement of Internet speed. Every confirmed defect is described in the same five parts in [Defects and corrections](docs/DEFECTS.md).

![Runtime flow: page, worker, model and test harness](docs/diagrams/object-lens-runtime-flow.png)

## First setup

Start in the folder where you cloned the repository. The target environment is Python 3.12 with Chrome. The first setup needs internet access to download the Python packages, the Chrome driver, the browser runtime, and the model files. The public sample photos are already in `dist/samples`; `tools/download_samples.py` checks them against their pinned upstream SHA-256 hashes, fetches only a photo that is missing, and stops with an error if any photo does not match. No paid API is needed.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe tools/prepare_assets.py
.\.venv\Scripts\python.exe tools/download_samples.py
.\.venv\Scripts\python.exe tools/browser_check.py
```

`requirements.txt` lists the direct dependencies, and `requirements-lock.txt` records the full tested environment. The model and runtime files go into `dist/assets`, which is kept out of Git. Their pinned sources and SHA-256 hashes are in `asset-lock.json`. To check the prepared files without downloading anything:

```powershell
.\.venv\Scripts\python.exe tools/prepare_assets.py --verify-only
.\.venv\Scripts\python.exe tools/download_samples.py --verify
```

If the app reports a missing file, run the asset preparation step again, then click **Try again** in the app.

## Run locally

```powershell
.\.venv\Scripts\python.exe serve.py
```

Open `http://127.0.0.1:8765` in Chrome. The server is reachable only from this computer, and Ctrl+C stops it. If port 8765 is already in use, run `serve.py --port 8766` and open port 8766 instead.

To try it: click **Try sample**, select the cup, move **Minimum model score** from 0.50 to 0.80, and click **Save result**. Then lower the filter again to bring the hidden predictions back. Predictions can include mistakes or duplicates, and a score does not guarantee the prediction is right.

## Run the tests

The tests start and stop their own local servers and use headless Chrome, so `serve.py` does not need to be running.

```powershell
# Full suite
.\.venv\Scripts\python.exe -m pytest

# Controlled app, server, package and harness checks; not evidence about the model
.\.venv\Scripts\python.exe -m pytest -m "not inference"

# Real model: three photo regression checks plus the static-package workflow
.\.venv\Scripts\python.exe -m pytest -m inference
```

The static-package test serves the prepared site under the subpath `/object-lens/` from an ordinary local static server. The worker resolves the model and runtime files relative to its own location, so the package works at a site root or under a subpath such as a GitHub Pages project site. The showcase is published by the manually started [pages.yml](.github/workflows/pages.yml) workflow, which builds the same allowlisted package with `tools/build_public_demo.py`; the tests do not check the hosted copy.

![Testing workflow](docs/diagrams/testing-workflow.png)

## More screenshots

[Empty state](docs/screenshots/app/empty.png), [filter hides every prediction](docs/screenshots/app/filtered-empty.png), [exported PNG](docs/screenshots/app/export.png), [input error](docs/screenshots/app/error.png), [timeout after Clear](docs/screenshots/app/timeout-cleared.png), and the layout at widths of [320](docs/screenshots/app/width-320.png), [390](docs/screenshots/app/width-390.png), [768](docs/screenshots/app/width-768.png) and [1440](docs/screenshots/app/width-1440.png) px. The input error comes from the real app with a deliberately unsupported file. The two timeout screens come from the controlled test worker.

## Read next

- [Design: question, acceptance examples, risks and decisions](docs/DESIGN.md)
- [Verification and release assessment](docs/VERIFICATION.md)
- [Defects and corrections](docs/DEFECTS.md)
- [Evidence index](docs/evidence/README.md)
- Diagrams of the [runtime architecture](docs/diagrams/runtime-architecture.png) and the [image sequence](docs/diagrams/image-sequence.png)
- [Security scope and reporting](SECURITY.md)
- [Image sources and the objects expected in each photo](docs/IMAGE_SOURCES.md)

## Which folders matter

| Folder | Purpose |
| --- | --- |
| `dist` | The app and its prepared local assets |
| `tests` | The pytest and Selenium suite, plus the controlled worker fixture |
| `tools` | Helpers for setup, packaging, collecting evidence and checking fault sensitivity |
| `docs` | Design, verification evidence, screenshots and diagrams |
| `baseline` | The original upstream example, kept for attribution and comparison |
| `.github/workflows` | CI for the controlled suite and dependency audit, and the manual showcase deployment |
| `.venv`, `.local`, `artifacts` | Generated locally and ignored by Git: the Python environment, the driver cache and local verification copies, and raw test outputs; not part of the app |

## Credits and licences

- Adapted from Hugging Face's Transformers.js vanilla JavaScript object-detection tutorial (Apache-2.0). The original is kept in [`baseline/upstream`](baseline/upstream/README.md), and its revision and checksums are in `baseline/source.json`.
- Model: [facebook/detr-resnet-50](https://huggingface.co/facebook/detr-resnet-50) (the model card states Apache-2.0), used through the browser-compatible conversion [Xenova/detr-resnet-50](https://huggingface.co/Xenova/detr-resnet-50) at the revision pinned in `asset-lock.json`.
- Runtime: [Transformers.js](https://github.com/huggingface/transformers.js) 2.17.2 (Apache-2.0), [ONNX Runtime Web](https://github.com/microsoft/onnxruntime) 1.14.0 (MIT) and [@huggingface/jinja](https://www.npmjs.com/package/@huggingface/jinja) 0.2.2 (MIT). The ONNX Runtime Web bundle embeds long 4.0.0 and flatbuffers 1.12.0 (Apache-2.0), onnx-proto 4.0.4 (MIT), protobufjs 6.11.3 (BSD-3-Clause) and guid-typescript 1.0.9 (ISC, as declared in its package metadata); their licences are in `dist/licenses` and listed on the app's credits page.
- Sample photos: unchanged copies from scikit-image v0.25.2. Each is public domain or CC0, and the creators are credited in [IMAGE_SOURCES.md](docs/IMAGE_SOURCES.md).

[NOTICE.md](NOTICE.md) has the full attribution. Object Lens is copyright 2026 Le Jie Tan and licensed under the [Apache License 2.0](LICENSE).
