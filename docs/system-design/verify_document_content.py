"""Verify the companion's source hashes/excerpts and optionally render its PDF.

Run with the document workspace runtime (python-docx, pypdf and pypdfium2).
This does not substitute for viewing every generated page image.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import sys
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render-dir', type=Path)
    parser.add_argument('--scale', type=float, default=1.5)
    parser.add_argument('--bundle-version', required=True,
                        help='Document runtime identifier for this run, for example a dependency-loader bundle version or system-python.')
    parser.add_argument('--word-state', type=Path,
                        help='The .state.json emitted by the matching hidden Word export.')
    parser.add_argument('--visual-reviewed-all', action='store_true',
                        help='Record only after a reviewer has opened every final page image.')
    parser.add_argument('--output', type=Path, default=HERE / 'document-validation.json')
    args = parser.parse_args()
    word_state = json.loads(args.word_state.read_text(encoding='utf-8')) if args.word_state else {}
    source_path = HERE / 'source.json'
    source = json.loads(source_path.read_text(encoding='utf-8'))
    nav = json.loads((HERE / 'navigation-audit.json').read_text(encoding='utf-8'))
    manifest = json.loads((HERE / 'navigation-manifest.json').read_text(encoding='utf-8'))
    docx = HERE / 'Object_Lens_System_Design.docx'
    pdf = HERE / 'Object_Lens_System_Design.pdf'
    errors = []
    checks = {}
    for group in ('reviewed_source_sha256', 'evidence_sha256'):
        hashes = source['metadata'][group]
        checks[group] = len(hashes)
        if not hashes:
            errors.append(f'No hashes in {group}')
        for name, expected in hashes.items():
            path = ROOT / name
            if not path.is_file() or sha(path) != expected:
                errors.append(f'Content hash mismatch: {name}')
    excerpts = 0
    assets = 0
    for section in source['sections']:
        for block in section['blocks']:
            if block['type'] == 'code' and isinstance(block.get('source'), dict):
                code = (ROOT / block['source']['file']).read_text(encoding='utf-8')
                if block['text'].strip() not in code:
                    errors.append('Code excerpt no longer matches ' + block['source']['file'])
                excerpts += 1
            if block['type'] == 'figure':
                path = (HERE / block['path']).resolve()
                if not path.is_file():
                    errors.append('Missing figure: ' + block['path'])
                assets += 1
    for record in manifest['assets']:
        if sha((HERE / record['declared_path']).resolve()) != record['sha256']:
            errors.append('Figure differs from built Word document: ' + record['declared_path'])
    if source['metadata'].get('pending_items') or source['metadata']['status'] != 'verified':
        errors.append('Source still marked provisional')
    if re.search(r'FOLLOWUP_[A-Z_]+|PENDING_', source_path.read_text(encoding='utf-8')):
        errors.append('Unresolved source marker')
    if sha(source_path) != manifest['source_sha256'] or sha(docx) != manifest['docx_sha256']:
        errors.append('Built Word document or source changed after manifest generation')
    if not nav['passed'] or nav['docx_sha256'] != sha(docx) or nav['pdf_sha256'] != sha(pdf):
        errors.append('Navigation audit is failed or stale')
    reader = PdfReader(pdf)
    page_text = [page.extract_text() or '' for page in reader.pages]
    bad_chars = sum(text.count('\x00') + text.count('\ufffd') for text in page_text)
    if bad_chars:
        errors.append('NUL or replacement character in PDF text')
    if args.render_dir:
        import pypdfium2 as pdfium
        args.render_dir.mkdir(parents=True, exist_ok=True)
        with pdfium.PdfDocument(pdf) as document:
            for i, page in enumerate(document):
                bitmap = page.render(scale=args.scale)
                bitmap.to_pil().save(args.render_dir / f'page-{i + 1}.png')
                bitmap.close()
                page.close()
    result = {
        'date': source['metadata']['date'],
        'documented_source': source['metadata']['documented_commit'],
        'base_commit': source['metadata']['base_commit'],
        'source_sha256': sha(source_path), 'docx_sha256': sha(docx), 'pdf_sha256': sha(pdf),
        'page_count': len(reader.pages), 'contents_heading_targets': nav['heading_count'],
        'pdf_contents_links': nav['pdf_contents_links'],
        'pdf_back_to_contents_links': nav['pdf_back_to_contents_links'],
        'navigation_audit': 'navigation-audit.json',
        'navigation_audit_sha256': sha(HERE / 'navigation-audit.json'),
        'visual_review': {
            'pages': list(range(1, len(reader.pages) + 1)) if args.visual_reviewed_all else [],
            'render_scale': args.scale,
            'render_backend': 'Microsoft Word direct PDF export and bundled pypdfium2 rasterization',
            'all_pages_reviewed': args.visual_reviewed_all,
            'finding': 'No clipping, overlap, missing glyph or unreadable figure text observed.' if args.visual_reviewed_all else 'Page-image review remains required.',
        },
        'render_environment': {
            'bundle_version': args.bundle_version,
            'python_version': sys.version.split()[0],
            'python_packages': {name: importlib.metadata.version(name)
                                for name in ('python-docx', 'pypdf', 'pypdfium2', 'lxml')},
            'word_export_state': word_state,
            'packaged_render_docx': 'Not used: LibreOffice soffice.exe is not installed on this Windows host.',
            'fallback': 'Existing hidden task-owned Word COM direct export, without field refresh or security-setting changes; pypdfium2 renders the resulting PDF.',
        },
        'source_checks': {**checks, 'code_excerpts_verified': excerpts,
                          'figure_assets_found': assets, 'pdf_text_bad_characters': bad_chars},
        'scope': 'Document content, navigation and layout. Application execution remains separately recorded in followup-verification.json.',
        'problems': errors,
        'status': 'passed' if not errors and args.visual_reviewed_all else 'failed' if errors else 'awaiting_visual_review',
    }
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'status': result['status'], 'pages': len(reader.pages), 'problems': errors}))
    if errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
