import pytest
from cryptography.fernet import Fernet
from woody.controller import Controller
from woody.storage import Store


@pytest.fixture
def store(tmp_path):
    value = Store(str(tmp_path / "test.sqlite"), Fernet.generate_key().decode())
    yield value
    value.close()


@pytest.fixture
def control(store):
    now = [1000.0]
    controller = Controller(store, lambda: now[0])
    controller.now = now
    for i in range(13):
        cid = f"00000000-0000-0000-0000-{i:012d}"
        controller.add_camera({"channel_id": cid, "alias": f"cam-{i}", "chat_enabled": True}, f"Camera {i}", f"rtsp://user:secret@camera-{i}/stream")
        controller.set_health(cid, "online", True)
    controller.set_program({"safe": False})
    controller.chat_settings({**controller.data["chat"], "enabled": True, "dry_run": False})
    return controller
