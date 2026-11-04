# Diagram source checks

These three editable diagrams (runtime architecture, image replacement sequence and browser testing workflow) describe the Object Lens system. The `object-lens-runtime-flow.*` figure in the same folder is not covered by these checks. Their component and message claims match the source files listed under Source fidelity. The diagrams are schematic: configuration/recovery detail is explained in [the design notes](../DESIGN.md) and assertion detail in [the verification assessment](../VERIFICATION.md). All labels and operational qualifications remain inside each SVG so they survive export.

## Files and display size

| Figure | Editable HTML | Exported SVG | Canvas | Intended display width |
| --- | --- | --- | --- | --- |
| Runtime architecture | `runtime-architecture.html` | `runtime-architecture.svg` | 1000 x 1052 | 6.5 in |
| Image replacement sequence | `image-sequence.html` | `image-sequence.svg` | 1000 x 1092 | 6.5 in |
| Browser testing workflow | `testing-workflow.html` | `testing-workflow.svg` | 1000 x 1184 | 6.5 in |

The three self-contained HTML files are the authoritative editable diagram sources. SVG and PNG files are their generated exports. Fonts use the installed Segoe UI/Arial/sans-serif stack. There are no scripts, external stylesheets, external images, webfonts or resource requests in the figure files. Most labels use 20-24 px at the source width; short connector labels use 18 px.

## Source fidelity

- `dist/worker.js`: local models only; fixed pretrained `Xenova/detr-resnet-50`; Transformers.js; ONNX Runtime Web CPU/WASM; quantized model; request ID and image data URL; fixed inference threshold 0.5; returned predictions and elapsed duration. The diagram deliberately says **Transformers.js**, not TensorFlow.js.
- `serve.py`: standard-library HTTP server on `127.0.0.1`, default port 8765; serves `dist` and runtime configuration; controlled test worker available only in explicit test mode. It does not implement an image-inference upload endpoint.
- `dist/app.js`: `selectFile` decodes locally; `startPendingInference` permits one active request and the latest pending image; `onWorkerMessage` clears the matching active request, accepts predictions only when their ID matches the current revision, and starts the next pending request. Replacement does not terminate the worker. `renderResults` validates/cache predictions; `renderFilteredResults` applies the minimum to the original scores and stable IDs.
- `tests/conftest.py`: pytest fixtures start isolated local servers and headless Chrome; Selenium operates that browser; failed checks capture a screenshot, page HTML, browser console and test context; fixtures close owned resources.
- `tests/fixtures/test-worker.js`: deliberately simulated predictions, delays and failures. The controlled path is not model-inference evidence.
- `tests/test_inference.py`: actual local model checks on public photographs, prediction observations and screenshots, visible label/score expectations, selected-coordinate regression and measured rendered geometry. The testing figure summarizes the real path and selected labels; it is not a complete assertion inventory. Reference boxes come from recorded pinned-model output rather than independent annotations. These checks do not establish general accuracy.

## PNG export implementation

The Canvas PNG export node and optional-export note match dist/png-export.js and saveResult in dist/app.js. The page draws the decoded image and current visible predictions onto a canvas, encodes PNG, and checks the export revision before initiating the browser download. Clear, replacement and filter changes retire an older export. The canvas work runs in the main page thread; model inference remains in its dedicated worker. No diagram claims that the OS has confirmed a completed file save.

## Deliberate scope and layout choices

- Runtime file serving is shown once at the browser boundary, rather than drawing separate file-request arrows for every asset. Both the UI and the worker obtain their local files from that server.
- The sequence is one successful A-to-B replacement example, not a complete error/retry state diagram. Its vertical spacing is logical ordering, not measured timing or CPU duration. It explicitly distinguishes stale-result rejection from inference cancellation.
- The testing figure describes browser tests. Its final note identifies server-only Python checks separately, so the figure does not imply that every test launches Chrome.
- The model/inference path and the controlled worker path are visibly separate. They merge only at the common assertion/reporting/evidence workflow.
- No application/UI screen is simulated by these figures. They are architecture and behavior illustrations, not execution evidence.
- The runtime and sequence diagrams match the worker, image-revision guards, filtered-result cache and canvas export in `app.js` and `png-export.js`, including the main-thread canvas, current-result snapshot and stale-export guard. The sequence shows one successful replacement, not failure or retry states. The runtime figure describes the local Python serving path; [the public package notes](../PUBLIC_DEMO.md) explain that the static package supplies the same browser files through an ordinary static server.
- The testing figure is an overview of browser checks. The suite also contains non-browser server/package and mocked cleanup checks. Assertion details not drawn include visible labels/scores, selected real-model coordinates and rendered geometry, malformed output, timeout/Clear recovery and announcement configuration. The figure does not claim those checks establish accuracy or screen-reader behavior.

## Diagram export checks

- The diagram authoring tool's `self_check.py --offline` and `export_svg.py --system-fonts` checks passed for all three files; the optional `verify-geometry.py` check was not available and did not run. These authoring tools are not included in this repository.
- Static source review: orthogonal arrows, distinct fan-out ports, accessible title/description IDs, all explanatory notes inside SVG, and no external resources.
- Browser PNG rendering at twice the logical SVG dimensions. All three PNG exports were visually inspected for legibility and source semantics.
- The figures are tall so that labels stay readable at a 6.5 in display width.
- The diagrams contain no pass count or application commit.
