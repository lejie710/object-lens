# Object Lens

## Purpose

Object Lens is a small local browser application for trying object detection on a photo. Its intended user is a developer, QA engineer or learner exploring a pretrained detector. This is a practical way to explore Python, pytest, Selenium and an AI-enabled web interface. It is not a semiconductor defect detector or an established commercial product.

The approved scope is one page, one image at a time, one fixed model and Chrome on Windows. The interface follows the approved design concept: a light background, large photograph, compact results list and essential controls. No accounts, history, cloud hosting, camera, video, batch processing, training, model picker or GPU tuning are included.

## Components

| Component | Responsibility |
| --- | --- |
| HTML and CSS | Accessible single-page interface and responsive layout |
| JavaScript | File validation, image state, result display and selection |
| Browser Web Worker | Runs the pretrained model without blocking the interface |
| Transformers.js 2.17.2 | Object-detection inference with a quantized DETR model |
| ONNX Runtime Web 1.14.0 | CPU/WASM execution underneath Transformers.js |
| Python standard HTTP server | Serves local application/model files on 127.0.0.1 |
| pytest and Selenium | Runs assertions against the application in headless Chrome |

The JavaScript library is kept on a pinned version compatible with the original example's API. A version migration is not part of this project. Exact model revision and asset checksums are in `asset-lock.json`.

## Data flow

1. The user selects a JPEG or PNG. The app validates format, size and dimensions before inference.
2. The image is displayed, with any previous detections removed.
3. A background worker runs the model and returns labels, model scores and normalized box coordinates.
4. The app accepts results only for the currently selected image, then renders boxes and matching list entries.
5. Selecting a list entry highlights the corresponding box. Clear removes the current image and invalidates any outstanding result.

Clearing or replacing an image does not promise interruption of CPU work already underway. It prevents that old work from changing the visible result. There is no hosted inference API.

## Acceptance criteria

| ID | Requirement |
| --- | --- |
| AC1 | Accept decodable JPEG/PNG files up to 10 MiB and 16,000,000 pixels; reject unsupported, unreadable or oversized files with an actionable message. |
| AC2 | Display processing state and results for the current image, with one matching list entry for every displayed box. |
| AC3 | A result selection highlights its matching box. Clear removes image and results. |
| AC4 | Results from an earlier image cannot repaint the page after replacement or clear. |
| AC5 | An empty prediction set is distinct from an inference failure. A valid image can be processed after an input or inference error. |
| AC6 | Keyboard controls have visible focus, updates are announced accessibly and the layout remains usable at a narrow viewport. |

The fixed confidence threshold is 0.5. The displayed value is a model score, not a measured accuracy percentage. Supported classes come from the model; unrecognized objects do not imply an application defect.

## Verification approach

The controlled browser tests exercise normal results, empty predictions, delays and errors through a test worker. They are deterministic tests of the application, not model-accuracy evidence. The test worker is served only when the Python server is explicitly started in test mode; normal use loads the real worker.

Real-inference checks use publicly sourced photos with independent notes about their visible objects. These confirm an actual inference path and document observed limitations on a small sample. They do not establish general accuracy. The source example is retained in `baseline/upstream`, with its origin recorded in `baseline/source.json`. Any runnable local baseline adaptation must record its asset-path/runtime changes.

Failures are investigated using reproduction steps, assertions, screenshots and browser logs. Initial loading and warm inference timing are recorded separately. No load, scalability, GPU or physical-hardware qualification is claimed.

## Delivery boundary

The design and evidence will be updated to match the implementation. The user should be able to launch the app, run the suite, explain a representative test and adjust a small existing test after the final walkthrough. Development does not include teaching exercises or optional features. Publication remains a separate decision.
