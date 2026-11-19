import time
import jwt
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from woody.app import Settings, create_app
from woody.core import PROGRAM_ID

SECRET = "test-core-secret-with-at-least-32-characters"
BOT = "different-bot-secret-with-at-least-32-characters"
CID = "00000000-0000-0000-0000-000000000001"


class FakeCore:
    def __init__(self, *args):
        pass

    def source(self, cid):
        return "Garden", "rtsp://admin:private-password@camera/live"

    def channels(self):
        return [{"channel_id": CID, "name": "Garden"}]

    def provision(self):
        return {"channel_id": PROGRAM_ID, "created": True}


def authorization(**claims):
    token = jwt.encode({"sub": "admin", "exp": time.time() + 60, "usefor": "access", **claims}, SECRET, algorithm="HS256")
    return {"Authorization": "Bearer " + token}


@pytest.fixture
def client(tmp_path):
    settings = Settings(str(tmp_path / "api.sqlite"), Fernet.generate_key().decode(), SECRET, BOT, engine="control-only")
    with TestClient(create_app(settings, core_factory=FakeCore)) as value:
        yield value


def test_authentication_and_bot_scope(client):
    root = "/api/woody/v1"
    assert client.get(root + "/state").status_code == 401
    assert client.get(root + "/state", headers=authorization(exp=1)).status_code == 401
    assert client.get(root + "/state", headers=authorization(usefor="refresh")).status_code == 401
    assert client.get(root + "/state", headers={"Authorization": "Bearer " + BOT}).status_code == 401
    assert client.get(root + "/bot/config", headers=authorization()).status_code == 401
    assert client.get(root + "/bot/config", headers={"Authorization": "Bearer " + BOT}).status_code == 200


def test_existing_channel_import_omits_credentials_and_masks_program(client):
    root, headers = "/api/woody/v1", authorization()
    response = client.post(root + "/cameras", headers=headers, json={"channel_id": CID, "alias": "garden", "chat_enabled": True})
    assert response.status_code == 200
    assert "private-password" not in response.text
    assert "rtsp:" not in response.text
    assert client.post(root + "/cameras", headers=headers, json={"channel_id": CID, "alias": "garden", "source": "rtsp://evil"}).status_code == 422
    control = client.app.state.controller
    control.set_health(CID, "online", True)
    assert client.post(root + "/program/switch", headers=headers, json={"camera": CID}).status_code == 200
    response = client.put(root + f"/cameras/{CID}/hidden", headers=headers, json={"hidden": True})
    assert response.json()["program"]["audio_camera"] is None
    assert control.frame_state()["slots"][0] is None
    assert client.post(root + "/program/switch", headers=headers, json={"camera": CID}).status_code == 409
    assert client.post(root + "/demo", headers=headers).status_code == 404


def test_bot_cannot_unhide_or_publish_and_refresh_token_is_not_accepted(client):
    root, headers = "/api/woody/v1", {"Authorization": "Bearer " + BOT}
    assert client.put(root + f"/cameras/{CID}/hidden", headers=headers, json={"hidden": False}).status_code == 401
    assert client.post(root + "/program/channel", headers=headers).status_code == 401
    assert client.put(root + "/chat", headers=authorization(), json={"viewer_enabled": True}).status_code == 422


def test_simulate_through_api_does_not_modify_program(client):
    root, headers = "/api/woody/v1", authorization()
    client.post(root + "/cameras", headers=headers, json={"channel_id": CID, "alias": "garden", "chat_enabled": True})
    client.app.state.controller.set_health(CID, "online", True)
    client.patch(root + "/program", headers=headers, json={"safe": False})
    before = client.get(root + "/state", headers=headers).json()["program"]
    response = client.post(root + "/chat/simulate", headers=headers, json={"platform": "simulator", "message_id": "test", "user_id": "admin", "role": "moderator", "text": "!camera garden", "timestamp": time.time()})
    assert response.json()["accepted"] and response.json()["simulated"]
    after = client.get(root + "/state", headers=headers).json()["program"]
    assert before == after


def test_environment_uses_the_existing_core_signing_key_derivation(monkeypatch, tmp_path):
    for name, value in {
        "CORE_API_AUTH_USERNAME": "admin", "CORE_API_AUTH_PASSWORD": "password",
        "CORE_API_AUTH_JWT_SECRET": SECRET, "WOODY_BOT_TOKEN": BOT,
        "WOODY_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "WOODY_DATABASE": str(tmp_path / "native-core.sqlite"), "WOODY_ENGINE": "control-only",
    }.items():
        monkeypatch.setenv(name, value)
    settings = Settings.from_env()
    assert settings.jwt_secret == "adminpassword" + SECRET
    token = jwt.encode({"sub": "admin", "exp": time.time() + 60, "usefor": "access"}, "adminpassword" + SECRET, algorithm="HS256")
    with TestClient(create_app(settings, core_factory=FakeCore)) as test:
        assert test.get("/api/woody/v1/state", headers={"Authorization": "Bearer " + token}).status_code == 200
