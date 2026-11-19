import pytest
from woody.controller import Rejected
from woody.core import Core, PROCESS_ID, PROGRAM_ID


class Fake(Core):
    def __init__(self):
        self.calls = []
        self.saved = []
        self.uri = "rtsp://camera/live"

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/v3/process" and method == "GET":
            return self.saved
        if path == "/v3/config":
            return {"config": {"rtmp": {"enable": True, "app": "/live", "token": ""}}}
        if method == "POST":
            self.saved.append(kwargs["json"])
        if method == "GET" and "restreamer-ui:ingest:" in path:
            return {"metadata": {"restreamer-ui": {"sources": [{"type": "network", "settings": {"mode": "pull"}, "inputs": [{"address": self.uri}]}], "profiles": [{"video": {"source": 0}}], "meta": {"name": "Garden"}}}}


def test_program_is_an_ordinary_discoverable_restreamer_channel_and_provision_is_idempotent():
    core = Fake()
    assert core.provision()["created"]
    assert not core.provision()["created"]
    posts = [call for call in core.calls if call[0] == "POST"]
    assert len(posts) == 1
    process = posts[0][2]["json"]
    assert process["id"] == PROCESS_ID and process["reference"] == PROGRAM_ID
    assert process["output"][0]["address"] == f"{{memfs}}/{PROGRAM_ID}.m3u8"
    metadata = next(call[2]["json"] for call in core.calls if call[0] == "PUT")
    assert [s["codec"] for s in metadata["streams"]] == ["h264", "aac"]


def test_source_is_read_only_and_only_existing_network_sources_are_supported():
    core = Fake()
    assert core.source("00000000-0000-0000-0000-000000000001") == ("Garden", "rtsp://camera/live")
    assert all(call[0] == "GET" for call in core.calls)
    with pytest.raises(Rejected):
        core.source(PROGRAM_ID)
    core.uri = "file:///etc/passwd"
    with pytest.raises(Rejected):
        core.source("00000000-0000-0000-0000-000000000001")
