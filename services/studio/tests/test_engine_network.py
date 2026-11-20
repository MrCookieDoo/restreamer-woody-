"""Real network ingestion; synthetic test:// sources bypass uridecodebin entirely."""
import time
import pytest

pytest.importorskip('gi', reason='Run in the Studio image for network media checks')
import gi
gi.require_version('Gst', '1.0')
try:
    gi.require_version('GstRtspServer', '1.0')
except ValueError:
    pytest.skip('GstRtspServer test fixture not installed', allow_module_level=True)
from gi.repository import Gst, GstRtspServer, GLib
from cryptography.fernet import Fernet
from woody.controller import Controller
from woody.engine import GstEngine
from woody.storage import Store
from test_engine import eventually


def test_rtsp_camera_rates_and_optional_audio_keep_program_live(tmp_path):
    Gst.init(None)
    server = GstRtspServer.RTSPServer()
    server.set_address('127.0.0.1')
    server.set_service('0')
    cases = [(5, True), (15, True), (25, True), (15, False), (25, False)]
    for index, (fps, audio) in enumerate(cases):
        factory = GstRtspServer.RTSPMediaFactory()
        launch = f'( videotestsrc is-live=true pattern=red ! video/x-raw,width=320,height=180,framerate={fps}/1 ! x264enc tune=zerolatency speed-preset=ultrafast key-int-max={fps} ! rtph264pay name=pay0 pt=96 '
        if audio:
            launch += 'audiotestsrc is-live=true wave=sine ! audioconvert ! avenc_aac ! rtpmp4gpay name=pay1 pt=97 '
        factory.set_launch(launch + ')')
        factory.set_shared(True)
        server.get_mount_points().add_factory(f'/camera{index}', factory)
    source_id = server.attach(None)
    assert source_id and server.get_bound_port() > 0
    store = Store(str(tmp_path / 'network.sqlite'), Fernet.generate_key().decode())
    controller = Controller(store)
    ids = []
    for index, (fps, audio) in enumerate(cases):
        cid = f'00000000-0000-0000-0000-{index:012d}'
        ids.append(cid)
        controller.add_camera({'channel_id': cid, 'alias': f'camera-{index}', 'chat_enabled': False}, f'{fps} fps', f'rtsp://127.0.0.1:{server.get_bound_port()}/camera{index}')
    engine = GstEngine(controller, test_output=True)
    engine.start()
    try:
        eventually(lambda: all(controller.health.get(cid, {}).get('state') == 'online' for cid in ids), timeout=20)
        assert [controller.health[cid]['audio'] for cid in ids] == [audio for _, audio in cases]
        start = engine.frames
        for cid in ids:
            controller.switch(cid)
            # Confirm actual decoded network pixels, not just a status flag.
            def selected_frame():
                sample = getattr(engine, 'last_sample', None)
                return sample and sample.get_buffer().extract_dup(360 * 1920 + 1280, 1)[0] > 30
            eventually(selected_frame)
            if controller.health[cid]['audio']:
                eventually(lambda: any(getattr(engine, 'last_audio', b'')))
            else:
                eventually(lambda: getattr(engine, 'last_audio', None) == engine.silence)
        assert engine.frames > start
        assert engine.restarts == 0
        assert all(controller.health[cid]['state'] == 'online' for cid in ids)
        pipeline = engine.cameras[ids[0]]['pipeline']
        controller.hide(ids[0], True)
        assert controller.frame_state()['slots'][0] != ids[0] or controller.audio_camera() is None
        assert engine.cameras[ids[0]]['pipeline'] == pipeline
    finally:
        engine.stop()
        GLib.source_remove(source_id)
        store.close()


def test_network_failures_have_safe_diagnostics_without_source_credentials(tmp_path):
    store = Store(str(tmp_path / 'unreachable.sqlite'), Fernet.generate_key().decode())
    controller = Controller(store)
    cid = '00000000-0000-0000-0000-000000000001'
    # Use a freshly released local TCP port to produce a real connection refusal.
    import socket
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
    controller.add_camera({'channel_id': cid, 'alias': 'missing', 'chat_enabled': False}, 'Missing camera', f'rtsp://private-user:private-password@127.0.0.1:{port}/live')
    engine = GstEngine(controller, test_output=True)
    engine.start()
    try:
        eventually(lambda: controller.health.get(cid, {}).get('reason') == 'connection-error')
        public = str(controller.state())
        assert 'private-user' not in public and 'private-password' not in public and 'rtsp://' not in public
        assert engine.status()['state'] == 'running'
    finally:
        engine.stop()
        store.close()
