# Selected verification evidence

These files summarize actual local checks and preserve their evidence boundaries. Raw run outputs remain in the ignored `artifacts` directory. JUnit copies here remove the machine hostname; `export-record.json` records the original file hashes and that redaction. Test counts, assertions and timestamps are preserved.

| File | What it establishes |
| --- | --- |
| `initial-full-suite.xml` | The first complete 26-case run after the functional fixes |
| `final-full-suite.xml` | The complete 26-case run with the final test diagnostics and valid PNG fixtures |
| `fresh-setup-suite.xml` | The complete run from independently prepared source, environment, assets and driver cache on the same laptop |
| `fresh-setup-summary.json` | Setup steps, versions, timing and the verified newline-only manifest repair |
| `model-observations.json` | Five real-photo observations and three comparisons with the runtime-normalized baseline; not general model accuracy |
| `test-sensitivity.json` | Two deliberately injected faults in isolated copies were detected by their intended tests; not discovered app/model defects |
| `rendered-review.json` | Viewport geometry, edge-label visibility and keyboard focus checks using controlled predictions |
| `stability-summary.json` | One hour of repeated real-model use on five fixed photos; not a load or accuracy benchmark |
| `final-contrast-review.json` | Computed browser text contrast after the final empty-state colour adjustment |

The generated design concept is separate from these records. Partial expected labels were based on upstream image descriptions and AI-assisted visual review, not exhaustive human annotation or the detector's own answers. The fresh-setup record is an earlier independent environment check; the final suite also includes later test-quality refinements.
