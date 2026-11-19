"""Actual GStreamer pixels and audio; runs in the Studio image, not a mock mixer."""
import time
import pytest

pytest.importorskip("gi", reason="Run in the Studio Docker image for GStreamer checks")
from woody.engine import GstEngine


def eventually(check, timeout=15):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if check():
            return
        time.sleep(.05)
    raise AssertionError("GStreamer condition did not become true")


@pytest.fixture
def engine(control):
    for index, camera in enumerate(control.data["cameras"].values()):
        camera["source"] = control.store.encrypt(f"test://{index}")
    mixer = GstEngine(control, test_output=True, allow_test=True)
    mixer.start()
    try:
        eventually(lambda: mixer.status()["state"] == "running")
        eventually(lambda: all(c.get("state") == "online" for c in control.health.values()))
        eventually(lambda: getattr(mixer, "last_sample", None) is not None)
        yield mixer
    finally:
        mixer.stop()


def center_luma(engine):
    sample = engine.last_sample
    buffer = sample.get_buffer()
    # Main pane center, clear of text labels. Output caps are I420 1920x1080.
    return buffer.extract_dup(360 * 1920 + 1280, 1)[0]


def test_thirteen_sources_and_one_hundred_switches_keep_output_alive(engine, control):
    ids = list(control.data["cameras"])
    start = engine.frames
    pts = []
    for index in range(100):
        control.switch(ids[index % 13])
        time.sleep(.04)
        pts.append(engine.last_sample.get_buffer().pts)
    assert engine.frames > start + 30
    assert pts == sorted(pts)
    assert engine.restarts == 0
    assert engine.output_state == "running"
    assert len(engine.cameras) == 13


def test_hidden_camera_is_black_and_silent_without_restarting_output(engine, control):
    cid = list(control.data["cameras"])[4]  # solid red test pattern
    control.switch(cid)
    eventually(lambda: center_luma(engine) > 30)
    eventually(lambda: any(getattr(engine, "last_audio", b"")))
    control.hide(cid, True)
    eventually(lambda: center_luma(engine) == 16, timeout=1)
    eventually(lambda: getattr(engine, "last_audio", None) == engine.silence, timeout=1)
    assert control.audio_camera() is None
    assert engine._take_audio(None) == engine.silence
    assert engine.restarts == 0
    control.save_scene({"alias": "previous", "name": "Previous", "layout": "six", "cameras": [cid], "chat_enabled": True})
    control.apply_scene("previous")
    time.sleep(.15)
    assert center_luma(engine) == 16


def test_stalled_camera_replaced_with_slate_while_other_sources_continue(engine, control):
    cid = list(control.data["cameras"])[4]
    control.switch(cid)
    eventually(lambda: center_luma(engine) > 30)
    previous = engine.frames
    def stall():
        engine.cameras[cid]["pipeline"].set_state(engine.Gst.State.PAUSED)
        return False
    engine.GLib.idle_add(stall)
    eventually(lambda: center_luma(engine) == 16, timeout=4)
    assert engine.frames > previous + 10
    assert engine.output_state == "running" and engine.restarts == 0


def test_output_error_recovers_without_restarting_camera_pipelines(engine):
    original = {cid: camera["pipeline"] for cid, camera in engine.cameras.items()}
    before = engine.frames
    engine.output.get_bus().post(engine.Gst.Message.new_eos(engine.output))
    eventually(lambda: engine.restarts == 1 and engine.output_state == "running", timeout=8)
    eventually(lambda: engine.frames > before + 10)
    assert all(engine.cameras[cid]["pipeline"] == pipeline for cid, pipeline in original.items())
