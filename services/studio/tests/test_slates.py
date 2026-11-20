import base64
from io import BytesIO
import pytest
from PIL import Image
from cryptography.fernet import Fernet
from woody.controller import Rejected
from woody.slates import normalize_slate
from woody.storage import Store
from test_api import client, authorization, CID, BOT


def image_data(color='white', size=(640, 360)):
    image = BytesIO()
    Image.new('RGB', size, color).save(image, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(image.getvalue()).decode()


def test_normalized_image_preserves_aspect_ratio_and_uses_i420_range():
    slate = normalize_slate(image_data(size=(100, 200)))
    assert len(slate['frame']) == 1280 * 720 * 3 // 2
    assert slate['frame'][0] == 16
    assert slate['frame'][360 * 1280 + 640] == 235
    assert Image.open(BytesIO(slate['image'])).size == (1280, 720)
    assert len(slate['version']) == 64


@pytest.mark.parametrize('value', ['https://example.org/image.jpg', 'data:image/svg+xml;base64,PHN2Zz4=', 'data:image/png;base64,invalid!', 'data:image/png;base64,bm90LWFuLWltYWdl'])
def test_invalid_or_active_images_are_rejected(value):
    with pytest.raises(Rejected):
        normalize_slate(value)


def test_slate_is_persistent_and_can_be_deleted(tmp_path):
    key = Fernet.generate_key().decode()
    path = str(tmp_path / 'persistent.sqlite')
    slate = normalize_slate(image_data())
    store = Store(path, key)
    store.put_slate(CID, slate)
    store.close()
    reopened = Store(path, key)
    assert reopened.slate(CID) == slate
    assert reopened.slate_frames()[CID] == slate['frame']
    reopened.delete_slate(CID)
    reopened.close()
    empty = Store(path, key)
    assert empty.slate(CID) is None
    empty.close()


def test_upload_is_admin_only_and_does_not_hide_the_live_camera(client):
    root, headers = '/api/woody/v1', authorization()
    client.post(root + '/cameras', headers=headers, json={'channel_id': CID, 'alias': 'garden'})
    client.app.state.controller.set_health(CID, 'online', True)
    client.post(root + '/program/switch', headers=headers, json={'camera': CID})
    path = root + '/cameras/' + CID + '/slate'
    for credentials in ({}, {'Authorization': 'Bearer ' + BOT}):
        assert client.put(path, headers=credentials, json={'image_data': image_data()}).status_code == 401
        assert client.get(path, headers=credentials).status_code == 401
        assert client.delete(path, headers=credentials).status_code == 401
    response = client.put(path, headers=headers, json={'image_data': image_data()})
    assert response.status_code == 200
    state = response.json()
    version = state['cameras'][CID]['slate_version']
    assert version and state['program']['audio_camera'] == CID
    assert not state['cameras'][CID]['hidden']
    assert 'image_data' not in response.text and 'rtsp:' not in response.text
    assert client.get(path, headers=headers).json()['image_data'].startswith('data:image/jpeg;base64,')
    # Refreshing an existing source must keep the uploaded image and privacy state.
    client.put(root + '/cameras/' + CID + '/hidden', headers=headers, json={'hidden': True})
    refreshed = client.post(root + '/cameras', headers=headers, json={'channel_id': CID, 'alias': 'garden'}).json()
    assert refreshed['cameras'][CID]['slate_version'] == version
    assert refreshed['cameras'][CID]['hidden']
    assert client.put(path, headers=headers, json={'image_data': 'invalid'}).status_code == 409
    assert client.get(path, headers=headers).json()['version'] == version
    removed = client.delete(path, headers=headers).json()
    assert removed['cameras'][CID]['slate_version'] is None
    assert removed['cameras'][CID]['hidden']
    assert client.get(path, headers=headers).status_code == 404


def test_custom_slate_is_visible_for_masked_slots_but_never_global_safe_mode(client):
    root, headers = '/api/woody/v1', authorization()
    client.post(root + '/cameras', headers=headers, json={'channel_id': CID, 'alias': 'garden'})
    controller = client.app.state.controller
    controller.set_health(CID, 'online', True)
    controller.switch(CID)
    controller.hide(CID, True)
    frame = controller.frame_state()
    assert frame['slots'][0] is None and frame['slates'][0] == CID
    assert controller.audio_camera() is None
    controller.set_program({'safe': True})
    assert controller.frame_state()['slates'][0] is None
