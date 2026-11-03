# Verification and release assessment

Status on 3 November 2026: the review follow-up keeps Object Lens suitable for its bounded local learning and demonstration workflow. The current combined result is **93 passed, 0 failures/errors/skips; 648.509 seconds of JUnit suite time (89 non-model and 4 real-model cases)**. Website upload remains parked; no successful public deployment or verified public URL is recorded.

## Current review follow-up

Environment: Python 3.12.10, pytest 9.0.3, Selenium 4.40.0, Chrome 156.0.8078.80 and ChromeDriver 156.0.8078.80. The integrated runner recorded 650.572 seconds of wall time; the JUnit suite duration above is the separate test-suite measurement. The run used one browser at a time.

The current execution record is [followup-verification.json](evidence/followup-verification.json), with the combined JUnit result in [followup-full-suite.xml](evidence/followup-full-suite.xml). It records the exact commands, environment and final source hashes. The implementation continues starting commit `74d108f`; the new hashes identify the tested changes without pretending that the starting commit already contained them.

| Agreed improvement | What is checked | What the evidence does not establish |
| --- | --- | --- |
| Visible labels and scores | Result rows and box labels show the expected name; result rows show two-decimal model scores; blank text in disposable copies is detected | Correct recognition of arbitrary images |
| Real-model box positions | Person, cup and cat coordinates stay within a stated tolerance of earlier pinned-model outputs; actual box geometry agrees with the displayed image | Localization accuracy against independent human annotations |
| Truthful timeout and Clear feedback | Model-loading and inference deadlines have distinct explanations; Clear leaves a stopped detector unavailable; Retry restores operation | That a real model outage occurred |
| Malformed model responses | Representative invalid scores, missing/non-finite coordinates, impossible boxes and mixed valid/invalid batches are rejected without misleading detections; recovery and clamping are checked | Exhaustive validation of every possible object shape or dependency fault |
| Useful feedback and announcements | Important input errors contain the format/limit/recovery information; status and error elements retain intended roles/live settings | Actual screen-reader speech, accessibility certification or every assistive technology |
| Current documentation and package | Current claims reconcile with the new evidence; Word/PDF contents, page references, return links and page layout are verified; package allowlist and hashes pass | Deployment or correctness on an untested hosting provider |

The current browser review and images are recorded in [followup-rendered-review.json](evidence/followup-rendered-review.json) and `docs/screenshots/review-followup`. Real coffee inference and export captures are distinguished from the deliberately controlled timeout/Clear state. The public package's separate record is [followup-package.json](evidence/followup-package.json). Browser console and request observations describe the captured sessions, not all operating-system activity.

## Reproduce the evidence

From the prepared repository environment:

```powershell
.\.venv\Scripts\python.exe tools/prepare_assets.py --verify-only
.\.venv\Scripts\python.exe tools/download_samples.py --verify
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe tools/check_review_sensitivity.py --output artifacts/review-sensitivity-new
.\.venv\Scripts\python.exe tools/check_recovery_comparison.py --output artifacts/recovery-comparison-new
.\.venv\Scripts\python.exe tools/capture_review.py --screenshots artifacts/review-captures-new --report artifacts/review-captures-new.json
.\.venv\Scripts\python.exe tools/record_verification.py --retain-prefix followup-new
.\.venv\Scripts\python.exe tools/build_public_demo.py
```

The manifest records the exact invocation used for the retained run, including its temporary directory outside any Git checkout. The helpers retain reusable procedures for the new sensitivity, capture and evidence-export work. They do not reconstruct every historical experiment whose original helper remained under ignored `artifacts`. JUnit evidence copies remove hostnames; the manifest records redaction and hashes of the raw and selected records.

Normal production deadlines remain 15 seconds for configuration, 120 seconds for model loading and 90 seconds for inference. Normal controlled loading keeps the production 120-second deadline. Dedicated loading-timeout tests accelerate only its 120000 ms timer to 2500 ms; controlled inference uses four seconds. Those durations exercise failure paths and are not measured model performance. Test processes run headlessly with local assets and a cached driver. They do not change system security settings.

## Deliberate fault sensitivity

[followup-recovery-comparison.json](evidence/followup-recovery-comparison.json) records three controlled wording checks failing against `74d108f` in 26.732 seconds and all three passing against the corrected source in 27.644 seconds. The old checks fail before Clear, so they do not independently reproduce the old Clear message. The passing current checks continue through Clear, truthful detector unavailability, Retry and a successful new image. The substituted runtime crash is a component simulation; no production trigger is claimed.

[followup-sensitivity.json](evidence/followup-sensitivity.json) records fresh disposable-copy experiments and their intended failing assertions. A six-case clean baseline passes before the four deliberate-fault runs. The clean application is preserved. These results show that the selected checks detect the selected faults; they are not a mutation score, broad test-completeness proof or naturally observed production incidents.

Earlier external review reported that blank labels/scores, displaced boxes and removed announcement settings could pass the previous assertions. That report motivated the new checks. Only the new locally retained runs are claimed as this follow-up's reproduced evidence. The malformed responses are deliberate test-worker outputs, not faults observed from the real pretrained model.

## Acceptance coverage

| Criterion | Representative evidence |
| --- | --- |
| AC1: input limits and useful rejection | Exact 10 MiB and 16,000,000-pixel boundaries, JPEG/EXIF, unsupported content and truncated PNG; meaningful visible format/limit messages |
| AC2: current-image results | Visible labels/scores, row/box identity, controlled geometry and selected-box regression on three real photos |
| AC3: selection and Clear | Selected-box/keyboard checks; Clear removes content and preserves truthful unavailable state after a stopped worker |
| AC4: stale-result protection | In-flight Clear, fast/slow replacement, sample-fetch cancellation and retired-worker checks |
| AC5: recovery | Input errors, empty results, inference failure, malformed responses, model/inference timeout and recovery |
| AC6: usable interface | Keyboard/focus, usable viewport widths, visible status/error content and announcement-configuration assertions |
| AC7: score filter | Raw-score boundary, restore without inference, stable identity/color/selection, filter-empty and keyboard behavior |
| AC8: Try sample | Real local-photo path; missing/unreadable data, actual 15-second fetch timeout and late-response rejection |
| AC9: PNG export | Downloaded PNG bytes/dimensions, retained/excluded annotation pixels, EXIF, encoder failure/timeout and stale-export rejection |
| AC10: bounded startup | Configuration headers/body deadline, invalid configuration, preserved input errors/preparation, model progress, stage-specific worker failure and Retry |
| AC11: static package | Exact file/ZIP/hash checks, private-file exclusions, optional Git provenance outside a checkout and actual model/export through an ordinary static server |

## Historical checkpoints

These executions retain their original source, date and limits. Counts overlap and are never added to the current result.

| Milestone | Recorded result | Retained evidence |
| --- | --- | --- |
| 3 November preceding correctness review | 72 passed, 0 failures/errors/skips; 531.53 s; 68 non-inference and four real-model cases | `review-full-suite.xml`, `source-review-verification.json` |
| 3 November public preparation | 59 passed; 441.33 s; focused run 11 passed in 52.46 s | `public-prep-full-suite.xml`, `public-prep-focused-suite.xml`, `public-prep-verification.json` |
| 2 November combined extension | 48 passed; 418.62 s; 45 non-inference and three real-model cases | `extension-full-suite.xml`, `extension-verification.json` |
| Filter checkpoint | 29 controlled cases passed; 199.37 s | `score-filter-suite.xml`, `score-filter-record.json` |
| Sample checkpoint | Seven controlled plus three real cases passed; 137.27 s | `sample-image-suite.xml`, `sample-image-record.json` |
| PNG checkpoint | Eight controlled export cases passed; 89.03 s | `export-png-suite.xml` |
| Base final suite | 26 passed; 215.13 s | `final-full-suite.xml` |
| Base fresh setup on the same laptop | 26 passed; 205.13 s | `fresh-setup-summary.json`, `fresh-setup-suite.xml` |
| Base repeated use | 320 cycles, 320 clears and 32 rapid replacements; 3615.927 s; no observed failure | `stability-summary.json` |

The historical public-preparation review paced only the model response at 10 Mbps on loopback: 43,102,531 bytes arrived in 34.493 seconds, and readiness occurred at 36.776 seconds. This controlled transfer observation is not Internet performance. The historical environment was Python 3.12.10, pytest 9.0.3, Selenium 4.40.0, Chrome 156.0.8078.74 and ChromeDriver 156.0.8078.80; the new manifest independently records the current run's versions.

## Findings and their interpretation

The preceding review reproduced missing configuration deadlines, startup erasing an input error, readiness misreporting an unfinished file read, optional package provenance failing outside Git, failure-evidence writing bypassing browser cleanup, and an incomplete document-navigation check. [SOURCE_REVIEW.md](SOURCE_REVIEW.md) preserves the before/after evidence and describes this follow-up separately.

The extension's 320-pixel viewport defect was observed rather than injected. Its vertical scrollbar left 305 pixels of usable width, but the body's minimum was 320 pixels. Comparing against `window.innerWidth` hid the overflow; the corrected check uses `documentElement.clientWidth`. [viewport-before-fix.xml](evidence/viewport-before-fix.xml) retains the real failing assertion, and the historical extension capture measured 305-pixel content inside that 305-pixel space after correction.

The first extension suite had 47 passes and one failed download-folder assertion. The extra file was `downloads.htm.crdownload`, with a CRX container header, not an application PNG; its producing request was not captured. The assertion was retained and external hostname resolution was disabled only inside isolated test browsers. The rerun passed 48 cases. [extension-first-full-suite.xml](evidence/extension-first-full-suite.xml) preserves that failed run without inventing its origin.

Earlier setup/test issues included a worker-failure injection that initially returned HTTP 200, an authenticated Git request unsuitable for public asset retrieval, proxy handling for numeric loopback, CRLF manifest output and insufficient failure diagnostics. Their original records remain in the evidence index. The base watchdog work addressed a possible silent worker; no real-model hang was observed.

## Real-model observations and limits

The five-photo historical observations are in [model-observations.json](evidence/model-observations.json). Astronaut produced person; coffee produced spoon, dining table, cup and another spoon; chelsea produced cat; camera included person with incorrect/duplicate other predictions; rocket produced no predictions. These convenience samples are not an exhaustive annotated dataset.

The three new geometry checks compare against earlier coordinates from that same pinned model, with tolerance documented in `tests/test_inference.py`. This detects a position regression or rendering displacement. It cannot establish whether the reference boxes are objectively correct. Expected-label notes came from upstream descriptions and separate AI-assisted visual inspection; they are partial expectations, not full human annotations.

## Release decision and remaining limits

The current combined suite and targeted fault/recovery evidence support the agreed local exploration workflow: **93 passed, 0 failures/errors/skips; 648.509 seconds of JUnit suite time (89 non-model and 4 real-model cases)**. The refreshed documents and rebuilt static ZIP are local deliverables. Source publication remains owner-operated, and website upload remains parked.

Only the recorded Windows/Chrome environment was checked. No other browser, iOS/Safari, hosted CI, deployed URL, general accuracy benchmark, GPU/NPU execution, semiconductor inspection or production-scale behavior was qualified. The historical one-hour session does not requalify this revision, establish a flake rate or certify memory-leak freedom. Timing varies with workstation load. Live-region configuration checks are not actual screen-reader testing.

Raw outputs and retained recovery-comparison copies remain under ignored working directories. The sensitivity runner removes its own temporary source copies after each run while preserving logs and results. The maintained application is the repository's root `dist` directory. Preserve those evidence boundaries when explaining the project or using screenshots in a learning update.
