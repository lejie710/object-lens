# Selected verification evidence

These files summarize actual local checks and preserve their evidence boundaries. Raw run outputs remain in the ignored `artifacts` directory. JUnit copies here remove the machine hostname. `export-record.json` records base-version hashes and redaction; `extension-verification.json` records the combined extension, with separate `score-filter-record.json` and `sample-image-record.json` checkpoint records. Test counts, assertions and timestamps are preserved.

Selected text files use UTF-8 with LF line endings to match Git checkout. Raw-run hashes continue to refer to the original files under `artifacts`; normalizing a selected copy does not change those raw hashes.

| File | What it establishes |
| --- | --- |
| `source-review-verification.json` and `review-full-suite.xml` | The corrected 72-case local gate, reviewed source hashes and limits; the suite used temporary files outside a Git checkout |
| `review-startup-before.xml` and `review-startup-after.xml` | Five startup regressions failed before correction and passed afterward; the full suite also includes the additional worker-retry preparation case |
| `review-package-before.xml` and `review-package-after.xml` | Reproduced outside-checkout provenance failure and successful browser-free package checks after correction |
| `review-harness-cleanup.xml` | Three mocked cleanup regressions, with no real Chrome launched for those cases |
| `review-navigation-original.json`, `review-navigation-negative.json`, `review-navigation-prior-rules.json` | Original document passes; removing one return link fails the strengthened checker but passed reconstructed prior rules |
| `public-prep-full-suite.xml` and `public-prep-focused-suite.xml` | The 3 November 59-case full run and 11-case focused startup/package run |
| `public-prep-verification.json` | Source hashes, raw-record provenance, current counts and explicit pre-deployment limits |
| `public-prep-review.json` | Local static-package real inference/export, simulated model transfer, viewport, credits-link and keyboard observations; not hosted verification |
| `extension-full-suite.xml` | The final combined 48-case run for the three additions and the corrected narrow-layout check |
| `extension-verification.json` | Final counts, application/test hashes, redaction records, actual findings and scope limits |
| `extension-demo.json` | Real sample/filter/PNG workflow and current usable-width geometry on four viewports |
| `score-filter-suite.xml` and `score-filter-record.json` | The 29-case controlled score-filter checkpoint |
| `sample-image-suite.xml` and `sample-image-record.json` | Seven sample-loading checks plus three real-inference cases |
| `export-png-suite.xml` | Eight controlled export cases using actual downloaded PNG bytes |
| `viewport-before-fix.xml` | Reproduction of the observed 320-versus-305-pixel horizontal-overflow defect |
| `extension-first-full-suite.xml` | Earlier 47-pass/one-failure run; the failed download-folder assertion found a non-PNG artifact, as explained in the verification record |
| `initial-full-suite.xml` | The first complete 26-case run after the functional fixes |
| `final-full-suite.xml` | The complete 26-case run with the final test diagnostics and valid PNG fixtures |
| `fresh-setup-suite.xml` | The complete run from independently prepared source, environment, assets and driver cache on the same laptop |
| `fresh-setup-summary.json` | Setup steps, versions, timing and the verified newline-only manifest repair |
| `model-observations.json` | Five real-photo observations and three comparisons with the runtime-normalized baseline; not general model accuracy |
| `test-sensitivity.json` | Two deliberately injected faults in isolated copies were detected by their intended tests; not discovered app/model defects |
| `rendered-review.json` | Viewport geometry, edge-label visibility and keyboard focus checks using controlled predictions |
| `stability-summary.json` | One hour of repeated real-model use on five fixed photos; not a load or accuracy benchmark |
| `final-contrast-review.json` | Computed browser text contrast after the final empty-state colour adjustment |

The generated design concept is separate from these records. Partial expected labels were based on upstream image descriptions and AI-assisted visual review, not exhaustive human annotation or the detector's own answers. The 26-case, fresh-setup, baseline-comparison and one-hour stability records belong to the earlier base version. The extension has its own final suite and demonstration record; earlier evidence is not relabelled as new execution.
