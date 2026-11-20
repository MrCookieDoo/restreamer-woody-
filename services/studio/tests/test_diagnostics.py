import json
from woody.diagnostics import snapshot, Unavailable


def test_report_only_emits_counters_and_status_not_sources_commands_or_logs():
    private = 'private-user:private-password@camera/live'
    def request(service, path, text=False):
        if service == 'studio':
            return {'engine': {'state': 'running', 'frames': 75, 'restarts': 0, 'uri': private},
                    'cameras': {'id': {'state': 'online', 'audio': True, 'source': private}}}
        if text:
            return '#EXTM3U\n#EXTINF:2\n' + private
        return {'config': {'input': private}, 'state': {'exec': 'running', 'order': 'start',
                'command': private, 'last_logline': private, 'progress': {'frame': 60, 'fps': 25, 'speed': 1}}}
    result = snapshot(request)
    assert private not in json.dumps(result)
    assert result['studio'] == {'state': 'running', 'frames': 75, 'restarts': 0, 'cameras': 1, 'online': 1, 'with_audio': 1}
    assert result['program']['frames'] == 60
    assert result['hls'] == {'http_status': 200, 'playlist': True}


def test_missing_program_is_distinguished_from_unreachable_or_unauthorized():
    def request(service, path, text=False):
        raise Unavailable(404 if service == 'core' else 401)
    result = snapshot(request)
    assert result['studio'] == {'http_status': 401}
    assert result['program'] == {'exists': False, 'http_status': 404}
    assert result['hls'] == {'http_status': 404, 'playlist': False}


def test_unexpected_status_strings_and_counter_values_are_not_printed():
    private = 'private-password'
    def request(service, path, text=False):
        if text:
            return '<html>' + private
        return {'engine': {'state': private, 'frames': private}, 'state': {'exec': private, 'order': private, 'progress': {'frames': private}}}
    result = snapshot(request)
    assert private not in json.dumps(result)
    assert result['hls']['playlist'] is False
