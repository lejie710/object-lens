# Object Lens system design

Read the [PDF companion](Object_Lens_System_Design.pdf) or the [editable Word edition](Object_Lens_System_Design.docx). Both contain clickable contents titles and page numbers, plus links back to the contents. The document describes application commit `781d9b75db1a3ebc9a200c238038b64aa108564a` and the dated evidence in [the extension verification record](../evidence/extension-verification.json).

Begin with the scope and technology responsibilities, then follow the architecture, image-replacement sequence and testing diagrams. The worked size-boundary test and real narrow-viewport defect explain how requirements, automation and failure investigation connect. The release assessment distinguishes the 48-case extension result from earlier base-version evidence.

## Sources and generated files

| File | Role |
| --- | --- |
| `source.json` | Authoritative prose, tables, captions, code excerpts, source commit and evidence hashes |
| `diagrams/*.html` | Authoritative editable diagrams, with self-contained inline SVG |
| `diagrams/*.svg` and `diagrams/*.png` | Generated diagram exports used by the document |
| `../screenshots/desktop.png` and `../screenshots/export.png` | Shared actual application and PNG-output captures |
| `build_document.py` | Builds the Word document from the JSON and declared image assets |
| `export_document.ps1` | Exports through a hidden, task-owned Word instance and records actual heading pages |
| `verify_document_navigation.py` | Checks Word anchors, PDF link destinations, printed contents pages and heading locations |
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

After any content or layout change, render and inspect every final PDF page at readable scale. Check text, tables, figures, captions, page numbering and the link audit. Keep page PNGs and intermediate conversion records under ignored QA directories. Update the application commit and evidence hashes only after verifying the new source and actual results.
