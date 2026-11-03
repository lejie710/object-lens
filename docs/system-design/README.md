# Object Lens system design

Read the [PDF companion](Object_Lens_System_Design.pdf) or the [editable Word edition](Object_Lens_System_Design.docx). Both contain clickable contents titles and page numbers, plus links back to the contents. Edition 2 is the 3 November 2026 review follow-up. Its starting source is `74d108f`; final implementation/test hashes in `source.json` and [followup-verification.json](../evidence/followup-verification.json) identify the tested changes. The older book remains available in Git history.

Begin with the scope and technology responsibilities, then follow the architecture, image-replacement sequence and testing diagrams. The current edition explains configuration/loading feedback, stage-specific timeout and Clear recovery, malformed output validation, visible result assertions, box-position regression and the static-package boundary. The worked size-limit test connects requirements to automation; the failure chapter distinguishes observed defects from deliberate fault experiments.

The current release assessment is based on the current follow-up execution. Earlier 26-, 48-, 59- and 72-case milestones retain their historical scope. Reference boxes are previous outputs of the pinned model, not independent ground truth. Announcement checks inspect page content and configuration, not actual screen-reader behavior. Website upload remains parked.

## Sources and generated files

| File | Role |
| --- | --- |
| `source.json` | Authoritative prose, tables, captions, code excerpts, source commit and evidence hashes |
| `diagrams/*.html` | Authoritative editable diagrams, with self-contained inline SVG |
| `diagrams/*.svg` and `diagrams/*.png` | Generated diagram exports used by the document |
| `../screenshots/review-followup/desktop.png` and `../screenshots/review-followup/export.png` | Shared actual application and PNG-output captures |
| `build_document.py` | Builds the Word document from the JSON and declared image assets |
| `export_document.ps1` | Exports through a hidden, task-owned Word instance and records actual heading pages |
| `verify_document_navigation.py` | Checks Word anchors, PDF link destinations, printed contents pages and heading locations |
| `verify_document_content.py` | Checks source/evidence/figure hashes and exact code excerpts; renders PDF page PNGs with bundled pypdfium2 |
| `page-map.json` | Verified one-based page numbers for the stable heading bookmarks |
| `navigation-manifest.json` and `navigation-audit.json` | Heading/asset manifest and results for the delivered document pair |
| `document-validation.json` | Final document hashes, source/evidence checks and the record of all-page visual inspection |

Edit the JSON and relevant diagram HTML when the content changes, then regenerate their outputs. Manual changes to a generated Word or PDF copy are not automatically imported into `source.json`. Diagram exports must retain the full canvas and its explanatory notes. `diagrams/SOURCE_CHECKS.md` records their scope and source correspondence.

Save authoring text as UTF-8 with LF line endings, matching the repository's Git attributes. The final builder checks the source JSON's line endings so byte hashes remain stable after checkout. Selected evidence text also uses LF; its original raw-run hashes continue to refer to the untouched files under `artifacts`.

## Rebuilding in the existing authoring environment

Reading these documents and running Object Lens require no document-authoring package installation. The application `.venv` is for the app's Python tests. Document production uses the existing Codex document runtime, including `python-docx`, `lxml`, `pypdf` and a PDF renderer, plus the already installed Word application on the recorded Windows environment. Resolve the current bundled Python path through Codex's workspace dependency loader and use it as `$documentPython` below.

From the repository root, rebuild the Word file with the existing verified page map:

```powershell
& $documentPython docs/system-design/build_document.py --source docs/system-design/source.json --output docs/system-design/Object_Lens_System_Design.docx --page-map docs/system-design/page-map.json --navigation-manifest docs/system-design/navigation-manifest.json
```

Use an ignored QA directory for intermediate conversion records. The tested Windows route uses static contents and direct PDF export, without a native TOC field-refresh dependency:

```powershell
New-Item -ItemType Directory -Force .local/document-planning | Out-Null
& docs/system-design/export_document.ps1 -InputDocx docs/system-design/Object_Lens_System_Design.docx -OutputPdf docs/system-design/Object_Lens_System_Design.pdf -NavigationManifest docs/system-design/navigation-manifest.json -ResultJson .local/document-planning/word-pages.json -ExportWithoutFieldRefresh
& $documentPython docs/system-design/verify_document_navigation.py --docx docs/system-design/Object_Lens_System_Design.docx --pdf docs/system-design/Object_Lens_System_Design.pdf --manifest docs/system-design/navigation-manifest.json --word-result .local/document-planning/word-pages.json --output docs/system-design/navigation-audit.json --page-map-output .local/document-planning/page-map.next.json
```

If headings or layout changed, first create an explicitly labelled preview with `--allow-draft`. The conversion records the actual heading pages. Inspect the PDF heading targets and adopt the newly verified page map, then rebuild without `--allow-draft`. Repeat the export and audit until the printed page numbers and targets agree. Do not retain preview labels or provisional page numbers in the delivered files.

The export helper requires an empty newly created Word instance, keeps it hidden and closes only its own document and instance. It does not change system security or network settings. Its recorded direct-export route performs the layout needed for the PDF; the static contents entries are generated from the verified page map.

After any content or layout change, render and inspect every final PDF page at readable scale. Check text, tables, figures, captions, page numbering and the link audit. Keep page PNGs and intermediate conversion records under ignored QA directories. Update the source/evidence hashes only after verifying the final bytes and actual results. The book records the starting commit plus final content hashes to avoid a circular claim about the commit that will contain the generated book.

The packaged `render_docx.py` was attempted for this edition but cannot find LibreOffice `soffice.exe` on this Windows host. The existing hidden Word export supplies the PDF instead. This fallback changes no Office security or execution-policy setting. Render and check the final artifacts with the bundled runtime:

```powershell
& $documentPython docs/system-design/verify_document_content.py --bundle-version 26.1026.10807 --word-state .local/document-planning/word-pages.json.state.json --render-dir artifacts/document-qa/followup-pages
```

Open every resulting page image and inspect text, tables, figures, captions and page edges. Only after completing that visual review, run the checker with `--visual-reviewed-all` to record it. That flag records the reviewer's completed inspection; the program cannot establish visual quality by itself.

Use the bundle version actually reported by the dependency loader if rebuilding in a newer environment. The checker records the running Python and package versions, and the export state supplies the actual Word and PowerShell versions.
