# Object Lens

## Purpose

Object Lens is a small local browser application for trying object detection on a photo. Its intended user is a developer, QA engineer or learner exploring a pretrained detector. This is a practical way to explore Python, pytest, Selenium and an AI-enabled web interface. It is not a semiconductor defect detector or an established commercial product.

The approved application scope is one image at a time, one fixed model and Chrome on Windows. The interface follows the approved design concept: a light background, large photograph, compact results list and essential controls. Public static hosting was approved on 3 November 2026, with repository privacy retained; its preparation and actual deployment status are recorded in [Public demo preparation](PUBLIC_DEMO.md). No accounts, image history, hosted inference service, camera, video, batch processing, training, model picker or GPU tuning are included.

## Two ways to use this project

The application and its automated tests have different jobs. You can use the application without running pytest.

| Command, from the project directory | What it does | Why you run it |
| --- | --- | --- |
| `.\.venv\Scripts\python.exe serve.py` | Starts a local server so you can open Object Lens in Chrome, choose photos and inspect predictions | To use or demonstrate the application yourself |
| `.\.venv\Scripts\python.exe -m pytest` | Runs the existing tests in this repository and reports pass/fail results | To check that the implemented behavior still matches its requirements |

The first command keeps serving files until you stop it with Ctrl+C. The second command finishes after the tests and their cleanup. Tests start their own temporary servers and headless browsers, so a manually started `serve.py` process is not required for testing. A second PowerShell window can run tests while your normal app window remains open.

![The application path and the separate automated-testing path](diagrams/object-lens-runtime-flow.png)

[Editable diagram](diagrams/object-lens-runtime-flow.html) · [SVG version](diagrams/object-lens-runtime-flow.svg)

## What the pytest command actually does

In `.\.venv\Scripts\python.exe -m pytest`, the executable selects this project's Python environment. Python's `-m` option launches the installed pytest module.

1. pytest finds the `test_*.py` files in `tests`, as configured by `pytest.ini`.
2. Test fixtures prepare the local server, test inputs and an isolated headless Chrome session.
3. pytest runs each Python test function. The function describes actions and checks, called assertions.
4. Selenium follows the test's instructions to select files, click controls and read the page.
5. The assertions compare the observed behavior with the expected rule. pytest reports a pass or a failure.
6. Fixtures close their browsers and servers. A failing browser check also attempts to preserve a screenshot, page HTML and console output for investigation.

The test author supplies the expected behavior. pytest does not invent tests or independently decide what the application ought to do. Selenium operates the test browser; the pretrained detector is the component that recognizes objects in the image.

For example, the requirement says an unsupported file should be rejected with a useful message. If the app displays that message, the negative test passes. An error message in the application can therefore be the correct result; the test fails when the observed behavior disagrees with its expectation.

| Scenario | Expected application behavior | Meaning of a passing test |
| --- | --- | --- |
| A valid image exactly at the 10 MiB limit | Accept and process it | The inclusive size boundary is implemented correctly |
| An image one byte above the limit | Reject it with an actionable message | Oversized input is handled correctly |
| Replace a photo while its analysis is running | Only the current photo's results may appear | An old response cannot repaint the new image |

In `.\.venv\Scripts\python.exe -m pytest -m inference`, the two `-m` options belong to different tools. The first launches pytest through Python; pytest interprets the second as a selection of tests marked `inference`. These run the actual model. The controlled UI tests instead supply deliberate predictions, delays or failures to test application behavior reproducibly.

The longer worked example and a small optional test edit are in [the learning guide](LEARNING.md). The result counts and evidence limits are in [the verification record](VERIFICATION.md). Passing the application checks does not establish general object-recognition accuracy.

## Components

| Component | Responsibility |
| --- | --- |
| HTML and CSS | Single-page controls, responsive layout and configured status/error announcements |
| JavaScript | File validation, image state, result display and selection |
| Canvas PNG export | Draws the current filtered annotations over the decoded photo at its original dimensions |
| Browser Web Worker | Runs the pretrained model without blocking the interface |
| Transformers.js 2.17.2 | Object-detection inference with a quantized DETR model |
| ONNX Runtime Web 1.14.0 | CPU/WASM execution underneath Transformers.js |
| Python standard HTTP server | Serves local application/model files on 127.0.0.1 |
| Static deployment package | Supplies the same browser app, normal-mode configuration, pinned assets and public credits without requiring the custom Python routes |
| Python test code | Defines test actions and assertions about expected behavior |
| pytest | Discovers and runs tests, manages fixtures and reports their outcomes |
| Selenium | Controls the test browser and reads the page for assertions |

The JavaScript library is kept on a pinned version compatible with the original example's API. A version migration is not part of this project. Exact model revision and asset checksums are in `asset-lock.json`.

## Data flow

1. The user selects a JPEG or PNG, or uses Try sample to load the existing coffee photo. The app validates format, size and dimensions before inference.
2. The image is displayed, with any previous detections removed.
3. A background worker runs the model and returns labels, model scores and normalized box coordinates.
4. The app accepts results only for the currently selected image. It validates every prediction before rendering matching boxes and list entries. Invalid model responses produce a recoverable error rather than a partial, misleading result.
5. Selecting a list entry highlights the corresponding box. Clear removes the current image and invalidates any outstanding result.

After successful inference, the app keeps validated predictions for that image. The minimum-score control redraws this cached set without invoking the model again. Each prediction keeps its identity and color when others are hidden. If the selected prediction is filtered out, the first visible prediction becomes selected. A new image or Clear resets the minimum to 0.50 and invalidates cached results.

Try sample reserves a new image revision before requesting the local photo. Clear or a newer selection invalidates that revision and cancels its pending fetch, so a late sample cannot overwrite the current workspace. A 15-second fetch deadline produces a recoverable sample-loading message. Sample loading uses the same image validation and inference path as file selection; there are no prerecorded sample answers in the normal application.

Save result captures the current photo, minimum score and visible prediction set. A separate canvas renderer draws that photo with boxes, labels and model scores at the browser-decoded, orientation-corrected dimensions. It does not rerun inference or include application controls, selection emphasis or a summary strip. Before initiating the download, an export revision guard checks that neither the photo nor the filter changed while PNG encoding was pending. Clear, replacement and filter changes invalidate unfinished exports.

Save is disabled when there are no visible predictions or the current export is being prepared. Encoding has a 15-second deadline. A scoped export message reports failure without discarding a valid detection result, and retry remains available. A successful message says the download started; it does not claim the operating system saved the file. Very small source images necessarily have limited annotation readability, and browser canvas limits can reject extreme image dimensions; failures are reported without silently changing resolution.

Clearing or replacing an image does not promise interruption of CPU work already underway. It prevents that old work from changing the visible result. There is no hosted inference API.

A nonresponding worker has a bounded recovery path. Model transfer fails only when no loading event arrives for 45 seconds, so a slow but steady connection can finish the 43 MB download; each progress event restarts that stall window. After the model file finishes, runtime initialization has its own fixed 120-second deadline that later settings-file events do not extend. Inference times out after 90 seconds. The worker is terminated. A stalled transfer asks the user to check the connection, an initialization timeout says the model took too long to start, and an inference timeout describes the image analysis. Clear removes image content and replaces that explanation with a generic detector-unavailable message offering restart. It does not claim that the stopped detector is ready or reclassify the prior failure as startup failure. Retry or a new valid image can recreate the worker. Normal controlled loading retains the production deadlines; dedicated timeout cases accelerate only the 45-second stall and 120-second initialization timers in their isolated browser. Controlled inference uses four seconds. These tests simulate component failure and do not establish an observed real-model outage.

Before a worker is selected, configuration loading has a separate 15-second deadline covering both response headers and JSON body reading. A boolean testMode is required. Failure exposes Retry, which fetches configuration again while preserving a valid selected image. A new valid selection can also retry failed configuration. The worker cannot start with an unvalidated mode.

File preparation retains its own image revision until reading and decoding finish. Successful background startup cannot clear an existing input error or announce an idle workspace during that preparation. Explicit retry restores the current preparation status where needed.

Startup feedback is independent of the main application status. Worker events identify model transfer and runtime initialization; received bytes are displayed only for a valid finite total. Finishing the transfer does not mark the model ready. An actual ready response hides the notice, and a failure or retry retires or resets it. Progress must not overwrite an input error, sample-loading state or a newer worker's state.

The list is titled "Detections" and the completion message counts "predictions". A real sample produced duplicate spoon detections; the count therefore must not be interpreted as a verified count of distinct physical objects.

## Acceptance criteria

| ID | Requirement |
| --- | --- |
| AC1 | Accept decodable JPEG/PNG files up to 10 MiB and 16,000,000 pixels; reject unsupported, unreadable or oversized files with an actionable message. |
| AC2 | Display processing state and results for the current image, with one matching list entry for every displayed box. |
| AC3 | A result selection highlights its matching box. Clear removes image and results. |
| AC4 | Results from an earlier image cannot repaint the page after replacement or clear. |
| AC5 | An empty prediction set is distinct from an inference failure. A valid image can be processed after an input or inference error. |
| AC6 | Keyboard controls have visible focus, status/error elements carry the intended announcement configuration and meaningful content, and the layout remains usable at a narrow viewport. Actual screen-reader speech remains unverified. |
| AC7 | A keyboard-accessible minimum-score filter from 0.50 to 1.00 includes predictions whose underlying score is at least the selected minimum. Boxes, list and visible/total counts agree. Lowering the minimum restores hidden predictions without rerunning inference; filter-empty and model-empty states have different explanations. |
| AC8 | Try sample loads the existing coffee photo through the real application path. Missing, unreadable or unresponsive sample data is recoverable. A delayed response cannot undo Clear or replace a newer selected image. |
| AC9 | Save result initiates a PNG download containing only the current filtered predictions at the decoded photo's original dimensions. It is unavailable without visible predictions. Encoding failure or timeout preserves the usable result, and a pending export cannot download after Clear, image replacement or filter change. |
| AC10 | Startup feedback distinguishes configuration, model transfer and readiness, handles unknown progress, preserves input errors and active preparation, and ignores retired-worker updates. Configuration stalls/invalid responses are bounded and recover through a new request. A stalled model transfer and a hung initialization are bounded separately, while a slow but steady transfer is not timed out. |
| AC11 | The public package contains only the approved app/configuration, verified model/runtime files, public sample and licence notices. It uses testMode false, excludes private/test materials and runs through ordinary static file serving. |

The model's fixed inference threshold is 0.5. A separate display filter starts at 0.50, moves in steps of 0.01 and cannot recover lower-score predictions discarded by inference. Comparisons use the underlying model score, while visible scores are rounded to two decimal places. The displayed value is a model score, not a measured accuracy percentage. Supported classes come from the model; unrecognized objects do not imply an application defect.

## Verification approach

The controlled browser tests exercise normal results, empty predictions, delays and errors through a test worker. They are deterministic tests of the application, not model-accuracy evidence. The test worker is served only when the Python server is explicitly started in test mode; normal use loads the real worker.

Real-inference checks use publicly sourced photos with independent notes about their visible objects. They assert visible names and formatted scores. For astronaut/person, coffee/cup and chelsea/cat, selected coordinates are compared with earlier outputs of the same pinned model and rendered boxes are measured against the displayed image. Those reference coordinates are not independent ground-truth annotations. The checks establish a limited output/geometry regression and actual inference path, not localization accuracy or general recognition accuracy. The source example is retained in `baseline/upstream`, with its origin recorded in `baseline/source.json`. Any runnable local baseline adaptation must record its asset-path/runtime changes.

Disposable-copy fault experiments deliberately remove visible result text or displace boxes to verify that the strengthened assertions fail. Controlled malformed-response cases cover invalid scores, coordinates and impossible boxes; valid out-of-range coordinates are clamped when they retain positive area. Announcement checks inspect DOM roles and live settings, not actual screen-reader behavior.

Failures are investigated using reproduction steps, assertions, screenshots and browser logs. Initial loading and warm inference timing are recorded separately. No load, scalability, GPU or physical-hardware qualification is claimed.

## Delivery boundary

The design and evidence stay versioned with the implementation. The user should be able to launch the app, run the suite, explain a representative test and adjust a small existing test after the final walkthrough. Optional learning exercises explain existing behavior without expanding the application feature scope. Public-demo preparation was approved on 3 November; verification of an actual hosted URL is an additional release step after the owner uploads the prepared package.

## Sharing boundary

The GitHub repository, tests and private design documents remain private. The owner has approved a public app and understands that visitors receive and can inspect its frontend files and model/runtime assets. A LinkedIn learning update can use actual screenshots, a short demonstration and, once verified, the public app link. The README retains real screenshots with relative image links.

A prospective showcase should describe this as an AI-assisted learning project around a pretrained detector and Python browser automation. Credit the upstream example and distinguish application tests, actual inference, deliberately simulated failures and observed model mistakes. Do not claim that the model was trained here or that a local address such as `127.0.0.1` is a public demo link.

The public ZIP is created from an explicit allowlist, not the entire checkout. Its normal-mode configuration and dependency hashes are verified before packaging. The public URL and hosted execution evidence remain unestablished until the owner uploads the reviewed package and the deployed version is checked.
