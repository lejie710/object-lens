# Selected verification evidence

These files summarize actual local checks and preserve their evidence boundaries. Raw run outputs remain in the ignored `artifacts` directory. JUnit copies here remove the machine hostname. Three older copies (`extension-first-full-suite.xml`, `review-package-before.xml` and `review-startup-before.xml`) also replace local absolute path prefixes with `<repository>`, `<workspace>` or `<user-home>` placeholders, as recorded in their redaction notes; the evidence tools redact paths when they write evidence. `export-record.json` records base-version hashes and redaction; `extension-verification.json` records the 48-case run, with separate `score-filter-record.json` and `sample-image-record.json` records. Test counts, assertions and timestamps are preserved.

Selected text files use UTF-8 with LF line endings to match Git checkout. Raw-run hashes continue to refer to the original files under `artifacts`; normalizing a selected copy does not change those raw hashes.

## Layout

Commit IDs: the documents cite the published commit IDs. Evidence records keep the IDs they were recorded with, before the history was rewritten for publication (personal email address, local user path and a private notes file removed; content, messages and dates otherwise unchanged). [history/commit-map.txt](history/commit-map.txt) maps each recorded ID to its published commit. For the same reason, the source hash of `tools/check_recovery_comparison.py`, whose default reference commit was updated to the published ID, differs from the hash in the records.

Current records are at the top level of this folder. Every earlier record is in `history/`, and the dependency audit report is in `security/`. Paths written inside older records (for example `docs/evidence/release-full-suite.xml` or `docs/screenshots/review-followup`) describe where files were when the record was made; the files have since moved without changing their content: earlier evidence to `history/`, current screenshots to `docs/screenshots/app` and older screenshots to `docs/screenshots/history/`. `slow-transfer-2-5-mbps.json` was recorded as `branch-review-slow-transfer.json`.

The `v1-0-2-*` files, `v1-0-rendered-review.json`, `social-preview-regeneration.json`, `fresh-clone-github.json`, `showcase-check.json`, `slow-transfer-2-5-mbps.json` and `security/pip-audit.json` are the current records. `model-observations.json` is the reference data the current real-model checks compare against. Every file in `history/` records an earlier run. Where the source is known, its commit is named in its row or in the [earlier recorded runs](../VERIFICATION.md#earlier-recorded-runs) table. No earlier record is combined with the current result. One run is not kept here: before this branch was merged, `v1-0-2-*` first recorded `9473c4e`, whose link preview was a crop of the coffee capture; after the image was redesigned the run was repeated under the same prefix, and the earlier files remain only in the branch's Git history (row `9473c4e` in the [earlier recorded runs](../VERIFICATION.md#earlier-recorded-runs) table). Hosted CI results are shown on GitHub and are not recorded here.

## Current records

| File | What it establishes |
| --- | --- |
| `v1-0-2-verification.json` and `v1-0-2-full-suite.xml` | Current 104-case suite (100 controlled, 4 real-model), environment, exact commands, source hashes and retained-record provenance |
| `v1-0-2-sensitivity.json` | 16 deliberate source faults in disposable copies, including the five core-rule faults, with a 30-case passing control and 28 intended failures; plus one equivalent fault whose 2 cases are expected to pass |
| `sample-captures.json` | The real model on the four other public sample photos (astronaut, chelsea, camera, rocket), with what the page showed and the hash of each capture used in the walkthrough; single runs, not an accuracy measurement |
| `v1-0-rendered-review.json` | Real-model captures (the visible page has not changed since; later changes add only head tags and the undisplayed link preview image), viewport measurements and labelled controlled timeout and Clear captures, with the hash of each capture; the 12 captures are expected to match the images in `docs/screenshots/app` |
| `v1-0-2-package.json` | Local static package identity and integrity: 29 files, including the link preview image, each entry verified against the manifest; no deployment |
| `social-preview-regeneration.json` | `tools/make_social_preview.py` run twice: both outputs match `dist/social-preview.png` byte for byte, with the Python, Pillow, font and source-capture hashes; one machine |
| `fresh-clone-github.json` | A fresh `git clone` of the public repository at `673f8b3`, before the link preview, into a new folder following the README exactly: setup, the smallest usage example and the test command (102 passed), with the operating system and runtime versions |
| `showcase-check.json` | The live GitHub Pages showcase, before the link preview was deployed, opened in a fresh headless Chrome profile: readiness, the try-it steps, the saved PNG, test mode off and unpublished test files |
| `slow-transfer-2-5-mbps.json` | 2.5 Mbps loopback probe: the fixed-deadline source (`a338f7c`) failed at 86% received; the stall-based package (`8c154b7`) reached ready at 140.6 seconds. Its `app.js` loading deadlines are identical to the current source. Includes the probe source |
| `security/pip-audit.json` | pip-audit report for `requirements-lock.txt` written by `tools/security_scan.py`: 30 packages checked, 0 known vulnerabilities on the day of the local run. Does not cover the browser runtime or model, which are pinned by hash in `asset-lock.json` |
| `model-observations.json` | Five real-photo observations and three comparisons with the runtime-normalized baseline; the reference for the real-model regression checks; not general model accuracy |

## Earlier records in `history/`

| File | What it establishes |
| --- | --- |
| `v1-0-1-verification.json`, `v1-0-1-full-suite.xml` and `v1-0-1-sensitivity.json` | 102-case suite (98 controlled, 4 real-model) of the files committed as `10addce`, and its 16-fault sensitivity run with a 30-case control and 28 intended failures |
| `v1-0-package.json` | Local static package identity and integrity for the files committed as `0c7e890`: 28 files; no deployment |
| `helpers-test-before-fix.xml` | `tests/test_helpers.py` from the corrected source run against the files committed as `e24155b`: the helper assertion failed with an empty message, hostname removed |
| `link-preview-sensitivity-before-fix.json` | Deliberate-fault run of the files committed as `e24155b` that stopped at `core-late-sample-defences-removed`: both intended tests failed, but one failure had no message to match; the clean control and 15 earlier faults behaved as intended, and the run stopped before the equivalent fault. The defect is in [DEFECTS.md](../DEFECTS.md#shared-helpers-raised-assertion-errors-with-no-message) |
| `fresh-clone-run.json` | A fresh `git clone` of the development repository at `ccd3d5b` following the README: 102 passed; an ignored pytest temp-folder warning after the summary line |
| `release-verification.json` and `release-full-suite.xml` | 102-case suite (98 controlled, 4 real-model) of the files committed as `ccd3d5b` (run from `0601bbc` with uncommitted changes), environment, exact commands, source hashes and retained-record provenance |
| `release-sensitivity.json` | 16 deliberate source faults in disposable copies of `ccd3d5b`, with a 30-case passing control and 28 intended failures, plus one equivalent fault whose 2 cases passed as expected |
| `release-rendered-review.json` | Real-model captures, viewport measurements and labelled controlled timeout and Clear captures for `ccd3d5b`; the 12 images are byte-identical to those now kept in `docs/screenshots/app` |
| `release-package.json` | Local static package identity and integrity for `ccd3d5b`: 23 files, before the five embedded-library licences were added; no deployment |
| `branch-review-verification.json` and `branch-review-full-suite.xml` | 102-case suite of the files committed as `8c154b7`, environment, exact commands, source hashes and retained-record provenance |
| `branch-review-sensitivity.json` | 11 deliberate source faults in disposable copies of `8c154b7`, with a 13-case passing control and 17 intended failures |
| `branch-review-recovery-comparison.json` | The three recovery wording checks run against `app.js` from `8a35f38` (all fail) and from `8c154b7` (all pass); `8c154b7` has the same `app.js` as the current source |
| `branch-review-rendered-review.json` | Real-model captures, viewport measurements and labelled controlled timeout and Clear captures for `8c154b7`; the images matched those then kept in `docs/screenshots/review-followup` |
| `branch-review-package.json` | Local static package identity and integrity for `8c154b7`; no deployment |
| `audit-17f2b9a-full-suite.xml` | A 93-case run of `a338f7c` in a disposable copy, hostname and paths redacted |
| `audit-17f2b9a-blank-label-fault.xml` | Deliberate fault: with the blank-label check deleted from `a338f7c`, 44 recovery and UI tests still passed |
| `loading-followup-verification.json` and `loading-followup-full-suite.xml` | 98-case run of the files committed as `b8ff7bc`. Its `evidence_type` text is a fixed label that does not describe this run; the source hashes identify it |
| `loading-followup-sensitivity.json` | Eight-fault run for `b8ff7bc`: an 11-case control and 14 intended failures |
| `loading-followup-recovery-comparison.json`, `loading-followup-rendered-review.json`, `loading-followup-package.json` | Recovery comparison, captures and package records for `b8ff7bc`. Its captures matched the images then kept in `docs/screenshots/review-followup` |
| `loading-followup-slow-transfer.json` | 2.5 Mbps probe for `b8ff7bc`: the fixed-deadline source failed at 86% received; that package reached ready at 139.6 seconds |
| `followup-verification.json` and `followup-full-suite.xml` | 93-case suite of the files committed as `a338f7c`, environment, exact commands, source hashes and retained-record provenance |
| `followup-sensitivity.json` | Four-fault run for `a338f7c`: deliberate source faults in disposable copies, with a 6-case passing control and 7 intended failures |
| `followup-recovery-comparison.json` | Three pre-Clear wording failures against `8a35f38` and three passes for `a338f7c` that continue through Clear, Retry and recovery; controlled faults |
| `followup-rendered-review.json` | Real-model app and export captures, viewport observations and explicitly controlled error and recovery captures for `a338f7c` |
| `followup-package.json` | Local static package identity and verification for `a338f7c`; no deployment |
| `source-review-verification.json` and `review-full-suite.xml` | Corrected 72-case gate of the files committed as `8a35f38`, reviewed source hashes and limits; the suite used temporary files outside a Git checkout |
| `review-startup-before.xml` and `review-startup-after.xml` | Five startup regressions failed before correction and passed afterward; the full suite also includes the worker-retry preparation case |
| `review-package-before.xml` and `review-package-after.xml` | Reproduced outside-checkout provenance failure and successful browser-free package checks after correction |
| `review-harness-cleanup.xml` | Three mocked cleanup regressions, with no real Chrome launched for those cases |
| `public-prep-full-suite.xml` and `public-prep-focused-suite.xml` | The 59-case full run and 11-case focused startup and package run of `e4781ab` |
| `public-prep-verification.json` | Source hashes, raw-record provenance, counts, the 10 Mbps loopback model transfer and pre-deployment limits for `e4781ab` |
| `public-prep-review.json` | Local static-package real inference and export, simulated model transfer, viewport, credits-link and keyboard observations for `e4781ab`; not hosted verification |
| `extension-full-suite.xml` | The 48-case run of `724d04d` covering sample loading, score filter, PNG export and the corrected narrow-layout check |
| `extension-verification.json` | Counts, application and test hashes, redaction records, observed findings and scope limits for `724d04d` |
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
| `test-sensitivity.json` | Two deliberately injected faults in isolated copies of the base version were detected by their intended tests; not discovered app or model defects |
| `rendered-review.json` | Viewport geometry, edge-label visibility and keyboard focus checks using controlled predictions |
| `stability-summary.json` | One hour of repeated real-model use on five fixed photos with the base version; not a load or accuracy benchmark |
| `final-contrast-review.json` | Computed browser text contrast, including the empty-state text |

The generated design concept is separate from these records. Partial expected labels were based on upstream image descriptions and a separate AI-assisted visual inspection, not exhaustive human annotation or the detector's own answers. The 26-case, fresh-setup, baseline-comparison and one-hour stability records belong to the base version. Records that identify their source commit or hashes say so; the others are marked "not recorded" in the [earlier recorded runs](../VERIFICATION.md#earlier-recorded-runs) table. Earlier evidence is not relabelled as new execution. Reusable procedures are under `tools`; some older records have no tracked helper.
