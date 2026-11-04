# Correctness reviews and regression fixes

Four review passes are recorded here, newest first. The branch review corrects documentation miscounts, two loading edge cases, a misleading message after Clear, weak assertions and local paths in retained evidence. The loading follow-up before it corrected a slow-connection loading defect and an untested label rule found by an AI-assisted audit of `17f2b9a`. The review follow-up continued `74d108f`, corrected stage-specific timeout/Clear wording and strengthened assertions for visible labels/scores, real-model box positions, malformed responses and announcement configuration. [The current verification assessment](VERIFICATION.md) and [branch-review-verification.json](evidence/branch-review-verification.json) identify the current execution and source hashes. The earlier sections remain historical records.

## Branch review

After the loading follow-up, two further AI-assisted reviews examined the whole branch on 3 and 4 November 2026. A separate single-agent review session ran the suite and its own deliberate faults. A multi-agent review then assigned six reviewers to one area each (application state, test strength, evidence claims, tools, privacy and how the repository reads to a reviewer); every finding had to survive three independent attempts to refute it, and a final reviewer looked for unexamined areas. 22 of 24 findings survived; the final reviewer added two more, which were checked directly rather than through the three-refuter step. Neither review found a new defect in the slow-connection fix itself. The findings below were corrected; overlapping findings are combined.

| Finding | Correction |
| --- | --- |
| The loading follow-up's documents counted nine faults, 15 intended failures and five new faults. The record held eight faults and 14 failures: the clean control had been counted as a fault | Recounted from the evidence. The current record holds 11 faults and 17 intended failures, quoted from the file |
| The real-model score check tolerated every score forced to 1.0: the selected references were all 0.998 to 0.999 | Every visible row is compared with the recorded output, including the 0.67 and 0.93 coffee spoons. A new deliberate fault forces every score to 1.0 and fails |
| The model's final bytes are followed by a silent 43 MB Cache Storage write before Transformers.js sends `done`, still under the 45-second connection-stall window | Once every byte of a known-size transfer has arrived, the 120-second initialization deadline applies. A controlled test and a deliberate fault cover it |
| Without a Content-Length header, Transformers.js 2.17.2 reports total = bytes received, so the page would show "100%" for the whole transfer. The existing test injected a shape the library never sends | A size is trusted only after an event shows fewer bytes than the total; otherwise the page shows megabytes received with an indeterminate bar. A new test replays the real event shape |
| After Clear, a hung analysis of the removed image still produced "Image analysis took too long" on an empty workspace | That case now restarts the detector quietly. Replacing a hung image with a new one keeps its existing error-and-retry behavior. A controlled test and a deliberate fault cover it |
| Startup tests counted only controlled-worker requests, so a premature real worker was invisible | Startup tests also count `/worker.js` requests and require none before valid configuration |
| Package provenance still failed for a repository with no commits | All Git calls fall back to absent provenance; a new test covers it |
| Two new and one older retained JUnit file contained the Windows user path | Selected copies use placeholders, recorded in each redaction note; raw-record hashes still refer to the originals |
| The verification record labelled itself with the previous round's name; the sensitivity tool wrote CRLF JSON and missed escaped paths | The recorder's label is neutral; the sensitivity tool writes LF and redacts escaped paths |
| Claims without retained evidence: the audit's 93-case reproduction and the "44 tests still passed" blank-label observation; four startup/package timings that differed from the retained JUnit | The two audit runs are now retained as evidence; the timings quote the JUnit records |
| Overstatements: an "independent oracle" that uses the same model's earlier output, "only the reference catches" scaled scores, "new" geometry checks from an earlier round, "2 to 3 source pixels" when one sample is 1.5 | Reworded to what the evidence shows |
| Presentation: the README sent readers first to an owner handoff note; 12 recaptured screenshots duplicated byte-identical images; the book's AC10 row omitted `test_recovery.py`; a cited table's source line could start a new page | Reordered links, kept one screenshot set, corrected the row and the builder |

Two findings were refuted. A suggested contradiction about the Clear button quirk was not one, and the CRLF finding was refuted as having no visible consequence, although the tool was corrected anyway. Rewriting Git history to remove the user path from earlier commits was not done; that is a decision for the owner.

## Loading follow-up

An AI-assisted audit of `17f2b9a` on 3 November 2026 reproduced the 93-case suite and the recorded fault and recovery checks, then looked for remaining gaps. It found one observed defect and one untested rule; both are corrected here.

| Finding | Before | Correction and observed check |
| --- | --- | --- |
| Slow connections could never load the model | The model-load deadline counted 120 seconds from worker start and ignored progress. With only the 43 MB model response paced at 2.5 Mbps on loopback, 37.4 MB (86%) had arrived when the deadline fired. Try again restarted the transfer from zero, so a steady connection below about 2.9 Mbps could not succeed by retrying. `PUBLIC_DEMO.md` said very slow connections "can require retry" | Transfer now fails only after 45 seconds without a loading event; each event restarts the window. Runtime initialization after the model file finishes keeps its own fixed 120-second deadline that later settings-file events cannot extend. Stage-specific messages distinguish a stalled transfer from slow initialization. Controlled tests cover a stalled transfer, a slow steady transfer that must not time out and an initialization hang, each followed by Clear and recovery where relevant |
| The blank-label check had no test | Deleting `!label.trim()` from `renderResults` left all 44 recovery and UI tests passing ([audit-17f2b9a-blank-label-fault.xml](evidence/audit-17f2b9a-blank-label-fault.xml)) | Empty and whitespace-only labels are added to the malformed-response cases; deleting the check fails both |

The audit also replaced one self-referential assertion. The real-model tests compared visible text with the page's own `data-*` attributes, so a fault that changed both consistently could pass. The selected row's visible label and score are now compared with the earlier recorded output of the same pinned model, with a 0.01 score tolerance. A deliberately scaled score fails all three photo cases.

Each new check has a deliberate fault in `tools/check_review_sensitivity.py`, alongside the four earlier faults. The paced-transfer observation came from an audit probe on loopback. Repeated against the corrected package, the same 2.5 Mbps transfer completed and the detector became ready at 139.6 seconds. [loading-followup-slow-transfer.json](evidence/loading-followup-slow-transfer.json) records both runs and the probe source. It is one run per condition on loopback, not an Internet speed measurement. Four cosmetic book corrections were also made: two headings gained missing commas ("Filtering, samples and PNG output"; "Testing with Python, pytest and Selenium"), the running header gained a separator, the narrow-viewport table received a table number, and the acceptance table's source line gained the four missing test files.

## Review follow-up

An earlier external AI-assisted review reproduced the preceding 72-case suite and reported important blind spots: blank visible text, displaced real-model boxes and removed announcement settings could evade its checks. Those are reported external experiments. The follow-up adds locally reproducible disposable-copy sensitivity checks and records their actual outcomes separately in `followup-sensitivity.json`. No broad mutation score is claimed.

The previous timeout callback always described image detection, including while the model was still loading. Clear then mapped any stopped worker to a startup failure. The corrected timeout callback selects a message for the active loading or inference stage. Clear uses the stopped-worker flag to show a generic unavailable/restart message; it does not retain or reclassify the earlier cause. Explicit Retry or a valid new selection can recover. Dedicated controlled tests exercise failure, Clear and recovery.

The retained [before/after comparison](evidence/followup-recovery-comparison.json) runs the same three new wording tests against a disposable copy of `74d108f` and the current source: three expected failures in 26.732 seconds, then three passes in 27.644 seconds. The earlier source fails at the pre-Clear message assertions. Its Clear behavior is therefore a source finding, not independently reached by that failed run. The current passing checks do continue through Clear, Retry and successful processing. Unexpected worker crashes are deliberately simulated; a real-model trigger was not observed.

Representative malformed predictions now have rejection and recovery checks, including missing/non-finite coordinates, invalid scores, impossible boxes and a mixed batch. Clamping remains a defined boundary behavior for finite out-of-range coordinates that leave a usable rectangle. These are simulated model-component failures, not evidence of defects observed inside the actual model.

Visible result assertions check both names and two-decimal scores. The three real-photo cases also compare selected coordinates with the earlier pinned-model outputs and measure the rendered box against the actual image rectangle. Tolerance accommodates small numeric/layout variation; it does not convert model-derived references into ground truth. Important input messages are checked for useful content without making every sentence an exact-text contract. DOM announcement checks establish configuration, not screen-reader certification.

The current documentation is reconciled around one current execution record. The Word/PDF companion is rebuilt for the new implementation, with verified contents destinations, page numbers, return links and all-page rendering. Historical evidence is retained, and the public ZIP is rebuilt locally. Upload remains parked.

## Preceding correctness review

Review date: 3 November 2026. Reviewed starting point: merged `main` at `9a60886`, containing the public-preparation implementation `3ac9422`. The review kept the feature scope fixed. Website upload remains parked; no successful public deployment or hosted verification is recorded.

## Scope and method

The maintained application, Python server, all tests, setup/package/evidence helpers and document-generation/navigation helpers were read. Model/runtime binaries, distributed notices and preserved upstream files were checked against their recorded hashes. That integrity check does not constitute a manual audit of every third-party implementation or a general model-accuracy evaluation.

Independent source-reading passes examined application state, packaging/reproducibility, and test/document evidence. Findings were reproduced through controlled local HTTP timing, ordinary temporary directories or isolated mocks/copies. The application's source was not deliberately corrupted to create these defects. This review was assisted by AI tools.

## Confirmed findings and corrections

| Finding | Before | Correction and observed check |
| --- | --- | --- |
| Configuration loading had no application deadline | A held response before headers or during its JSON body left the app loading after the 20-second regression wait; the model watchdog had not started | A real 15-second configuration deadline aborts the request. Retry fetches configuration again and retains the chosen image. Both held-response cases pass. |
| Background startup could erase an input error | An invalid file's explanation disappeared when delayed configuration completed and started the worker | Worker creation no longer clears user-facing errors as an incidental startup action. The error remains until a deliberate recovery action. |
| Worker readiness could misreport an active file read | The app said Ready to choose an image while a held file read was still pending | Track the current preparation revision separately. Ready and retry paths preserve Reading image or Loading sample until preparation actually finishes. |
| Package provenance depended on the test's parent directory | The privacy test failed outside a Git checkout because a deliberately incomplete `.git` marker caused Git to exit 128 | Missing/unusable optional Git metadata produces absent provenance; a source copy never inherits its parent's repository metadata. Byte-integrity and public-file checks are unchanged. |
| Failure-evidence writing could bypass browser cleanup | Injected evidence-directory denial skipped `driver.quit()`; observed mock call count was zero | An outer `finally` always attempts browser cleanup after creation. Evidence-write failures remain secondary. Three mocked failure paths require exactly one cleanup call. |
| Navigation checking did not require return links | Prior rules accepted a disposable PDF with one Back to contents link removed | Require one return link per top-level section. The delivered document passes with ten; the damaged copy fails with nine. Its page content was unchanged. |

The initial five startup regressions failed against the previous app in 73.298 seconds of JUnit time. After the first correction they passed in 63.996 seconds. A further regression covers worker retry during an unfinished file read. The original packaging privacy case failed outside the checkout in 1.688 seconds; after the provenance fix, eight browser-free cases passed there in 4.176 seconds. A separate case also covers a missing Git executable.

A controlled duplicate-label case was added because actual model observations include two spoon predictions. It verifies selection, coordinates, colors and filtering by prediction identity rather than merely comparing labels. No current duplicate-selection defect was found; this strengthens the regression oracle for an existing requirement.

## Historical combined result

The complete suite passed **72 cases**, with zero failures, errors or skips, in **531.363 seconds** of JUnit time (531.53 seconds by the runner). It used a temporary directory outside any Git repository, addressing the condition hidden by the earlier in-checkout test runs. There are 68 non-inference cases and four actual-model cases. The static-package real-model workflow remains included.

At that preceding review checkpoint, the delivered Word/PDF files were unchanged. The stricter navigation check passed the 19-page document, 31 heading targets, 62 contents links and ten return links. Removing one return annotation from a disposable copy failed the new check; reconstructed prior rules incorrectly passed that same copy. This is a corrected verification gap, not a claim that the delivered document was missing its links.

The selected records and source hashes are in `docs/evidence/source-review-verification.json`. Earlier 26-, 48- and 59-case records retain their original source/version scope; their counts are not added together or relabelled as current execution.

## Limits of the preceding review

No blocking finding remains from this bounded review of the agreed local workflow. This does not prove every possible input, browser, operating-system behavior or third-party dependency correct. Chrome on the recorded Windows environment remains the verified target; wider browser/device support, general recognition accuracy and hosted behavior remain unqualified.

When this review was recorded, the optional transfer-rate checker respected the app's former fixed 120-second model-load deadline, so a sufficiently low requested rate was a negative loading scenario. The second follow-up replaced that deadline with a stall window; the checker's own 120-second readiness wait remains a separate limit of that helper. The recorded 10 Mbps model-only simulation remains limited to that scenario.

The corrected deployment package supersedes the earlier prepared ZIP, but upload remains paused. An independent reviewer should inspect this branch and the retained evidence before making additional release claims. Any next changes should address a demonstrated defect or a necessary clarification within the frozen scope.
