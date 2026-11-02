"""Verify controlled predictions cannot be served by a normal application server."""
import json
from urllib.error import HTTPError
from urllib.request import urlopen

import pytest


def test_controlled_worker_requires_explicit_test_mode(real_url, controlled_url):
    with urlopen(real_url + "/runtime-config.json") as response:
        assert json.load(response) == {"testMode": False}
    with pytest.raises(HTTPError) as rejected:
        urlopen(real_url + "/test-worker.js")
    assert rejected.value.code == 404
    with urlopen(controlled_url + "/runtime-config.json") as response:
        assert json.load(response) == {"testMode": True}
    with urlopen(controlled_url + "/test-worker.js") as response:
        assert b"CONTROLLED TEST DATA" in response.read()
