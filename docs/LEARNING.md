# A short guide to Object Lens

## 1. Start with the application

Launch the local server using the README command, open the page in Chrome and click Try sample. The detector proposes labels and boxes. Selecting the cup in the list highlights its box. Raise Minimum model score to 0.80, then use Save result to download the visible predictions as an annotated PNG. Lower the minimum to restore hidden predictions, replace the image with `chelsea.png`, then use Clear.

These are actual model predictions. The coffee sample can produce two spoon boxes for the same visible spoon. The app should present those results faithfully and make them understandable; a passing UI test does not prove that the model is always right.

## 2. What each part does, and why

| Part | What it does | Why it is present |
| --- | --- | --- |
| HTML and CSS | Define the page, controls, spacing and colours | Make the image and results understandable |
| `dist/app.js` | Validates files, tracks the current image and renders results | Keeps what is on screen consistent with what the user selected |
| `dist/worker.js` | Runs the pretrained detector in a browser worker | Performs inference without blocking the main interface |
| `dist/png-export.js` | Draws the current filtered annotations into a PNG | Produces a reusable image without another model run |
| `serve.py` | Serves local files to Chrome | Lets the browser load the app, model and runtime from this computer |
| Python tests | Describe actions and expected outcomes | Turn a requirement into an executable check |
| Selenium | Operates Chrome and reads page elements | Repeats user workflows automatically |
| pytest | Starts fixtures, runs tests and reports assertions | Gives each check a clear pass or fail result |

Python is the main language to learn for this project's automation. The actual application is JavaScript. The Python server does not perform model inference.

Headless Chrome still renders the page and can save screenshots, but it does not open a visible browser window. Selenium controls that isolated browser session, not your mouse or desktop. Your normal browser profile is not used for the tests.

The pretrained model is the AI inside the app. AI coding agents helped build this project; that is separate from the model inside the app, and neither supplies a trustworthy expected answer for a test.

The filter compares full model scores, even though the interface rounds them to two decimal places. A score of 0.7999 can display as 0.80 and still disappear at a minimum of 0.80. In the real coffee result, the cup score is about 0.9979: it displays as 1.00 but is below a minimum of 1.00. Neither displayed value is a measured accuracy percentage.

## 3. Follow one real test

The requirement in AC1 says: accept a valid image of **at most 10 MiB**, and reject an image larger than that limit. One MiB is 1,048,576 bytes.

Open `tests/test_ui.py` and find `test_file_size_boundary`:

```python
@pytest.mark.parametrize("size,expected_state", [
    (10 * 1024 * 1024, "complete"),
    (10 * 1024 * 1024 + 1, "error"),
])
def test_file_size_boundary(app, make_image, size, expected_state):
    upload(app, make_image("size-boundary.png", total_bytes=size))
    wait_state(app, expected_state, timeout=20)
```

The actual test continues with assertions about the displayed error or results. Here is the important reasoning:

1. **Parameterization** runs one test with two different inputs. This avoids copying the test function.
2. **Exactly 10 MiB** must be accepted because the requirement says "at most".
3. **One byte above 10 MiB** must be rejected. This catches an off-by-one mistake at the boundary.
4. `make_image` creates a structurally valid synthetic PNG with the requested file size, using a metadata chunk for padding.
5. Selenium selects the file, and the test waits for an observable outcome. It does not assume that processing finishes after an arbitrary sleep.
6. Assertions compare the outcome with the requirement; pytest reports a failure if they differ.

This test uses **controlled model responses**. A plain generated image returning laptop/cup labels is intentional test data. It tests application behavior, not object recognition.

One small change you can make is to add this parameter:

```python
(10 * 1024 * 1024 - 1, "complete"),
```

That adds a just-below-the-limit check without changing the application. Run only this test:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui.py::test_file_size_boundary -v
```

## 4. Controlled tests and real inference answer different questions

| Evidence | Question it answers | What it cannot establish |
| --- | --- | --- |
| Controlled laptop/cup response | Does the app display the expected visible names, two-decimal scores and matching rows/boxes? | Whether an AI model recognizes that image |
| Controlled delayed response | Can an old result repaint a newly selected image? | How often a real model responds slowly |
| Controlled error or silence | Can the app recover instead of remaining stuck? | That the real model actually suffered that failure |
| Real astronaut/cup/cat tests | Does the pinned model run, show the expected label/score and retain the selected box location and rendered geometry? | General accuracy, independent localization accuracy or correctness of every other prediction |
| Baseline comparison | Did shared labels and boxes change under the same pinned inference setup? | Equivalence to every upstream library version or all possible images |

The real-model tests are deliberately small. For example, the cup check does not reject the extra duplicate spoon predictions. Its reference coordinates are recorded outputs from the same model, not human-drawn correct boxes. Comparing those values detects regression; it cannot prove localization accuracy.

A test that only reads `data-label="cup"` can pass even when the visible word is blank. The result checks read the text the user sees as well as identity metadata. Disposable-copy experiments blank names/scores or move boxes, then show the intended assertions fail. A deliberately introduced fault is evidence about test sensitivity, not a naturally discovered product incident.

Malformed-response and timeout cases ask whether the app rejects invalid component output and recovers. They do not claim the real model produced those faults. Similarly, checking `role` and `aria-live` confirms the configured announcement mechanism; it does not measure what a screen reader actually speaks.

## 5. Understand a failure before changing the code

A test failure can come from the application, the model, the test itself or the environment. Read the assertion and the saved screenshot/logs before deciding which one it is.

Check that a failure test actually causes the failure. A worker-loading failure test whose server returns HTTP 200 lets the page become Ready, so it tests nothing. Returning HTTP 503 once makes the failure real, and Retry then succeeds. Changing the application to satisfy a test that never caused its failure would address the wrong problem.

A worker that never replies has a deadline and a restart path. A controlled silent-worker test, `tests/test_ui.py::test_nonresponding_worker_times_out_and_retries_the_latest_image`, verifies that recovery. This is not evidence that the real model hangs.

An example of a defect in both the app and its test: at a 320-pixel window width, the vertical scrollbar left only 305 pixels of usable width. A fixed 320-pixel body therefore overflowed, while a test using the full window width incorrectly passed. The corrected test, `tests/test_ui.py::test_narrow_layout_preserves_results_and_does_not_overflow`, uses the document's client width; it fails against the unfixed CSS and passes against the fixed CSS. Both the application and the rule used to judge its output had to change.

A timing defect: a fixed model-loading deadline counted 120 seconds from worker start and ignored progress. With the 43 MB model paced at 2.5 Mbps on loopback, 86% had arrived when the deadline fired, and Try again restarted the download from zero, so a steady connection below about 2.9 Mbps could never finish. The app measures a stall instead: each loading event restarts a 45-second window, and runtime initialization after the transfer keeps its own 120-second limit. Three controlled tests cover a stalled transfer, a slow steady transfer that must not time out, and an initialization hang. The lesson is to ask what a timeout is really protecting against. Here it protects against a dead connection, not a slow one.

## 6. A small exercise with an answer

Suppose the model score is 0.7999, the visible score is 0.80 and the filter minimum is 0.80. Should the prediction remain visible, and what should a test inspect?

Answer: it should be hidden, because filtering compares the unrounded 0.7999 with 0.80. A display assertion separately checks that the score is formatted as 0.80 before filtering. These are different requirements: rounding is presentation, while inclusion uses the original model value. The existing `test_filter.py` boundary case is an executable example.

A second exercise: a visitor's connection delivers one progress event every 10 seconds for six minutes, then the model finishes and initialization takes 30 seconds. Does loading succeed? What changes if the connection then drops completely for a minute before the model finishes?

Answer: the first case succeeds. Each event arrives well inside the 45-second stall window, so the transfer watchdog keeps restarting, and 30 seconds of initialization is inside its 120-second limit. In the second case the stall window expires 45 seconds after the last event and the app reports that the model stopped loading. `test_slow_steady_model_transfer_is_not_timed_out` and `test_stalled_model_transfer_times_out_after_its_last_progress` in `tests/test_recovery.py` exercise both shapes with accelerated timers. To see one fail, change `extendLoadWatchdog` in `dist/app.js` to return immediately, run those two tests, then restore the file with `git checkout -- dist/app.js`.

## 7. A useful release explanation

An honest explanation connects the requirement, test and evidence: "I defined the rule that replacing an image must never display its predecessor's results, and I directed tests that deliver delayed responses deliberately, kept separate from real inference, with failure evidence preserved. AI coding agents implemented most of the code and tests. The app is suitable for this local learning/evaluation workflow, with the model limitations documented."

Do not describe the project as proof of semiconductor hardware validation, production-grade recognition, general model accuracy or work written without AI assistance. The goal is to understand and explain the real contribution you can demonstrate.
