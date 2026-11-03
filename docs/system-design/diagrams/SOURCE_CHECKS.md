# Diagram source checks

These editable diagrams describe the Object Lens system documented by source.json. Their component and message claims were reconciled with the implemented application on 2 November 2026. All labels and operational qualifications remain inside each SVG so they survive export.

## Files and display size

| Figure | Editable HTML | Exported SVG | Canvas | Intended document width |
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
- `tests/test_inference.py`: actual local model checks on public photographs, prediction observations and screenshots, selected-label expectations. These checks do not establish general accuracy.

## PNG export implementation

The Canvas PNG export node and optional-export note match dist/png-export.js and saveResult in dist/app.js. The page draws the decoded image and current visible predictions onto a canvas, encodes PNG, and checks the export revision before initiating the browser download. Clear, replacement and filter changes retire an older export. The canvas work runs in the main page thread; model inference remains in its dedicated worker. No diagram claims that the OS has confirmed a completed file save.

## Deliberate scope and layout choices

- Runtime file serving is shown once at the browser boundary, rather than drawing separate file-request arrows for every asset. Both the UI and the worker obtain their local files from that server.
- The sequence is one successful A-to-B replacement example, not a complete error/retry state diagram. Its vertical spacing is logical ordering, not measured timing or CPU duration. It explicitly distinguishes stale-result rejection from inference cancellation.
- The testing figure describes browser tests. Its final note identifies server-only Python checks separately, so the figure does not imply that every test launches Chrome.
- The model/inference path and the controlled worker path are visibly separate. They merge only at the common assertion/reporting/evidence workflow.
- No application/UI screen is simulated by these figures. They are architecture and behavior illustrations, not execution evidence.

## Checks performed

- `self_check.py --offline`: passed for all three HTML files.
- `export_svg.py --system-fonts`: succeeded for all three, producing separate SVG files.
- Referenced optional `verify-geometry.py`: not present in the installed skill scripts, so that check could not run. No package or helper was downloaded.
- Static source review: orthogonal arrows, distinct fan-out ports, accessible title/description IDs, all explanatory notes inside SVG, and no external resources.
- Browser PNG rendering completed at twice the logical SVG dimensions. All three actual PNG exports were visually inspected for legibility and source semantics.
- Current app.js and png-export.js were checked against the diagrams, including the main-thread canvas, current-result snapshot and stale-export guard.
- Final Word/PDF integration was visually reviewed at the actual document size. All 19 pages were inspected by both the document authoring agent and the independent reviewing agent, including diagram pages 5, 7 and 11. The tall figures use up to eight inches of page height to preserve readable labels.
