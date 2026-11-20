"""Fan out an existing Restreamer-style HTTP HLS output without touching its input."""
import functools
import shutil
import subprocess
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import pytest

pytest.importorskip('gi', reason='Run in the Studio image for HLS media checks')
from cryptography.fernet import Fernet
from woody.controller import Controller
from woody.engine import GstEngine
from woody.storage import Store
from test_engine import eventually


def test_existing_hls_output_supports_second_reader_and_studio(tmp_path, monkeypatch):
    # The fixture is local; never send its requests to the CI/workspace proxy.
    for name in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'):
        monkeypatch.delenv(name, raising=False)
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        pytest.skip('FFmpeg is required to serve a real HLS fixture')
    producer = subprocess.Popen([
        ffmpeg, '-hide_banner', '-loglevel', 'error', '-re', '-f', 'lavfi', '-i', 'testsrc2=size=320x180:rate=15',
        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-c:v', 'libx264', '-preset', 'ultrafast',
        '-tune', 'zerolatency', '-g', '15', '-c:a', 'aac', '-f', 'hls', '-hls_time', '1', '-hls_list_size', '6',
        '-hls_flags', 'delete_segments+independent_segments', '-hls_segment_filename', str(tmp_path / 'segment%05d.ts'), str(tmp_path / 'camera.m3u8'),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Handler, directory=str(tmp_path)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    store = Store(str(tmp_path / 'hls.sqlite'), Fernet.generate_key().decode())
    controller = Controller(store)
    cid = '00000000-0000-0000-0000-000000000001'
    uri = f'http://127.0.0.1:{server.server_port}/camera.m3u8'
    controller.add_camera({'channel_id': cid, 'alias': 'legacy', 'chat_enabled': False}, 'Legacy HLS', uri)
    engine = GstEngine(controller, test_output=True)
    reader = None
    try:
        eventually(lambda: (tmp_path / 'camera.m3u8').exists(), timeout=10)
        # This reader represents the ordinary Restreamer channel/player.
        reader = subprocess.Popen([ffmpeg, '-hide_banner', '-loglevel', 'error', '-i', uri, '-f', 'null', '-'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        engine.start()
        eventually(lambda: controller.health.get(cid, {}).get('state') == 'online', timeout=30)
        eventually(lambda: controller.health[cid]['audio'])
        controller.switch(cid)
        eventually(lambda: getattr(engine, 'last_sample', None) is not None)
        eventually(lambda: engine.last_sample.get_buffer().extract_dup(360 * 1920 + 1280, 1)[0] > 16)
        eventually(lambda: any(getattr(engine, 'last_audio', b'')))
        original = producer.pid
        time.sleep(2)
        assert producer.poll() is None and reader.poll() is None
        assert producer.pid == original and engine.restarts == 0
        assert controller.health[cid]['state'] == 'online'
    finally:
        if hasattr(engine, 'thread'):
            engine.stop()
        for process in (reader, producer):
            if process:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait()
        server.shutdown(); server.server_close()
        store.close()
