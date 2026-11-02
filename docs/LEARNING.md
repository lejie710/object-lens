# A short guide to Object Lens

## 1. Start with the application

Launch the local server using the README command, open the page in Chrome and choose `dist/samples/coffee.png`. The detector proposes labels and boxes. Selecting the cup in the list highlights its box. Replace the image with `chelsea.png`, then use Clear.

These are actual model predictions. The coffee sample can produce two spoon boxes for the same visible spoon. The app should present those results faithfully and make them understandable; a passing UI test does not prove that the model is always right.

## 2. What each part does, and why

| Part | What it does | Why it is present |
| --- | --- | --- |
| HTML and CSS | Define the page, controls, spacing and colours | Make the image and results understandable |
| `dist/app.js` | Validates files, tracks the current image and renders results | Keeps what is on screen consistent with what the user selected |
| `dist/worker.js` | Runs the pretrained detector in a browser worker | Performs inference without blocking the main interface |
| `serve.py` | Serves local files to Chrome | Lets the browser load the app, model and runtime from this computer |
| Python tests | Describe actions and expected outcomes | Turn a requirement into an executable check |
| Selenium | Operates Chrome and reads page elements | Repeats user workflows automatically |
| pytest | Starts fixtures, runs tests and reports assertions | Gives each check a clear pass or fail result |

Python is the main language to learn for this project's automation. The actual application is JavaScript. The Python server does not perform model inference.

Headless Chrome still renders the page and can save screenshots, but it does not open a visible browser window. Selenium controls that isolated browser session, not your mouse or desktop. Your normal browser profile is not used for the tests.

The pretrained model is the AI inside the app. The coding agent's help in developing this project is a separate form of AI assistance. Both are credited, and neither supplies a trustworthy expected answer automatically.

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

After the walkthrough, one small change you can make is to add this parameter:

```python
(10 * 1024 * 1024 - 1, "complete"),
```

That adds a just-below-the-limit check without changing the application. Run only this test:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_ui.py::test_file_size_boundary -v
```

This is a suggested post-delivery change, not a claim that you have already made it.

## 4. Controlled tests and real inference answer different questions

| Evidence | Question it answers | What it cannot establish |
| --- | --- | --- |
| Controlled laptop/cup response | Does the app display matching rows and boxes? | Whether an AI model recognizes that image |
| Controlled delayed response | Can an old result repaint a newly selected image? | How often a real model responds slowly |
| Controlled error or silence | Can the app recover instead of remaining stuck? | That the real model actually suffered that failure |
| Real astronaut/cup/cat tests | Does the prepared local model run and include a reviewed expected label? | General accuracy, absence of duplicates or correctness of every other prediction |
| Baseline comparison | Did shared labels and boxes change under the same pinned inference setup? | Equivalence to every upstream library version or all possible images |

The selected-label inference tests are deliberately small. For example, finding `cup` in the coffee image does not fail because there are also duplicate spoon predictions. Those are recorded separately in the evaluation notes.

## 5. Understand a failure before changing the code

A test failure can come from the application, the model, the test itself or the environment. Read the assertion and the saved screenshot/logs before deciding which one it is.

During development, an attempted test of worker-loading failure initially did not create that failure at all: the server returned HTTP 200 and the page became Ready. The test was corrected to return HTTP 503 once, after which Retry succeeded. Changing the application to satisfy the mistaken first test would have addressed the wrong problem.

The review also found a missing recovery path for a worker that never replies. The fix added a deadline and worker restart. A controlled silent-worker test verifies that recovery. This is not evidence that the real model was observed hanging.

## 6. A useful release explanation

An honest explanation connects the requirement, test and evidence: "I checked that replacing an image cannot display its predecessor's results. I tested delayed responses deliberately, kept those tests separate from real inference, and preserved failure evidence. The app is suitable for this local learning/evaluation workflow, with the model limitations documented."

Do not describe the project as proof of semiconductor hardware validation, production-grade recognition, general model accuracy or work independently written without AI assistance. The goal is to understand and explain the real contribution you can demonstrate.
