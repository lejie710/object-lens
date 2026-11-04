"""Allowlisted public package checks and local static-server integration.

The browser check uses the actual prepared model, but does not verify a hosted URL.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import threading
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest
from selenium.webdriver.common.by import By

from test_export import downloads, wait_for_png  # noqa: F401 - imports the shared download fixture
from test_filter import set_minimum
from test_ui import result_labels, wait_state
from tools.build_public_demo import build, git_provenance

ROOT = Path(__file__).resolve().parents[1]
APP_FILES = {
    "index.html", "style.css", "app.js", "worker.js", "png-export.js",
    "credits.html", "runtime-config.json",
}
ASSET_PATHS = {
    "assets/runtime/transformers.min.js",
    "assets/runtime/ort-wasm-simd.wasm",
    "assets/runtime/ort-wasm.wasm",
    "assets/models/Xenova/detr-resnet-50/config.json",
    "assets/models/Xenova/detr-resnet-50/preprocessor_config.json",
    "assets/models/Xenova/detr-resnet-50/onnx/model_quantized.onnx",
}
FIXTURE_LICENSE = "licenses/fixture-license.txt"


def write_payload(project, relative, contents):
    path = project / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)
    return path


def locked_file(path, payload):
    return {"path": path, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}


@pytest.mark.parametrize("probe_failure", ["not-repository", "missing-git"])
def test_git_provenance_is_absent_for_a_non_repository_marker(tmp_path, monkeypatch, probe_failure):
    project = tmp_path / "source-copy"
    write_payload(project, ".git/config", b"PRIVATE_FIXTURE_SENTINEL\n")

    def not_a_repository(command, **kwargs):
        if probe_failure == "missing-git":
            raise FileNotFoundError("Git is not installed in this controlled setup")
        raise subprocess.CalledProcessError(128, command)

    monkeypatch.setattr(subprocess, "check_output", not_a_repository)
    assert git_provenance(project.resolve()) == (None, None)


def test_git_provenance_is_absent_for_a_repository_without_commits(tmp_path, monkeypatch):
    project = tmp_path / "source-copy"
    write_payload(project, ".git/config", b"PRIVATE_FIXTURE_SENTINEL\n")

    def commitless_repository(command, **kwargs):
        if command[-2:] == ["rev-parse", "--show-toplevel"]:
            return str(project.resolve()) + "\n"
        raise subprocess.CalledProcessError(128, command)

    monkeypatch.setattr(subprocess, "check_output", commitless_repository)
    assert git_provenance(project.resolve()) == (None, None)


def test_git_provenance_never_uses_a_parent_repository(tmp_path, monkeypatch):
    project = tmp_path / "source-copy"
    write_payload(project, ".git/config", b"PRIVATE_FIXTURE_SENTINEL\n")

    def parent_repository(command, **kwargs):
        if command[-2:] == ["rev-parse", "--show-toplevel"]:
            return str(tmp_path.resolve()) + "\n"
        pytest.fail("A source copy must not inherit its parent's commit or status")

    monkeypatch.setattr(subprocess, "check_output", parent_repository)
    assert git_provenance(project.resolve()) == (None, None)


@pytest.fixture
def package_project(tmp_path):
    """Tiny checked assets avoid copying the 43 MB model for packaging unit checks."""
    project = tmp_path / "project"
    for name in APP_FILES - {"runtime-config.json"}:
        write_payload(project, f"dist/{name}", f"Public fixture file: {name}\n".encode())
    write_payload(project, "dist/runtime-config.json", b'{"testMode": false}\n')
    asset_lock = {
        "transformers_js": "2.17.2", "onnxruntime_web": "1.14.0",
        "model": "Xenova/detr-resnet-50",
        "model_revision": "8be7ab59ff663484ee9ba2e8d8f267330d5ad03e", "files": [],
    }
    for name in sorted(ASSET_PATHS):
        payload = f"Deliberate packaging-test bytes for {name}\n".encode()
        write_payload(project, f"dist/{name}", payload)
        asset_lock["files"].append(locked_file(name, payload))
    write_payload(project, "asset-lock.json", json.dumps(asset_lock).encode())
    license_payload = b"Deliberate license fixture for packaging verification.\n"
    write_payload(project, f"dist/{FIXTURE_LICENSE}", license_payload)
    write_payload(project, "credits-lock.json", json.dumps({
        "files": [locked_file(FIXTURE_LICENSE, license_payload)],
    }).encode())
    # The builder's independently pinned sample hash remains enabled.
    sample = ROOT / "dist" / "samples" / "coffee.png"
    assert sample.is_file(), "Prepare the documented public coffee sample before this check"
    target = project / "dist" / "samples" / "coffee.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(sample, target)
    return project


def test_public_zip_exactly_matches_manifest_and_excludes_private_material(package_project, tmp_path):
    private_paths = [
        ".git/config", ".venv/private.txt", "tests/private.txt", "docs/private.docx",
        "baseline/private.txt", "artifacts/private.txt", "dist/test-worker.js",
        "dist/tests/fixture.js", "dist/docs/private.txt", "dist/baseline/private.txt",
        "dist/.env", "dist/.git/private.txt", "dist/samples/extra-photo.png",
    ]
    for name in private_paths:
        write_payload(package_project, name, b"PRIVATE_FIXTURE_SENTINEL\n")
    output_root = tmp_path / "packages"
    result = build(output_root, project_root=package_project)
    for key in ("site_directory", "archive", "manifest"):
        assert Path(result[key]).is_absolute()
        assert Path(result[key]).exists()
    manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
    assert manifest["content_id"] == result["content_id"]
    assert manifest["archive_sha256"] == hashlib.sha256(Path(result["archive"]).read_bytes()).hexdigest()
    expected = APP_FILES | ASSET_PATHS | {FIXTURE_LICENSE, "samples/coffee.png"}
    entries = {entry["path"]: entry for entry in manifest["files"]}
    assert len(entries) == len(manifest["files"]), "Manifest contains duplicate paths"
    assert set(entries) == expected
    site = Path(result["site_directory"])
    assert {path.relative_to(site).as_posix() for path in site.rglob("*") if path.is_file()} == expected
    with zipfile.ZipFile(result["archive"]) as archive:
        assert set(archive.namelist()) == expected
        assert len(archive.namelist()) == len(expected)
        for name in expected:
            payload = (site / name).read_bytes()
            assert archive.read(name) == payload
            assert entries[name]["bytes"] == len(payload)
            assert entries[name]["sha256"] == hashlib.sha256(payload).hexdigest()
            assert b"PRIVATE_FIXTURE_SENTINEL" not in payload
    assert json.loads((site / "runtime-config.json").read_text(encoding="utf-8")) == {"testMode": False}

    # Identical content has the same identity but a later build cannot overwrite its predecessor.
    again = build(output_root, project_root=package_project)
    assert again["content_id"] == result["content_id"]
    assert Path(again["site_directory"]) != site
    assert Path(result["archive"]).is_file()


@pytest.mark.parametrize("condition", ["missing", "tampered"])
def test_missing_or_changed_runtime_asset_prevents_a_public_package(package_project, tmp_path, condition):
    target = package_project / "dist" / "assets" / "runtime" / "ort-wasm.wasm"
    if condition == "missing":
        target.unlink()
    else:
        contents = target.read_bytes()
        target.write_bytes(b"!" + contents[1:])  # Same byte count, wrong SHA-256.
    with pytest.raises((ValueError, FileNotFoundError)) as failure:
        build(tmp_path / "packages", project_root=package_project)
    assert "ort-wasm.wasm" in str(failure.value)


def test_changed_license_prevents_a_public_package(package_project, tmp_path):
    target = package_project / "dist" / FIXTURE_LICENSE
    contents = target.read_bytes()
    target.write_bytes(b"!" + contents[1:])
    with pytest.raises((ValueError, FileNotFoundError)) as failure:
        build(tmp_path / "packages", project_root=package_project)
    assert "fixture-license.txt" in str(failure.value)


def test_controlled_test_mode_cannot_be_packaged_for_public_use(package_project, tmp_path):
    write_payload(package_project, "dist/runtime-config.json", b'{"testMode": true}\n')
    with pytest.raises(ValueError) as failure:
        build(tmp_path / "packages", project_root=package_project)
    assert "test" in str(failure.value).lower()


def test_manifest_cannot_add_an_unapproved_path(package_project, tmp_path):
    payload = b"PRIVATE_FIXTURE_SENTINEL\n"
    write_payload(package_project, "private.txt", payload)
    lock_path = package_project / "asset-lock.json"
    asset_lock = json.loads(lock_path.read_text(encoding="utf-8"))
    asset_lock["files"].append(locked_file("../private.txt", payload))
    lock_path.write_text(json.dumps(asset_lock), encoding="utf-8")
    with pytest.raises(ValueError):
        build(tmp_path / "packages", project_root=package_project)


@pytest.mark.inference
def test_packaged_site_runs_real_sample_filter_and_export_on_an_ordinary_static_server(browser, downloads, tmp_path):
    result = build(tmp_path / "public-package", project_root=ROOT)
    site = Path(result["site_directory"])
    # Deliberately avoid serve.AppHandler: all required routes must be ordinary files.
    handler = partial(SimpleHTTPRequestHandler, directory=str(site))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    url = f"http://127.0.0.1:{server.server_port}"
    try:
        with urlopen(url + "/runtime-config.json", timeout=10) as response:
            assert json.load(response) == {"testMode": False}
        with urlopen(url + "/credits.html", timeout=10) as response:
            assert response.status == 200
        for route in ["/test-worker.js", "/tests/fixtures/test-worker.js", "/docs/DESIGN.md", "/.git/config"]:
            with pytest.raises(HTTPError) as failure:
                urlopen(url + route, timeout=10)
            assert failure.value.code == 404

        browser.get(url)
        wait_state(browser, "ready", timeout=120)
        browser.find_element(By.ID, "try-sample").click()
        wait_state(browser, "complete", timeout=120)
        assert browser.find_element(By.ID, "filename").text == "coffee.png"
        original = [
            {"label": row.get_attribute("data-label"), "score": float(row.get_attribute("data-score"))}
            for row in browser.find_elements(By.CSS_SELECTOR, ".result-row")
        ]
        assert "cup" in [item["label"] for item in original]
        assert "Controlled test mode" not in browser.find_element(By.TAG_NAME, "body").text
        set_minimum(browser, 0.80)
        expected = [item["label"] for item in original if item["score"] >= 0.80]
        assert result_labels(browser) == expected
        assert [box.get_attribute("data-label") for box in browser.find_elements(By.CSS_SELECTOR, ".detection-box")] == expected
        browser.find_element(By.ID, "save-result").click()
        exported, dimensions = wait_for_png(browser, downloads)
        assert dimensions == (600, 400)
        report = {
            "evidence_type": "Local static-package integration with real model inference",
            "hosting": "Python standard SimpleHTTPRequestHandler on numeric loopback; no hosted URL tested",
            "content_id": result["content_id"],
            "browser_version": browser.capabilities.get("browserVersion"),
            "input_action": "Try sample button using the packaged coffee photo",
            "observed_predictions": original,
            "minimum_score": 0.80,
            "filtered_labels": expected,
            "downloaded_png": exported.name,
            "downloaded_dimensions": list(dimensions),
            "console": browser.get_log("browser"),
            "limitations": "One local Chrome session and one public image; not general model accuracy or hosted deployment evidence.",
        }
        target = ROOT / "artifacts" / "public-package-integration"
        target.mkdir(parents=True, exist_ok=True)
        (target / "observations.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
