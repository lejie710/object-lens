# Selected verification evidence

These files summarize actual local checks and preserve their evidence boundaries. Raw run outputs remain in the ignored `artifacts` directory. JUnit copies here remove the machine hostname. Three older copies (`extension-first-full-suite.xml`, `review-package-before.xml` and `review-startup-before.xml`) also replace local absolute path prefixes with `<repository>`, `<workspace>` or `<user-home>` placeholders, as recorded in their redaction notes; the evidence tools redact paths when they write evidence. `export-record.json` records base-version hashes and redaction; `extension-verification.json` records the 48-case run, with separate `score-filter-record.json` and `sample-image-record.json` records. Test counts, assertions and timestamps are preserved.

Selected text files use UTF-8 with LF line endings to match Git checkout. Raw-run hashes continue to refer to the original files under `artifacts`; normalizing a selected copy does not change those raw hashes.

The `release-*` files and `fresh-clone-run.json` are the current records. Every other file records an earlier run. Where the source is known, its commit is named in its row or in the [earlier recorded runs](../VERIFICATION.md#earlier-recorded-runs) table. No earlier record is combined with the current result. `model-observations.json` is the reference data the current real-model checks compare against.

| File | What it establishes |
| --- | --- |
| `release-verification.json` and `release-full-suite.xml` | Current 102-case suite (98 controlled, 4 real-model), environment, exact commands, source hashes and retained-record provenance |
| `release-sensitivity.json` | 16 deliberate source faults in disposable copies, including the five core-rule faults, with a 30-case passing control and 28 intended failures; plus one equivalent fault whose 2 cases are expected to pass and do |
| `release-rendered-review.json` | Current real-model captures, viewport measurements and labelled controlled timeout and Clear captures, with the hash of each capture |
| `release-package.json` | Rebuilt local static package identity and integrity; no deployment |
| `fresh-clone-run.json` | A fresh `git clone` into a new folder following the README exactly: setup, the smallest usage example and the test command, with the operating system and runtime versions |
| `branch-review-verification.json` and `branch-review-full-suite.xml` | 102-case suite of the files committed as `764fb9d`, environment, exact commands, source hashes and retained-record provenance |
| `branch-review-sensitivity.json` | 11 deliberate source faults in disposable copies of `764fb9d`, with a 13-case passing control and 17 intended failures |
| `branch-review-recovery-comparison.json` | The three recovery wording checks run against `app.js` from `74d108f` (all fail) and from `764fb9d` (all pass); `764fb9d` has the same `app.js` as the release source |
| `branch-review-rendered-review.json` | Real-model captures, viewport measurements and labelled controlled timeout and Clear captures for `764fb9d`; the images match those kept in `docs/screenshots/review-followup` |
| `branch-review-package.json` | Local static package identity and integrity for `764fb9d`; no deployment |
| `branch-review-slow-transfer.json` | 2.5 Mbps loopback probe: the fixed-deadline source (`17f2b9a`) failed at 86% received; the stall-based package reached ready at 140.6 seconds. Its loading code is identical to the release source. Includes the probe source |
| `audit-17f2b9a-full-suite.xml` | A 93-case run of `17f2b9a` in a disposable copy, hostname and paths redacted |
| `audit-17f2b9a-blank-label-fault.xml` | Deliberate fault: with the blank-label check deleted from `17f2b9a`, 44 recovery and UI tests still passed |
| `loading-followup-verification.json` and `loading-followup-full-suite.xml` | 98-case run of the files committed as `f1a19a9`. Its `evidence_type` text is a fixed label that does not describe this run; the source hashes identify it |
| `loading-followup-sensitivity.json` | Eight-fault run for `f1a19a9`: an 11-case control and 14 intended failures |
| `loading-followup-recovery-comparison.json`, `loading-followup-rendered-review.json`, `loading-followup-package.json` | Recovery comparison, captures and package records for `f1a19a9`. Its captures match the images kept in `docs/screenshots/review-followup` |
| `loading-followup-slow-transfer.json` | 2.5 Mbps probe for `f1a19a9`: the fixed-deadline source failed at 86% received; that package reached ready at 139.6 seconds |
| `followup-verification.json` and `followup-full-suite.xml` | 93-case suite of the files committed as `17f2b9a`, environment, exact commands, source hashes and retained-record provenance |
| `followup-sensitivity.json` | Four-fault run for `17f2b9a`: deliberate source faults in disposable copies, with a 6-case passing control and 7 intended failures |
| `followup-recovery-comparison.json` | Three pre-Clear wording failures against `74d108f` and three passes for `17f2b9a` that continue through Clear, Retry and recovery; controlled faults |
| `followup-rendered-review.json` | Real-model app and export captures, viewport observations and explicitly controlled error and recovery captures for `17f2b9a` |
| `followup-package.json` | Local static package identity and verification for `17f2b9a`; no deployment |
| `source-review-verification.json` and `review-full-suite.xml` | Corrected 72-case gate of the files committed as `74d108f`, reviewed source hashes and limits; the suite used temporary files outside a Git checkout |
| `review-startup-before.xml` and `review-startup-after.xml` | Five startup regressions failed before correction and passed afterward; the full suite also includes the worker-retry preparation case |
| `review-package-before.xml` and `review-package-after.xml` | Reproduced outside-checkout provenance failure and successful browser-free package checks after correction |
| `review-harness-cleanup.xml` | Three mocked cleanup regressions, with no real Chrome launched for those cases |
| `review-navigation-original.json`, `review-navigation-negative.json`, `review-navigation-prior-rules.json` | The companion document passes the navigation checker; removing one return link fails the strengthened checker but passed the reconstructed prior rules |
| `public-prep-full-suite.xml` and `public-prep-focused-suite.xml` | The 59-case full run and 11-case focused startup and package run of `3ac9422` |
| `public-prep-verification.json` | Source hashes, raw-record provenance, counts, the 10 Mbps loopback model transfer and pre-deployment limits for `3ac9422` |
| `public-prep-review.json` | Local static-package real inference and export, simulated model transfer, viewport, credits-link and keyboard observations for `3ac9422`; not hosted verification |
| `extension-full-suite.xml` | The 48-case run of `781d9b7` covering sample loading, score filter, PNG export and the corrected narrow-layout check |
| `extension-verification.json` | Counts, application and test hashes, redaction records, observed findings and scope limits for `781d9b7` |
| `extension-demo.json` | Real sample, filter and PNG workflow and usable-width geometry on four viewports |
| `score-filter-suite.xml` and `score-filter-record.json` | The 29-case controlled score-filter suite |
| `sample-image-suite.xml` and `sample-image-record.json` | Seven sample-loading checks plus three real-inference cases |
| `export-png-suite.xml` | Eight controlled export cases using actual downloaded PNG bytes |
| `viewport-before-fix.xml` | Reproduction of the observed 320-versus-305-pixel horizontal-overflow defect |
| `extension-first-full-suite.xml` | A 47-pass, one-failure run; the failed download-folder assertion found a non-PNG artifact, as explained in `extension-verification.json` |
| `initial-full-suite.xml` | A complete 26-case run of the base version before the final test diagnostics |
| `final-full-suite.xml` | The complete 26-case run of the base version with the final test diagnostics and valid PNG fixtures |
| `fresh-setup-suite.xml` | The complete 26-case run from independently prepared source, environment, assets and driver cache on the same laptop; not a clone |
| `fresh-setup-summary.json` | Setup steps, versions, timing and the verified newline-only manifest repair for that prepared copy |
| `model-observations.json` | Five real-photo observations and three comparisons with the runtime-normalized baseline; the reference for the real-model regression checks; not general model accuracy |
| `test-sensitivity.json` | Two deliberately injected faults in isolated copies of the base version were detected by their intended tests; not discovered app or model defects |
| `rendered-review.json` | Viewport geometry, edge-label visibility and keyboard focus checks using controlled predictions |
| `stability-summary.json` | One hour of repeated real-model use on five fixed photos with the base version; not a load or accuracy benchmark |
| `final-contrast-review.json` | Computed browser text contrast, including the empty-state text |

The generated design concept is separate from these records. Partial expected labels were based on upstream image descriptions and a separate AI-assisted visual inspection, not exhaustive human annotation or the detector's own answers. The 26-case, fresh-setup, baseline-comparison and one-hour stability records belong to the base version. Records that identify their source commit or hashes say so; the others are marked "not recorded" in the [earlier recorded runs](../VERIFICATION.md#earlier-recorded-runs) table. Earlier evidence is not relabelled as new execution. Reusable procedures are under `tools`; some older records have no tracked helper.
