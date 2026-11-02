# Verification and release assessment

Status: ready for the agreed local learning/evaluation workflow, based on the checks below on 2 November 2026. No blocking defect remains in that scope. This is not a production-recognition, hardware-validation or general-accuracy claim.

## Extension checkpoint

The minimum-score filter passed 29 controlled application/server checks in 199.37 seconds, including six new filter tests; three real-inference cases were deselected at that checkpoint. Evidence: `docs/evidence/score-filter-suite.xml` and `score-filter-record.json`.

Try sample passed seven controlled loading/recovery checks and three actual-model cases in 137.27 seconds. The coffee case used Try sample; astronaut and cat used file selection. The sample fetch deadline was exercised at its actual 15-second value. Evidence: `docs/evidence/sample-image-suite.xml` and `sample-image-record.json`.

The combined extension will receive its own final verification after PNG export is integrated. The results below describe the preceding base version.

## Base-version results

| Check | Observed result | Evidence |
| --- | --- | --- |
| Final complete suite | 26 passed, 0 failures/errors/skips; 215.13 seconds | `docs/evidence/final-full-suite.xml` |
| Independent fresh setup | Fresh source, virtual environment, locked packages, model/runtime files and driver cache on the same laptop; 26 passed in 205.13 seconds | `docs/evidence/fresh-setup-summary.json` and `fresh-setup-suite.xml` |
| One-hour repeated use | 320 completed cycles, 320 clears and 32 rapid replacements; 3615.927 seconds; no observed failure or browser console entry | `docs/evidence/stability-summary.json` |
| Prediction repeatability within that session | One recorded label sequence per repeated photo; five fixed photos, not 320 distinct inputs | Complete local cycle record in `artifacts/stability/result.json` |
| Real output comparison | Labels and normalized boxes matched the local baseline on astronaut, coffee and chelsea | `docs/evidence/model-observations.json` |
| Rendered UI review | 320, 390, 768 and 1440 CSS-pixel widths; no horizontal overflow, readable edge labels, visible keyboard focus and correct selected-box stacking | `docs/evidence/rendered-review.json` |
| Test sensitivity | Two isolated deliberate source faults were caught by their intended tests | `docs/evidence/test-sensitivity.json` |
| Ordinary launch walkthrough | README command served the real app on port 8765; coffee/cup, replacement with cat, selection and clear succeeded | `artifacts/launch-check/result.json` and actual screenshots |

The final suite contains 23 controlled application/server checks and three real-inference checks. Controlled checks do not establish AI accuracy. The initial fresh-setup run preceded the later test-diagnostic and PNG-fixture refinements; the final suite includes those refinements. No application behavior changed between those runs.

After the complete suite and long-session run, the only application change was a slightly darker empty-state text colour. Its computed contrast and actual rendering were checked separately; no logic, model, layout or interaction changed.

Environment: Python 3.12.10, pytest 9.0.3, Selenium 4.40.0, Chrome 156.0.8078.74 and ChromeDriver 156.0.8078.80. Runtime/model versions and file checksums are in `asset-lock.json`. This was one Windows laptop, not a second-machine or cross-browser qualification.

## Acceptance coverage

| Criterion | Main evidence |
| --- | --- |
| AC1: input limits and rejection | Exact byte-size boundary, pixel boundary, JPEG, EXIF orientation, unsupported content and truncated PNG checks |
| AC2: current-image results | Row/box matching and geometry checks; three real-model selected-label checks |
| AC3: selection and clearing | Selected-box tests, keyboard Clear and rendered selection review |
| AC4: stale-result protection | In-flight clear, quick and slow replacement checks; an isolated missing-guard fault is detected |
| AC5: error recovery | Processing error, worker-start failure and nonresponding-worker retry checks |
| AC6: usable interface | Keyboard focus, viewport checks, overlay-label contrast and actual rendered state inspection |

## Evidence boundaries

Controlled application tests use labelled simulated predictions, delays or failures. Real inference uses the prepared pretrained model and public photographs. The generated approved design concept is not an execution screenshot. Tests of selected-label presence do not measure general recognition accuracy.

## Earlier verification stages

- Initial controlled suite: 18 passed; three real-inference cases were deselected.
- Real-model checks: person in astronaut, cup in coffee and cat in chelsea all passed.
- A corrected worker-startup recovery test passed after its first attempt failed to create the intended network fault.
- Six focused recovery/format tests passed after the watchdog and test improvements.
- A separate real-model evaluation ran on five public photos with external hostname resolution disabled in the isolated browser. Recorded HTTP requests stayed on numeric loopback.
- The runtime-normalized upstream comparison matched Object Lens's labels and box coordinates on astronaut, coffee and chelsea. This is not a test of the stock upstream runtime.

## Findings

### F1: Missing recovery for a nonresponding worker

Code review found that the active request could remain occupied forever if the worker never returned a result or error. Clearing the photo did not release that request, so a later image could remain pending. No real model hang was observed.

The fix adds bounded loading/inference deadlines, terminates the failed worker and allows retry with the current image. A controlled silent-worker test now verifies clear, new-image selection, timeout and successful retry. Production deadlines are 120 seconds for loading and 90 seconds for inference; controlled tests use four seconds.

### F2: A startup-failure test did not actually inject its intended fault

The first request-blocking attempt left the page Ready. Its preserved page/console and server log show the worker returned HTTP 200. This was a test-fixture problem, not an application defect. A test-only server now returns HTTP 503 once and then permits a successful retry.

### F3: Prediction counts are not verified object counts

The real coffee photo produced two overlapping spoon predictions. The results heading was changed to "Detections" and the status counts "predictions". No model predictions were removed to make the result look more accurate.

The camera photo produced a large person box together with additional person and bicycle predictions around the camera/tripod. These illustrate limitations of the general-purpose pretrained detector. The rocket photo produced no predictions; rocket is outside the supported category list. No complete dataset accuracy metric is claimed.

### F4: Overlay label contrast

White text on the original teal label background measured 4.401:1. Darkening that colour to `#008078` raised the contrast to 4.818:1. Other label colours meet 4.5:1 for their white text.

The final review also found empty-state secondary text at 4.478:1 against the image-pane background. A scoped change to `#606D80` raised it to 4.685:1. Computed browser colours and a refreshed actual screenshot verified that adjustment. This was a targeted contrast/render check, not full accessibility certification.

### F5: The first isolated-network evidence run blocked loopback too

The first browser host-resolution rule caused `ERR_NAME_NOT_RESOLVED` before the application was reached. Explicitly excluding `127.0.0.1`, as well as localhost, corrected the evidence harness. The subsequent local-model run completed. This was an environment/test setup issue.

### F6: Stable manifest output on Windows

Fresh setup preserved all asset values and hashes but rewrote the lock manifest with CRLF line endings. The setup helpers now write explicit LF. Redownloading one 455-byte derived configuration file verified that the repaired manifest matches the archived source bytes. This was a reproducibility detail, not an application or model failure.

### F7: Clearer diagnostics and stronger fixtures

A deliberate off-by-one fault was detected, but the first failure output was a generic Selenium timeout. The wait helper now reports expected state, observed state, visible filename and UI error. Normal cases passed, and a separate injected fault verified the improved message without changing the delivered app.

The size-boundary image generator was also strengthened: it now places a valid PNG `tEXt` metadata chunk before IEND instead of relying on browser-tolerated trailing bytes. An independent parser checked chunk lengths, CRCs, decoded scanline length and IEND placement. Both exact boundary sizes passed their expected browser checks. These are test-quality improvements, not production defects.

## Real model evaluation

The five-photo observations and timings are in `artifacts/evaluation/observations.json`. They are a small convenience sample. Timing is measured from image submission until the visible UI reports completion, including decoding, inference, rendering and polling; workstation load was not controlled.

| Image | Observed labels | Interpretation |
| --- | --- | --- |
| astronaut.png | person | Reviewed expected label present |
| coffee.png | spoon, dining table, cup, spoon | Cup present; duplicate spoon predictions visible |
| chelsea.png | cat | Reviewed expected label present |
| camera.png | bicycle, handbag, person, person, person, bicycle | Expected person present; visual review shows additional mistaken/duplicate predictions |
| rocket.jpg | none | Observed empty prediction set on an out-of-vocabulary example |

Initial model readiness was observed at 2.144 seconds for Object Lens. Image-to-result observations ranged from 8.325 to 13.612 seconds in that run. These are environment-specific observations, not a performance promise or proof of acceleration.

## Release decision and remaining limits

Release for local exploration of the agreed stack and workflow. The specified application behavior passed its checks, real inference ran, fresh setup was reproduced and a bounded long session completed. Tests remain inspectable and can be changed without creating another framework.

The model can miss or duplicate objects and produce incorrect labels. Partial label expectations came from upstream descriptions and AI-assisted visual inspection; this project does not contain an exhaustive human-annotated dataset. One laptop and one browser were checked. The long session is not a load test or memory-leak certification. Recorded timing is not a performance guarantee. No hosted CI, public deployment, GPU/NPU execution or semiconductor inspection was performed.

Raw failure captures remain local under `artifacts`. Selected repository evidence removes the machine hostname from JUnit XML and records that redaction. A baseline-only missing favicon returned HTTP 404; it did not affect inference or the delivered UI.

Optional cleanup of generated verification copies was not performed because this machine blocked the unsigned PowerShell cleanup script. No execution policy or permissions were changed. Those ignored copies remain under `.local`; the maintained application is the root `dist` directory. The documented launch and test commands use Python directly and were verified successfully.
