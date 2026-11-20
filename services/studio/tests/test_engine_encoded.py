"""Exercise the real encoder/muxer; raw appsrc counters alone hide slow output."""
import time
import pytest

pytest.importorskip('gi', reason='Run in the Studio image for encoded media checks')
from woody.controller import Controller
from woody.engine import GstEngine
from test_engine import eventually


def test_encoded_output_progresses_with_independent_pts_and_bounded_pixel_cache(store, tmp_path, monkeypatch):
    control = Controller(store)
    for index in range(3):
        cid = f'00000000-0000-0000-0000-{index:012d}'
        control.add_camera({'channel_id': cid, 'alias': f'cam-{index}', 'chat_enabled': False},
                           f'Camera {index}', f'test://{index + 1}')
    destination = tmp_path / 'program.flv'
    engine = GstEngine(control, output_uri=str(destination), allow_test=True)
    parse = engine.Gst.parse_launch
    monkeypatch.setattr(engine.Gst, 'parse_launch', lambda description: parse(description.replace('rtmpsink name=publish', 'filesink name=publish')))
    # Headers get their own timestamps; changing one must not alter the
    # cached pixels or another queued frame's header.
    used = set()
    first = engine._video_buffer(engine.black, 100, 40000000, used)
    second = engine._video_buffer(engine.black, 101, 40000000, used)
    assert first.pts == 4000000000 and second.pts == 4040000000
    assert first.extract_dup(0, first.get_size()) == engine.black
    engine.start()
    try:
        eventually(lambda: len(control.health) == 3 and all(c['state'] == 'online' for c in control.health.values()))
        control.set_program({'safe': False})
        eventually(lambda: engine.status()['output_fps'] >= 15)
        before = engine.output_frames
        time.sleep(2)
        assert engine.output_frames > before + 20
        assert engine.status()['output_age_seconds'] < 1
        assert destination.stat().st_size > 10000
        assert len(engine.video_cache) <= 8
        assert engine.restarts == 0
    finally:
        engine.stop()
