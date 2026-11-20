"""Every button response must be renderable before the next polling request."""
from test_api import client, authorization, CID
from woody.core import PROGRAM_ID


def test_all_studio_mutations_return_the_complete_polling_envelope(client):
    root, headers = '/api/woody/v1', authorization()

    def check(method, path, body=None):
        response = client.request(method, root + path, headers=headers, json=body)
        assert response.status_code == 200, response.text
        data = response.json()
        assert data['engine'] == client.app.state.engine.status()
        assert data['program_channel_id'] == PROGRAM_ID
        assert {'program', 'cameras', 'rotation', 'scenes', 'chat', 'bots', 'revision'} <= data.keys()
        return data

    check('GET', '/state')
    check('POST', '/cameras', {'channel_id': CID, 'alias': 'garden'})
    client.app.state.controller.set_health(CID, 'online', True)
    check('PATCH', '/cameras/' + CID, {'chat_enabled': True})
    check('PATCH', '/program', {'safe': False, 'layout': 'six'})
    check('POST', '/program/switch', {'camera': CID})
    check('PUT', '/cameras/' + CID + '/hidden', {'hidden': True})
    check('PUT', '/cameras/' + CID + '/hidden', {'hidden': False})
    check('PUT', '/rotation', {'enabled': False, 'interval_seconds': 30, 'order': [CID]})
    check('PUT', '/scenes', {'alias': 'garden', 'name': 'Garden', 'cameras': [CID]})
    check('POST', '/scenes/garden/apply')
    check('DELETE', '/scenes/garden')
    check('PUT', '/chat', {'enabled': False})
    check('DELETE', '/cameras/' + CID)
